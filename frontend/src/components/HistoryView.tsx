import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import { DailyEnergy, HistoryPoint, YearlyEnergy, getJson } from '../api';
import { EChart } from './EChart';
import { Language, languageLocales, translate } from '../i18n';

function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function currentMonth(): string {
  return todayIso().slice(0, 7);
}

export function HistoryView({ language }: { language: Language }) {
  const t = (key: string) => translate(language, key);
  const monthLabels = useMemo(
    () =>
      Array.from({ length: 12 }, (_, month) =>
        new Intl.DateTimeFormat(languageLocales[language], { month: 'short' }).format(
          new Date(2020, month, 1),
        ),
      ),
    [language],
  );
  const [day, setDay] = useState(todayIso);
  const [month, setMonth] = useState(currentMonth);
  const [year, setYear] = useState(() => new Date().getFullYear());
  const daily = useQuery({
    queryKey: ['history-day', day],
    queryFn: () => getJson<HistoryPoint[]>(`/api/history/daily?day=${day}`),
  });
  const monthly = useQuery({
    queryKey: ['history-month', month],
    queryFn: () => {
      const [year, monthNumber] = month.split('-').map(Number);
      return getJson<{ days: DailyEnergy[] }>(
        `/api/history/month?year=${year}&month=${monthNumber}`,
      );
    },
  });
  const yearly = useQuery({
    queryKey: ['history-year', year],
    queryFn: () => getJson<YearlyEnergy>(`/api/history/year?year=${year}`),
  });

  const dailyOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: ['#18864b', '#dd4f3e', '#337dcc'],
      legend: {
        type: 'plain',
        bottom: 0,
        left: 0,
        right: 0,
        itemWidth: 18,
        itemHeight: 10,
        itemGap: 12,
        textStyle: { fontSize: 12 },
      },
      tooltip: {
        trigger: 'axis',
        confine: true,
        extraCssText: 'max-width: min(320px, calc(100vw - 32px)); white-space: normal;',
      },
      grid: { left: 46, right: 22, top: 24, bottom: 90 },
      xAxis: {
        type: 'category',
        data: daily.data?.map((point) => point.recorded_at.slice(11, 16)) ?? [],
      },
      yAxis: { type: 'value', name: 'kW' },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 22, bottom: 34 }],
      series: [
        {
          type: 'line',
          name: t('electric'),
          data: daily.data?.map((point) => point.electric_power_kw) ?? [],
          showSymbol: false,
        },
        {
          type: 'line',
          name: t('heat'),
          data: daily.data?.map((point) => point.heating_power_kw) ?? [],
          showSymbol: false,
        },
        {
          type: 'line',
          name: t('coolingShort'),
          data: daily.data?.map((point) => point.cooling_power_kw) ?? [],
          showSymbol: false,
        },
      ],
    }),
    [daily.data, language],
  );

  const monthlyOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: ['#18864b', '#dd4f3e', '#337dcc'],
      legend: {
        type: 'plain',
        bottom: 0,
        left: 0,
        right: 0,
        itemWidth: 18,
        itemHeight: 10,
        itemGap: 12,
        textStyle: { fontSize: 12 },
      },
      tooltip: {
        trigger: 'axis',
        confine: true,
        extraCssText: 'max-width: min(320px, calc(100vw - 32px)); white-space: normal;',
      },
      grid: { left: 48, right: 20, top: 24, bottom: 90 },
      xAxis: {
        type: 'category',
        data: monthly.data?.days.map((item) => item.day.slice(-2)) ?? [],
      },
      yAxis: { type: 'value', name: 'kWh' },
      series: [
        {
          type: 'bar',
          name: t('electric'),
          data: monthly.data?.days.map((item) => item.electric_kwh) ?? [],
        },
        {
          type: 'bar',
          name: t('heat'),
          data: monthly.data?.days.map((item) => item.heating_kwh) ?? [],
        },
        {
          type: 'bar',
          name: t('coolingShort'),
          data: monthly.data?.days.map((item) => item.cooling_kwh) ?? [],
        },
      ],
    }),
    [monthly.data, language],
  );

  const yearlyOption = useMemo<EChartsOption>(
    () => ({
      animation: false,
      color: [
        '#dd4f3e',
        '#f29b21',
        '#e1cc24',
        '#337dcc',
        '#82b9e7',
        '#18864b',
        '#8bd1ae',
        '#7357a5',
        '#a89bc7',
      ],
      legend: {
        type: 'plain',
        bottom: 0,
        left: 0,
        right: 0,
        itemWidth: 18,
        itemHeight: 10,
        itemGap: 12,
        textStyle: { fontSize: 11 },
      },
      tooltip: {
        trigger: 'axis',
        confine: true,
        extraCssText: 'max-width: min(320px, calc(100vw - 32px)); white-space: normal;',
      },
      grid: { left: 52, right: 45, top: 24, bottom: 132 },
      xAxis: {
        type: 'category',
        data: monthLabels,
      },
      yAxis: [
        { type: 'value', name: 'kWh' },
        { type: 'value', name: 'SPF', min: 0, splitLine: { show: false } },
      ],
      series: [
        {
          type: 'bar',
          stack: 'production',
          name: t('dhw'),
          data: yearly.data?.months.map((item) => item.dhw_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'production',
          name: t('heating'),
          data: yearly.data?.months.map((item) => item.heating_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'production',
          name: t('pool'),
          data: yearly.data?.months.map((item) => item.pool_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'production',
          name: t('coolingShort'),
          data: yearly.data?.months.map((item) => item.cooling_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'production',
          name: t('passiveCooling'),
          data: yearly.data?.months.map((item) => item.passive_cooling_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'consumption',
          name: t('electric'),
          data: yearly.data?.months.map((item) => item.electric_kwh) ?? [],
        },
        {
          type: 'bar',
          stack: 'consumption',
          name: t('auxiliary'),
          data: yearly.data?.months.map((item) => item.electric_auxiliary_kwh) ?? [],
        },
        {
          type: 'line',
          yAxisIndex: 1,
          name: 'SPF',
          data: yearly.data?.months.map((item) => item.spf) ?? [],
          showSymbol: false,
        },
        {
          type: 'line',
          yAxisIndex: 1,
          name: 'SPFG',
          data: yearly.data?.months.map((item) => item.spfg) ?? [],
          showSymbol: false,
        },
      ],
    }),
    [yearly.data, language, monthLabels],
  );

  return (
    <div className="history">
      <section className="chart-card">
        <div className="section-heading">
          <div>
            <h2>{t('dayPowers')}</h2>
          </div>
          <label>
            {t('day')}
            <input type="date" value={day} max={todayIso()} onChange={(event) => setDay(event.target.value)} />
          </label>
        </div>
        {daily.isError ? (
          <p>{t('dailyError')}</p>
        ) : daily.data?.length === 0 ? (
          <p>{t('noDailyData')}</p>
        ) : (
          <EChart option={dailyOption} height={360} />
        )}
      </section>

      <section className="chart-card">
        <div className="section-heading">
          <div>
            <h2>{t('monthProduction')}</h2>
          </div>
          <label>
            {t('month')}
            <input type="month" value={month} max={currentMonth()} onChange={(event) => setMonth(event.target.value)} />
          </label>
        </div>
        {monthly.isError ? (
          <p>{t('monthlyError')}</p>
        ) : monthly.data?.days.length === 0 ? (
          <p>{t('noMonthlyData')}</p>
        ) : (
          <EChart option={monthlyOption} height={360} />
        )}
      </section>

      <section className="chart-card">
        <div className="section-heading">
          <div>
            <h2>{t('yearProduction')}</h2>
          </div>
          <label>
            {t('year')}
            <input
              type="number"
              min="2000"
              max={new Date().getFullYear()}
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            />
          </label>
        </div>
        {yearly.isError ? (
          <p>{t('yearlyError')}</p>
        ) : (
          <EChart option={yearlyOption} height={380} />
        )}
      </section>
    </div>
  );
}

