async function getJson(path, signal) {
  const response = await fetch(path, { cache: "no-store", signal });
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body?.detail || body?.error || `Request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return body;
}

export function getPatients(signal) {
  return getJson("/api/patients", signal);
}

export function getPatientLatest(patientId, signal) {
  return getJson(`/api/patients/${encodeURIComponent(patientId)}/latest`, signal);
}

export function getPatientHistory(patientId, signal) {
  return getJson(`/api/patients/${encodeURIComponent(patientId)}/history?limit=400`, signal);
}
