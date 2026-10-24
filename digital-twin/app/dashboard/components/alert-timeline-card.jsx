"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getAlertTimeline } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

function formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? "Unknown time"
    : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const chip = (active) => ({
  padding: "3px 10px", borderRadius: 999, fontSize: 12, cursor: "pointer", color: "inherit",
  border: "1px solid rgba(255,255,255,0.2)", background: active ? "rgba(255,255,255,0.14)" : "transparent",
});

export default function AlertTimelineCard({ className, history = [] }) {
  const [onlyAlerts, setOnlyAlerts] = useState(false);
  const all = getAlertTimeline(history);
  const alerts = onlyAlerts ? all.filter((a) => a.rank > 0) : all;

  return (
    <Card className={cn(styles.panel, styles.timelinePanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>Prediction history · {alerts.length} events</p>
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" style={chip(!onlyAlerts)} onClick={() => setOnlyAlerts(false)}>All</button>
          <button type="button" style={chip(onlyAlerts)} onClick={() => setOnlyAlerts(true)}>Alerts only</button>
        </div>
      </div>
      {alerts.length > 0 ? (
        <div style={{ maxHeight: 320, overflowY: "auto", paddingRight: 6, scrollbarWidth: "thin" }} tabIndex={0} aria-label="Scrollable prediction history">
          <ol className={styles.alertList}>
            {alerts.map((alert) => (
              <li className={styles.alertItem} key={alert.key}>
                <span className={cn(styles.alertDot, styles[alert.color], alert.current && styles.currentAlert)} />
                <div>
                  <strong>{alert.title}</strong>
                  <span>{alert.detail}</span>
                  <span>{formatTimestamp(alert.timestamp)}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p className={styles.noData}>No model risk transitions are available in the loaded history.</p>
      )}
      <p className={styles.dataNote}>
        Newest first. An event is recorded when an alert level changes or glucose crosses a threshold. Derived from stored predictions.
      </p>
    </Card>
  );
}