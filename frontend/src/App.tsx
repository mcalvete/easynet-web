import { lazy, Suspense, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppConfig, CurrentState, getJson } from './api';
import { ConfigDialog } from './components/ConfigDialog';
import { Overview } from './components/Overview';
import { translate } from './i18n';
import { TemperatureIcon } from './components/icons';

type View = 'overview' | 'temperatures' | 'history';
const HistoryView = lazy(() =>
  import('./components/HistoryView').then((module) => ({ default: module.HistoryView })),
);
const TemperatureView = lazy(() =>
  import('./components/TemperatureView').then((module) => ({
    default: module.TemperatureView,
  })),
);

function SettingsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 15.25a3.25 3.25 0 1 0 0-6.5 3.25 3.25 0 0 0 0 6.5Z" />
      <path d="M19.4 13.5a7.8 7.8 0 0 0 .05-1.5 7.8 7.8 0 0 0-.05-1.5l2-1.55-2-3.46-2.5 1a7.85 7.85 0 0 0-2.6-1.5L14 2.3h-4l-.4 2.7a7.85 7.85 0 0 0-2.6 1.5l-2.5-1-2 3.46 2 1.55a7.8 7.8 0 0 0-.05 1.5c0 .51.02 1.01.05 1.5l-2 1.55 2 3.46 2.5-1a7.85 7.85 0 0 0 2.6 1.5l.4 2.7h4l.4-2.7a7.85 7.85 0 0 0 2.6-1.5l2.5 1 2-3.46-2.1-1.56Z" />
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
  const [configOpen, setConfigOpen] = useState(false);
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

  return (
    <div className="app">
      <header className="app-bar">
        <div className="brand">
          <div className="brand-mark">E</div>
          <h1>Easynet</h1>
        </div>
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
            onClick={() => {
              window.dispatchEvent(new Event('easynet:hide-chart-tooltip'));
              setConfigOpen(true);
            }}
            disabled={!config.data}
            aria-label={t('config')}
            title={t('config')}
          >
            <SettingsIcon />
          </button>
        </div>
      </header>

      <main>
        <nav className="section-nav" aria-label={t('sections')}>
          <button className={view === 'overview' ? 'selected' : ''} onClick={() => setView('overview')}>
            <StatusIcon />
            <span>{t('overview')}</span>
          </button>
          <button
            className={view === 'temperatures' ? 'selected' : ''}
            onClick={() => setView('temperatures')}
          >
            <TemperatureIcon />
            <span>{t('temperatures')}</span>
          </button>
          <button className={view === 'history' ? 'selected' : ''} onClick={() => setView('history')}>
            <HistoryIcon />
            <span>{t('history')}</span>
          </button>
        </nav>

        <div className="content">
          {view === 'history' ? (
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
      {configOpen && config.data && (
        <ConfigDialog
          config={config.data}
          language={language}
          onClose={() => setConfigOpen(false)}
          onSaved={async () => {
            await config.refetch();
          }}
        />
      )}
    </div>
  );
}

