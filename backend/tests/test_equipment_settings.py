from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from easynet_web.easynet.settings import (
    ALARM_RESET_REGISTER,
    OFFICIAL_BLOCK_FIELDS,
    SETTINGS_WHITELIST,
    EquipmentSettingsService,
    SettingsApplyError,
    SettingsValidationError,
)


class AuditDatabase:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_equipment_change(self, **record: object) -> None:
        self.records.append(record)


class FakeClient:
    def __init__(self) -> None:
        self.registers = {6100: 1, 6101: 0, 6159: 180, 6148: 50}
        self.registers.update({address: 2 for address in range(6143, 6148)})
        self.registers.update({6106: 500, 6105: 20, 6104: 750, 6108: 12, 6110: 30})
        self.registers.update(
            {
                6091: 22,
                6093: 0,
                6090: 7,
                6092: 0,
                6094: 100,
                6089: 50,
            }
        )
        self.coils = {
            1552: True,
            1524: True,
            1527: False,
            1526: False,
            1528: False,
            1529: True,
            1530: False,
            1531: False,
            1532: False,
            1533: False,
            1502: False,
            1500: False,
            1501: False,
            1503: False,
            1508: False,
            1507: False,
            1517: False,
            1516: False,
        }
        self.write_hook: Callable[[str, int, bool | int], None] | None = None
        self.writes: list[tuple[str, int, bool | int]] = []
        self.verification_override: dict[int, str] = {}
        self.block_overrides: dict[str, str] = {}

    async def read_registers(self, address: int, count: int) -> dict[int, str]:
        assert count == 1
        value = self.verification_override.get(address, f"{self.registers[address] & 0xFFFF:04x}")
        return {address: value}

    async def read_coils(self, address: int, count: int) -> dict[int, str]:
        assert count == 1
        return {address: "1" if self.coils[address] else "0"}

    async def write_register(self, address: int, value: int) -> None:
        self._write("register", address, value)
        self.registers[address] = value

    async def write_coil(self, address: int, value: bool) -> None:
        self._write("coil", address, value)
        self.coils[address] = value

    def _write(self, kind: str, address: int, value: bool | int) -> None:
        self.writes.append((kind, address, value))
        if kind == "register":
            address_fields = {
                6159: "TCC",
                **{6142 + number: f"OCZ{number}" for number in range(1, 6)},
            }
            if address in address_fields:
                self.block_overrides[address_fields[address]] = f"{value & 0xFFFF:04x}"
        if self.write_hook:
            self.write_hook(kind, address, value)

    async def read_block(self, operation: int) -> list[str]:
        values = OFFICIAL_BLOCK_FIELDS.get(operation)
        if values:
            defaults = {
                "KO": "0001",
                "TAI": "0078",
                "TAV": "00DC",
                "NHA": "0008",
                "TCC": "00B4",
                "ECU": "1",
                "AEU": "1",
                "AS": "01F4",
                "AO": "0028",
                "ATSH": "02BC",
                "OCZ1": "0002",
                "OCZ2": "0002",
                "OCZ3": "0002",
                "OCZ4": "0002",
                "OCZ5": "0002",
            }
            extra_defaults = {
                "CGFI": "0000",
                "ERU": "0000",
                "TCFA": "0018",
                "TCFP": "001C",
                "OIF": "0032",
                "PGFI": "0000",
                "EPU": "0",
                "EHI": "0",
                "EHV": "0",
                "PDTS": "001E",
                "PDOT": "0000",
                "PPDO": "001E",
            }
            def block_value(name: str) -> str:
                fallback = defaults.get(name, extra_defaults.get(name, "0000"))
                return self.block_overrides.get(name, fallback)

            return [
                f"{name}={block_value(name)}" for name in values
            ]
        if operation in {2102, 2105, 2109, 2126}:
            values = [
                "PROGRAM=0001",
                "PHBC=0",
                "ESO=0",
                "PHA=0",
                "PHC=0",
                "PHR=0",
                "PHRA=0",
                "EHN=0",
                "HHNS=0000",
                "MHNS=0000",
                "HHNE=0000",
                "MHNE=0000",
                "PMHN=03E8",
                "FMPNT=01F4",
                "EHAU=0",
                "MD2E=0",
                "MD2M=0000",
                "MD2SMW=0000",
                "MD2SW=0000",
                "MD2SM=0000",
                "MD2SH=0000",
                "MD2EMW=0000",
                "MD2EW=0000",
                "MD2EM=0000",
                "MD2EH=0000",
                "ESTC=0",
                "EWTC=0",
                "STWSD=0001",
                "STWSM=000A",
                "STSSD=0001",
                "STSSM=0003",
                "DWPO=0000",
                "DWVO=0000",
                "HWPO=0000",
                "HWVO=0000",
                "DSPO=0000",
                "DSVO=0000",
                "HSPO=0000",
                "HSVO=0000",
            ]
            if operation == 2102:
                values += ["CY=001A", "CMO=000B", "CD=001A", "CH=000C", "CM=001E"]
            return values
        if operation == 2135:
            return ["alarms=0"]
        if operation == 1079:
            return ["get_alarmas=N"]
        raise AssertionError(f"Unexpected operation {operation}")


@pytest.fixture
def service() -> tuple[EquipmentSettingsService, FakeClient, AuditDatabase]:
    client = FakeClient()
    database = AuditDatabase()
    return EquipmentSettingsService(client, database), client, database  # type: ignore[arg-type]


def test_whitelist_rejects_arbitrary_address() -> None:
    assert "6100" not in SETTINGS_WHITELIST
    assert "anything.address" not in SETTINGS_WHITELIST
    assert {item.address for item in SETTINGS_WHITELIST.values()} == {
        6100,
        6101,
        1552,
        6159,
        6148,
        6143,
        6144,
        6145,
        6146,
        6147,
        1524,
        6106,
        6105,
        6104,
        1527,
        6108,
        6110,
        1529,
        1530,
        1531,
        1528,
        1533,
        1532,
        1526,
        1502,
        1500,
        1501,
        1503,
        1508,
        1507,
        1517,
        6091,
        6093,
        6090,
        6092,
        6094,
        6089,
        1516,
        1509,
        6074,
        6081,
        6082,
        6080,
        6079,
        6077,
        6078,
        6076,
        6075,
        1643,
        1642,
        6427,
        6426,
        6429,
        6428,
        6416,
        6417,
        6420,
        6421,
        6414,
        6415,
        6418,
        6419,
        1568,
        6219,
        6220,
        6208,
        6203,
        6204,
        6205,
        6206,
        6207,
        1574,
        6253,
        6251,
        6252,
        1570,
        1571,
    }


@pytest.mark.asyncio
async def test_settings_contract_and_scaled_encoding(service: Any) -> None:
    manager, client, _ = service

    result = await manager.apply(
        {"heating.cutoff_c": 19.5, "heating.group_offsets.1": -2},
        confirm=True,
    )

    assert client.writes == [
        ("register", 6159, 195),
        ("register", 6143, 0),
    ]
    assert result["settings"]["system"]["mode"] == 1
    assert result["settings"]["heating"]["group_offsets"][0] == -2
    assert result["changed"] == [
        {"key": "heating.cutoff_c", "before": 18.0, "after": 19.5},
        {"key": "heating.group_offsets.1", "before": 0, "after": -2},
    ]
    assert result["partial"] is False


@pytest.mark.asyncio
async def test_rejects_ranges_and_confirmation(service: Any) -> None:
    manager, _, database = service

    with pytest.raises(SettingsValidationError, match="confirm"):
        await manager.apply({"system.mode": 1}, confirm=False)
    with pytest.raises(SettingsValidationError, match="between"):
        await manager.apply({"dhw.setpoint_c": 90}, confirm=True)

    assert len(database.records) == 2
    assert all(record["success"] is False for record in database.records)


@pytest.mark.asyncio
async def test_partial_write_failure_is_explicit(service: Any) -> None:
    manager, client, database = service

    def fail_second(_kind: str, address: int, _value: bool | int) -> None:
        if address == 6101:
            raise RuntimeError("device rejected write")

    client.write_hook = fail_second

    with pytest.raises(SettingsApplyError) as error:
        await manager.apply(
            {"system.mode": 2, "system.program": 1},
            confirm=True,
        )

    assert error.value.detail()["partial"] is True
    assert error.value.detail()["applied_keys"] == ["system.mode"]
    assert error.value.detail()["failed_key"] == "system.program"
    assert database.records[-1]["success"] is False


@pytest.mark.asyncio
async def test_verification_mismatch_is_visible(service: Any) -> None:
    manager, client, database = service
    client.block_overrides["OPK"] = "0003"

    with pytest.raises(SettingsApplyError, match="verification") as error:
        await manager.apply({"system.program": 1}, confirm=True)

    assert error.value.partial_apply is True
    assert error.value.mismatches == {"system.program": {"expected": 1, "actual": 3}}
    assert database.records[-1]["success"] is False


@pytest.mark.asyncio
async def test_alarm_reset_address_is_fixed(service: Any) -> None:
    manager, client, _ = service

    response = await manager.reset_alarms(confirm=True)

    assert client.writes == [("register", ALARM_RESET_REGISTER, 1)]
    assert response == {
        "active": [],
        "summary": {"2135": {"alarms": "0"}, "1079": {"get_alarmas": "N"}},
        "raw_code": "N",
    }


@pytest.mark.asyncio
async def test_clock_sync_uses_official_sequence(service: Any) -> None:
    manager, client, _ = service
    now = datetime(2026, 11, 26, 12, 30)
    client.block_overrides.update(
        {"CY": "001A", "CMO": "000B", "CD": "001A", "CH": "000C", "CM": "001E"}
    )

    def match_clock(kind: str, address: int, value: bool | int) -> None:
        del kind, address, value

    client.write_hook = match_clock
    await manager.sync_clock(confirm=True, now=now)

    assert client.writes == [
        ("register", 6083, 26),
        ("coil", 1510, True),
        ("register", 6647, 26),
        ("register", 6086, 11),
        ("coil", 1513, True),
        ("register", 6646, 11),
        ("register", 6088, 26),
        ("coil", 1515, True),
        ("register", 6645, 26),
        ("register", 6084, 12),
        ("coil", 1511, True),
        ("register", 6648, 12),
        ("register", 6085, 30),
        ("coil", 1512, True),
        ("register", 6649, 30),
    ]
