import { Card } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const num = (v, digits = 0) => (Number.isFinite(v) ? v.toFixed(digits) : "Not provided");

export default function PatientProfileCard({ className, patientId = "", profile, modelFolder }) {
  const p = profile || {};
  const initials = patientId ? patientId.slice(0, 2).toUpperCase() : "—";
  const sex = Number.isFinite(p.sex_male) ? (p.sex_male === 1 ? "Male" : "Female") : "Not provided";

  return (
    <Card className={cn(styles.panel, styles.profilePanel, className)}>
      <p className={styles.eyebrow}>Patient profile</p>
      <div className={styles.patientHeading}>
        <Avatar className={styles.patientAvatar}><AvatarFallback>{initials}</AvatarFallback></Avatar>
        <div>
          <h2 className={styles.patientName}>{patientId || "No patient selected"}</h2>
          <p className={styles.patientId}>Patient ID</p>
        </div>
      </div>
      <div className={styles.demographics}>
        <div className={styles.detailTile}><span>Age</span><strong>{num(p.age)}</strong></div>
        <div className={styles.detailTile}><span>Sex</span><strong>{sex}</strong></div>
        <div className={styles.detailTile}><span>BMI</span><strong>{num(p.bmi, 1)}</strong></div>
        <div className={styles.detailTile}><span>Model</span><strong>{modelFolder || "Not provided"}</strong></div>
      </div>
      <p className={styles.dataNote}>
        Only fields supplied by the backend are shown. Conditions and medications are not available from its API.
        The model folder is the cross-validation fold that excluded this participant, so the replay is out-of-sample.
      </p>
    </Card>
  );
}