import csv
from datetime import datetime
from io import StringIO

from easynet_web.models import HistorySample

EXPECTED_HEADER = [f"G{index}" for index in range(32)]


class HistoryFileError(ValueError):
    pass


def parse_history_csv(raw: str, *, source_file: str) -> list[HistorySample]:
    try:
        rows = list(csv.reader(StringIO(raw), delimiter=";"))
    except csv.Error as exc:
        raise HistoryFileError("Invalid Easynet CSV") from exc
    if not rows or [value for value in rows[0] if value] != EXPECTED_HEADER:
        raise HistoryFileError("Unexpected Easynet CSV header")

    samples: list[HistorySample] = []
    occurrences: dict[datetime, int] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not row or all(not value for value in row):
            continue
        values = row[:-1] if row and row[-1] == "" else row
        if len(values) != 32:
            raise HistoryFileError(f"Invalid CSV row {row_number}: expected 32 values")
        try:
            recorded_at = datetime.strptime(values[1], "%Y/%m/%d %H:%M:%S")
            numeric = [int(value) for value in values[2:]]
        except (ValueError, IndexError) as exc:
            raise HistoryFileError(f"Invalid CSV row {row_number}") from exc
        occurrence = occurrences.get(recorded_at, 0)
        occurrences[recorded_at] = occurrence + 1
        samples.append(
            HistorySample(
                recorded_at=recorded_at,
                occurrence=occurrence,
                source_sequence=row_number,
                electric_power_kw=numeric[24] / 10,
                heating_power_kw=numeric[25] / 10,
                cooling_power_kw=numeric[26] / 10,
                raw_values=numeric,
                source_file=source_file,
            )
        )
    return samples

