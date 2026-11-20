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

