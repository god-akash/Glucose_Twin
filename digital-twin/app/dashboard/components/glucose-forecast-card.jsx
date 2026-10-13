import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { buildGlucoseChart } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function GlucoseForecastCard({ className, history }) {
  const chart = buildGlucoseChart(history);

  return (
    <Card className={cn(styles.panel, styles.forecastPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Measured glucose history · latest 24 readings</p>
        {chart && <span className={styles.updates}>{chart.min}–{chart.max} mg/dL</span>}
      </div>
      {chart ? (
        <svg className={styles.historyChart} viewBox="0 0 680 180" preserveAspectRatio="none" role="img" aria-label="Measured glucose history">
          <line className={styles.gridLine} x1="32" y1="30" x2="660" y2="30" />
          <line className={styles.gridLine} x1="32" y1="90" x2="660" y2="90" />
          <line className={styles.gridLine} x1="32" y1="150" x2="660" y2="150" />
          <text x="2" y="33">{chart.max}</text>
          <text x="2" y="93">{((chart.max + chart.min) / 2).toFixed(0)}</text>
          <text x="2" y="153">{chart.min}</text>
          <polyline className={styles.measuredLine} points={chart.polyline} transform="translate(32 30) scale(1 .92)" />
          {chart.points.map(({ x, y, reading }) => (
            <circle key={reading.timestamp} className={styles.chartPoint} cx={32 + x} cy={30 + y * 0.92} r="3" />
          ))}
          <text x="32" y="176">{formatTime(chart.firstTimestamp)}</text>
          <text x="600" y="176">{formatTime(chart.lastTimestamp)}</text>
        </svg>
      ) : (
        <p className={styles.noData}>No measured glucose history is available for this patient.</p>
      )}
      <p className={styles.dataNote}>The FastAPI model returns event risks, not predicted glucose values; no forecast curve is shown.</p>
    </Card>
  );
}
