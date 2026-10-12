"use client";

import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import styles from "../dashboard.module.css";

const results = {
  HbA1c: [["Sep 2026", "7.9 %", "+0.2"], ["Jun 2026", "7.7 %", "−0.4"], ["Mar 2026", "8.1 %", "−0.1"], ["Dec 2025", "8.2 %", "baseline"]],
  Lipids: [["Sep 2026", "LDL 98", "−8"], ["Jun 2026", "LDL 106", "−4"], ["Mar 2026", "LDL 110", "+2"], ["Dec 2025", "LDL 108", "baseline"]],
  Renal: [["Sep 2026", "eGFR 82", "+2"], ["Jun 2026", "eGFR 80", "−1"], ["Mar 2026", "eGFR 81", "+1"], ["Dec 2025", "eGFR 80", "baseline"]],
  Vitals: [["Sep 2026", "128/82", "−4"], ["Jun 2026", "132/84", "−2"], ["Mar 2026", "134/86", "+2"], ["Dec 2025", "132/84", "baseline"]],
};

export default function HistoricalLabsCard({ className }) {
  return (
    <Card className={cn(styles.panel, styles.labsPanel, className)}>
      <p className={styles.eyebrow}>Historical labs</p>
      <Tabs defaultValue="HbA1c">
        <TabsList className={styles.labTabs} aria-label="Historical lab category">
          {Object.keys(results).map((label) => <TabsTrigger className={styles.labTab} key={label} value={label}>{label}</TabsTrigger>)}
        </TabsList>
        {Object.entries(results).map(([category, rows]) => (
          <TabsContent className={styles.labContent} key={category} value={category}>
            {category === "HbA1c" && <svg className={styles.labChart} viewBox="0 0 240 48" role="img" aria-label="HbA1c trend">
              <polyline points="8,10 78,22 150,16 222,6" />
              <circle cx="8" cy="10" r="3.5" /><circle cx="78" cy="22" r="3.5" /><circle cx="150" cy="16" r="3.5" /><circle className={styles.latestPoint} cx="222" cy="6" r="4" />
            </svg>}
            <div className={styles.labRows}>
              {rows.map(([date, value, change]) => <div className={styles.labRow} key={date}><span>{date}</span><strong>{value}</strong><span className={change.startsWith("+") ? styles.amber : change === "baseline" ? "" : styles.green}>{change}</span></div>)}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </Card>
  );
}
