import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

export default function PredictedEventCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.predictionPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Predicted event</p>
        <Badge className={cn(styles.tag, styles.warningTag)}>Above threshold</Badge>
      </div>
      <h2 className={styles.eventTitle}>Post-meal glucose spike</h2>
      <div className={styles.riskRow}>
        <strong className={styles.riskValue}>78%</strong>
        <span>chance of exceeding 180<br />mg/dL</span>
      </div>
      <div className={styles.predictionStats}>
        <div className={styles.detailTile}><span>Time horizon</span><strong>~45 min</strong><small>window 30–65 min</small></div>
        <div className={styles.detailTile}><span>Expected peak</span><strong>214 <small>mg/dL</small></strong><small>80% range 190–238</small></div>
      </div>
      <div className={styles.confidence}>
        <div className={styles.confidenceHeading}><span>Confidence</span><strong>Medium</strong></div>
        <div className={styles.confidenceTrack}><span /></div>
      </div>
      <div className={styles.contextTags}>
        <Badge className={styles.tag}>Lunch ~62 g carbs · 13:05</Badge>
        <Badge className={styles.tag}>Sleep 6 h 12 m</Badge>
        <Badge className={styles.tag}>Low insulin on board</Badge>
      </div>
      <p className={styles.modelFootnote}>Alert threshold ≥ 60% · Model v0.3 · updated 14:20:12</p>
    </Card>
  );
}
