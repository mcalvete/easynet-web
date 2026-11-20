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

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

