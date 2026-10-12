import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const alerts = [
  { title: "Spike risk crossed 60%", detail: "Today 14:18 · now 78%", color: "amber", current: true },
  { title: "Post-meal rise detected", detail: "Today 13:42 · +2.4 mg/dL/min", color: "teal" },
  { title: "Low-glucose risk cleared", detail: "Today 09:40 · below 10%", color: "green" },
  { title: "Night-time low risk 38%", detail: "Yesterday 23:10 · resolved by 00:05", color: "mutedDot" },
];

export default function AlertTimelineCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.timelinePanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Alert timeline</p>
        <span className={styles.updates}>spike ≥ 60% · low ≥ 30%</span>
      </div>
      <ol className={styles.alertList}>
        {alerts.map((alert) => (
          <li className={styles.alertItem} key={alert.title}>
            <span className={cn(styles.alertDot, styles[alert.color], alert.current && styles.currentAlert)} />
            <div><strong>{alert.title}</strong><span>{alert.detail}</span></div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
