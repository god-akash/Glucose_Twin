import { Card } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const medications = [
  ["Metformin", "1000 mg · 2×/day"],
  ["Empagliflozin", "10 mg · daily"],
  ["Insulin glargine", "18 U · nightly"],
  ["Amlodipine", "5 mg · daily"],
];

export default function PatientProfileCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.profilePanel, className)}>
      <p className={styles.eyebrow}>Patient profile</p>
      <div className={styles.patientHeading}>
        <Avatar className={styles.patientAvatar}><AvatarFallback>AK</AvatarFallback></Avatar>
        <div>
          <h2 className={styles.patientName}>A. K.</h2>
          <p className={styles.patientId}>ID DTT-00426</p>
        </div>
      </div>
      <div className={styles.demographics}>
        <div className={styles.detailTile}><span>Age · Sex</span><strong>54 · Male</strong></div>
        <div className={styles.detailTile}><span>BMI</span><strong>29.4</strong><small>Overweight</small></div>
      </div>
      <div className={styles.profileSection}>
        <p className={styles.eyebrow}>Conditions</p>
        <div className={styles.tagList}>
          <Badge className={cn(styles.tag, styles.primaryTag)}>Type 2 diabetes · 2016</Badge>
          <Badge className={styles.tag}>Hypertension</Badge>
        </div>
      </div>
      <div className={styles.profileSection}>
        <p className={styles.eyebrow}>Medications</p>
        <ul className={styles.medicationList}>
          {medications.map(([name, dosage]) => (
            <li key={name}><span>{name}</span><span>{dosage}</span></li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
