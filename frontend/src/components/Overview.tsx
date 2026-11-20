import { CurrentState } from '../api';
import { convertTemperature } from '../units';
import type { TemperatureUnit } from '../units';
import { Language, languageLocales, translate } from '../i18n';

function formatNumber(value: number, digits = 1, locale = 'es-ES'): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function Metric({
  label,
  value,
  unit,
  featured,
}: {
  label: string;
  value: string;
  unit?: string;
  featured?: boolean;
}) {
  return (
    <article className={featured ? 'metric featured' : 'metric'}>
      <span>{label}</span>
      <strong>{value}</strong>
      {unit && <small>{unit}</small>}
    </article>
  );
}

export function Overview({
  data,
  temperatureUnit,
  language,
}: {
  data: CurrentState;
  temperatureUnit: TemperatureUnit;
  language: Language;
}) {
  const t = (key: string) => translate(language, key);
  const locale = languageLocales[language];
  const number = (value: number, digits = 1) => formatNumber(value, digits, locale);
  const programs = [t('winter'), t('summer'), t('auto'), t('combined'), t('remote')];
  const productionNames: Record<string, string> = {
    dhw: t('dhw'),
    heating: t('heating'),
    cooling: t('cooling'),
  };
  const demandNames: Record<string, string> = {
    dhw: t('dhw'),
    heating: t('heating'),
    cooling: t('cooling'),
    pool: t('pool'),
  };
  const temperature = (value: number) => convertTemperature(value, temperatureUnit);
  const temperatureLabel = temperatureUnit === 'f' ? '°F' : '°C';

  return (
    <>
      {data.freshness !== 'live' && (
        <div className="stale-warning" role="status">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 8v5M12 17h.01M10.3 3.8 2.6 17.1A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.9L13.7 3.8a2 2 0 0 0-3.4 0Z" />
          </svg>
          <span>{t('staleReading')}</span>
        </div>
      )}

      <section className="summary" aria-label={t('overview')}>
        <div>
          <span>{t('program')}</span>
          <strong>{programs[data.program] ?? `${t('program')} ${data.program}`}</strong>
        </div>
        <div>
          <span>{t('lastReading')}</span>
          <strong>{new Date(data.observed_at).toLocaleString(locale)}</strong>
        </div>
        <div>
          <span>{t('currentProduction')}</span>
          <strong>
            {['dhw', 'heating', 'cooling']
              .filter((key) => data.production[key])
              .map((key) => productionNames[key])
              .join(' · ') || t('waiting')}
          </strong>
        </div>
      </section>

      <section className="metrics">
        <Metric label={t('electricPower')} value={number(data.power.electric_w / 1000, 2)} unit="kW" featured />
        <Metric label={t('thermalPower')} value={number(data.power.heating_w / 1000, 2)} unit="kW" featured />
        <Metric label={t('coolingPower')} value={number(data.power.cooling_w / 1000, 2)} unit="kW" />
        <Metric label="COP" value={number(data.power.cop)} featured />
        <Metric label={t('outdoor')} value={number(temperature(data.temperatures.outdoor))} unit={temperatureLabel} />
        <Metric label={t('dhw')} value={number(temperature(data.temperatures.dhw))} unit={temperatureLabel} />
        <Metric label={t('heatingSupply')} value={number(temperature(data.temperatures.heating_supply))} unit={temperatureLabel} />
        <Metric label={t('brineReturn')} value={number(temperature(data.temperatures.brine_return))} unit={temperatureLabel} />
        <Metric label={t('heatingPressure')} value={number(data.pressures.heating)} unit="bar" />
        <Metric label={t('brinePressure')} value={number(data.pressures.brine)} unit="bar" />
        <Metric label={t('dailyConsumption')} value={number(data.energy.today_kwh, 2)} unit="kWh" />
        <Metric label={t('monthlyConsumption')} value={number(data.energy.month_kwh)} unit="kWh" />
      </section>

      <section className="demands">
        <h2>{t('demands')}</h2>
        <div className="tags">
          {['dhw', 'heating', 'cooling', 'pool'].map((key) => (
            <span className={data.demands[key] ? 'active' : ''} key={key}>
              {demandNames[key]}
            </span>
          ))}
        </div>
      </section>
    </>
  );
}

