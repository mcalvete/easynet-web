import { lazy, Suspense, useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppConfig, CurrentState, getJson } from './api';
import { Overview } from './components/Overview';
import { translate } from './i18n';
import { TemperatureIcon } from './components/icons';

type View = 'overview' | 'temperatures' | 'history' | 'settings';
const HistoryView = lazy(() =>
  import('./components/HistoryView').then((module) => ({ default: module.HistoryView })),
);
const TemperatureView = lazy(() =>
  import('./components/TemperatureView').then((module) => ({
    default: module.TemperatureView,
  })),
);
const SettingsView = lazy(() =>
  import('./components/SettingsView').then((module) => ({ default: module.SettingsView })),
);

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function StatusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 13h3l2-7 4 14 2-7h5" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 19V5M4 19h16M7 15l4-4 3 2 5-6" />
    </svg>
  );
}

export function App() {
  const [view, setView] = useState<View>('overview');
  const [settingsSection, setSettingsSection] = useState('app');
  const [menuOpen, setMenuOpen] = useState(false);
  const config = useQuery({
    queryKey: ['config'],
    queryFn: () => getJson<AppConfig>('/api/config'),
  });
  const language = config.data?.language ?? 'es';
  const t = (key: string) => translate(language, key);
  const state = useQuery({
    queryKey: ['state'],
    queryFn: () => getJson<CurrentState>('/api/state'),
    refetchInterval: 60_000,
  });
  const statusText = state.data
    ? state.data.alarm.active
      ? t('alarm')
      : state.data.powered
        ? t('operational')
        : t('stopped')
    : '';

  useEffect(() => {
    if (!menuOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', close);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', close);
    };
  }, [menuOpen]);

  const navigate = (next: View, section = 'app') => {
    window.dispatchEvent(new Event('easynet:hide-chart-tooltip'));
    setView(next);
    setSettingsSection(section);
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="app">
      <header className="app-bar">
        <button className="brand" onClick={() => navigate('overview')} aria-label={t('overview')}>
          <div className="brand-mark">E</div>
          <h1>Easynet</h1>
        </button>
        <div className="app-bar-actions">
          {state.data && (
            <div
              className={state.data.alarm.active ? 'status alarm' : 'status'}
              title={statusText}
              aria-label={statusText}
            >
              <span className="status-indicator" aria-hidden="true">
                {state.data.alarm.active ? (
                  <svg viewBox="0 0 24 24">
                    <path d="M12 8v5m0 3h.01M12 3 2 21h20L12 3Z" />
                  </svg>
                ) : state.data.powered ? (
                  <svg viewBox="0 0 24 24">
                    <path d="M12 3v9m-4.5-6.5a8 8 0 1 0 9 0" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24">
                    <path d="M6 12h12" />
                  </svg>
                )}
              </span>
              <span className="status-label">{statusText}</span>
            </div>
          )}
          <button
            className="icon-button"
            onClick={() => setMenuOpen((open) => !open)}
            disabled={!config.data}
            aria-label={t('menu')}
            aria-expanded={menuOpen}
            title={t('menu')}
          >
            <MenuIcon />
          </button>
        </div>
      </header>

      <main>
        <div className="content">
          {view === 'settings' && config.data ? (
            <Suspense fallback={<div className="loading compact">{t('loadingSettings')}</div>}>
              <SettingsView
                appConfig={config.data}
                language={language}
                initialSection={settingsSection}
                onAppConfigSaved={async () => {
                  await config.refetch();
                }}
              />
            </Suspense>
          ) : view === 'history' ? (
            <Suspense fallback={<div className="loading compact">{t('loadingHistory')}</div>}>
              <HistoryView language={language} />
            </Suspense>
          ) : view === 'temperatures' ? (
            <Suspense fallback={<div className="loading compact">{t('loadingTemperatures')}</div>}>
              <TemperatureView
                language={language}
                temperatureUnit={config.data?.temperature_unit ?? 'c'}
                state={state.data}
              />
            </Suspense>
          ) : state.isPending ? (
            <div className="loading compact">{t('connecting')}</div>
          ) : state.isError || !state.data ? (
            <section className="chart-card error">
              <h2>{t('unavailable')}</h2>
              <p>{t('unavailableBody')}</p>
              <button onClick={() => state.refetch()}>{t('retry')}</button>
            </section>
          ) : (
            <Overview
              data={state.data}
              temperatureUnit={config.data?.temperature_unit ?? 'c'}
              language={language}
            />
          )}
        </div>
      </main>
      {menuOpen && (
        <div className="app-menu-backdrop" onMouseDown={() => setMenuOpen(false)}>
          <nav
            className="app-menu"
            aria-label={t('sections')}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="app-menu-header">
              <strong>{t('menu')}</strong>
              <button className="icon-button" onClick={() => setMenuOpen(false)} aria-label={t('close')}>×</button>
            </div>
            <button className={view === 'overview' ? 'selected' : ''} onClick={() => navigate('overview')}><StatusIcon />{t('overview')}</button>
            <button className={view === 'temperatures' ? 'selected' : ''} onClick={() => navigate('temperatures')}><TemperatureIcon />{t('temperatures')}</button>
            <button className={view === 'history' ? 'selected' : ''} onClick={() => navigate('history')}><HistoryIcon />{t('history')}</button>
            <div className="app-menu-divider" />
            <button className={view === 'settings' && settingsSection === 'app' ? 'selected' : ''} onClick={() => navigate('settings', 'app')}>{t('application')}</button>
            <button className={view === 'settings' && settingsSection === 'system' ? 'selected' : ''} onClick={() => navigate('settings', 'system')}>{t('system')}</button>
            <button className={view === 'settings' && settingsSection === 'heating' ? 'selected' : ''} onClick={() => navigate('settings', 'heating')}>{t('heating')}</button>
            <button className={view === 'settings' && settingsSection === 'dhw' ? 'selected' : ''} onClick={() => navigate('settings', 'dhw')}>{t('dhw')}</button>
            <button className={view === 'settings' && settingsSection === 'cooling' ? 'selected' : ''} onClick={() => navigate('settings', 'cooling')}>{t('cooling')}</button>
            <button className={view === 'settings' && settingsSection === 'pool' ? 'selected' : ''} onClick={() => navigate('settings', 'pool')}>{t('pool')}</button>
            <button className={view === 'settings' && settingsSection === 'scheduling' ? 'selected' : ''} onClick={() => navigate('settings', 'scheduling')}>{t('scheduling')}</button>
            <button className={view === 'settings' && settingsSection === 'alarms' ? 'selected' : ''} onClick={() => navigate('settings', 'alarms')}>{t('alarms')}</button>
          </nav>
        </div>
      )}
    </div>
  );
}

