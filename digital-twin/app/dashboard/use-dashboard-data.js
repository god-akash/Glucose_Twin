"use client";

import { useEffect, useState } from "react";
import { getPatientHistory, getPatientLatest, getPatients } from "@/lib/api/client";

const REFRESH_INTERVAL = 30_000;

export function useDashboardData() {
  const [patients, setPatients] = useState(null);
  const [patientId, setPatientId] = useState("");
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);

  useEffect(() => {
    let active = true;
    let timer;
    let controller;

    const loadPatients = async () => {
      controller = new AbortController();
      try {
        const result = await getPatients(controller.signal);
        if (!Array.isArray(result)) {
          throw new Error("The patients endpoint returned an invalid response.");
        }
        if (!active) return;

        setPatients(result);
        setError("");
        setPatientId((current) =>
          result.some((patient) => patient.patient_id === current)
            ? current
            : result[0]?.patient_id || "",
        );
      } catch (loadError) {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      } finally {
        if (active) {
          setPatientsLoading(false);
          timer = setTimeout(loadPatients, REFRESH_INTERVAL);
        }
      }
    };

    loadPatients();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
    };
  }, []);

  useEffect(() => {
    if (!patientId) {
      setLatest(null);
      setHistory([]);
      setDataLoading(false);
      return undefined;
    }

    setLatest(null);
    setHistory([]);
    let active = true;
    let timer;
    let controller;

    const loadPatientData = async () => {
      controller = new AbortController();
      setDataLoading(true);
      try {
        const [latestResult, historyResult] = await Promise.all([
          getPatientLatest(patientId, controller.signal),
          getPatientHistory(patientId, controller.signal),
        ]);
        if (!Array.isArray(historyResult)) {
          throw new Error("The patient history endpoint returned an invalid response.");
        }
        if (!active) return;

        setLatest(latestResult);
        setHistory(historyResult);
        setError("");
      } catch (loadError) {
        if (active && loadError.name !== "AbortError") setError(loadError.message);
      } finally {
        if (active) {
          setDataLoading(false);
          timer = setTimeout(loadPatientData, REFRESH_INTERVAL);
        }
      }
    };

    loadPatientData();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
    };
  }, [patientId]);

  return {
    patients: patients || [],
    patientId,
    setPatientId,
    latest,
    history,
    error,
    loading: patientsLoading || (!!patientId && dataLoading && !latest),
  };
}
