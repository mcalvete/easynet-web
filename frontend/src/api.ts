export type DataFreshness = 'live' | 'stale' | 'unavailable';
export type DataQuality = 'complete' | 'incomplete' | 'estimated' | 'unavailable';

export interface CurrentState {
  observed_at: string;
  powered: boolean;
  emergency: boolean;
  program: number;
  dhw_enabled: boolean;
  heating_enabled: boolean;
  production: Record<string, boolean>;
  demands: Record<string, boolean>;
  group_demands: number[];
  temperatures: Record<string, number>;
  pressures: Record<string, number>;
  group_setpoints: number[];
  power: {
    electric_w: number;
    heating_w: number;
    cooling_w: number;
    cop: number;
  };
  energy: {
    today_kwh: number;
    month_kwh: number;
  };
  alarm: {
    code: string | null;
    active: boolean;
  };
  freshness: DataFreshness;
}

export interface HistoryPoint {
  recorded_at: string;
  electric_power_kw: number | null;
  heating_power_kw: number | null;
  cooling_power_kw: number | null;
  dhw_temperature: number | null;
  outdoor_temperature: number | null;
  heating_buffer_temperature: number | null;
  cooling_buffer_temperature: number | null;
  heating_supply_temperature: number | null;
  heating_return_temperature: number | null;
  brine_supply_temperature: number | null;
  brine_return_temperature: number | null;
  group_temperatures: Array<number | null>;
}

export interface DailyEnergy {
  day: string;
  electric_kwh: number;
  heating_kwh: number;
  cooling_kwh: number;
  expected_samples: number;
  received_samples: number;
  quality: DataQuality;
}

export interface YearlyEnergyMonth {
  month: number;
  electric_kwh: number;
  heating_kwh: number;
  cooling_kwh: number;
  complete_days: number;
  incomplete_days: number;
  dhw_kwh: number;
  pool_kwh: number;
  passive_cooling_kwh: number;
  electric_auxiliary_kwh: number;
  spf: number;
  spfg: number;
  source: string;
}

export interface YearlyEnergy {
  year: number;
  months: YearlyEnergyMonth[];
}

export interface AppConfig {
  language: 'es' | 'en' | 'de' | 'fr' | 'it' | 'nl' | 'pl';
  temperature_unit: 'c' | 'f';
  easynet_ip: string;
}

export interface EquipmentSettings {
  system: {
    powered: boolean;
    mode: number;
    program: number;
    auto_winter_c: number;
    auto_summer_c: number;
    auto_change_hours: number;
  };
  heating: {
    enabled: boolean;
    cutoff_c: number;
    delta_c: number;
    buffer_c: number;
    group_offsets: number[];
  };
  dhw: {
    enabled: boolean;
    setpoint_c: number;
    delta_c: number;
    htr_setpoint_c: number;
    legionella: {
      enabled: boolean;
      hour: number;
      minute: number;
      days: boolean[];
    };
  };
  cooling: {
    available: boolean;
    enabled: boolean;
    active_cutoff_c: number;
    passive_cutoff_c: number;
    delta_c: number;
    group_offsets: number[];
  };
  pool: {
    available: boolean;
    enabled: boolean;
    setpoint_c: number;
    delta_c: number;
    duration_minutes: number;
    winter_enabled: boolean;
    summer_enabled: boolean;
  };
  scheduling: Record<string, unknown>;
  updated_at: string;
}

export interface EquipmentChange {
  key: string;
  before: boolean | number;
  after: boolean | number;
}

export interface EquipmentApplyResult {
  settings: EquipmentSettings;
  changed: EquipmentChange[];
  partial: boolean;
}

export interface EquipmentAlarms {
  active: string[];
  summary: Record<string, unknown>;
  raw_code: string | null;
}

export async function putJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

