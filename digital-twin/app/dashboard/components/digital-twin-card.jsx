import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { getRiskStates } from "@/lib/api/dashboard";
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
        <div className={styles.bodyFigure} role="img" aria-label="Illustrative body model; risk values are supplied by the prediction API">
          <svg viewBox="0 0 110 250" aria-hidden="true">
            <ellipse className={styles.figureHead} cx="55" cy="20" rx="12" ry="12" />
            <path className={styles.figureBody} d="M35 43 Q55 37 75 43 L83 100 Q55 111 27 100 Z" />
            <path className={styles.figureLimb} d="M35 47 L20 99 L15 145 M75 47 L90 99 L95 145 M42 104 L39 183 L37 225 M68 104 L71 183 L73 225" />
            <circle className={styles.figurePulse} cx="62" cy="65" r="6" />
            <ellipse className={styles.figureGlow} cx="55" cy="91" rx="11" ry="5" />
            <ellipse className={styles.figureBase} cx="55" cy="226" rx="38" ry="4" />
          </svg>
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
