import json
import sqlite3
from pathlib import Path

from easynet_web.models import CurrentState

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    serial TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT 'ecoGEO',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS current_state (
    device_id INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    day TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, path, day)
);

CREATE TABLE IF NOT EXISTS history_samples (
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    recorded_at TEXT NOT NULL,
    occurrence INTEGER NOT NULL DEFAULT 0,
    source_sequence INTEGER NOT NULL,
    electric_power_kw REAL,
    heating_power_kw REAL,
    cooling_power_kw REAL,
    raw_json TEXT NOT NULL,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(device_id, recorded_at, occurrence)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS daily_energy (
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    electric_kwh REAL NOT NULL,
    heating_kwh REAL NOT NULL,
    cooling_kwh REAL NOT NULL,
    expected_samples INTEGER NOT NULL DEFAULT 288,
    received_samples INTEGER NOT NULL,
    quality TEXT NOT NULL,
    native_electric_kwh REAL,
    difference_percent REAL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(device_id, day)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS native_monthly_energy (
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    dhw_kwh REAL NOT NULL,
    heating_kwh REAL NOT NULL,
    pool_kwh REAL NOT NULL,
    cooling_kwh REAL NOT NULL,
    passive_cooling_kwh REAL NOT NULL,
    electric_kwh REAL NOT NULL,
    dhw_auxiliary_kwh REAL NOT NULL,
    heating_auxiliary_kwh REAL NOT NULL,
    pool_auxiliary_kwh REAL NOT NULL,
    spf REAL NOT NULL,
    spfg REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(device_id, year, month)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS app_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    language TEXT NOT NULL DEFAULT 'es',
    temperature_unit TEXT NOT NULL DEFAULT 'c',
    easynet_ip TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS history_samples_recorded_at_idx
    ON history_samples(recorded_at);
CREATE INDEX IF NOT EXISTS daily_energy_day_idx
    ON daily_energy(day);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def upsert_device(self, serial: str) -> int:
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO devices(serial) VALUES (?)", (serial,))
            row = connection.execute(
                "SELECT id FROM devices WHERE serial = ?", (serial,)
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to create device")
            return int(row["id"])

    def save_current_state(self, device_id: int, state: CurrentState) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO current_state(device_id, observed_at, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    observed_at=excluded.observed_at,
                    payload_json=excluded.payload_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (device_id, state.observed_at.isoformat(), state.model_dump_json()),
            )

    def ensure_app_config(self, easynet_host: str) -> None:
        from urllib.parse import urlparse

        hostname = urlparse(easynet_host).hostname
        if hostname is None:
            raise ValueError("Easynet host does not contain an IP")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO app_config(id, easynet_ip)
                VALUES (1, ?)
                """,
                (hostname,),
            )

    def get_app_config(self) -> dict[str, str] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT language, temperature_unit, easynet_ip FROM app_config WHERE id = 1"
            ).fetchone()
        return dict(row) if row else None

    def save_app_config(
        self, *, language: str, temperature_unit: str, easynet_ip: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE app_config
                SET language = ?, temperature_unit = ?, easynet_ip = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (language, temperature_unit, easynet_ip),
            )

    def get_current_state(self, device_id: int) -> CurrentState | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM current_state WHERE device_id = ?", (device_id,)
            ).fetchone()
        return CurrentState.model_validate(json.loads(row["payload_json"])) if row else None

    def get_first_device_id(self) -> int | None:
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM devices ORDER BY id LIMIT 1").fetchone()
        return int(row["id"]) if row else None

    def has_history_day(self, device_id: int, day: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM source_files
                WHERE device_id = ? AND day = ?
                LIMIT 1
                """,
                (device_id, day),
            ).fetchone()
        return row is not None

    def save_native_monthly_energy(
        self, device_id: int, rows: list[dict[str, float | int]]
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO native_monthly_energy(
                    device_id, year, month, dhw_kwh, heating_kwh, pool_kwh,
                    cooling_kwh, passive_cooling_kwh, electric_kwh,
                    dhw_auxiliary_kwh, heating_auxiliary_kwh,
                    pool_auxiliary_kwh, spf, spfg
                ) VALUES (
                    :device_id, :year, :month, :dhw_kwh, :heating_kwh, :pool_kwh,
                    :cooling_kwh, :passive_cooling_kwh, :electric_kwh,
                    :dhw_auxiliary_kwh, :heating_auxiliary_kwh,
                    :pool_auxiliary_kwh, :spf, :spfg
                )
                ON CONFLICT(device_id, year, month) DO UPDATE SET
                    dhw_kwh=excluded.dhw_kwh,
                    heating_kwh=excluded.heating_kwh,
                    pool_kwh=excluded.pool_kwh,
                    cooling_kwh=excluded.cooling_kwh,
                    passive_cooling_kwh=excluded.passive_cooling_kwh,
                    electric_kwh=excluded.electric_kwh,
                    dhw_auxiliary_kwh=excluded.dhw_auxiliary_kwh,
                    heating_auxiliary_kwh=excluded.heating_auxiliary_kwh,
                    pool_auxiliary_kwh=excluded.pool_auxiliary_kwh,
                    spf=excluded.spf,
                    spfg=excluded.spfg,
                    updated_at=CURRENT_TIMESTAMP
                """,
                ({"device_id": device_id, **row} for row in rows),
            )

