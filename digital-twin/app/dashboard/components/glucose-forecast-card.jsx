import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

export default function GlucoseForecastCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.forecastPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Glucose forecast · last 6 h and next 2 h</p>
        <div className={styles.chartLegend}><span><i />Measured</span><span><i />Forecast range</span></div>
      </div>
      <svg className={styles.forecastChart} viewBox="0 0 680 180" preserveAspectRatio="none" role="img" aria-label="Glucose history and forecast chart">
        <line className={styles.gridLine} x1="32" y1="28" x2="660" y2="28" />
        <line className={styles.gridLine} x1="32" y1="88" x2="660" y2="88" />
        <line className={styles.gridLine} x1="32" y1="148" x2="660" y2="148" />
        <text x="3" y="31">260</text><text x="3" y="91">180</text><text x="9" y="151">70</text>
        <path className={styles.targetArea} d="M32 88H660V148H32Z" />
        <line className={styles.thresholdLine} x1="32" y1="88" x2="660" y2="88" />
        <path className={styles.forecastBand} d="M450 91 L480 75 L510 54 L540 43 L570 47 L600 58 L630 66 L660 75 L660 110 L630 101 L600 92 L570 82 L540 73 L510 70 L480 80 L450 96Z" />
        <line className={styles.nowLine} x1="450" y1="12" x2="450" y2="158" />
        <line className={styles.peakLine} x1="540" y1="48" x2="540" y2="158" />
        <polyline className={styles.measuredLine} points="32,126 55,125 78,128 101,120 124,112 147,100 170,92 193,101 216,114 239,119 262,122 285,116 308,106 331,94 354,84 377,88 400,95 423,96 450,90" />
        <polyline className={styles.predictedLine} points="450,90 480,76 510,61 540,56 570,68 600,78 630,86 660,97" />
        <circle className={styles.currentPoint} cx="450" cy="90" r="4.5" />
        <circle className={styles.peakPoint} cx="540" cy="56" r="5" />
        <text className={styles.nowLabel} x="458" y="22">Now 168</text>
        <text className={styles.peakLabel} x="548" y="30">Predicted peak ~214 · ~15:05</text>
        <text x="32" y="176">08:20</text><text x="166" y="176">10:20</text><text x="300" y="176">12:20</text><text className={styles.nowLabel} x="438" y="176">14:20</text><text x="560" y="176">+1h</text><text x="650" y="176">+2h</text>
      </svg>
    </Card>
  );
}
