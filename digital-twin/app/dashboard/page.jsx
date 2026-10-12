import styles from "./dashboard.module.css";
import PatientProfileCard from "./components/patient-profile-card";
import DigitalTwinCard from "./components/digital-twin-card";
import PredictedEventCard from "./components/predicted-event-card";
import LiveVariablesCard from "./components/live-variables-card";
import HistoricalLabsCard from "./components/historical-labs-card";
import GlucoseForecastCard from "./components/glucose-forecast-card";
import AlertTimelineCard from "./components/alert-timeline-card";
import AlertExplanationCard from "./components/alert-explanation-card";

export default function DashboardPage() {
  return (
    <main className={styles.dashboard}>
      <header className={styles.topbar}>
        <div className={styles.brandGroup}>
          <a className={styles.brand} href="/dashboard">Digital Twin</a>
          <span className={styles.headerDivider} />
          <span className={styles.viewName}>Clinician view · Diabetes</span>
        </div>
        <div className={styles.headerStatus}>
          <span className={styles.sampleBadge}>Sample data</span>
          <span className={styles.syncStatus}><span className={styles.liveDot} />Live · synced 12s ago</span>
          <span className={styles.userInitials}>AR</span>
          <span className={styles.userName}>Dr. A. Rao</span>
        </div>
      </header>

      <section className={styles.dashboardGrid} aria-label="Patient digital twin dashboard">
        <PatientProfileCard className={styles.profile} />
        <DigitalTwinCard className={styles.twin} />
        <PredictedEventCard className={styles.prediction} />
        <LiveVariablesCard className={styles.variables} />
        <HistoricalLabsCard className={styles.labs} />
        <GlucoseForecastCard className={styles.forecast} />
        <AlertTimelineCard className={styles.timeline} />
        <AlertExplanationCard className={styles.explanation} />
      </section>
    </main>
  );
}
