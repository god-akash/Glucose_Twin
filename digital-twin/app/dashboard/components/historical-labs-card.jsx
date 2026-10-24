import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const FIELDS = [
  ["HbA1c", "hba1c", "%", 1],
  ["Fasting glucose", "fasting_glucose", "mg/dL", 0],
  ["Insulin", "insulin", "", 1],
  ["HOMA-IR", "homa_ir", "", 1],
];

export default function HistoricalLabsCard({ className, profile }) {
  const p = profile || {};
  const rows = FIELDS.filter(([, key]) => Number.isFinite(p[key]));

  return (
    <Card className={cn(styles.panel, styles.labsPanel, className)}>
      <p className={styles.eyebrow}>Baseline lab values</p>
      {rows.length > 0 ? (
        <div className={styles.labRows}>
          {rows.map(([label, key, unit, digits]) => (
            <div className={styles.labRow} key={key}>
              <span>{label}</span>
              <strong>{p[key].toFixed(digits)}</strong>
              <span>{unit}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className={styles.noData}>No lab or baseline values were supplied in the patient profile.</p>
      )}
      <p className={styles.dataNote}>
        Single baseline values from the dataset, with no history or trend. Shown for clinical context; the risk models do not use them.
      </p>
    </Card>
  );
}