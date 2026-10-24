import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getGlucoseChange, getTrendLabel } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function buildSparkline(history) {
  const readings = history.filter((r) => Number.isFinite(r.glucose)).slice(-8);
  if (readings.length < 2) return "";
  const values = readings.map((r) => r.glucose);
  const min = Math.min(...values);
  const range = Math.max(Math.max(...values) - min, 1);
  return readings.map((r, i) => {
    const x = (i / (readings.length - 1)) * 116 + 2;
    const y = 28 - ((r.glucose - min) / range) * 26;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function formatChange(change) {
  if (!change) return "Awaiting another reading";
  const arrow = change.change > 0 ? "↑" : change.change < 0 ? "↓" : "→";
  const sign = change.change > 0 ? "+" : "";
  return `${arrow} ${sign}${change.change.toFixed(1)} mg/dL since prior reading`;
}

function activityLabel(level) {
  if (level == null) return "No activity data";
  if (level < 0.5) return "Mostly resting";
  if (level < 1.5) return "Light to moderate";
  return "Vigorous";
}

export default function LiveVariablesCard({ className, latest = {}, history = [] }) {
  const currentGlucose = Number.isFinite(latest?.glucose) ? latest.glucose : null;
  const change = getGlucoseChange(history);
  const sparkline = buildSparkline(history);
  const status = latest?.predicted ? "Prediction ready" : latest?.warming_up ? "Building history" : "Prediction unavailable";
  const hr = latest?.signals?.hr_bpm;
  const act = latest?.signals?.activity_level;

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
          <div className={styles.metricLabel}>Glucose trend</div>
          <div className={cn(styles.metricValue, styles.amber)}>{getTrendLabel(change?.perMinute)}</div>
          <p className={styles.metricNote}>
            {change ? `${change.perMinute > 0 ? "+" : ""}${change.perMinute.toFixed(2)} mg/dL/min between the two latest readings` : "Needs two readings"}
          </p>
        </div>
        <div className={styles.metricTile}>
          <div className={styles.metricLabel}>Heart rate</div>
          <div className={styles.metricValue}>{hr ?? "—"}<small> bpm</small></div>
          <p className={styles.metricNote}>{activityLabel(act)} · average of the last 15 minutes</p>
        </div>
      </div>
      <p className={styles.dataNote}>Heart rate and activity come from the wearable stream. HRV, sleep and steps are not in this dataset.</p>
    </Card>
  );
}