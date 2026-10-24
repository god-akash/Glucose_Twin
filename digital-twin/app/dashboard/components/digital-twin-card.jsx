import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { getRiskStates } from "@/lib/api/dashboard";
import DashboardHuman from "./dashboard-human";
import styles from "../dashboard.module.css";

const STATUS_TEXT = { ok: "OK", watch: "Watch", alert: "Alert", in_event: "In event", unavailable: "Unavailable" };

function reach(minutes) {
  if (minutes == null) return "not within 6 h";
  if (minutes <= 30) return "within 30 min";
  return `about ${minutes} min`;
}

export default function DigitalTwinCard({ className, tasks }) {
  const states = getRiskStates(tasks);

  return (
    <Card className={cn(styles.panel, styles.twinPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Model risk by event</p>
        <span className={styles.updates}>FastAPI predictions</span>
      </div>
      <div className={styles.twinContent}>
        <div className={styles.bodyFigure} role="img" aria-label="Interactive 3D digital twin anatomy">
          <DashboardHuman />
        </div>
        <div className={styles.stateList}>
          {states.length === 0 && <p className={styles.noData}>No prediction results are available.</p>}
          {states.map((item) => (
            <div className={styles.stateItem} key={item.name}>
              <div className={styles.stateLabel}>
                <span>{item.title}</span>
                <span className={styles[item.color]}>
                  {item.value == null
                    ? STATUS_TEXT[item.status] || item.status
                    : `${STATUS_TEXT[item.status] || item.status} · ${Math.round(item.value)}% · ${item.horizon} min`}
                </span>
              </div>
              {item.value != null && (
                <Progress value={item.value} aria-label={`${item.title} risk`} className={cn(styles.meter, styles[item.color + "Meter"])} />
              )}
              {item.value != null && item.hasReach && (
                <span style={{ fontSize: 12, opacity: 0.7 }}>
                  30% chance {reach(item.reach30)} · 50% chance {reach(item.reach50)}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
      <p className={styles.dataNote}>
        Probabilities use the 120 minute model. Times are approximate and interpolated between horizons. Not a diagnosis.
      </p>
    </Card>
  );
}