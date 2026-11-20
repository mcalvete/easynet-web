import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI, HTTPException

from easynet_web.collector import Collector
from easynet_web.config import get_settings
from easynet_web.database import Database
from easynet_web.models import (
    AppConfig,
    CollectorHealth,
    CurrentState,
    DailyEnergy,
    DataFreshness,
    MonthlyEnergy,
    YearlyEnergy,
    YearlyEnergyMonth,
)


def _energy_performance(
    thermal_kwh: float, electric_kwh: float, auxiliary_kwh: float = 0
) -> tuple[float, float]:
    spf = round(thermal_kwh / electric_kwh, 1) if electric_kwh > 0 else 0.0
    total_input = electric_kwh + auxiliary_kwh
    spfg = (
        round((thermal_kwh + auxiliary_kwh) / total_input, 1) if total_input > 0 else 0.0
    )
    return spf, spfg


def _csv_temperature(values: list[int], index: int) -> float | None:
    value = values[index] / 10
    return None if value <= -999 else value


settings = get_settings()
database = Database(settings.database_absolute_path)
collector = Collector(settings, database)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.initialize()
    database.ensure_app_config(settings.easynet_host)
    stored_config = database.get_app_config()
    if stored_config:
        await collector.client.set_host(f"https://{stored_config['easynet_ip']}")
    task = asyncio.create_task(collector.start())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await collector.stop()


app = FastAPI(title="Easynet Web", version="0.1.0", lifespan=lifespan)


@app.get("/api/health", response_model=CollectorHealth)
def health() -> CollectorHealth:
    return collector.health


@app.get("/api/config", response_model=AppConfig)
def config() -> AppConfig:
    value = database.get_app_config()
    if value is None:
        raise HTTPException(status_code=503, detail="Configuration is unavailable")
    return AppConfig.model_validate(value)


@app.put("/api/config", response_model=AppConfig)
async def update_config(value: AppConfig) -> AppConfig:
    database.save_app_config(
        language=value.language,
        temperature_unit=value.temperature_unit,
        easynet_ip=str(value.easynet_ip),
    )
    await collector.client.set_host(f"https://{value.easynet_ip}")
    return value


@app.get("/api/state", response_model=CurrentState)
def state() -> CurrentState:
    device_id = database.get_first_device_id()
    value = database.get_current_state(device_id) if device_id is not None else None
    if value is None:
        raise HTTPException(status_code=503, detail="No current Easynet reading is available")
    if (datetime.now() - value.observed_at).total_seconds() > settings.collect_interval_seconds * 3:
        value = value.model_copy(update={"freshness": DataFreshness.stale})
    return value


@app.get("/api/history/daily", response_model=list[dict[str, object]])
def history_daily(
    day: date,
) -> list[dict[str, object]]:
    device_id = database.get_first_device_id()
    if device_id is None:
        return []
    start = datetime.combine(day, datetime.min.time()).isoformat()
    end = datetime.combine(day, datetime.max.time()).isoformat()
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT recorded_at, electric_power_kw, heating_power_kw, cooling_power_kw, raw_json
            FROM history_samples
            WHERE device_id = ? AND recorded_at >= ? AND recorded_at <= ?
            ORDER BY source_sequence, occurrence
            """,
            (device_id, start, end),
        ).fetchall()
    result = []
    for row in rows:
        values = json.loads(row["raw_json"])

        item = dict(row)
        item.pop("raw_json")
        item["dhw_temperature"] = _csv_temperature(values, 10)
        item["outdoor_temperature"] = _csv_temperature(values, 11)
        item["heating_buffer_temperature"] = _csv_temperature(values, 13)
        item["cooling_buffer_temperature"] = _csv_temperature(values, 14)
        item["heating_supply_temperature"] = _csv_temperature(values, 15)
        item["heating_return_temperature"] = _csv_temperature(values, 16)
        item["brine_supply_temperature"] = _csv_temperature(values, 17)
        item["brine_return_temperature"] = _csv_temperature(values, 18)
        item["group_temperatures"] = [
            _csv_temperature(values, index) for index in range(19, 24)
        ]
        result.append(item)
    return result


@app.get("/api/history/month", response_model=MonthlyEnergy)
def history_month(year: int, month: int) -> MonthlyEnergy:
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")
    device_id = database.get_first_device_id()
    days: list[DailyEnergy] = []
    if device_id is not None:
        with database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM daily_energy
                WHERE device_id = ? AND substr(day, 1, 7) = ?
                ORDER BY day
                """,
                (device_id, f"{year:04d}-{month:02d}"),
            ).fetchall()
        days = [
            DailyEnergy(
                day=row["day"],
                electric_kwh=row["electric_kwh"],
                heating_kwh=row["heating_kwh"],
                cooling_kwh=row["cooling_kwh"],
                expected_samples=row["expected_samples"],
                received_samples=row["received_samples"],
                quality=row["quality"],
                native_electric_kwh=row["native_electric_kwh"],
                difference_percent=row["difference_percent"],
            )
            for row in rows
        ]
    return MonthlyEnergy(year=year, month=month, days=days)


@app.get("/api/history/year", response_model=YearlyEnergy)
def history_year(year: int) -> YearlyEnergy:
    if not 2000 <= year <= 2200:
        raise HTTPException(status_code=422, detail="year must be between 2000 and 2200")
    device_id = database.get_first_device_id()
    monthly_values = {
        month: {
            "electric_kwh": 0.0,
            "heating_kwh": 0.0,
            "cooling_kwh": 0.0,
            "complete_days": 0,
            "incomplete_days": 0,
        }
        for month in range(1, 13)
    }
    if device_id is not None:
        with database.connect() as connection:
            rows = connection.execute(
                """
                SELECT cast(substr(day, 6, 2) AS INTEGER) AS month,
                       coalesce(sum(electric_kwh), 0) AS electric_kwh,
                       coalesce(sum(heating_kwh), 0) AS heating_kwh,
                       coalesce(sum(cooling_kwh), 0) AS cooling_kwh,
                       sum(CASE WHEN quality = 'complete' THEN 1 ELSE 0 END) AS complete_days,
                       sum(CASE WHEN quality <> 'complete' THEN 1 ELSE 0 END) AS incomplete_days
                FROM daily_energy
                WHERE device_id = ? AND substr(day, 1, 4) = ?
                GROUP BY substr(day, 6, 2)
                ORDER BY month
                """,
                (device_id, f"{year:04d}"),
            ).fetchall()
            native_rows = connection.execute(
                """
                SELECT * FROM native_monthly_energy
                WHERE device_id = ? AND year = ?
                ORDER BY month
                """,
                (device_id, year),
            ).fetchall()
        for row in rows:
            monthly_values[int(row["month"])] = {
                "electric_kwh": round(row["electric_kwh"], 3),
                "heating_kwh": round(row["heating_kwh"], 3),
                "cooling_kwh": round(row["cooling_kwh"], 3),
                "complete_days": int(row["complete_days"]),
                "incomplete_days": int(row["incomplete_days"]),
            }
        for row in native_rows:
            native_total = (
                row["dhw_kwh"]
                + row["heating_kwh"]
                + row["pool_kwh"]
                + row["cooling_kwh"]
                + row["passive_cooling_kwh"]
                + row["electric_kwh"]
                + row["dhw_auxiliary_kwh"]
                + row["heating_auxiliary_kwh"]
                + row["pool_auxiliary_kwh"]
            )
            if native_total == 0 and monthly_values[int(row["month"])]["electric_kwh"] > 0:
                continue
            aggregate = monthly_values[int(row["month"])]
            aggregate.update(
                {
                    "electric_kwh": row["electric_kwh"],
                    "heating_kwh": row["heating_kwh"],
                    "cooling_kwh": row["cooling_kwh"],
                    "dhw_kwh": row["dhw_kwh"],
                    "pool_kwh": row["pool_kwh"],
                    "passive_cooling_kwh": row["passive_cooling_kwh"],
                    "electric_auxiliary_kwh": (
                        row["dhw_auxiliary_kwh"]
                        + row["heating_auxiliary_kwh"]
                        + row["pool_auxiliary_kwh"]
                    ),
                    "spf": row["spf"],
                    "spfg": row["spfg"],
                    "source": "easynet",
                }
            )
    for value in monthly_values.values():
        value.setdefault("dhw_kwh", 0.0)
        value.setdefault("pool_kwh", 0.0)
        value.setdefault("passive_cooling_kwh", 0.0)
        value.setdefault("electric_auxiliary_kwh", 0.0)
        thermal_kwh = (
            value.get("dhw_kwh", 0.0)
            + value["heating_kwh"]
            + value.get("pool_kwh", 0.0)
            + value["cooling_kwh"]
            + value.get("passive_cooling_kwh", 0.0)
        )
        electric_kwh = value["electric_kwh"]
        auxiliary_kwh = value.get("electric_auxiliary_kwh", 0.0)
        spf, spfg = _energy_performance(thermal_kwh, electric_kwh, auxiliary_kwh)
        value.setdefault("spf", spf)
        value.setdefault("spfg", spfg)
        value.setdefault("source", "samples")
    return YearlyEnergy(
        year=year,
        months=[
            YearlyEnergyMonth(month=month, **monthly_values[month])
            for month in range(1, 13)
        ],
    )

