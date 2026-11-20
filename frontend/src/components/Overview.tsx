import { CurrentState } from '../api';
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
  const groupDemandNames: Record<number, string> = {
    0: t('noDemand'),
    1: t('heating'),
    2: t('cooling'),
  };
  const configuredGroups = data.group_setpoints
    .map((setpoint, index) => ({
      index,
      setpoint,
      demand: data.group_demands[index] ?? 0,
    }))
    .filter(({ setpoint }) => setpoint > 0);
  const unitLabel = temperatureUnit === 'f' ? '°F' : '°C';
  const displayTemperature = (value: number) =>
    number(temperatureUnit === 'f' ? value * 1.8 + 32 : value);

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
        <div className="summary-item summary-program">
          <span>{t('program')}</span>
          <strong>{programs[data.program] ?? `${t('program')} ${data.program}`}</strong>
        </div>
        <div className="summary-item summary-time">
          <span>{t('lastReading')}</span>
          <strong>
            {new Date(data.observed_at).toLocaleTimeString(locale, {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </strong>
        </div>
        <div className="summary-item summary-production">
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
        <Metric label={t('dailyConsumption')} value={number(data.energy.today_kwh, 2)} unit="kWh" />
        <Metric label={t('monthlyConsumption')} value={number(data.energy.month_kwh)} unit="kWh" />
      </section>

      <section className="pressure-summary" aria-label={t('pressures')}>
        <div>
          <span>{t('heatingPressure')}</span>
          <strong>{number(data.pressures.heating)} <small>bar</small></strong>
        </div>
        <div>
          <span>{t('brinePressure')}</span>
          <strong>{number(data.pressures.brine)} <small>bar</small></strong>
        </div>
      </section>

      <section className="demands">
        <h2>{t('productionDemands')}</h2>
        <div className="tags">
          {['dhw', 'heating', 'cooling', 'pool'].map((key) => (
            <span className={data.demands[key] ? 'active' : ''} key={key}>
              {demandNames[key]}
            </span>
          ))}
        </div>
      </section>

      {configuredGroups.length > 0 && (
        <section className="demands consumption-demands">
          <h2>{t('consumptionDemands')}</h2>
          <div className="group-demand-grid">
            {configuredGroups.map(({ index, setpoint, demand }) => (
              <div className="group-demand" key={index}>
                <div>
                  <span>{t('group')} {index + 1}</span>
                  <small>{displayTemperature(setpoint)} {unitLabel}</small>
                </div>
                <strong className={`demand-${demand}`}>
                  {groupDemandNames[demand] ?? t('noDemand')}
                </strong>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

