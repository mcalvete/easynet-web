from datetime import date, datetime, timedelta
from itertools import pairwise
from statistics import fmean
from zoneinfo import ZoneInfo

from easynet_web.database import Database
from easynet_web.models import DataQuality


def calculate_daily_energy(
    database: Database,
    device_id: int,
    day: date,
    timezone_name: str = "Europe/Madrid",
) -> None:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT recorded_at, source_sequence,
                   electric_power_kw, heating_power_kw, cooling_power_kw
            FROM history_samples
            WHERE device_id = ? AND recorded_at >= ? AND recorded_at < ?
            ORDER BY source_sequence, occurrence
            """,
            (device_id, start.isoformat(), end.isoformat()),
        ).fetchall()

    if not rows:
        return

    points = [
        (
            datetime.fromisoformat(row["recorded_at"]),
            row["electric_power_kw"],
            row["heating_power_kw"],
            row["cooling_power_kw"],
        )
        for row in rows
    ]
    totals = [0.0, 0.0, 0.0]
    timezone = ZoneInfo(timezone_name)
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone)
    next_day = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone)
    expected = round((next_day - day_start).total_seconds() / 300)
    missing_intervals = 0
    for previous, current in pairwise(points):
        hours = (current[0] - previous[0]).total_seconds() / 3600
        seconds = hours * 3600
        if seconds <= 0:
            if expected != 288:
                hours = 5 / 60
            else:
                continue
        elif seconds > 7 * 60:
            missing_intervals += max(0, round(seconds / 300) - 1)
            continue
        for index in range(3):
            left, right = previous[index + 1], current[index + 1]
            if left is not None and right is not None:
                totals[index] += fmean((left, right)) * hours
    received = len(points)
    if day != date.today():
        start_gap = max(0, round((points[0][0] - start).total_seconds() / 300))
        end_gap = max(0, round((end - points[-1][0]).total_seconds() / 300) - 1)
        missing_intervals += start_gap + end_gap
    if day == date.today():
        quality = DataQuality.estimated
    elif missing_intervals == 0:
        quality = DataQuality.complete
    elif missing_intervals <= 2:
        quality = DataQuality.estimated
    else:
        quality = DataQuality.incomplete
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_energy(
                device_id, day, electric_kwh, heating_kwh, cooling_kwh,
                expected_samples, received_samples, quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, day) DO UPDATE SET
                electric_kwh=excluded.electric_kwh,
                heating_kwh=excluded.heating_kwh,
                cooling_kwh=excluded.cooling_kwh,
                received_samples=excluded.received_samples,
                quality=excluded.quality,
                calculated_at=CURRENT_TIMESTAMP
            """,
            (
                device_id,
                day.isoformat(),
                round(totals[0], 3),
                round(totals[1], 3),
                round(totals[2], 3),
                expected,
                received,
                quality.value,
            ),
        )

