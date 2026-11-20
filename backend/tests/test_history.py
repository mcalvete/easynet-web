from pathlib import Path

from easynet_web.history.csv_parser import parse_history_csv


def test_parse_sanitized_history_sample() -> None:
    fixture = Path(__file__).parents[2] / "fixtures/history/sample_day.csv"
    raw = fixture.read_text()

    sample = parse_history_csv(raw, source_file="/historic/sample.csv")

    assert len(sample) == 3
    assert sample[0].recorded_at.isoformat() == "2026-11-18T00:00:00"
    assert sample[0].electric_power_kw == 0.8
    assert sample[0].heating_power_kw == 1.8
    assert sample[0].cooling_power_kw == 0


def test_preserves_repeated_local_time_at_clock_change() -> None:
    header = ";".join(f"G{index}" for index in range(32)) + ";\n"
    first = ["SERIAL", "2026/10/25 02:05:00"] + ["0"] * 30
    second = ["SERIAL", "2026/10/25 02:05:00"] + ["1"] * 30
    raw = header + ";".join(first) + ";\n" + ";".join(second) + ";\n"

    samples = parse_history_csv(raw, source_file="/historic/dst.csv")

    assert [sample.occurrence for sample in samples] == [0, 1]
    assert [sample.source_sequence for sample in samples] == [2, 3]
    assert samples[0].electric_power_kw == 0
    assert samples[1].electric_power_kw == 0.1

