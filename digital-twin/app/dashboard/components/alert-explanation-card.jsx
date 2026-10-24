"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { postExplain } from "@/lib/api/client";
import styles from "../dashboard.module.css";

const btn = {
  padding: "6px 12px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.2)",
  background: "transparent", color: "inherit", cursor: "pointer", fontSize: 13,
};

export default function AlertExplanationCard({ className, tasks = {}, patientId, timestamp }) {
  const hasTasks = Object.keys(tasks).length > 0;
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(null);

  useEffect(() => {
  requestRef.current?.abort();
  requestRef.current = null;

  setResult(null);
  setError("");
  setBusy(false);

  return () => {
    requestRef.current?.abort();
  };
}, [patientId, timestamp]);

  async function run(useLlm) {
  if (!patientId || !hasTasks) return;

  requestRef.current?.abort();

  const controller = new AbortController();
  requestRef.current = controller;

  setBusy(true);
  setError("");

  try {
    const data = await postExplain(
      patientId,
      "overview",
      useLlm,
      null,
      controller.signal
    );

    if (requestRef.current === controller) {
      setResult(data);
    }
  } catch (e) {
    if (e.name !== "AbortError" && requestRef.current === controller) {
      setError(e.message || "Unable to generate the explanation.");
    }
  } finally {
    if (requestRef.current === controller) {
      requestRef.current = null;
      setBusy(false);
    }
  }
}

  const stale = result && timestamp && result.timestamp !== timestamp;
  const drivers = result?.facts?.drivers || [];

  return (
    <Card className={cn(styles.panel, styles.explanationPanel, className)}>
      <div className={styles.explanationHeader}>
        <div className={styles.explanationHeading}>
          <span className={styles.explanationIcon}><Sparkles size={17} aria-hidden="true" /></span>
          <div>
            <p className={styles.eyebrow}>Explanation</p>
            <h2 className={styles.explanationTitle}>What the twin is showing and why</h2>
          </div>
        </div>
        <span className={styles.explanationTag}>
          {!result ? "On demand" : result.source === "llm" ? `Local AI · ${result.model}` : "Rule-based text"}
        </span>
      </div>
      <div className={styles.explanationBody}>
        <div className={styles.explanationSummary}>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button type="button" style={btn} disabled={!hasTasks || busy} onClick={() => run(true)}>
              {busy ? "Thinking..." : "Explain (free local AI)"}
            </button>
            <button type="button" style={btn} disabled={!hasTasks || busy} onClick={() => run(false)}>
              Explain (rules only)
            </button>
          </div>
          {busy && <p style={{ fontSize: 12, opacity: 0.7 }}>The first request can take up to a minute while the local model loads.</p>}
          {error && <p style={{ color: "#e5484d" }}>{error}</p>}
          <p>{result ? result.text : hasTasks ? "Press Explain for a plain-language summary of this patient's glucose, risks and the factors behind them." : "No usable prediction yet."}</p>
          {stale && <span className={styles.explanationDisclaimer}>A newer reading has arrived. Explain again to update.</span>}
          {result?.llm_fallback_reason && (
            <span className={styles.explanationDisclaimer}>Local AI unavailable ({result.llm_fallback_reason}); showing rule-based text.</span>
          )}
          <span className={styles.explanationDisclaimer}>Model estimates are not a diagnosis and should not replace clinical judgment.</span>
          {result?.facts && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: "pointer", fontSize: 12 }}>Facts this explanation is based on</summary>
              <pre style={{ fontSize: 11, maxHeight: 160, overflow: "auto" }}>{JSON.stringify(result.facts, null, 2)}</pre>
            </details>
          )}
        </div>
        <div className={styles.factorGrid} aria-label="Factors behind the estimate">
          {drivers.length ? drivers.map((d) => (
            <div className={styles.factorTile} key={d.factor}>
              <span>{d.factor}</span>
              <strong>{d.effect}, {d.strength}</strong>
            </div>
          )) : (
            <div className={styles.factorTile}><span>Factors</span><strong>Shown after you press Explain</strong></div>
          )}
        </div>
      </div>
    </Card>
  );
}