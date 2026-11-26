from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from easynet_web.database import Database
from easynet_web.easynet.client import EasyNetClient
from easynet_web.easynet.decoder import parse_analog, parse_bool, parse_int16

BlockValue = bool | int | float


OFFICIAL_BLOCK_FIELDS: dict[int, tuple[str, ...]] = {
    2110: ("KO", "OPK", "NHA", "TAI", "TAV"),
    2107: ("TCC",),
    2108: ("ECU",),
    2106: ("TSIC", "OIC", "OCZ1", "OCZ2", "OCZ3", "OCZ4", "OCZ5"),
    2103: ("AS", "AO", "ATSH", "AHL", "AML"),
    2104: ("AEU", "LE", "LL", "LM", "LMI", "LJ", "LV", "LS", "LD"),
    2101: ("CGFI", "CCFI", "CAF", "CTF", "PGFI", "RCFI", "PCF", "PPFI"),
}
COOLING_BLOCK_FIELDS = {
    2111: ("OIF", "OCFZ1", "OCFZ2", "OCFZ3", "OCFZ4", "OCFZ5"),
    2112: ("TCFA", "TCFP"),
    2113: ("ERU",),
}
POOL_BLOCK_FIELDS = {
    2115: ("PDTS", "PDOT", "PPDO"),
    2116: ("EPU", "EHI", "EHV"),
}
SCHEDULE_BLOCKS = (2102, 2105, 2109, 2126)
ALARM_BLOCKS = (2135, 1079)
ALARM_RESET_REGISTER = 6755
READ_SOURCES: dict[str, tuple[int, str]] = {
    "system.mode": (2110, "KO"),
    "system.program": (2110, "OPK"),
    "heating.enabled": (2108, "ECU"),
    "heating.cutoff_c": (2107, "TCC"),
    "heating.delta_c": (2106, "OIC"),
    **{f"heating.group_offsets.{number}": (2106, f"OCZ{number}") for number in range(1, 6)},
    "dhw.enabled": (2104, "AEU"),
    "dhw.setpoint_c": (2103, "AS"),
    "dhw.delta_c": (2103, "AO"),
    "dhw.htr_setpoint_c": (2103, "ATSH"),
    "dhw.legionella.enabled": (2104, "LE"),
    "dhw.legionella.hour": (2103, "AHL"),
    "dhw.legionella.minute": (2103, "AML"),
    "dhw.legionella.days.0": (2104, "LL"),
    "dhw.legionella.days.1": (2104, "LM"),
    "dhw.legionella.days.2": (2104, "LMI"),
    "dhw.legionella.days.3": (2104, "LJ"),
    "dhw.legionella.days.4": (2104, "LV"),
    "dhw.legionella.days.5": (2104, "LS"),
    "dhw.legionella.days.6": (2104, "LD"),
    "cooling.enabled": (2113, "ERU"),
    "cooling.active_cutoff_c": (2112, "TCFA"),
    "cooling.passive_cutoff_c": (2112, "TCFP"),
    "cooling.delta_c": (2111, "OIF"),
    **{
        f"cooling.group_offsets.{number}": (2111, f"OCFZ{number}")
        for number in range(1, 6)
    },
    "pool.enabled": (2116, "EPU"),
    "pool.setpoint_c": (2115, "PDTS"),
    "pool.delta_c": (2115, "PDOT"),
    "pool.duration_minutes": (2115, "PPDO"),
    "pool.winter_enabled": (2116, "EHI"),
    "pool.summer_enabled": (2116, "EHV"),
    "scheduling.pump_calendar": (2109, "PHBC"),
    "scheduling.vacation_calendar": (2109, "ESO"),
    "scheduling.dhw_calendar": (2109, "PHA"),
    "scheduling.heating_calendar": (2109, "PHC"),
    "scheduling.cooling_calendar": (2109, "PHR"),
    "scheduling.recirculation_calendar": (2109, "PHRA"),
    "scheduling.night_mode_enabled": (2109, "EHN"),
    "scheduling.night_start_hour": (2109, "HHNS"),
    "scheduling.night_start_minute": (2109, "MHNS"),
    "scheduling.night_end_hour": (2109, "HHNE"),
    "scheduling.night_end_minute": (2109, "MHNE"),
    "scheduling.night_compressor_offset_c": (2109, "PMHN"),
    "scheduling.night_fan_offset": (2109, "FMPNT"),
    "scheduling.night_fan_enabled": (2109, "EHAU"),
    "scheduling.dst_enabled": (2105, "MD2E"),
    "scheduling.dst_offset_minutes": (2105, "MD2M"),
    "scheduling.dst_start_week": (2105, "MD2SMW"),
    "scheduling.dst_start_weekday": (2105, "MD2SW"),
    "scheduling.dst_start_month": (2105, "MD2SM"),
    "scheduling.dst_start_hour": (2105, "MD2SH"),
    "scheduling.dst_end_week": (2105, "MD2EMW"),
    "scheduling.dst_end_weekday": (2105, "MD2EW"),
    "scheduling.dst_end_month": (2105, "MD2EM"),
    "scheduling.dst_end_hour": (2105, "MD2EH"),
    "scheduling.tariff_winter_enabled": (2126, "ESTC"),
    "scheduling.tariff_summer_enabled": (2126, "EWTC"),
    "scheduling.tariff_winter_day": (2126, "STWSD"),
    "scheduling.tariff_winter_month": (2126, "STWSM"),
    "scheduling.tariff_summer_day": (2126, "STSSD"),
    "scheduling.tariff_summer_month": (2126, "STSSM"),
    "scheduling.tariff_winter_dhw_peak": (2126, "DWPO"),
    "scheduling.tariff_winter_dhw_offpeak": (2126, "DWVO"),
    "scheduling.tariff_winter_heating_peak": (2126, "HWPO"),
    "scheduling.tariff_winter_heating_offpeak": (2126, "HWVO"),
    "scheduling.tariff_summer_dhw_peak": (2126, "DSPO"),
    "scheduling.tariff_summer_dhw_offpeak": (2126, "DSVO"),
    "scheduling.tariff_summer_heating_peak": (2126, "HSPO"),
    "scheduling.tariff_summer_heating_offpeak": (2126, "HSVO"),
}


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    kind: Literal["coil", "register"]
    address: int
    value_type: Literal["bool", "int", "float", "level"]
    minimum: float
    maximum: float

    def encode(self, value: BlockValue) -> bool | int:
        if self.value_type == "bool":
            if not isinstance(value, bool):
                raise SettingsValidationError(self.key, "must be a boolean")
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsValidationError(self.key, "must be a number")
        number = float(value)
        if not self.minimum <= number <= self.maximum:
            raise SettingsValidationError(
                self.key, f"must be between {self.minimum:g} and {self.maximum:g}"
            )
        if self.value_type in {"int", "level"}:
            if not number.is_integer():
                raise SettingsValidationError(self.key, "must be an integer")
            return int(number) + 2 if self.value_type == "level" else int(number)
        encoded = round(number * 10)
        if abs(encoded / 10 - number) > 1e-9:
            raise SettingsValidationError(self.key, "supports at most one decimal place")
        return encoded

    def decode(self, raw: str) -> BlockValue:
        if self.kind == "coil":
            return parse_bool("1" if int(raw, 16) != 0 else "0")
        integer = parse_int16(raw)
        if self.value_type == "int":
            return integer
        if self.value_type == "level":
            return integer - 2
        return integer / 10


def _register(
    key: str,
    address: int,
    minimum: int,
    maximum: int,
    *,
    scaled: bool = False,
) -> SettingDefinition:
    return SettingDefinition(
        key,
        "register",
        address,
        "float" if scaled else "int",
        minimum,
        maximum,
    )


def _coil(key: str, address: int) -> SettingDefinition:
    return SettingDefinition(key, "coil", address, "bool", 0, 1)


def _level(key: str, address: int) -> SettingDefinition:
    return SettingDefinition(key, "register", address, "level", -2, 2)


SETTINGS_WHITELIST: dict[str, SettingDefinition] = {
    definition.key: definition
    for definition in (
        _register("system.mode", 6100, 0, 2),
        _register("system.program", 6101, 0, 4),
        _coil("heating.enabled", 1552),
        _register("heating.cutoff_c", 6159, -20, 40, scaled=True),
        _register("heating.delta_c", 6148, 0, 20, scaled=True),
        *[
            _level(
                f"heating.group_offsets.{number}",
                6142 + number,
            )
            for number in range(1, 6)
        ],
        _coil("dhw.enabled", 1524),
        _register("dhw.setpoint_c", 6106, 25, 80, scaled=True),
        _register("dhw.delta_c", 6105, 0, 20, scaled=True),
        _register("dhw.htr_setpoint_c", 6104, 0, 100, scaled=True),
        _coil("dhw.legionella.enabled", 1527),
        _register("dhw.legionella.hour", 6108, 0, 23),
        _register("dhw.legionella.minute", 6110, 0, 59),
        _coil("dhw.legionella.days.0", 1529),
        _coil("dhw.legionella.days.1", 1530),
        _coil("dhw.legionella.days.2", 1531),
        _coil("dhw.legionella.days.3", 1528),
        _coil("dhw.legionella.days.4", 1533),
        _coil("dhw.legionella.days.5", 1532),
        _coil("dhw.legionella.days.6", 1526),
        _coil("cooling.enabled", 1568),
        _register("cooling.active_cutoff_c", 6219, -20, 40, scaled=True),
        _register("cooling.passive_cutoff_c", 6220, -20, 40, scaled=True),
        _register("cooling.delta_c", 6208, 0, 20, scaled=True),
        *[
            _level(
                f"cooling.group_offsets.{number}",
                6202 + number,
            )
            for number in range(1, 6)
        ],
        _coil("pool.enabled", 1574),
        _register("pool.setpoint_c", 6253, 10, 50, scaled=True),
        _register("pool.delta_c", 6251, 0, 20, scaled=True),
        _register("pool.duration_minutes", 6252, 0, 1440),
        _coil("pool.winter_enabled", 1570),
        _coil("pool.summer_enabled", 1571),
        _coil("scheduling.pump_calendar", 1502),
        _coil("scheduling.vacation_calendar", 1500),
        _coil("scheduling.dhw_calendar", 1501),
        _coil("scheduling.heating_calendar", 1503),
        _coil("scheduling.cooling_calendar", 1508),
        _coil("scheduling.recirculation_calendar", 1507),
        _coil("scheduling.night_mode_enabled", 1517),
        _register("scheduling.night_start_hour", 6091, 0, 23),
        _register("scheduling.night_start_minute", 6093, 0, 59),
        _register("scheduling.night_end_hour", 6090, 0, 23),
        _register("scheduling.night_end_minute", 6092, 0, 59),
        _register("scheduling.night_compressor_offset_c", 6094, -999.9, 999.9, scaled=True),
        _register("scheduling.night_fan_offset", 6089, -999.9, 999.9, scaled=True),
        _coil("scheduling.night_fan_enabled", 1516),
        _coil("scheduling.dst_enabled", 1509),
        _register("scheduling.dst_offset_minutes", 6074, -999, 999),
        _register("scheduling.dst_start_week", 6081, 0, 4),
        _register("scheduling.dst_start_weekday", 6082, 0, 7),
        _register("scheduling.dst_start_month", 6080, 0, 12),
        _register("scheduling.dst_start_hour", 6079, 0, 23),
        _register("scheduling.dst_end_week", 6077, 0, 4),
        _register("scheduling.dst_end_weekday", 6078, 0, 7),
        _register("scheduling.dst_end_month", 6076, 0, 12),
        _register("scheduling.dst_end_hour", 6075, 0, 23),
        _coil("scheduling.tariff_winter_enabled", 1643),
        _coil("scheduling.tariff_summer_enabled", 1642),
        _register("scheduling.tariff_winter_day", 6427, 1, 31),
        _register("scheduling.tariff_winter_month", 6426, 1, 12),
        _register("scheduling.tariff_summer_day", 6429, 1, 31),
        _register("scheduling.tariff_summer_month", 6428, 1, 12),
        _register("scheduling.tariff_winter_dhw_peak", 6416, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_winter_dhw_offpeak", 6417, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_winter_heating_peak", 6420, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_winter_heating_offpeak", 6421, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_summer_dhw_peak", 6414, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_summer_dhw_offpeak", 6415, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_summer_heating_peak", 6418, -999.9, 999.9, scaled=True),
        _register("scheduling.tariff_summer_heating_offpeak", 6419, -999.9, 999.9, scaled=True),
    )
}


class SettingsError(RuntimeError):
    pass


class SettingsValidationError(SettingsError):
    def __init__(self, key: str, message: str) -> None:
        self.key = key
        super().__init__(f"{key}: {message}")


class SettingsApplyError(SettingsError):
    def __init__(
        self,
        message: str,
        *,
        applied_keys: list[str],
        failed_key: str | None = None,
        mismatches: dict[str, dict[str, BlockValue]] | None = None,
    ) -> None:
        self.applied_keys = applied_keys
        self.failed_key = failed_key
        self.mismatches = mismatches or {}
        self.partial_apply = bool(applied_keys)
        super().__init__(message)

    def detail(self) -> dict[str, object]:
        return {
            "code": "equipment_apply_failed",
            "message": str(self),
            "partial": self.partial_apply,
            "applied_keys": self.applied_keys,
            "failed_key": self.failed_key,
            "mismatches": self.mismatches,
        }


class EquipmentSettingsService:
    def __init__(self, client: EasyNetClient, database: Database) -> None:
        self.client = client
        self.database = database

    async def read_settings(self) -> dict[str, object]:
        official_blocks = await self._read_required_blocks(OFFICIAL_BLOCK_FIELDS)
        cooling_available = bool(parse_int16(official_blocks["2101"]["CGFI"]) & 0b1111)
        pool_available = bool(parse_int16(official_blocks["2101"]["PGFI"]) & 1)
        if cooling_available:
            official_blocks.update(await self._read_required_blocks(COOLING_BLOCK_FIELDS))
        if pool_available:
            official_blocks.update(await self._read_required_blocks(POOL_BLOCK_FIELDS))
        schedule_blocks = {
            str(operation): await self.client.read_block(operation) for operation in SCHEDULE_BLOCKS
        }
        values: dict[str, BlockValue] = {}
        blocks = {str(operation): values for operation, values in official_blocks.items()} | {
            operation: {
                key: value
                for line in lines
                if "=" in line
                for key, value in [line.split("=", maxsplit=1)]
            }
            for operation, lines in schedule_blocks.items()
        }
        for definition in SETTINGS_WHITELIST.values():
            operation, field_name = READ_SOURCES[definition.key]
            if definition.key.startswith("cooling.") and not cooling_available:
                continue
            if definition.key.startswith("pool.") and not pool_available:
                continue
            values[definition.key] = definition.decode(blocks[str(operation)][field_name])
        mode = int(values["system.mode"])
        clock_block = blocks["2102"]
        pump_clock = datetime(
            2000 + parse_int16(clock_block["CY"]),
            parse_int16(clock_block["CMO"]),
            parse_int16(clock_block["CD"]),
            parse_int16(clock_block["CH"]),
            parse_int16(clock_block["CM"]),
        ).isoformat()
        return {
            "system": {
                "powered": mode != 0,
                "mode": mode,
                "program": values["system.program"],
                "auto_winter_c": parse_analog(official_blocks["2110"]["TAI"]),
                "auto_summer_c": parse_analog(official_blocks["2110"]["TAV"]),
                "auto_change_hours": parse_int16(official_blocks["2110"]["NHA"]),
            },
            "heating": {
                "enabled": values["heating.enabled"],
                "cutoff_c": values["heating.cutoff_c"],
                "delta_c": values["heating.delta_c"],
                "buffer_c": parse_analog(official_blocks["2107"]["TCC"]),
                "group_offsets": [
                    values[f"heating.group_offsets.{number}"] for number in range(1, 6)
                ],
            },
            "dhw": {
                "enabled": values["dhw.enabled"],
                "setpoint_c": values["dhw.setpoint_c"],
                "delta_c": values["dhw.delta_c"],
                "htr_setpoint_c": values["dhw.htr_setpoint_c"],
                "legionella": {
                    "enabled": values["dhw.legionella.enabled"],
                    "hour": values["dhw.legionella.hour"],
                    "minute": values["dhw.legionella.minute"],
                    "days": [values[f"dhw.legionella.days.{day}"] for day in range(7)],
                },
            },
            "cooling": {
                "available": cooling_available,
                "enabled": values.get("cooling.enabled", False),
                "active_cutoff_c": values.get("cooling.active_cutoff_c", 0.0),
                "passive_cutoff_c": values.get("cooling.passive_cutoff_c", 0.0),
                "delta_c": values.get("cooling.delta_c", 0.0),
                "group_offsets": [
                    values.get(f"cooling.group_offsets.{number}", 0)
                    for number in range(1, 6)
                ],
            },
            "pool": {
                "available": pool_available,
                "enabled": values.get("pool.enabled", False),
                "setpoint_c": values.get("pool.setpoint_c", 0.0),
                "delta_c": values.get("pool.delta_c", 0.0),
                "duration_minutes": values.get("pool.duration_minutes", 0),
                "winter_enabled": values.get("pool.winter_enabled", False),
                "summer_enabled": values.get("pool.summer_enabled", False),
            },
            "scheduling": {
                "pump_clock": pump_clock,
                "pump_calendar": values["scheduling.pump_calendar"],
                "vacation_calendar": values["scheduling.vacation_calendar"],
                "dhw_calendar": values["scheduling.dhw_calendar"],
                "heating_calendar": values["scheduling.heating_calendar"],
                "cooling_calendar": values["scheduling.cooling_calendar"],
                "recirculation_calendar": values["scheduling.recirculation_calendar"],
                "night_mode_enabled": values["scheduling.night_mode_enabled"],
                "night_start_hour": values["scheduling.night_start_hour"],
                "night_start_minute": values["scheduling.night_start_minute"],
                "night_end_hour": values["scheduling.night_end_hour"],
                "night_end_minute": values["scheduling.night_end_minute"],
                "night_compressor_offset_c": values["scheduling.night_compressor_offset_c"],
                "night_fan_offset": values["scheduling.night_fan_offset"],
                "night_fan_enabled": values["scheduling.night_fan_enabled"],
                **{
                    key.removeprefix("scheduling."): value
                    for key, value in values.items()
                    if key.startswith(
                        (
                            "scheduling.dst_",
                            "scheduling.tariff_",
                        )
                    )
                },
                "blocks": schedule_blocks,
                "official_blocks": {
                    key: official_blocks[key] for key in ("2106", "2103", "2104", "2108")
                },
            },
            "updated_at": datetime.now().isoformat(),
        }

    async def apply(self, changes: dict[str, BlockValue], *, confirm: bool) -> dict[str, object]:
        try:
            encoded = self._validate_changes(changes, confirm=confirm)
        except SettingsValidationError as exc:
            self.database.record_equipment_change(
                change_count=0,
                success=False,
                error=str(exc),
                snapshot={"requested": changes, "confirmed": confirm},
            )
            raise
        applied: list[str] = []
        try:
            before_settings = await self.read_settings()
            for key, _, _ in encoded:
                if key.startswith("cooling.") and not before_settings["cooling"]["available"]:
                    raise SettingsValidationError(
                        key, "is unavailable on this EasyNet installation"
                    )
                if key.startswith("pool.") and not before_settings["pool"]["available"]:
                    raise SettingsValidationError(
                        key, "is unavailable on this EasyNet installation"
                    )
            before = {
                key: self._setting_from_snapshot(before_settings, key)
                for key, _, _ in encoded
            }
        except Exception as exc:
            error = SettingsApplyError(
                "Could not read EasyNet settings before applying changes",
                applied_keys=[],
            )
            self.database.record_equipment_change(
                change_count=0,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                snapshot={"requested": changes, "confirmed": confirm},
            )
            raise error from exc
        snapshot: dict[str, object] = {
            "requested": dict(changes),
            "confirmed": confirm,
        }
        if not encoded:
            snapshot["result"] = "no_changes"
            self.database.record_equipment_change(
                change_count=0,
                success=True,
                error=None,
                snapshot=snapshot,
            )
            return {
                "settings": await self.read_settings(),
                "changed": [],
                "partial": False,
            }

        try:
            for key, definition, value in encoded:
                try:
                    if definition.kind == "coil":
                        await self.client.write_coil(definition.address, bool(value))
                    else:
                        await self.client.write_register(definition.address, int(value))
                    applied.append(key)
                except Exception as exc:
                    snapshot["applied_keys"] = applied
                    error = SettingsApplyError(
                        f"EasyNet write failed for {key}; previous changes may be applied",
                        applied_keys=list(applied),
                        failed_key=key,
                    )
                    self.database.record_equipment_change(
                        change_count=len(applied),
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                        snapshot=snapshot,
                    )
                    raise error from exc

            mismatches: dict[str, dict[str, BlockValue]] = {}
            verified_values: dict[str, BlockValue] = {}
            settings = await self.read_settings()
            for key, definition, value in encoded:
                actual = self._setting_from_snapshot(settings, key)
                expected: BlockValue
                if definition.value_type == "bool":
                    expected = bool(value)
                elif definition.value_type == "level":
                    expected = int(value) - 2
                elif definition.value_type == "float":
                    expected = int(value) / 10
                else:
                    expected = int(value)
                verified_values[key] = actual
                if actual != expected:
                    mismatches[key] = {"expected": expected, "actual": actual}
            if mismatches:
                snapshot["mismatches"] = mismatches
                error = SettingsApplyError(
                    "EasyNet verification failed; requested changes may be partially applied",
                    applied_keys=list(applied),
                    mismatches=mismatches,
                )
                self.database.record_equipment_change(
                    change_count=len(applied),
                    success=False,
                    error=str(error),
                    snapshot=snapshot,
                )
                raise error
        except SettingsApplyError:
            raise
        except Exception as exc:
            error = SettingsApplyError(
                "Could not verify EasyNet changes; requested changes may be partially applied",
                applied_keys=list(applied),
            )
            self.database.record_equipment_change(
                change_count=len(applied),
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                snapshot=snapshot,
            )
            raise error from exc

        snapshot["applied_keys"] = applied
        snapshot["verified_values"] = verified_values
        self.database.record_equipment_change(
            change_count=len(applied),
            success=True,
            error=None,
            snapshot=snapshot,
        )
        return {
            "settings": settings,
            "changed": [
                {"key": key, "before": before[key], "after": verified_values[key]}
                for key in applied
            ],
            "partial": False,
        }

    async def read_alarms(self) -> dict[str, object]:
        blocks = await self._read_blocks(ALARM_BLOCKS)
        current = blocks.get("1079", {}).get("get_alarmas") or next(
            iter(blocks.get("1079", {}).values()), ""
        )
        active = [] if current in {"", "N", "0"} else [part.strip() for part in current.split(",")]
        return {
            "active": active,
            "summary": blocks,
            "raw_code": current or None,
        }

    async def reset_alarms(self, *, confirm: bool) -> dict[str, object]:
        if confirm is not True:
            error = SettingsValidationError("confirm", "must be true")
            self.database.record_equipment_change(
                change_count=0,
                success=False,
                error=str(error),
                snapshot={"requested": {"alarms_reset": True}, "confirmed": confirm},
            )
            raise error
        try:
            await self.client.write_register(ALARM_RESET_REGISTER, 1)
            result = await self.read_alarms()
            if result["active"]:
                raise SettingsError("An alarm remains active after the reset request")
        except Exception as exc:
            self.database.record_equipment_change(
                change_count=0,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                snapshot={"requested": {"alarms_reset": True}, "confirmed": True},
            )
            raise SettingsApplyError(
                "Alarm reset failed or could not be verified; the reset register may be set",
                applied_keys=[],
                failed_key="alarms_reset",
            ) from exc
        self.database.record_equipment_change(
            change_count=1,
            success=True,
            error=None,
            snapshot={
                "requested": {"alarms_reset": True},
                "confirmed": True,
                "result": result,
            },
        )
        return result

    async def sync_clock(self, *, confirm: bool, now: datetime | None = None) -> None:
        if confirm is not True:
            error = SettingsValidationError("confirm", "must be true")
            self.database.record_equipment_change(
                change_count=0,
                success=False,
                error=str(error),
                snapshot={"requested": {"sync_clock": True}, "confirmed": confirm},
            )
            raise error
        now = now or datetime.now()
        writes = (
            ("day", 6083, 1510, 6647, now.day),
            ("month", 6086, 1513, 6646, now.month),
            ("year", 6088, 1515, 6645, now.year % 100),
            ("hour", 6084, 1511, 6648, now.hour),
            ("minute", 6085, 1512, 6649, now.minute),
        )
        applied: list[str] = []
        try:
            for key, primary, trigger, mirror, value in writes:
                await self.client.write_register(primary, value)
                applied.append(f"clock.{key}.primary")
                await self.client.write_coil(trigger, True)
                applied.append(f"clock.{key}.trigger")
                await self.client.write_register(mirror, value)
                applied.append(f"clock.{key}.mirror")
            block = (await self._read_blocks((2102,)))["2102"]
            actual = {
                "day": parse_int16(block["CD"]),
                "month": parse_int16(block["CMO"]),
                "year": parse_int16(block["CY"]),
                "hour": parse_int16(block["CH"]),
                "minute": parse_int16(block["CM"]),
            }
            expected = {
                "day": now.day,
                "month": now.month,
                "year": now.year % 100,
                "hour": now.hour,
                "minute": now.minute,
            }
            if actual != expected:
                raise SettingsError(f"Clock verification failed: expected {expected}, got {actual}")
        except Exception as exc:
            self.database.record_equipment_change(
                change_count=len(applied),
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                snapshot={"requested": {"sync_clock": now.isoformat()}, "applied_keys": applied},
            )
            raise SettingsApplyError(
                "Clock synchronization failed; part of the request may be applied",
                applied_keys=applied,
                failed_key="clock",
            ) from exc
        self.database.record_equipment_change(
            change_count=len(applied),
            success=True,
            error=None,
            snapshot={"requested": {"sync_clock": now.isoformat()}, "applied_keys": applied},
        )

    def _validate_changes(
        self, changes: dict[str, BlockValue], *, confirm: bool
    ) -> list[tuple[str, SettingDefinition, bool | int]]:
        if confirm is not True:
            raise SettingsValidationError("confirm", "must be true")
        encoded: list[tuple[str, SettingDefinition, bool | int]] = []
        for key, value in changes.items():
            definition = SETTINGS_WHITELIST.get(key)
            if definition is None:
                raise SettingsValidationError(key, "is not an allowed setting")
            encoded.append((key, definition, definition.encode(value)))
        return encoded

    async def _read_value(self, definition: SettingDefinition) -> BlockValue:
        if definition.kind == "coil":
            values = await self.client.read_coils(definition.address, 1)
        else:
            values = await self.client.read_registers(definition.address, 1)
        return definition.decode(values[definition.address])

    @staticmethod
    def _setting_from_snapshot(
        snapshot: dict[str, object], key: str
    ) -> BlockValue:
        value: object = snapshot
        for part in key.split("."):
            if isinstance(value, list):
                index = int(part)
                if "heating.group_offsets" in key:
                    index -= 1
                value = value[index]
            else:
                value = dict(value)[part]
        return value  # type: ignore[return-value]

    async def _read_blocks(self, operations: tuple[int, ...]) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for operation in operations:
            lines = await self.client.read_block(operation)
            values: dict[str, str] = {}
            for line in lines:
                if "=" in line:
                    key, value = line.split("=", maxsplit=1)
                    values[key] = value
            result[str(operation)] = values
        return result

    async def _read_required_blocks(
        self, required: dict[int, tuple[str, ...]]
    ) -> dict[str, dict[str, str]]:
        blocks = await self._read_blocks(tuple(required))
        for operation, fields in required.items():
            present = blocks[str(operation)]
            missing = [field for field in fields if field not in present]
            if missing:
                raise SettingsError(
                    f"EasyNet operation {operation} is missing fields: {', '.join(missing)}"
                )
        return blocks
