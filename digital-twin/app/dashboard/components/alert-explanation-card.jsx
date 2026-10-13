import { Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getPrimaryRisk, formatTaskTitle } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

export default function AlertExplanationCard({ className, tasks }) {
  const primary = getPrimaryRisk(tasks);
  const riskPercent = primary?.risk.probability == null
    ? null
    : Math.round(primary.risk.probability * 100);

  return (
    <Card className={cn(styles.panel, styles.explanationPanel, className)}>
      <div className={styles.explanationHeader}>
        <div className={styles.explanationHeading}>
          <span className={styles.explanationIcon}><Sparkles size={17} aria-hidden="true" /></span>
          <div>
            <p className={styles.eyebrow}>Prediction details</p>
            <h2 className={styles.explanationTitle}>What the model returned</h2>
          </div>
        </div>
        <span className={styles.explanationTag}>No generated explanation endpoint</span>
      </div>
      <div className={styles.explanationBody}>
        <div className={styles.explanationSummary}>
          {primary ? (
            <p>
              The highest available event risk is {riskPercent == null ? "currently in progress" : `${riskPercent}% within ${primary.risk.horizon} minutes`} for {formatTaskTitle(primary.name, primary.task)}.
              {" "}This is the model output only; the API does not return contributing factors or a clinical explanation.
            </p>
          ) : (
            <p>No usable risk prediction is available. The API does not provide generated explanations or contributing factors.</p>
          )}
          <span className={styles.explanationDisclaimer}>Model estimates are not a diagnosis and should not replace clinical judgment.</span>
        </div>
        <div className={styles.factorGrid} aria-label="Prediction data availability">
          <div className={styles.factorTile}><span>Risk probabilities</span><strong>{primary ? "Provided by the model API" : "Not available"}</strong></div>
          <div className={styles.factorTile}><span>Contributing factors</span><strong>Not provided by the API</strong></div>
          <div className={styles.factorTile}><span>AI explanation</span><strong>Not provided by the API</strong></div>
        </div>
      </div>
    </Card>
  );
}
