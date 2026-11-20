import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import { CurrentState, HistoryPoint, getJson } from '../api';
import { Language, languageLocales, translate } from '../i18n';
import { convertTemperature, TemperatureUnit } from '../units';
import { EChart } from './EChart';
import { LocalizedDateInput } from './LocalizedDateInput';

function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function TemperatureView({
  language,
  temperatureUnit,
  state,
}: {
  language: Language;
  temperatureUnit: TemperatureUnit;
  state: CurrentState | undefined;
}) {
  const t = (key: string) => translate(language, key);
  const unit = temperatureUnit === 'f' ? '°F' : '°C';
  const convert = (value: number | null | undefined) =>
    value == null ? null : convertTemperature(value, temperatureUnit);
  const format = (value: number | null | undefined) =>
    value == null
      ? '—'
      : new Intl.NumberFormat(languageLocales[language], {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        }).format(convert(value) ?? 0);
  const [day, setDay] = useState(todayIso);
  const history = useQuery({
    queryKey: ['temperature-history', day],
    queryFn: () => getJson<HistoryPoint[]>(`/api/history/daily?day=${day}`),
  });

  const sensors = state
    ? [
        { label: t('outdoor'), value: state.temperatures.outdoor },
        { label: t('dhw'), value: state.temperatures.dhw },
        { label: t('heatingSupply'), value: state.temperatures.heating_supply },
        { label: t('heatingReturn'), value: state.temperatures.heating_return },
        { label: t('brineSupply'), value: state.temperatures.brine_supply },
        { label: t('brineReturn'), value: state.temperatures.brine_return },
      ].filter(({ value }) => value > -999)
    : [];
  const option = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [
        '#159447',
        '#d84b3e',
        '#b02be0',
        '#cb6cb7',
        '#176eaa',
        '#62a6d3',
        '#f39c12',
        '#e6c229',
        '#6f42c1',
        '#d63384',
        '#20c997',
      ],
      legend: {
        type: 'plain',
        bottom: 0,
        left: 0,
        right: 0,
        itemWidth: 18,
        itemHeight: 10,
        textStyle: { fontSize: 11 },
      },
      tooltip: {
        trigger: 'axis',
        confine: true,
        extraCssText: 'max-width: min(320px, calc(100vw - 32px)); white-space: normal;',
      },
      grid: { left: 46, right: 18, top: 24, bottom: 105 },
      xAxis: {
        type: 'category',
        data: history.data?.map((point) => point.recorded_at.slice(11, 16)) ?? [],
      },
      yAxis: { type: 'value', name: unit },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 22, bottom: 55 }],
      series: [
        {
          name: t('outdoor'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.outdoor_temperature)) ?? [],
        },
        {
          name: t('dhw'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.dhw_temperature)) ?? [],
        },
        {
          name: t('heatingSupply'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.heating_supply_temperature)) ?? [],
        },
        {
          name: t('heatingReturn'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.heating_return_temperature)) ?? [],
        },
        {
          name: t('brineSupply'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.brine_supply_temperature)) ?? [],
        },
        {
          name: t('brineReturn'),
          type: 'line',
          showSymbol: false,
          connectNulls: false,
          data: history.data?.map((point) => convert(point.brine_return_temperature)) ?? [],
        },
        ...Array.from({ length: 5 }, (_, index) => {
          const data =
            history.data?.map((point) => convert(point.group_temperatures[index] ?? null)) ?? [];
          return {
            name: `${t('group')} ${index + 1}`,
            type: 'line' as const,
            showSymbol: false,
            connectNulls: false,
            data,
          };
        }).filter(({ data }) => data.some((value) => value != null && value !== 0)),
      ],
    }),
    [history.data, language, temperatureUnit],
  );

  return (
    <div className="temperature-view">
      <section className="temperature-summary" aria-label={t('temperatures')}>
        {sensors.map(({ label, value }) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{format(value)} <small>{unit}</small></strong>
          </div>
        ))}
      </section>

      <section className="chart-card">
        <div className="section-heading">
          <div>
            <h2>{t('temperatureEvolution')}</h2>
          </div>
          <LocalizedDateInput
            label={t('day')}
            value={day}
            max={todayIso()}
            language={language}
            onChange={setDay}
          />
        </div>
        {history.isError ? (
          <p>{t('dailyError')}</p>
        ) : history.data?.length === 0 ? (
          <p>{t('noDailyData')}</p>
        ) : (
          <EChart option={option} height={420} />
        )}
      </section>
    </div>
  );
}
