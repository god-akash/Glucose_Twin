import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getGlucoseChange } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function buildSparkline(history) {
  const readings = history
    .filter((reading) => Number.isFinite(reading.glucose))
    .slice(-8);
  if (readings.length < 2) return "";

  const values = readings.map((reading) => reading.glucose);
  const min = Math.min(...values);
  const range = Math.max(Math.max(...values) - min, 1);
  return readings.map((reading, index) => {
    const x = (index / (readings.length - 1)) * 116 + 2;
    const y = 28 - ((reading.glucose - min) / range) * 26;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function formatChange(change) {
  if (!change) return "Awaiting another reading";
  const arrow = change.change > 0 ? "↑" : change.change < 0 ? "↓" : "→";
  const sign = change.change > 0 ? "+" : "";
  return `${arrow} ${sign}${change.change.toFixed(1)} mg/dL since prior reading`;
}

export default function LiveVariablesCard({ className, latest, history }) {
  const currentGlucose = Number.isFinite(latest.glucose) ? latest.glucose : null;
  const change = getGlucoseChange(history);
  const sparkline = buildSparkline(history);
  const status = latest.predicted ? "Prediction ready" : latest.warming_up ? "Building history" : "Prediction unavailable";

  return (
    <Card className={cn(styles.panel, styles.variablesPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Latest glucose reading</p>
        <span className={styles.updates}>{status}</span>
      </div>
      <div className={styles.currentGlucose}>
        <div className={styles.glucoseHeading}><span>Measured value</span><strong>{formatChange(change)}</strong></div>
        <div className={styles.glucoseReading}>
          <div>
            <strong>{currentGlucose == null ? "—" : currentGlucose.toFixed(1)}</strong>
            <span> mg/dL</span>
          </div>
          {sparkline && (
            <svg className={styles.sparkline} viewBox="0 0 120 32" role="img" aria-label="Recent measured glucose readings">
              <polyline points={sparkline} />
            </svg>
          )}
        </div>
      </div>
      <div className={styles.metricGrid}>
        <div className={styles.metricTile}>
          <div className={styles.metricLabel}>Change rate</div>
          <div className={cn(styles.metricValue, styles.amber)}>{change ? `${change.perMinute > 0 ? "+" : ""}${change.perMinute.toFixed(2)}` : "—"}<small> mg/dL/min</small></div>
          <p className={styles.metricNote}>Calculated from the two latest readings</p>
        </div>
        <div className={styles.metricTile}>
          <div className={styles.metricLabel}>Readings loaded</div>
          <div className={styles.metricValue}>{history.length}</div>
          <p className={styles.metricNote}>Most recent history returned by the API</p>
        </div>
      </div>
      <p className={styles.dataNote}>Heart rate, activity, HRV, and sleep are not included in the dashboard API response.</p>
    </Card>
  );
}
