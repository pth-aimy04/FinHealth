import { useEffect, useRef, type ReactElement } from "react";
import {
  init,
  use as registerCharts,
  type EChartsCoreOption,
} from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  MarkLineComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { TableRegion } from "../shared";
registerCharts([
  BarChart,
  LineChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  MarkLineComponent,
  SVGRenderer,
]);
/** Shared ECharts lifecycle with semantic theme tokens and an accessible table alternative. */
export function Chart({
  option,
  summary,
  columns,
  rows,
  onPoint,
}: {
  option: EChartsCoreOption;
  summary: string;
  columns: string[];
  rows: (string | number | null)[][];
  onPoint?: (index: number) => void;
}): ReactElement {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const element = ref.current;
    let chart: ReturnType<typeof init> | undefined;
    const draw = (): void => {
      chart?.dispose();
      const css = getComputedStyle(document.documentElement);
      const color = (token: string): string =>
        css.getPropertyValue(token).trim();
      const axisTheme = {
        axisLabel: { color: color("--muted") },
        nameTextStyle: { color: color("--muted") },
        axisLine: { lineStyle: { color: color("--border") } },
        splitLine: { lineStyle: { color: color("--border") } },
      };
      chart = init(
        element,
        {
          categoryAxis: axisTheme,
          valueAxis: axisTheme,
          bar: { label: { color: color("--foreground"), textBorderWidth: 0 } },
          line: { label: { color: color("--foreground"), textBorderWidth: 0 } },
        },
        { renderer: "svg" },
      );
      chart.setOption({
        color: [1, 2, 3, 4, 5].map((n) => color(`--chart-${n}`)),
        textStyle: {
          fontFamily: "Be Vietnam Pro, sans-serif",
          color: color("--muted"),
        },
        animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
        animationDuration: 200,
        grid: { left: 58, right: 24, top: 40, bottom: 48 },
        tooltip: {
          trigger: "axis",
          renderMode: "html",
          backgroundColor: color("--surface"),
          borderColor: color("--border"),
          textStyle: { color: color("--foreground") },
        },
        legend: {
          top: 5,
          textStyle: { color: color("--muted") },
          type: "scroll",
        },
        aria: { enabled: true, description: summary },
        ...option,
      });
      chart.on("click", (params) => {
        const data: unknown = params.data;
        if (
          data &&
          typeof data === "object" &&
          "sourceIndex" in data &&
          typeof data.sourceIndex === "number"
        )
          onPoint?.(data.sourceIndex);
        else if (typeof params.dataIndex === "number")
          onPoint?.(params.dataIndex);
      });
    };
    draw();
    const resize = new ResizeObserver(() => chart?.resize());
    resize.observe(element);
    const observer = new MutationObserver(draw);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => {
      resize.disconnect();
      observer.disconnect();
      chart?.dispose();
    };
  }, [option, summary, onPoint]);
  return (
    <figure>
      <div className="chart" ref={ref} role="img" aria-label={summary} />
      <figcaption className="chart-legend">{summary}</figcaption>
      <details className="chart-data">
        <summary>Dữ liệu biểu đồ · bảng thay thế</summary>
        <TableRegion name={summary}>
          <table>
            <thead>
              <tr>
                {columns.map((column, i) => (
                  <th key={i}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {row.map((value, j) => (
                    <td key={j}>{value ?? "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </TableRegion>
      </details>
    </figure>
  );
}
