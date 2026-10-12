import { Card } from "@/components/ui/card";
import { Activity, Footprints, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

function MiniMetric({ label, value, unit, note, color, icon: Icon }) {
  return (
    <div className={styles.metricTile}>
      <div className={styles.metricLabel}>{Icon && <Icon size={14} aria-hidden="true" />}<span>{label}</span></div>
      <div className={cn(styles.metricValue, styles[color])}>{value}<small>{unit}</small></div>
      <p className={styles.metricNote}>{note}</p>
    </div>
  );
}

export default function LiveVariablesCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.variablesPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Live variables</p>
        <span className={styles.updates}>updates every 5 min</span>
      </div>
      <div className={styles.currentGlucose}>
        <div className={styles.glucoseHeading}><span>Current glucose</span><strong>↑ +2.1 mg/dL/min</strong></div>
        <div className={styles.glucoseReading}>
          <div><strong>168</strong><span> mg/dL</span></div>
          <svg className={styles.sparkline} viewBox="0 0 120 32" role="img" aria-label="Glucose trend rising">
            <polyline points="2,24 20,19 35,22 51,15 68,8 84,10 99,4 118,1" />
          </svg>
        </div>
      </div>
      <div className={styles.metricGrid}>
        <MiniMetric label="Heart rate" value="82" unit=" bpm" note="resting avg 68" color="pink" icon={Activity} />
        <MiniMetric label="HRV" value="34" unit=" ms" note="7-day avg 41" color="purple" />
        <MiniMetric label="Steps today" value="3,120" unit="" note="goal 8,000" color="green" icon={Footprints} />
        <MiniMetric label="Sleep, last night" value="6h 12m" unit="" note="score 71 · 84% efficient" color="purple" icon={Moon} />
      </div>
    </Card>
  );
}
