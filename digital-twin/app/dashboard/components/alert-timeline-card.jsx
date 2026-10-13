import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getAlertTimeline } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString();
}

export default function AlertTimelineCard({ className, history }) {
  const alerts = getAlertTimeline(history);

  return (
    <Card className={cn(styles.panel, styles.timelinePanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Prediction history</p>
        <span className={styles.updates}>Model risk transitions</span>
      </div>
      {alerts.length > 0 ? (
        <ol className={styles.alertList}>
          {alerts.map((alert) => (
            <li className={styles.alertItem} key={alert.key}>
              <span className={cn(styles.alertDot, styles[alert.color], alert.current && styles.currentAlert)} />
              <div>
                <strong>{alert.title}</strong>
                <span>{alert.detail}</span>
                <span>{formatTimestamp(alert.timestamp)}</span>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className={styles.noData}>No model risk transitions are available in the loaded history.</p>
      )}
      <p className={styles.dataNote}>Transitions are derived from stored prediction results; the backend has no separate alert-events endpoint.</p>
    </Card>
  );
}
