import asyncio
import logging
from datetime import date, datetime, timedelta

from easynet_web.config import Settings
from easynet_web.database import Database
from easynet_web.easynet.client import EasyNetClient, EasyNetError
from easynet_web.easynet.decoder import (
    BLOCK_ALARMS,
    BLOCK_DEMANDS,
    BLOCK_ENERGY_MONTH,
    BLOCK_ENERGY_TODAY,
    BLOCK_MAIN,
    BLOCK_SETTINGS,
    BLOCK_TANKS,
    BLOCK_YEAR,
    BLOCK_YEAR_AUXILIARIES,
    BLOCK_YEAR_HEATER_AUXILIARIES,
    BLOCK_YEAR_PASSIVE_ELECTRIC,
    BLOCK_YEAR_POOL_COOLING,
    BLOCK_YEAR_PUMPS,
    DecodeError,
    RegisterSet,
    decode_annual_energy,
    decode_current_month_energy,
    decode_state,
    parse_block,
    parse_bool,
    parse_int16,
)
from easynet_web.history.aggregate import calculate_daily_energy
from easynet_web.history.csv_parser import HistoryFileError
from easynet_web.history.importer import import_history_file
from easynet_web.models import CollectorHealth

LOGGER = logging.getLogger(__name__)


class Collector:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database
        self.client = EasyNetClient(
            settings.easynet_host,
            settings.easynet_username,
            settings.easynet_password.get_secret_value(),
            verify_tls=settings.easynet_verify_tls,
            timeout_seconds=settings.easynet_timeout_seconds,
        )
        self.health = CollectorHealth(status="starting")
        self.serial: str | None = None
        self.device_id: int | None = None
        self._backfilled = False
        self._annual_read_at: datetime | None = None

    async def start(self) -> None:
        await self._state_once()
        await asyncio.gather(self._state_loop(), self._history_loop())

    async def stop(self) -> None:
        await self.client.close()

    async def _state_once(self) -> None:
        try:
            if self.serial is None or self.device_id is None:
                serial = await self.client.read_serial()
                if not serial:
                    raise EasyNetError("Easynet returned an empty serial number")
                self.serial = serial
                self.device_id = self.database.upsert_device(serial)
            registers = await self.client.read_registers(6100, 2)
            dhw = await self.client.read_coils(1524, 1)
            heating = await self.client.read_coils(1552, 1)
            register_set = RegisterSet(
                on_off=parse_int16(registers[6100]),
                program=parse_int16(registers[6101]),
                dhw_enabled=parse_bool(dhw[1524]),
                heating_enabled=parse_bool(heating[1552]),
            )
            state = decode_state(
                register_set,
                main=await self.client.read_block(BLOCK_MAIN),
                demands=await self.client.read_block(BLOCK_DEMANDS),
                tanks=await self.client.read_block(BLOCK_TANKS),
                energy_today=await self.client.read_block(BLOCK_ENERGY_TODAY),
                energy_month=await self.client.read_block(BLOCK_ENERGY_MONTH),
                alarms=await self.client.read_block(BLOCK_ALARMS),
            )
            self.database.save_current_state(self.device_id, state)
            self.health.status = "healthy"
            self.health.last_success_at = state.observed_at
            self.health.last_error = None
        except (EasyNetError, DecodeError, KeyError, ValueError) as exc:
            LOGGER.exception("State collection failed")
            self.health.status = "degraded"
            self.health.last_error_at = datetime.now()
            self.health.last_error = str(exc)

    async def _state_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.collect_interval_seconds)
            await self._state_once()

    async def _history_loop(self) -> None:
        while True:
            if not self._backfilled:
                self._backfilled = await self._backfill_history()
            await self._history_once()
            await self._annual_once()
            await asyncio.sleep(self.settings.history_interval_seconds)

    async def _annual_once(self) -> None:
        if not self.device_id:
            return
        if self._annual_read_at and (datetime.now() - self._annual_read_at).seconds < 3600:
            return
        try:
            settings_block = parse_block(await self.client.read_block(BLOCK_SETTINGS))
            include_pumps = parse_int16(settings_block["ECCOP"]) == 1
            now = datetime.now()
            operations = (
                BLOCK_YEAR,
                BLOCK_YEAR_POOL_COOLING,
                BLOCK_YEAR_PASSIVE_ELECTRIC,
                BLOCK_YEAR_AUXILIARIES,
                BLOCK_YEAR_HEATER_AUXILIARIES,
                BLOCK_YEAR_PUMPS,
            )
            blocks = {
                operation: await self.client.read_block(operation) for operation in operations
            }
            values = decode_annual_energy(
                blocks,
                include_pumps=include_pumps,
                year=now.year,
                current_month=now.month,
            )
            current_month = decode_current_month_energy(
                await self.client.read_block(BLOCK_ENERGY_MONTH),
                include_pumps=include_pumps,
                year=now.year,
                month=now.month,
            )
            values = [value for value in values if (value["year"], value["month"]) != (
                now.year,
                now.month,
            )]
            values.append(current_month)
            self.database.save_native_monthly_energy(self.device_id, values)
            self._annual_read_at = datetime.now()
        except (EasyNetError, DecodeError, KeyError, ValueError):
            LOGGER.exception("Annual counter collection failed")

    async def _backfill_history(self) -> bool:
        if not self.serial or self.device_id is None:
            return False
        LOGGER.info("Checking retained Easynet history")
        retry_needed = False
        for offset in range(1, 95):
            day = date.today() - timedelta(days=offset)
            if self.database.has_history_day(self.device_id, day.isoformat()):
                continue
            path = f"/historic/backup/{day.isoformat()}_{self.serial}_1_historico.csv"
            try:
                raw = await self.client.fetch_history(path)
                inserted = import_history_file(
                    self.database,
                    device_id=self.device_id,
                    day=day,
                    source_path=path,
                    raw=raw,
                )
                calculate_daily_energy(
                    self.database, self.device_id, day, self.settings.timezone
                )
                if inserted:
                    LOGGER.info("Backfilled %s samples from %s", inserted, path)
            except EasyNetError as exc:
                if "not found" not in str(exc):
                    LOGGER.warning("Could not backfill %s: %s", path, exc)
                    retry_needed = True
            except HistoryFileError as exc:
                LOGGER.error("Invalid backfill file %s: %s", path, exc)
                retry_needed = True
            await asyncio.sleep(0.05)
        return not retry_needed

    async def _history_once(self) -> None:
        if not self.serial or self.device_id is None:
            return
        for offset, directory in ((0, "/historic"), (1, "/historic/backup")):
            day = date.today() - timedelta(days=offset)
            path = f"{directory}/{day.isoformat()}_{self.serial}_1_historico.csv"
            try:
                raw = await self.client.fetch_history(path)
                inserted = import_history_file(
                    self.database,
                    device_id=self.device_id,
                    day=day,
                    source_path=path,
                    raw=raw,
                )
                if inserted:
                    LOGGER.info("Imported %s samples from %s", inserted, path)
                calculate_daily_energy(
                    self.database, self.device_id, day, self.settings.timezone
                )
                if offset == 0:
                    continue
            except EasyNetError as exc:
                if "not found" not in str(exc):
                    LOGGER.warning("History file unavailable %s: %s", path, exc)
            except HistoryFileError as exc:
                LOGGER.error("Invalid history file %s: %s", path, exc)

