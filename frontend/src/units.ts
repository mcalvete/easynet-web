export type TemperatureUnit = 'c' | 'f';

export function convertTemperature(value: number, unit: TemperatureUnit): number {
  return unit === 'f' ? value * 1.8 + 32 : value;
}

