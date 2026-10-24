import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getPrimaryRisk, formatTaskTitle, getTimeToRisk } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function formatReach(minutes) {
  if (minutes == null) return "Not within 6 h";
  if (minutes <= 30) return "Within 30 min";
  return `About ${minutes} min`;
}

export default function PredictedEventCard({ className, tasks, modelFolder }) {
  const primary = getPrimaryRisk(tasks);
  const riskPercent = primary?.risk.probability == null ? null : Math.round(primary.risk.probability * 100);
  const reach = getTimeToRisk(primary?.task);
  const at = (pct) => reach.find((r) => r.pct === pct)?.minutes;

  return (
    <Card className={cn(styles.panel, styles.predictionPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Highest current model risk</p>
        {primary && (
          <Badge className={cn(styles.tag, styles.warningTag)}>
            {primary.risk.inEvent ? "In event" : primary.task.level || primary.task.status}
          </Badge>
        )}
      </div>
      {primary ? (
        <>
          <h2 className={styles.eventTitle}>{formatTaskTitle(primary.name, primary.task)}</h2>
          <div className={styles.riskRow}>
            <strong className={styles.riskValue}>{riskPercent == null ? "—" : `${riskPercent}%`}</strong>
            <span>
              {primary.risk.inEvent
                ? "Glucose is already past this threshold, so no forecast is shown."
                : `Chance of crossing within ${primary.risk.horizon} minutes.`}
            </span>
          </div>
          <div className={styles.predictionStats}>
            <div className={styles.detailTile}>
              <span>Event threshold</span>
              <strong>{primary.task.threshold != null ? `${primary.task.threshold} mg/dL` : "Not provided"}</strong>
            </div>
            <div className={styles.detailTile}>
              <span>Risk classification</span>
              <strong>{primary.risk.inEvent ? "In event" : primary.task.level || "Unavailable"}</strong>
            </div>
            {!primary.risk.inEvent && (
              <>
                <div className={styles.detailTile}>
                  <span>30% chance by</span>
                  <strong>{formatReach(at(30))}</strong>
                </div>
                <div className={styles.detailTile}>
                  <span>50% chance by</span>
                  <strong>{formatReach(at(50))}</strong>
                </div>
              </>
            )}
          </div>
          <p className={styles.modelFootnote}>
            Model {modelFolder || "not specified"} · times are approximate, interpolated between the 30, 60, 90 and 120 minute models.
          </p>
        </>
      ) : (
        <p className={styles.noData}>The backend has not returned a usable prediction for this patient.</p>
      )}
    </Card>
  );
}