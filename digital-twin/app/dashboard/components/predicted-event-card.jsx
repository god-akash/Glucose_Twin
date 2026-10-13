import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getPrimaryRisk, formatTaskTitle } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

export default function PredictedEventCard({ className, tasks, modelFolder }) {
  const primary = getPrimaryRisk(tasks);
  const riskPercent = primary?.risk.probability == null
    ? null
    : Math.round(primary.risk.probability * 100);

  return (
    <Card className={cn(styles.panel, styles.predictionPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Highest current model risk</p>
        {primary && <Badge className={cn(styles.tag, styles.warningTag)}>{primary.risk.inEvent ? "In event" : primary.task.level || primary.task.status}</Badge>}
      </div>
      {primary ? (
        <>
          <h2 className={styles.eventTitle}>{formatTaskTitle(primary.name, primary.task)}</h2>
          <div className={styles.riskRow}>
            <strong className={styles.riskValue}>{riskPercent == null ? "—" : `${riskPercent}%`}</strong>
            <span>{primary.risk.inEvent ? "Model reports the threshold event is in progress." : `Model probability within ${primary.risk.horizon} minutes.`}</span>
          </div>
          <div className={styles.predictionStats}>
            <div className={styles.detailTile}>
              <span>Event threshold</span>
              <strong>{primary.task.threshold ?? "Not provided"}{primary.task.threshold != null ? " mg/dL" : ""}</strong>
            </div>
            <div className={styles.detailTile}>
              <span>Risk classification</span>
              <strong>{primary.risk.inEvent ? "In event" : primary.task.level || "Unavailable"}</strong>
            </div>
          </div>
          <p className={styles.modelFootnote}>Model {modelFolder || "not specified"} · estimate from the latest server response.</p>
        </>
      ) : (
        <p className={styles.noData}>The backend has not returned a usable prediction for this patient.</p>
      )}
    </Card>
  );
}
