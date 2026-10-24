async function requestJson(path, options = {}) {
  const { signal, ...fetchOptions } = options;

  const response = await fetch(path, {
    ...fetchOptions,
    cache: "no-store",
    signal,
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      body?.detail ||
      body?.error ||
      `Request failed with status ${response.status}.`;

    throw new Error(message);
  }

  return body;
}

export function getPatients(signal) {
  return requestJson("/api/patients", { signal });
}

// get the real time data 

export function getPatientLatest(patientId, signal) {
  return requestJson(
    `/api/patients/${encodeURIComponent(patientId)}/latest`,
    { signal },
  );
}

// get the old data ( history ) to analyze the patients 

export function getPatientHistory(patientId, signal) {
  return requestJson(
    `/api/patients/${encodeURIComponent(patientId)}/history?limit=400`,
    { signal },
  );
}

// it tell when thw patients eat any things does this effect or not 

export function postPatientWhatIf(patientId, meal, signal) {
  return requestJson("/api/scenario", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_id: patientId,
      meal,
    }),
    signal,
  });
}

export function postExplain(patientId, event = "overview", useLlm = true, meal = null, signal) {
  return requestJson("/api/AI-Summary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patient_id: patientId, event, use_llm: useLlm, meal }),
    signal,
  });
}