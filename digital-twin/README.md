# Digital Twin frontend

## Connect to the FastAPI backend

Copy `.env.example` to `.env.local` and set `GLUCOSE_TWIN_API_URL` to the URL of the running FastAPI server. This variable is read by the Next.js server-side API proxy and does not need a `NEXT_PUBLIC_` prefix.

Run the frontend from this directory:

```sh
npm install
npm run dev
```

The dashboard proxies these backend endpoints:

- `GET /patients` to discover available patients
- `GET /patients/{patient_id}/latest` for the latest glucose reading, profile, and model predictions
- `GET /patients/{patient_id}/history?limit=400` for measured glucose and prediction history

The dashboard refreshes patient data every 30 seconds. Patients must already exist in the FastAPI process and have readings submitted through its `/ingest` endpoint. The backend keeps patient state in memory, so restarting it clears that state.

The backend currently does not provide medication lists, condition history, historical lab results, wearable summaries, glucose-value forecasts, alert events, or generated explanations. The dashboard does not fabricate these values: it shows only profile values and model outputs returned by the API, and clearly labels unavailable information.
