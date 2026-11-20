import { useEffect, useRef } from 'react';
import { init, use as registerECharts } from 'echarts/core';
import type { EChartsOption } from 'echarts';
import { BarChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

registerECharts([
  LineChart,
  BarChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

export function EChart({ option, height = 320 }: { option: EChartsOption; height?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<ReturnType<typeof init> | null>(null);

  useEffect(() => {
    if (!container.current) {
      return;
    }
    chart.current = init(container.current);
    const resize = new ResizeObserver(() => chart.current?.resize());
    resize.observe(container.current);
    chart.current.setOption(option, { notMerge: true });
    return () => {
      resize.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div className="chart" ref={container} style={{ height }} />;
}

