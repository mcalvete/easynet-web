from easynet_web.easynet.decoder import (
    RegisterSet,
    decode_current_month_energy,
    decode_state,
)


def _values(count: int) -> list[str]:
    return ["0000"] * count


def test_decode_state_builds_read_only_snapshot() -> None:
    main = _values(40)
    demands = _values(32)
    tanks = _values(35)
    main[18:29] = [
        "000A", "0014", "0018", "FFF6", "013E", "0118", "010E", "0000", "0001", "0000", "0000"
    ]
    demands[0:12] = [
        "000A",
        "0028",
        "001E",
        "000A",
        "0000",
        "0000",
        "0001",
        "0001",
        "0000",
        "0000",
        "0000",
        "0001",
    ]
    demands[31] = "0001"
    tanks[20:29] = ["0136", "014A", "0000", "0096", "00AA", "0000", "01F4", "0032", "01C2"]
    today = [
        "DIEH=0000", "DDBEH=0000", "DBEH=0000", "DAU=0014", "DA=0000", "DH=0000",
        "DP=0000", "DAC=0000", "DPC=0000", "DE=0064", "DSE=0000", "DD=0000",
        "DPF=0000", "DCI=000A", "DAAB=000A",
    ]
    month = [
        "MIEH=0000",
        "MDEH=0000",
        "MBEH=0000",
        "MAU=0014",
        "MA=0000",
        "MH=0000",
        "MP=0000",
        "MAC=0000",
        "MPC=0000",
        "ME=0064",
        "MSE=0000",
        "MDF=0000",
        "MPF=0000",
        "MCI=000A",
        "MAAB=000A",
    ]

    state = decode_state(
        RegisterSet(on_off=1, program=0, dhw_enabled=True, heating_enabled=True),
        main=main,
        demands=demands,
        tanks=tanks,
        energy_today=today,
        energy_month=month,
        alarms=["get_alarmas=N"],
    )

    assert state.power.electric_w == 10
    assert state.power.heating_w == 40
    assert state.power.cop == 4
    assert state.production["heating"] is True
    assert state.demands["dhw"] is True
    assert state.energy.today_kwh == 11


def test_current_month_decodes_dhw_and_heating() -> None:
    fields = [
        "MAU=0014",
        "MD=0854",
        "MH=15FB",
        "MP=0000",
        "MAC=0000",
        "MPC=0000",
        "ME=04F9",
        "MSE=0000",
        "MDF=0000",
        "MIEH=0000",
        "MDEH=0000",
        "MBEH=0000",
        "MPF=003D",
        "MCI=00C2",
        "MAAB=000A",
    ]

    value = decode_current_month_energy(fields, include_pumps=True, year=2026, month=11)

    assert value["dhw_kwh"] == 213.2
    assert value["heating_kwh"] == 562.7
    assert value["electric_kwh"] == 146.7
    assert value["spf"] == 5.3

