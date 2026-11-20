import hashlib
import json
from datetime import date

from easynet_web.database import Database
from easynet_web.history.csv_parser import parse_history_csv
from easynet_web.models import HistorySample


def import_history_file(
    database: Database,
    *,
    device_id: int,
    day: date,
    source_path: str,
    raw: str,
) -> int:
    samples = parse_history_csv(raw, source_file=source_path)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with database.connect() as connection:
        connection.execute("BEGIN")
        existing = connection.execute(
            "SELECT 1 FROM source_files WHERE device_id = ? AND path = ? AND sha256 = ?",
            (device_id, source_path, digest),
        ).fetchone()
        if existing:
            connection.rollback()
            return 0
        inserted = 0
        for sample in samples:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO history_samples(
                    device_id, recorded_at, occurrence, source_sequence,
                    electric_power_kw, heating_power_kw, cooling_power_kw,
                    raw_json, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _sample_values(device_id, sample),
            )
            inserted += cursor.rowcount
        connection.execute(
            """
            INSERT INTO source_files(device_id, path, day, sha256, row_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(device_id, path, day) DO UPDATE SET
                sha256=excluded.sha256,
                row_count=excluded.row_count,
                imported_at=CURRENT_TIMESTAMP
            """,
            (device_id, source_path, day.isoformat(), digest, len(samples)),
        )
    return inserted


def _sample_values(device_id: int, sample: HistorySample) -> tuple[object, ...]:
    return (
        device_id,
        sample.recorded_at.isoformat(timespec="seconds"),
        sample.occurrence,
        sample.source_sequence,
        sample.electric_power_kw,
        sample.heating_power_kw,
        sample.cooling_power_kw,
        json.dumps(sample.raw_values, separators=(",", ":")),
        sample.source_file,
    )

