import { describe, expect, it } from 'vitest';
import { convertTemperature } from './units';

describe('convertTemperature', () => {
  it('keeps Celsius values unchanged', () => {
    expect(convertTemperature(-10, 'c')).toBe(-10);
  });

  it('converts Celsius values to Fahrenheit', () => {
    expect(convertTemperature(0, 'f')).toBe(32);
    expect(convertTemperature(20, 'f')).toBe(68);
  });
});

