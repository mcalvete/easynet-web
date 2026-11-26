import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AppConfig,
  EquipmentAlarms,
  EquipmentApplyResult,
  EquipmentSettings,
  getJson,
  postJson,
} from '../api';
import { Language, translate, languages } from '../i18n';
import { ConfigDialog } from './ConfigDialog';

type Section = 'app' | 'system' | 'heating' | 'dhw' | 'cooling' | 'pool' | 'scheduling' | 'alarms';
type Value = boolean | number;

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z" />
      <path d="m14.5 7.5 3 3" />
    </svg>
  );
}

function ResetIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" />
      <path d="M4 4v4.5h4.5" />
    </svg>
  );
}

function SyncIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 7a8 8 0 0 0-14-2L3 8m0 0h5M3 8V3M4 17a8 8 0 0 0 14 2l3-3m0 0h-5m5 0v5" />
    </svg>
  );
}

function field(
  settings: EquipmentSettings,
  key: string,
): Value {
  const path = key.split('.');
  let value: unknown = settings;
  path.forEach((part) => {
    if (Array.isArray(value)) {
      const arrayIndex =
        key.startsWith('heating.group_offsets.') ? Number(part) - 1 : Number(part);
      value = value[arrayIndex];
    } else {
      value = (value as Record<string, unknown>)[part];
    }
  });
  return value as Value;
}

function formatChange(key: string, value: Value, language: Language): string {
  if (key === 'system.mode') {
    return [translate(language, 'off'), translate(language, 'on'), translate(language, 'emergency')][
      Number(value)
    ] ?? String(value);
  }
  if (key === 'system.program') {
    return [
      translate(language, 'winter'),
      translate(language, 'summer'),
      translate(language, 'auto'),
      translate(language, 'combined'),
    ][Number(value)] ?? String(value);
  }
  if (key.startsWith('heating.group_offsets.')) {
    const number = Number(value);
    return `${translate(language, 'level')} ${number > 0 ? '+' : ''}${number}`;
  }
  if (typeof value === 'boolean') {
    return value ? translate(language, 'enabled') : translate(language, 'disabled');
  }
  if (key.endsWith('_c') || key.includes('setpoint')) {
    return `${value.toFixed(1)} °C`;
  }
  return String(value);
}

export function SettingsView({
  appConfig,
  language,
  initialSection = 'app',
  onAppConfigSaved,
}: {
  appConfig: AppConfig;
  language: Language;
  initialSection?: string;
  onAppConfigSaved: () => Promise<void>;
}) {
  const t = (key: string) => translate(language, key);
  const [section, setSection] = useState<Section>(initialSection as Section);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, Value>>({});
  const [confirmation, setConfirmation] = useState<Record<string, Value> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [appOpen, setAppOpen] = useState(false);
  const [localClock, setLocalClock] = useState(() => new Date());
  const settings = useQuery({
    queryKey: ['equipment-settings'],
    queryFn: () => getJson<EquipmentSettings>('/api/equipment/settings'),
    retry: 1,
    enabled: section !== 'app' && section !== 'alarms',
  });
  const alarms = useQuery({
    queryKey: ['equipment-alarms'],
    queryFn: () => getJson<EquipmentAlarms>('/api/equipment/alarms'),
    retry: 1,
    enabled: section === 'alarms',
  });

  const headings: Record<Section, { title: string; description: string }> = {
    app: { title: t('application'), description: t('appSettingsHelp') },
    system: { title: t('machineControl'), description: t('systemSettingsHelp') },
    heating: { title: t('heating'), description: t('heatingSettingsHelp') },
    dhw: { title: t('dhw'), description: t('dhwSettingsHelp') },
    cooling: { title: t('cooling'), description: t('coolingSettingsHelp') },
    pool: { title: t('pool'), description: t('poolSettingsHelp') },
    scheduling: { title: t('scheduling'), description: t('schedulingSettingsHelp') },
    alarms: { title: t('alarms'), description: t('alarmsHelp') },
  };

  useEffect(() => {
    setSection(initialSection as Section);
    setDraft({});
    setConfirmation(null);
    setEditing(false);
    setError('');
  }, [initialSection]);

  useEffect(() => {
    const timer = window.setInterval(() => setLocalClock(new Date()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const changes = useMemo(() => {
    if (!settings.data) return {};
    return Object.fromEntries(
      Object.entries(draft).filter(([key, value]) => field(settings.data!, key) !== value),
    );
  }, [draft, settings.data]);

  const value = (key: string): Value =>
    key in draft ? draft[key] : field(settings.data as EquipmentSettings, key);
  const set = (key: string, next: Value) => setDraft((current) => ({ ...current, [key]: next }));
  const sectionAvailable =
    !settings.data ||
    (section === 'cooling' ? settings.data.cooling.available : section === 'pool' ? settings.data.pool.available : true);
  const unset = (key: string) =>
    setDraft((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });

  function startEditing() {
    setDraft({});
    setError('');
    setEditing(true);
  }

  function cancelEditing() {
    setDraft({});
    setConfirmation(null);
    setError('');
    setEditing(false);
  }

  async function apply() {
    if (!confirmation) return;
    setSaving(true);
    setError('');
    try {
      await postJson<EquipmentApplyResult>('/api/equipment/settings/apply', {
        changes: confirmation,
        confirm: true,
      });
      await settings.refetch();
      setDraft({});
      setConfirmation(null);
      setEditing(false);
    } catch (reason) {
      await settings.refetch();
      setError(reason instanceof Error ? reason.message : t('equipmentError'));
    } finally {
      setSaving(false);
    }
  }

  async function resetAlarms() {
    if (!window.confirm(t('resetAlarmConfirm'))) return;
    setSaving(true);
    try {
      await postJson('/api/equipment/alarms/reset', { confirm: true });
      await alarms.refetch();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('equipmentError'));
    } finally {
      setSaving(false);
    }
  }

  async function syncClock() {
    const now = new Date();
    if (
      !window.confirm(
        `${t('syncClockConfirm')} ${now.toLocaleString(language === 'es' ? 'es-ES' : undefined)}.`,
      )
    ) {
      return;
    }
    setSaving(true);
    try {
      await postJson('/api/equipment/clock/sync', { confirm: true });
      await settings.refetch();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('equipmentError'));
    } finally {
      setSaving(false);
    }
  }

  const booleanControl = (key: string, label: string) => (
    <label className="settings-control">
      <span>{label}</span>
      <select
        disabled={!editing}
        value={value(key) ? '1' : '0'}
        onChange={(event) => set(key, event.target.value === '1')}
      >
        <option value="0">{t('disabled')}</option>
        <option value="1">{t('enabled')}</option>
      </select>
    </label>
  );

  const numberControl = (
    key: string,
    label: string,
    minimum: number,
    maximum: number,
    step = 0.1,
    unit = '',
  ) => (
    <label className="settings-control">
      <span>{label}</span>
      <div className="settings-number">
        <input
          type="number"
          disabled={!editing}
          min={minimum}
          max={maximum}
          step={step}
          value={Number(value(key))}
          onChange={(event) =>
            event.target.value === '' ? unset(key) : set(key, Number(event.target.value))
          }
        />
        {unit && <small>{unit}</small>}
      </div>
    </label>
  );

  return (
    <div className="settings-view">
      <div className={`settings-heading${editing ? ' editing' : ''}`}>
        <div className="settings-title">
          <h2>{headings[section].title}</h2>
          <p>{headings[section].description}</p>
        </div>
        <div className="settings-actions">
          {section === 'app' ? (
            <button
              className="settings-icon-action"
              onClick={() => setAppOpen(true)}
              aria-label={t('editPreferences')}
              title={t('editPreferences')}
            >
              <PencilIcon />
            </button>
          ) : section === 'alarms' ? (
            <button
              className="settings-icon-action danger"
              onClick={resetAlarms}
              disabled={saving || !alarms.data?.active.length}
              aria-label={t('resetAlarms')}
              title={t('resetAlarms')}
            >
              <ResetIcon />
            </button>
          ) : !editing ? (
            <button
              className="settings-icon-action"
              onClick={startEditing}
              disabled={!settings.data || !sectionAvailable}
              aria-label={t('enableEditing')}
              title={t('enableEditing')}
            >
              <PencilIcon />
            </button>
          ) : (
            <>
              <button className="secondary" onClick={cancelEditing}>{t('cancel')}</button>
              <button
                onClick={() => setConfirmation(changes)}
                disabled={Object.keys(changes).length === 0}
              >
                {t('reviewChanges')}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      {section === 'app' && (
        <section className="settings-card">
          <dl className="settings-summary">
            <div><dt>{t('language')}</dt><dd>{languages.find((item) => item.value === appConfig.language)?.label}</dd></div>
            <div><dt>{t('temperature')}</dt><dd>{appConfig.temperature_unit === 'f' ? '°F' : '°C'}</dd></div>
            <div><dt>{t('easynetIp')}</dt><dd>{appConfig.easynet_ip}</dd></div>
          </dl>
        </section>
      )}

      {section !== 'app' && section !== 'alarms' && settings.isPending && (
        <div className="loading compact">{t('loadingSettings')}</div>
      )}
      {section !== 'app' && section !== 'alarms' && settings.isError && (
        <section className="chart-card error"><p>{t('equipmentError')}</p><button onClick={() => settings.refetch()}>{t('retry')}</button></section>
      )}

      {settings.data && section === 'system' && (
        <section className="settings-card">
          <div className="settings-grid">
            <label className="settings-control">
              <span>{t('powered')}</span>
              <select disabled={!editing} value={Number(value('system.mode'))} onChange={(event) => set('system.mode', Number(event.target.value))}>
                {[t('off'), t('on'), t('emergency')].map((label, index) => <option value={index} key={label}>{label}</option>)}
              </select>
            </label>
            <label className="settings-control">
              <span>{t('programMode')}</span>
              <select disabled={!editing} value={Number(value('system.program'))} onChange={(event) => set('system.program', Number(event.target.value))}>
                {[t('winter'), t('summer'), t('auto'), t('combined')].map((label, index) => <option value={index} key={label}>{label}</option>)}
              </select>
            </label>
          </div>
        </section>
      )}

      {settings.data && section === 'heating' && (
        <section className="settings-card">
          <div className="settings-grid">
            {booleanControl('heating.enabled', t('enabled'))}
            {numberControl('heating.cutoff_c', t('heatingCutoff'), -20, 40, 0.1, '°C')}
            {numberControl('heating.delta_c', t('startDelta'), 0, 20, 0.1, '°C')}
          </div>
          <div className="settings-divider" />
          <h4>{t('groupOffsets')}</h4>
          <div className="settings-grid compact">
            {settings.data.heating.group_offsets.map((_, index) => (
              <label className="settings-control" key={index}>
                <span>{t('group')} {index + 1}</span>
                <select
                  disabled={!editing}
                  value={Number(value(`heating.group_offsets.${index + 1}`))}
                  onChange={(event) => set(`heating.group_offsets.${index + 1}`, Number(event.target.value))}
                >
                  {[-2, -1, 0, 1, 2].map((level) => <option value={level} key={level}>{t('level')} {level > 0 ? '+' : ''}{level}</option>)}
                </select>
              </label>
            ))}
          </div>
        </section>
      )}

      {settings.data && section === 'dhw' && (
        <section className="settings-card">
          <div className="settings-grid">
            {booleanControl('dhw.enabled', t('enabled'))}
            {numberControl('dhw.setpoint_c', t('setpoint'), 25, 80, 0.1, '°C')}
            {numberControl('dhw.delta_c', t('startDelta'), 0, 20, 0.1, '°C')}
            {numberControl('dhw.htr_setpoint_c', t('htrSetpoint'), 0, 100, 0.1, '°C')}
          </div>
          <div className="settings-divider" />
          <h4>{t('legionellaProtection')}</h4>
          <div className="settings-grid">
            {booleanControl('dhw.legionella.enabled', t('enabled'))}
            {numberControl('dhw.legionella.hour', t('hour'), 0, 23, 1)}
            {numberControl('dhw.legionella.minute', t('minute'), 0, 59, 1)}
          </div>
          <div className="weekday-grid">
            {[t('monday'), t('tuesday'), t('wednesday'), t('thursday'), t('friday'), t('saturday'), t('sunday')].map((day, index) => (
              <label className="weekday-toggle" key={day}>
                <input type="checkbox" disabled={!editing} checked={Boolean(value(`dhw.legionella.days.${index}`))} onChange={(event) => set(`dhw.legionella.days.${index}`, event.target.checked)} />
                <span>{day}</span>
              </label>
            ))}
          </div>
        </section>
      )}

      {settings.data && section === 'cooling' && !settings.data.cooling.available && (
        <section className="settings-card feature-unavailable">
          <strong>{t('featureUnavailable')}</strong>
          <p>{t('coolingUnavailableHelp')}</p>
        </section>
      )}

      {settings.data && section === 'cooling' && settings.data.cooling.available && (
        <section className="settings-card">
          <div className="settings-grid">
            {booleanControl('cooling.enabled', t('enabled'))}
            {numberControl('cooling.active_cutoff_c', t('activeCoolingCutoff'), -20, 40, 0.1, '°C')}
            {numberControl('cooling.passive_cutoff_c', t('passiveCoolingCutoff'), -20, 40, 0.1, '°C')}
            {numberControl('cooling.delta_c', t('startDelta'), 0, 20, 0.1, '°C')}
          </div>
          <div className="settings-divider" />
          <h4>{t('groupOffsets')}</h4>
          <div className="settings-grid compact">
            {settings.data.cooling.group_offsets.map((_, index) => (
              <label className="settings-control" key={index}>
                <span>{t('group')} {index + 1}</span>
                <select disabled={!editing} value={Number(value(`cooling.group_offsets.${index + 1}`))} onChange={(event) => set(`cooling.group_offsets.${index + 1}`, Number(event.target.value))}>
                  {[-2, -1, 0, 1, 2].map((level) => <option value={level} key={level}>{t('level')} {level > 0 ? '+' : ''}{level}</option>)}
                </select>
              </label>
            ))}
          </div>
        </section>
      )}

      {settings.data && section === 'pool' && !settings.data.pool.available && (
        <section className="settings-card feature-unavailable">
          <strong>{t('featureUnavailable')}</strong>
          <p>{t('poolUnavailableHelp')}</p>
        </section>
      )}

      {settings.data && section === 'pool' && settings.data.pool.available && (
        <section className="settings-card">
          <div className="settings-grid">
            {booleanControl('pool.enabled', t('enabled'))}
            {numberControl('pool.setpoint_c', t('setpoint'), 10, 50, 0.1, '°C')}
            {numberControl('pool.delta_c', t('startDelta'), 0, 20, 0.1, '°C')}
            {numberControl('pool.duration_minutes', t('durationMinutes'), 0, 1440, 1)}
            {booleanControl('pool.winter_enabled', t('winterSystem'))}
            {booleanControl('pool.summer_enabled', t('summerSystem'))}
          </div>
        </section>
      )}

      {settings.data && section === 'scheduling' && (
        <section className="settings-card">
          <div className="clock-card">
            <div className="clock-column">
              <span>{t('pumpClock')}</span>
              <strong>
                {new Date(String(settings.data.scheduling.pump_clock)).toLocaleString(
                  language === 'es' ? 'es-ES' : undefined,
                  { dateStyle: 'short', timeStyle: 'short' },
                )}
              </strong>
            </div>
            <div className="clock-column">
              <span>{t('localClock')}</span>
              <strong>
                {localClock.toLocaleString(language === 'es' ? 'es-ES' : undefined, {
                  dateStyle: 'short',
                  timeStyle: 'short',
                })}
              </strong>
            </div>
            <button
              className="settings-icon-action clock-sync"
              onClick={syncClock}
              disabled={!editing || saving}
              aria-label={t('syncClock')}
              title={t('syncClock')}
            >
              <SyncIcon />
            </button>
          </div>
          <div className="settings-grid">
            {booleanControl('scheduling.pump_calendar', t('pumpCalendar'))}
            {booleanControl('scheduling.vacation_calendar', t('vacationCalendar'))}
            {booleanControl('scheduling.dhw_calendar', t('dhwCalendar'))}
            {booleanControl('scheduling.heating_calendar', t('heatingCalendar'))}
            {booleanControl('scheduling.cooling_calendar', t('coolingCalendar'))}
            {booleanControl('scheduling.recirculation_calendar', t('recirculationCalendar'))}
          </div>
          <div className="settings-divider" />
          <h4>{t('nightMode')}</h4>
          <div className="settings-grid">
            {booleanControl('scheduling.night_mode_enabled', t('enabled'))}
            {numberControl('scheduling.night_start_hour', t('startHour'), 0, 23, 1)}
            {numberControl('scheduling.night_start_minute', t('startMinute'), 0, 59, 1)}
            {numberControl('scheduling.night_end_hour', t('endHour'), 0, 23, 1)}
            {numberControl('scheduling.night_end_minute', t('endMinute'), 0, 59, 1)}
            {numberControl('scheduling.night_compressor_offset_c', t('compressorOffset'), -999.9, 999.9, 0.1, '°C')}
            {booleanControl('scheduling.night_fan_enabled', t('fanEnabled'))}
            {numberControl('scheduling.night_fan_offset', t('fanOffset'), -999.9, 999.9, 0.1)}
          </div>
          <div className="settings-divider" />
          <h4>{t('daylightSaving')}</h4>
          <div className="settings-grid">
            {booleanControl('scheduling.dst_enabled', t('enabled'))}
            {numberControl('scheduling.dst_offset_minutes', t('offsetMinutes'), -999, 999, 1)}
            {numberControl('scheduling.dst_start_week', t('startWeek'), 0, 4, 1)}
            {numberControl('scheduling.dst_start_weekday', t('startWeekday'), 0, 7, 1)}
            {numberControl('scheduling.dst_start_month', t('startMonth'), 0, 12, 1)}
            {numberControl('scheduling.dst_start_hour', t('startHour'), 0, 23, 1)}
            {numberControl('scheduling.dst_end_week', t('endWeek'), 0, 4, 1)}
            {numberControl('scheduling.dst_end_weekday', t('endWeekday'), 0, 7, 1)}
            {numberControl('scheduling.dst_end_month', t('endMonth'), 0, 12, 1)}
            {numberControl('scheduling.dst_end_hour', t('endHour'), 0, 23, 1)}
          </div>
          <div className="settings-divider" />
          <h4>{t('tariffControl')}</h4>
          <div className="settings-grid">
            {booleanControl('scheduling.tariff_winter_enabled', t('winterSchedule'))}
            {numberControl('scheduling.tariff_winter_day', t('winterStartDay'), 1, 31, 1)}
            {numberControl('scheduling.tariff_winter_month', t('winterStartMonth'), 1, 12, 1)}
            {booleanControl('scheduling.tariff_summer_enabled', t('summerSchedule'))}
            {numberControl('scheduling.tariff_summer_day', t('summerStartDay'), 1, 31, 1)}
            {numberControl('scheduling.tariff_summer_month', t('summerStartMonth'), 1, 12, 1)}
            {numberControl('scheduling.tariff_winter_dhw_peak', t('winterDhwPeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_winter_dhw_offpeak', t('winterDhwOffpeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_winter_heating_peak', t('winterHeatingPeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_winter_heating_offpeak', t('winterHeatingOffpeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_summer_dhw_peak', t('summerDhwPeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_summer_dhw_offpeak', t('summerDhwOffpeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_summer_heating_peak', t('summerHeatingPeak'), -999.9, 999.9, 0.1, '°C')}
            {numberControl('scheduling.tariff_summer_heating_offpeak', t('summerHeatingOffpeak'), -999.9, 999.9, 0.1, '°C')}
          </div>
          <details className="settings-advanced">
            <summary>{t('advancedSchedulingValues')}</summary>
            <pre className="settings-data">{JSON.stringify(settings.data.scheduling, null, 2)}</pre>
          </details>
        </section>
      )}

      {section === 'alarms' && (
        <section className="settings-card alarm-status-card">
          {alarms.isPending ? <p className="alarm-loading">{t('loadingAlarms')}</p> : alarms.isError ? <p className="form-error">{t('equipmentError')}</p> : alarms.data.active.length ? (
            <ul className="alarm-list">{alarms.data.active.map((alarm) => <li key={alarm}>{alarm}</li>)}</ul>
          ) : (
            <div className="alarm-empty" role="status">
              <span className="alarm-empty-icon" aria-hidden="true">✓</span>
              <div>
                <strong>{t('noActiveAlarms')}</strong>
                <small>{t('pumpReady')}</small>
              </div>
            </div>
          )}
        </section>
      )}

      {confirmation && settings.data && (
        <div className="dialog-backdrop" role="presentation">
          <section className="config-dialog confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h2 id="confirm-title">{t('confirmEquipmentChanges')}</h2>
            <p>{t('confirmEquipmentChangesHelp')}</p>
            <ul className="change-list">
              {Object.entries(confirmation).map(([key, after]) => (
                <li key={key}><strong>{key}</strong><span>{formatChange(key, field(settings.data!, key), language)} → {formatChange(key, after, language)}</span></li>
              ))}
            </ul>
            {error && <p className="form-error">{error}</p>}
            <div className="dialog-actions">
              <button className="secondary" onClick={() => setConfirmation(null)} disabled={saving}>{t('cancel')}</button>
              <button onClick={apply} disabled={saving}>{saving ? t('saving') : t('applyChanges')}</button>
            </div>
          </section>
        </div>
      )}

      {appOpen && (
        <ConfigDialog config={appConfig} language={language} onClose={() => setAppOpen(false)} onSaved={async () => { await onAppConfigSaved(); setAppOpen(false); }} />
      )}
    </div>
  );
}
