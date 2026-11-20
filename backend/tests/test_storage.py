from datetime import date, datetime, timedelta
from pathlib import Path

from easynet_web.api import _energy_performance
from easynet_web.database import Database
from easynet_web.history.aggregate import calculate_daily_energy
from easynet_web.history.importer import import_history_file


def test_history_import_is_idempotent_and_calculates_daily_quality(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures/history/sample_day.csv"
    raw = fixture.read_text()
    database = Database(tmp_path / "easynet.db")
    database.initialize()
    device_id = database.upsert_device("SANITIZED")

    assert import_history_file(
        database,
        device_id=device_id,
        day=date(2026, 11, 18),
        source_path="/historic/backup/2026-11-18_sanitized.csv",
        raw=raw,
    ) == 3
    assert import_history_file(
        database,
        device_id=device_id,
        day=date(2026, 11, 18),
        source_path="/historic/backup/2026-11-18_sanitized.csv",
        raw=raw,
    ) == 0

    calculate_daily_energy(database, device_id, date(2026, 11, 18))

    with database.connect() as connection:
        daily = connection.execute(
            "SELECT * FROM daily_energy WHERE device_id = ? AND day = ?",
            (device_id, "2026-11-18"),
        ).fetchone()
        sample_count = connection.execute(
            "SELECT count(*) AS count FROM history_samples WHERE device_id = ?", (device_id,)
        ).fetchone()

    assert daily is not None
    assert daily["received_samples"] == 3
    assert daily["quality"] == "incomplete"
    expected_kwh = ((0.8 + 1.2) / 2 + (1.2 + 0) / 2) / 12
    assert daily["electric_kwh"] == round(expected_kwh, 3)
    assert sample_count is not None
    assert sample_count["count"] == 3


def test_daily_energy_can_be_grouped_by_month(tmp_path: Path) -> None:
    database = Database(tmp_path / "easynet.db")
    database.initialize()
    device_id = database.upsert_device("SANITIZED")
    with database.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_energy(
                device_id, day, electric_kwh, heating_kwh, cooling_kwh,
                expected_samples, received_samples, quality
            ) VALUES (?, ?, ?, ?, ?, 288, ?, ?)
            """,
            [
                (device_id, "2026-01-01", 1, 2, 0, 288, "complete"),
                (device_id, "2026-01-02", 2, 4, 1, 280, "incomplete"),
                (device_id, "2026-02-01", 3, 6, 0, 288, "complete"),
            ],
        )
        values = connection.execute(
            """
            SELECT cast(substr(day, 6, 2) AS INTEGER) AS month,
                   sum(electric_kwh) AS electric,
                   sum(heating_kwh) AS heating,
                   sum(cooling_kwh) AS cooling
            FROM daily_energy
            WHERE device_id = ? AND substr(day, 1, 4) = ?
            GROUP BY substr(day, 6, 2)
            ORDER BY month
            """,
            (device_id, "2026"),
        ).fetchall()

    assert [(row["month"], row["electric"], row["heating"], row["cooling"]) for row in values] == [
        (1, 3, 6, 1),
        (2, 3, 6, 0),
    ]


def test_native_monthly_energy_replaces_aggregates(tmp_path: Path) -> None:
    database = Database(tmp_path / "easynet.db")
    database.initialize()
    device_id = database.upsert_device("SANITIZED")
    database.save_native_monthly_energy(
        device_id,
        [
            {
                "year": 2026,
                "month": 10,
                "dhw_kwh": 10.0,
                "heating_kwh": 20.0,
                "pool_kwh": 0.0,
                "cooling_kwh": 0.0,
                "passive_cooling_kwh": 0.0,
                "electric_kwh": 8.0,
                "dhw_auxiliary_kwh": 1.0,
                "heating_auxiliary_kwh": 2.0,
                "pool_auxiliary_kwh": 0.0,
                "spf": 3.8,
                "spfg": 4.0,
            }
        ],
    )
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM native_monthly_energy
            WHERE device_id = ? AND year = 2026 AND month = 10
            """,
            (device_id,),
        ).fetchone()
    assert row is not None
    assert row["dhw_kwh"] == 10.0
    assert row["electric_kwh"] == 8.0


def test_sample_month_uses_energy_weighted_spf() -> None:
    spf, spfg = _energy_performance(620.0, 120.0, 10.0)

    assert spf == 5.2
    assert spfg == 4.8


def test_timestamp_jitter_does_not_make_day_incomplete(tmp_path: Path) -> None:
    header = ";".join(f"G{index}" for index in range(32)) + ";\n"
    rows = []
    start = date(2020, 1, 1)
    for sequence in range(288):
        timestamp = datetime.combine(start, datetime.min.time()) + timedelta(minutes=5 * sequence)
        if sequence % 2:
            timestamp += timedelta(seconds=20)
        row = ["SERIAL", timestamp.strftime("%Y/%m/%d %H:%M:%S")] + ["0"] * 30
        rows.append(";".join(row) + ";")
    raw = header + "\n".join(rows) + "\n"
    database = Database(tmp_path / "easynet.db")
    database.initialize()
    device_id = database.upsert_device("SANITIZED")
    import_history_file(
        database,
        device_id=device_id,
        day=date(2020, 1, 1),
        source_path="/historic/jitter.csv",
        raw=raw,
    )
    calculate_daily_energy(database, device_id, date(2020, 1, 1))
    with database.connect() as connection:
        row = connection.execute(
            "SELECT quality FROM daily_energy WHERE device_id = ? AND day = ?",
            (device_id, "2020-01-01"),
        ).fetchone()
    assert row is not None
    assert row["quality"] == "complete"


def test_app_config_is_persisted_and_private(tmp_path: Path) -> None:
    import pytest
    from easynet_web.models import AppConfig

    database = Database(tmp_path / "easynet.db")
    database.initialize()
    database.ensure_app_config("https://192.0.2.10")
    database.save_app_config(
        language="en", temperature_unit="f", easynet_ip="192.0.2.11"
    )
    value = AppConfig.model_validate(database.get_app_config())

    assert value.language == "en"
    assert value.temperature_unit == "f"
    assert str(value.easynet_ip) == "192.0.2.11"
    with pytest.raises(ValueError):
        AppConfig(language="es", temperature_unit="c", easynet_ip="8.8.8.8")

