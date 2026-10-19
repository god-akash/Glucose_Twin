import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { getRiskStates } from "@/lib/api/dashboard";
import DashboardHuman from "./dashboard-human";
import styles from "../dashboard.module.css";

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
                <span className={styles[item.color]}>{item.value == null ? item.status : `${item.status} · ${Math.round(item.value)}% · ${item.horizon} min`}</span>
              </div>
              {item.value != null && (
                <Progress value={item.value} aria-label={`${item.title} risk`} className={cn(styles.meter, styles[item.color + "Meter"])} />
              )}
            </div>
          ))}
        </div>
      </div>
      <p className={styles.dataNote}>Probabilities use the model&apos;s available prediction horizon; they are not a diagnosis.</p>
    </Card>
  );
}
