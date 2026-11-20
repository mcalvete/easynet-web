import { lazy, Suspense, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppConfig, CurrentState, getJson } from './api';
import { ConfigDialog } from './components/ConfigDialog';
import { Overview } from './components/Overview';
import { translate } from './i18n';

type View = 'overview' | 'history';
const HistoryView = lazy(() =>
  import('./components/HistoryView').then((module) => ({ default: module.HistoryView })),
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

  return (
    <div className="app">
      <header className="app-bar">
        <div className="brand">
          <div className="brand-mark">E</div>
          <h1>Easynet</h1>
        </div>
        <div className="app-bar-actions">
          {state.data && (
            <div className={state.data.alarm.active ? 'status alarm' : 'status'}>
              <span className="status-dot" aria-hidden="true" />
              {state.data.alarm.active
                ? t('alarm')
                : state.data.powered
                  ? t('operational')
                  : t('stopped')}
            </div>
          )}
          <button
            className="icon-button"
            onClick={() => setConfigOpen(true)}
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

