import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const profileFields = [
  ["HbA1c", "hba1c"],
  ["Fasting glucose", "fasting_glucose"],
  ["Insulin", "insulin"],
  ["HOMA-IR", "homa_ir"],
];

export default function HistoricalLabsCard({ className, profile }) {
  const availableFields = profileFields.filter(([, key]) => Number.isFinite(profile[key]));

  return (
    <Card className={cn(styles.panel, styles.labsPanel, className)}>
      <p className={styles.eyebrow}>Available baseline inputs</p>
      {availableFields.length > 0 ? (
        <div className={styles.labRows}>
          {availableFields.map(([label, key]) => (
            <div className={styles.labRow} key={key}>
              <span>{label}</span>
              <strong>{profile[key]}</strong>
              <span>Profile</span>
            </div>
          ))}
        </div>
      ) : (
        <p className={styles.noData}>No lab or baseline values were supplied in the patient profile.</p>
      )}
      <p className={styles.dataNote}>The API provides profile inputs only; it does not return historical lab results or trends.</p>
    </Card>
  );
}
