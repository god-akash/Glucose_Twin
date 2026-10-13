"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import styles from "./dashboard.module.css";
import PatientProfileCard from "./components/patient-profile-card";
import DigitalTwinCard from "./components/digital-twin-card";
import PredictedEventCard from "./components/predicted-event-card";
import LiveVariablesCard from "./components/live-variables-card";
import HistoricalLabsCard from "./components/historical-labs-card";
import GlucoseForecastCard from "./components/glucose-forecast-card";
import AlertTimelineCard from "./components/alert-timeline-card";
import AlertExplanationCard from "./components/alert-explanation-card";
import { useDashboardData } from "./use-dashboard-data";

function formatTimestamp(timestamp) {
  if (!timestamp) return "No readings";
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString();
}

export default function DashboardPage() {
  const { patients, patientId, setPatientId, latest, history, error, loading } = useDashboardData();
  const selectedPatient = patients.find((patient) => patient.patient_id === patientId);

  return (
    <main className={styles.dashboard}>
      <header className={styles.topbar}>
        <div className={styles.brandGroup}>
          <Link className={styles.brand} href="/dashboard">Digital Twin</Link>
          <span className={styles.headerDivider} />
          <span className={styles.viewName}>Clinician view · Diabetes</span>
        </div>
        <div className={styles.headerStatus}>
          {patients.length > 1 ? (
            <label className={styles.patientPicker}>
              <span>Patient</span>
              <select
                className={styles.patientSelect}
                value={patientId}
                onChange={(event) => setPatientId(event.target.value)}
                aria-label="Select patient"
              >
                {patients.map((patient) => (
                  <option key={patient.patient_id} value={patient.patient_id}>{patient.patient_id}</option>
                ))}
              </select>
            </label>
          ) : (
            <span className={styles.patientBadge}>{patientId || (loading ? "Loading patients…" : "No patient selected")}</span>
          )}
          <span className={styles.syncStatus}>
            <span className={cn(styles.liveDot, error && styles.offlineDot)} />
            {selectedPatient?.model_folder || "FastAPI"} · {formatTimestamp(latest?.timestamp || selectedPatient?.last)}
          </span>
        </div>
      </header>

      {error && <p className={styles.errorBanner} role="alert">Unable to load live patient data: {error}</p>}

      {!loading && !error && patients.length === 0 && (
        <section className={styles.emptyState} aria-live="polite">
          <h1>No patient data is available</h1>
          <p>The FastAPI server has no registered patients yet. Send patient readings to its <code>/ingest</code> endpoint to populate this dashboard.</p>
        </section>
      )}

      {loading && !latest && <p className={styles.loadingState} role="status">Loading patient data from FastAPI…</p>}

      {latest && (
        <section className={styles.dashboardGrid} aria-label="Patient digital twin dashboard">
          <PatientProfileCard className={styles.profile} patientId={patientId} profile={latest.profile || {}} modelFolder={latest.model_folder} />
          <DigitalTwinCard className={styles.twin} tasks={latest.tasks || {}} />
          <PredictedEventCard className={styles.prediction} tasks={latest.tasks || {}} modelFolder={latest.model_folder} />
          <LiveVariablesCard className={styles.variables} latest={latest} history={history} />
          <HistoricalLabsCard className={styles.labs} profile={latest.profile || {}} />
          <GlucoseForecastCard className={styles.forecast} history={history} />
          <AlertTimelineCard className={styles.timeline} history={history} />
          <AlertExplanationCard className={styles.explanation} tasks={latest.tasks || {}} />
        </section>
      )}
    </main>
  );
}
