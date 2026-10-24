"use client";

import { useEffect, useState } from "react";
import styles from "./dashboard.module.css";
import PatientProfileCard from "./components/patient-profile-card";
import DigitalTwinCard from "./components/digital-twin-card";
import PredictedEventCard from "./components/predicted-event-card";
import LiveVariablesCard from "./components/live-variables-card";
import HistoricalLabsCard from "./components/historical-labs-card";
import GlucoseForecastCard from "./components/glucose-forecast-card";
import AlertTimelineCard from "./components/alert-timeline-card";
import AlertExplanationCard from "./components/alert-explanation-card";
import {
  getPatients,
  getPatientLatest,
  getPatientHistory,
} from "@/lib/api/client";
import { usePatientStream } from "@/hooks/usePatientStream";

export default function DashboardPage() {
  const [patients, setPatients] = useState([]);
  const [patientId, setPatientId] = useState("");
  const [meta, setMeta] = useState(null);
  const [polled, setPolled] = useState([]);
  const [error, setError] = useState("");
  const { history: streamed, connected } = usePatientStream(patientId);

  useEffect(() => {
    let stop = false;
    const load = () =>
      getPatients()
        .then((list) => {
          if (stop) return;
          setPatients(list);
          setPatientId((cur) => cur || list[0]?.patient_id || "");
          setError("");
        })
        .catch((e) => !stop && setError(e.message));
    load();
    const id = setInterval(load, 5000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!patientId) return;
    let stop = false;
    setMeta(null);
    setPolled([]);
    const load = () =>
      getPatientLatest(patientId)
        .then((m) => !stop && setMeta(m))
        .catch(() => {});
    load();
    const id = setInterval(load, 10000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [patientId]);

  useEffect(() => {
    if (!patientId || connected) return;
    let stop = false;
    const load = () =>
      getPatientHistory(patientId)
        .then((h) => !stop && setPolled(h))
        .catch(() => {});
    load();
    const id = setInterval(load, 2000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [patientId, connected]);

  const history = streamed.length ? streamed : polled;
  const latest = history.length ? history[history.length - 1] : null;
  const tasks = latest?.tasks || {};

  return (
    <main className={styles.dashboard}>
      <header className={styles.topbar}>
        <div className={styles.brandGroup}>
          <a className={styles.brand} href="/dashboard">
            Digital Twin
          </a>
          <span className={styles.headerDivider} />
          <span className={styles.viewName}>Clinician view · Diabetes</span>
        </div>
        <div className={styles.headerStatus}>
          <select
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            style={{
              background: "transparent",
              color: "inherit",
              border: "1px solid rgba(255,255,255,0.2)",
              borderRadius: 8,
              padding: "4px 8px",
            }}
            aria-label="Patient"
          >
            {patients.length === 0 && <option value="">No patients yet</option>}
            {patients.map((p) => (
              <option key={p.patient_id} value={p.patient_id}>
                {p.patient_id}
              </option>
            ))}
          </select>
          <span className={styles.syncStatus}>
            <span className={styles.liveDot} />
            {connected ? "Live · WebSocket" : "Polling"}
          </span>
        </div>
      </header>

      {error && <p className={styles.noData}>{error}</p>}
      {!patientId && !error && (
        <p className={styles.noData}>
          No patients yet. Start the replay: python src\replay.py 36 --speed 15
          --ff-hours 48
        </p>
      )}

      <section
        className={styles.dashboardGrid}
        aria-label="Patient digital twin dashboard"
      >
        <PatientProfileCard
          className={styles.profile}
          patientId={patientId}
          profile={meta?.profile || {}}
          modelFolder={meta?.model_folder}
        />
        <DigitalTwinCard className={styles.twin} tasks={tasks} />
        <PredictedEventCard
          className={styles.prediction}
          tasks={tasks}
          modelFolder={meta?.model_folder}
        />
        <LiveVariablesCard
          className={styles.variables}
          latest={latest || {}}
          history={history}
        />
        <HistoricalLabsCard
          className={styles.labs}
          profile={meta?.profile || {}}
        />
        <GlucoseForecastCard
          className={styles.forecast}
          history={history}
          tasks={tasks}
        />
        <AlertTimelineCard className={styles.timeline} history={history} />
        <AlertExplanationCard
          className={styles.explanation}
          tasks={tasks}
          patientId={patientId}
          timestamp={latest?.timestamp}
        />
      </section>
    </main>
  );
}
