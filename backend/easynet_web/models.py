from datetime import date, datetime
from enum import StrEnum
from ipaddress import IPv4Address

from pydantic import BaseModel, Field, field_validator


class DataFreshness(StrEnum):
    live = "live"
    stale = "stale"
    unavailable = "unavailable"


class DataQuality(StrEnum):
    complete = "complete"
    incomplete = "incomplete"
    estimated = "estimated"
    unavailable = "unavailable"


class PowerReading(BaseModel):
    electric_w: float
    heating_w: float
    cooling_w: float
    cop: float


class EnergyReading(BaseModel):
    today_kwh: float
    month_kwh: float


class Alarm(BaseModel):
    code: str | None = None
    active: bool = Field(default=False)

    def model_post_init(self, __context: object) -> None:
        self.active = self.code is not None


class CurrentState(BaseModel):
    observed_at: datetime = Field(default_factory=datetime.now)
    powered: bool
    emergency: bool
    program: int
    dhw_enabled: bool
    heating_enabled: bool
    production: dict[str, bool]
    demands: dict[str, bool]
    group_demands: list[int]
    temperatures: dict[str, float]
    pressures: dict[str, float]
    group_setpoints: list[float]
    power: PowerReading
    energy: EnergyReading
    alarm: Alarm
    freshness: DataFreshness


class CollectorHealth(BaseModel):
    status: str
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None


class AppConfig(BaseModel):
    language: str = "es"
    temperature_unit: str = "c"
    easynet_ip: IPv4Address

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in {"es", "en", "de", "fr", "it", "nl", "pl"}:
            raise ValueError("unsupported language")
        return value

    @field_validator("temperature_unit")
    @classmethod
    def validate_temperature_unit(cls, value: str) -> str:
        if value not in {"c", "f"}:
            raise ValueError("temperature unit must be c or f")
        return value

    @field_validator("easynet_ip")
    @classmethod
    def validate_private_ip(cls, value: IPv4Address) -> IPv4Address:
        if not value.is_private:
            raise ValueError("Easynet IP must be private")
        return value


class EquipmentSystemSettings(BaseModel):
    powered: bool
    mode: int
    program: int
    auto_winter_c: float
    auto_summer_c: float
    auto_change_hours: int


class EquipmentHeatingSettings(BaseModel):
    enabled: bool
    cutoff_c: float
    delta_c: float
    buffer_c: float
    group_offsets: list[float] = Field(min_length=5, max_length=5)


class EquipmentLegionellaSettings(BaseModel):
    enabled: bool
    hour: int
    minute: int
    days: list[bool] = Field(min_length=7, max_length=7)


class EquipmentDhwSettings(BaseModel):
    enabled: bool
    setpoint_c: float
    delta_c: float
    htr_setpoint_c: float
    legionella: EquipmentLegionellaSettings


class EquipmentCoolingSettings(BaseModel):
    available: bool
    enabled: bool
    active_cutoff_c: float
    passive_cutoff_c: float
    delta_c: float
    group_offsets: list[float] = Field(min_length=5, max_length=5)


class EquipmentPoolSettings(BaseModel):
    available: bool
    enabled: bool
    setpoint_c: float
    delta_c: float
    duration_minutes: int
    winter_enabled: bool
    summer_enabled: bool


class EquipmentSettingsResponse(BaseModel):
    system: EquipmentSystemSettings
    heating: EquipmentHeatingSettings
    dhw: EquipmentDhwSettings
    cooling: EquipmentCoolingSettings
    pool: EquipmentPoolSettings
    scheduling: dict[str, object]
    updated_at: datetime


class EquipmentSettingChange(BaseModel):
    key: str
    before: bool | int | float
    after: bool | int | float


class EquipmentSettingsApplyRequest(BaseModel):
    changes: dict[str, bool | int | float]
    confirm: bool = False


class EquipmentSettingsApplyResponse(BaseModel):
    settings: EquipmentSettingsResponse
    changed: list[EquipmentSettingChange]
    partial: bool = False


class AlarmResetRequest(BaseModel):
    confirm: bool = False


class EquipmentAlarmsResponse(BaseModel):
    active: list[str]
    summary: dict[str, object]
    raw_code: str | None


class HistorySample(BaseModel):
    recorded_at: datetime
    occurrence: int = 0
    source_sequence: int
    electric_power_kw: float | None
    heating_power_kw: float | None
    cooling_power_kw: float | None
    raw_values: list[int]
    source_file: str


class DailyEnergy(BaseModel):
    day: date
    electric_kwh: float
    heating_kwh: float
    cooling_kwh: float
    expected_samples: int = 288
    received_samples: int
    quality: DataQuality
    native_electric_kwh: float | None = None
    difference_percent: float | None = None


class MonthlyEnergy(BaseModel):
    year: int
    month: int
    days: list[DailyEnergy]


class YearlyEnergyMonth(BaseModel):
    month: int
    electric_kwh: float
    heating_kwh: float
    cooling_kwh: float
    complete_days: int
    incomplete_days: int
    dhw_kwh: float
    heating_kwh: float
    pool_kwh: float
    cooling_kwh: float
    passive_cooling_kwh: float
    electric_auxiliary_kwh: float
    spf: float
    spfg: float
    source: str


class YearlyEnergy(BaseModel):
    year: int
    months: list[YearlyEnergyMonth]

