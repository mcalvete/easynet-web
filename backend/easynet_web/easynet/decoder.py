import re
from dataclasses import dataclass

from easynet_web.models import Alarm, CurrentState, DataFreshness, EnergyReading, PowerReading

BLOCK_MAIN = 2148
BLOCK_DEMANDS = 2149
BLOCK_TANKS = 2151
BLOCK_ENERGY_TODAY = 2137
BLOCK_ENERGY_MONTH = 2140
BLOCK_ALARMS = 1079
BLOCK_YEAR = 2141
BLOCK_YEAR_POOL_COOLING = 2142
BLOCK_YEAR_PASSIVE_ELECTRIC = 2143
BLOCK_YEAR_AUXILIARIES = 2144
BLOCK_YEAR_HEATER_AUXILIARIES = 2145
BLOCK_YEAR_PUMPS = 2154
BLOCK_SETTINGS = 2126

HEXADECIMAL = re.compile(r"^[0-9A-Fa-f]{4}$")


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class RegisterSet:
    on_off: int
    program: int
    dhw_enabled: bool
    heating_enabled: bool


def parse_int16(raw: str) -> int:
    if not HEXADECIMAL.fullmatch(raw):
        raise DecodeError(f"Invalid signed 16-bit value: {raw!r}")
    value = int(raw, 16)
    return value - 65536 if value >= 32768 else value


def parse_analog(raw: str) -> float:
    return parse_int16(raw) / 10


def parse_bool(raw: str) -> bool:
    if raw not in {"0", "1"}:
        raise DecodeError(f"Invalid coil value: {raw!r}")
    return raw == "1"


def parse_block(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise DecodeError(f"Invalid keyed block line: {line!r}")
        key, value = line.split("=", maxsplit=1)
        if not key or key in fields:
            raise DecodeError(f"Duplicate or empty block key: {key!r}")
        fields[key] = value
    return fields


def _block_value(lines: list[str], index: int, label: str) -> str:
    if index >= len(lines):
        raise DecodeError(f"Missing {label} at block index {index}")
    return lines[index]


def _required(fields: dict[str, str], key: str) -> str:
    try:
        return fields[key]
    except KeyError as exc:
        raise DecodeError(f"Missing field {key}") from exc


def _energy_to_kwh(fields: dict[str, str], prefix: str, include_pumps: bool) -> float:
    units = parse_analog(_required(fields, f"{prefix}AU"))
    electric = parse_analog(_required(fields, f"{prefix}E"))
    pumps = parse_analog(_required(fields, f"{prefix}CI")) if include_pumps else 0
    aux_units = parse_analog(_required(fields, f"{prefix}AAB"))
    aux_keys = [f"{prefix}IEH", "DDBEH" if prefix == "D" else "MDEH", f"{prefix}BEH"]
    auxiliaries = sum(parse_analog(_required(fields, key)) for key in aux_keys)
    multipliers = {0: 0.001, 1: 0.001, 2: 1, 3: 1000}
    auxiliary_multipliers = multipliers
    try:
        total = (
            (electric + pumps) * multipliers[units]
            + auxiliaries * auxiliary_multipliers[aux_units]
        )
        return round(total, 2)
    except KeyError as exc:
        raise DecodeError(f"Unsupported energy unit: {units} or {aux_units}") from exc


def decode_state(
    registers: RegisterSet,
    *,
    main: list[str],
    demands: list[str],
    tanks: list[str],
    energy_today: list[str],
    energy_month: list[str],
    alarms: list[str],
) -> CurrentState:
    power_units = parse_analog(_block_value(demands, 0, "power unit"))
    power_multipliers = {1: 1, 2: 100, 3: 1000}
    if power_units not in power_multipliers:
        raise DecodeError(f"Unsupported power unit: {power_units}")
    to_watts = power_multipliers[power_units]
    heating_power = parse_int16(_block_value(demands, 1, "heating power")) * to_watts
    cooling_power = parse_int16(_block_value(demands, 2, "cooling power")) * to_watts
    electric_register_power = parse_int16(_block_value(demands, 3, "electric power"))
    pump_power = parse_int16(_block_value(demands, 30, "pump power"))
    include_pumps = parse_int16(_block_value(demands, 31, "pump inclusion")) == 1
    electric_power = (electric_register_power + (pump_power if include_pumps else 0)) * to_watts
    today_fields = parse_block(energy_today)
    month_fields = parse_block(energy_month)
    alarm_fields = parse_block(alarms)
    alarm_code = _required(alarm_fields, "get_alarmas")
    program = registers.program
    if program not in {0, 1, 2, 3, 4}:
        raise DecodeError(f"Unsupported operating program: {program}")
    return CurrentState(
        powered=registers.on_off == 1,
        emergency=registers.on_off == 2,
        program=program,
        dhw_enabled=registers.dhw_enabled,
        heating_enabled=registers.heating_enabled,
        production={
            "dhw": any(
                (
                    parse_int16(_block_value(main, 25, "DHW mode")) in {1, 2, 4},
                    parse_int16(_block_value(main, 34, "DHW heater mode")) == 1,
                    parse_int16(_block_value(main, 35, "DHW active")) == 1,
                )
            ),
            "heating": parse_int16(_block_value(main, 26, "heating mode")) in {1, 4},
            "cooling": parse_int16(_block_value(main, 28, "cooling mode")) == 1,
        },
        demands={
            "dhw": parse_int16(_block_value(demands, 6, "DHW demand")) != 0,
            "heating": parse_int16(_block_value(demands, 7, "heating demand")) != 0,
            "cooling": parse_int16(_block_value(demands, 9, "cooling demand")) != 0
            or parse_int16(_block_value(demands, 4, "active cooling")) != 0,
            "pool": parse_int16(_block_value(demands, 10, "pool demand")) != 0,
        },
        group_demands=[
            parse_int16(_block_value(demands, 11 + index, f"group {index + 1} demand"))
            for index in range(5)
        ],
        temperatures={
            "outdoor": parse_analog(_block_value(main, 21, "outdoor temperature")),
            "heating_supply": parse_analog(_block_value(main, 22, "heating supply")),
            "brine_supply": parse_analog(_block_value(main, 23, "brine supply")),
            "brine_return": parse_analog(_block_value(main, 24, "brine return")),
            "dhw": parse_analog(_block_value(tanks, 28, "DHW temperature")),
            "heating_buffer": parse_analog(_block_value(tanks, 20, "heating buffer")),
            "cooling_buffer": parse_analog(_block_value(tanks, 23, "cooling buffer")),
        },
        pressures={
            "heating": parse_analog(_block_value(main, 18, "heating pressure")),
            "brine": parse_analog(_block_value(main, 20, "brine pressure")),
        },
        group_setpoints=[
            parse_analog(_block_value(tanks, index, f"group {index + 1} setpoint"))
            for index in range(5)
        ],
        power=PowerReading(
            electric_w=electric_power,
            heating_w=heating_power,
            cooling_w=cooling_power,
            cop=round(heating_power / electric_power, 1) if electric_power > 0 else 0,
        ),
        energy=EnergyReading(
            today_kwh=_energy_to_kwh(today_fields, "D", include_pumps),
            month_kwh=_energy_to_kwh(month_fields, "M", include_pumps),
        ),
        alarm=Alarm(code=None if alarm_code in {"", "N"} else alarm_code),
        freshness=DataFreshness.live,
    )


def _annual_values(lines: list[str], suffix: str) -> list[str]:
    fields = parse_block(lines)
    names = [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    return [_required(fields, f"{name}{suffix}") for name in names]


def decode_annual_energy(
    blocks: dict[int, list[str]], *, include_pumps: bool, year: int, current_month: int
) -> list[dict[str, float | int]]:
    def values(operation: int, key: str) -> list[float]:
        return [parse_analog(value) for value in _annual_values(blocks[operation], key)]

    unit_fields = parse_block(blocks[BLOCK_YEAR])
    unit = parse_analog(_required(unit_fields, "MAU"))
    pump_lines = blocks[BLOCK_YEAR_PUMPS]
    if len(pump_lines) != 13:
        raise DecodeError("Invalid annual pump counter block")
    auxiliary_unit = parse_analog(pump_lines[-1])
    to_kwh = {0: 0.001, 1: 0.001, 2: 1, 3: 1000}
    try:
        energy_factor = to_kwh[unit]
        auxiliary_factor = to_kwh[auxiliary_unit]
    except KeyError as exc:
        raise DecodeError("Unsupported annual energy unit") from exc

    dhw = values(BLOCK_YEAR, "D")
    heating = values(BLOCK_YEAR, "H")
    pool = values(BLOCK_YEAR_POOL_COOLING, "P")
    cooling = values(BLOCK_YEAR_POOL_COOLING, "AC")
    passive_cooling = values(BLOCK_YEAR_PASSIVE_ELECTRIC, "PC")
    electric = values(BLOCK_YEAR_PASSIVE_ELECTRIC, "E")
    pool_aux = values(BLOCK_YEAR_AUXILIARIES, "IEH")
    dhw_aux = values(BLOCK_YEAR_HEATER_AUXILIARIES, "DEH")
    heating_aux = values(BLOCK_YEAR_HEATER_AUXILIARIES, "BEH")
    pumps = [parse_analog(value) for value in pump_lines[:12]]

    result: list[dict[str, float | int]] = []
    for index in range(12):
        value_year = year if index + 1 <= current_month else year - 1
        electric_kwh = electric[index] * energy_factor
        if include_pumps:
            electric_kwh += pumps[index] * energy_factor
        production = (
            dhw[index] + heating[index] + pool[index] + cooling[index] + passive_cooling[index]
        ) * energy_factor
        auxiliary = (
            dhw_aux[index] + heating_aux[index] + pool_aux[index]
        ) * auxiliary_factor
        spf = round(production / electric_kwh, 1) if electric_kwh > 0 else 0
        spfg = (
            round((production + auxiliary) / (electric_kwh + auxiliary), 1)
            if electric_kwh + auxiliary > 0
            else 0
        )
        result.append(
            {
                "year": value_year,
                "month": index + 1,
                "dhw_kwh": round(dhw[index] * energy_factor, 3),
                "heating_kwh": round(heating[index] * energy_factor, 3),
                "pool_kwh": round(pool[index] * energy_factor, 3),
                "cooling_kwh": round(cooling[index] * energy_factor, 3),
                "passive_cooling_kwh": round(passive_cooling[index] * energy_factor, 3),
                "electric_kwh": round(electric_kwh, 3),
                "dhw_auxiliary_kwh": round(dhw_aux[index] * auxiliary_factor, 3),
                "heating_auxiliary_kwh": round(heating_aux[index] * auxiliary_factor, 3),
                "pool_auxiliary_kwh": round(pool_aux[index] * auxiliary_factor, 3),
                "spf": spf,
                "spfg": spfg,
            }
        )
    return result


def decode_current_month_energy(
    lines: list[str], *, include_pumps: bool, year: int, month: int
) -> dict[str, float | int]:
    fields = parse_block(lines)
    unit = parse_analog(_required(fields, "MAU"))
    auxiliary_unit = parse_analog(_required(fields, "MAAB"))
    to_kwh = {0: 0.001, 1: 0.001, 2: 1, 3: 1000}
    try:
        energy_factor = to_kwh[unit]
        auxiliary_factor = to_kwh[auxiliary_unit]
    except KeyError as exc:
        raise DecodeError("Unsupported current-month energy unit") from exc

    electric = parse_analog(_required(fields, "ME"))
    if include_pumps:
        electric += parse_analog(_required(fields, "MCI"))
    dhw = parse_analog(_required(fields, "MD"))
    heating = parse_analog(_required(fields, "MH"))
    pool = parse_analog(_required(fields, "MP"))
    cooling = parse_analog(_required(fields, "MAC"))
    passive_cooling = parse_analog(_required(fields, "MPC"))
    dhw_aux = parse_analog(_required(fields, "MDEH"))
    heating_aux = parse_analog(_required(fields, "MBEH"))
    pool_aux = parse_analog(_required(fields, "MIEH"))
    production = (dhw + heating + pool + cooling + passive_cooling) * energy_factor
    auxiliary = (dhw_aux + heating_aux + pool_aux) * auxiliary_factor
    electric_kwh = electric * energy_factor
    spf = round(production / electric_kwh, 1) if electric_kwh > 0 else 0.0
    spfg = (
        round((production + auxiliary) / (electric_kwh + auxiliary), 1)
        if electric_kwh + auxiliary > 0
        else 0.0
    )
    return {
        "year": year,
        "month": month,
        "dhw_kwh": round(dhw * energy_factor, 3),
        "heating_kwh": round(heating * energy_factor, 3),
        "pool_kwh": round(pool * energy_factor, 3),
        "cooling_kwh": round(cooling * energy_factor, 3),
        "passive_cooling_kwh": round(passive_cooling * energy_factor, 3),
        "electric_kwh": round(electric_kwh, 3),
        "dhw_auxiliary_kwh": round(dhw_aux * auxiliary_factor, 3),
        "heating_auxiliary_kwh": round(heating_aux * auxiliary_factor, 3),
        "pool_auxiliary_kwh": round(pool_aux * auxiliary_factor, 3),
        "spf": spf,
        "spfg": spfg,
    }

