import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const states = [
  { label: "Glycaemic control", value: 72, status: "Rising", color: "amber" },
  { label: "Insulin sensitivity", value: 44, status: "Reduced", color: "amber" },
  { label: "Autonomic balance", value: 48, status: "Lower", color: "purple" },
  { label: "Recovery", value: 70, status: "Fair", color: "green" },
];

export default function DigitalTwinCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.twinPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Digital twin state</p>
        <Badge className={cn(styles.tag, styles.warningTag)}>Elevated</Badge>
      </div>
      <div className={styles.twinContent}>
        <div className={styles.bodyFigure} role="img" aria-label="Illustration of the patient's digital twin">
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
          {states.map((item) => (
            <div className={styles.stateItem} key={item.label}>
              <div className={styles.stateLabel}><span>{item.label}</span><span className={styles[item.color]}>{item.status}</span></div>
              <Progress value={item.value} className={cn(styles.meter, styles[item.color + "Meter"])} />
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
