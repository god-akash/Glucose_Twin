export function formatTaskTitle(name, task) {
  const direction =
    task?.direction === "below" ? "Low glucose" : "High glucose";
  const base =
    task?.threshold == null
      ? name.replace(/([a-z])(\d)/i, "$1 $2")
      : `${direction} ${task.direction === "below" ? "<" : ">"} ${task.threshold} mg/dL`;
  return task?.exploratory ? `${base} · experimental` : base;
}

export function getTimeToRisk(task) {
  const t = task?.time_to_risk_min;
  if (!t) return [];
  return Object.entries(t)
    .map(([pct, minutes]) => ({ pct: Number(pct), minutes }))
    .sort((a, b) => a.pct - b.pct);
}

export function getTrendLabel(perMinute) {
  if (!Number.isFinite(perMinute)) return "Unknown";
  if (perMinute > 2) return "Rising rapidly";
  if (perMinute >= 1) return "Rising";
  if (perMinute < -2) return "Falling rapidly";
  if (perMinute <= -1) return "Falling";
  return "Steady";
}

export function getTaskRisk(task) {
  if (task?.status === "in_event") {
    return { horizon: null, probability: null, inEvent: true };
  }

  const risks = task?.risk;
  if (!risks || typeof risks !== "object") return null;

  const horizon = Object.hasOwn(risks, "120")
    ? "120"
    : Object.keys(risks).sort((a, b) => Number(a) - Number(b)).at(-1);
  const probability = risks[horizon];

  return Number.isFinite(probability)
    ? { horizon, probability, inEvent: false }
    : null;
}
export function getPrimaryRisk(tasks = {}) {
  return (
    Object.entries(tasks)
      .map(([name, task]) => ({ name, task, risk: getTaskRisk(task) }))
      .filter(({ risk }) => risk)
      .sort((a, b) => {
        if (Boolean(a.task.exploratory) !== Boolean(b.task.exploratory))
          return a.task.exploratory ? 1 : -1;
        if (a.risk.inEvent !== b.risk.inEvent) return a.risk.inEvent ? -1 : 1;
        return (b.risk.probability || 0) - (a.risk.probability || 0);
      })[0] || null
  );
}

export function getRiskStates(tasks = {}) {
  return Object.entries(tasks).map(([name, task]) => {
    const risk = getTaskRisk(task);
    const reach = task?.time_to_risk_min;
    return {
      name,
      title: formatTaskTitle(name, task),
      value: risk?.probability == null ? null : risk.probability * 100,
      horizon: risk?.horizon,
      status: risk?.inEvent ? "in_event" : task.level || task.status || "unavailable",
      hasReach: Boolean(reach),
      reach30: reach?.["30"] ?? null,
      reach50: reach?.["50"] ?? null,
      color: task.level === "alert" || risk?.inEvent
        ? "amber"
        : task.level === "watch"
          ? "purple"
          : task.level === "ok"
            ? "green"
            : "mutedDot",
    };
  });
}


// get the glucose change
export function getGlucoseChange(history = []) {
  const readings = history.filter((reading) =>
    Number.isFinite(reading.glucose),
  );
  if (readings.length < 2) return null;

  const current = readings[readings.length - 1];
  const previous = readings[readings.length - 2];
  const minutes =
    (Date.parse(current.timestamp) - Date.parse(previous.timestamp)) / 60_000;
  if (!Number.isFinite(minutes) || minutes <= 0) return null;

  const change = current.glucose - previous.glucose;
  return { change, perMinute: change / minutes };
}

// get aleart time line
const RANK = { ok: 0, watch: 1, alert: 2, in_event: 3 };

export function getAlertTimeline(history = [], limit = 80) {
  const previous = new Map();
  const lastIndex = new Map();
  const alerts = [];

  for (const reading of history) {
    for (const [name, task] of Object.entries(reading.tasks || {})) {
      const risk = getTaskRisk(task);
      if (!risk && !["ok", "watch", "alert"].includes(task.level)) continue;

      const state = risk?.inEvent ? "in_event" : task.level || "ok";
      const rank = RANK[state] ?? 0;
      const before = previous.get(name) ?? 0;

      if (rank !== before && (rank > 0 || before > 0)) {
        const word = task.direction === "below" ? "below" : "above";
        const reach50 = task.time_to_risk_min?.["50"];
        let detail;
        if (state === "in_event") {
          detail = `Glucose crossed ${word} ${task.threshold} mg/dL (${Math.round(reading.glucose)} mg/dL)`;
        } else if (rank === 0) {
          detail = before === 3 ? "Glucose is back inside the range" : "Risk returned to the OK level";
        } else {
          detail = `${state === "alert" ? "Alert" : "Watch"} · ${Math.round(risk.probability * 100)}% within ${risk.horizon} min`
            + (reach50 ? ` · 50% by about ${reach50} min` : "");
        }
        alerts.push({
          key: `${reading.timestamp}-${name}-${rank}`,
          timestamp: reading.timestamp,
          name,
          title: formatTaskTitle(name, task),
          rank,
          glucose: reading.glucose,
          detail,
          color: rank >= 2 ? "amber" : rank === 1 ? "purple" : "green",
        });
        lastIndex.set(name, alerts.length - 1);
      }
      previous.set(name, rank);
    }
  }

  alerts.forEach((a, i) => { a.current = a.rank > 0 && lastIndex.get(a.name) === i; });
  return alerts.reverse().slice(0, limit);
}

//  glucose chart
export function buildGlucoseChart(history = [], width = 628, height = 130) {
  const readings = history
    .filter((reading) => Number.isFinite(reading.glucose))
    .slice(-24);
  if (!readings.length) return null;

  const values = readings.map((reading) => reading.glucose);
  const min = Math.floor(Math.min(...values) / 10) * 10;
  const max = Math.ceil(Math.max(...values) / 10) * 10;
  const range = Math.max(max - min, 10);
  const firstTime = Date.parse(readings[0].timestamp);
  const lastTime = Date.parse(readings[readings.length - 1].timestamp);
  const duration = lastTime - firstTime;
  const points = readings.map((reading, index) => {
    const x =
      duration > 0
        ? ((Date.parse(reading.timestamp) - firstTime) / duration) * width
        : readings.length === 1
          ? width / 2
          : (index / (readings.length - 1)) * width;
    const y = height - ((reading.glucose - min) / range) * height;
    return { x, y, reading };
  });

  return {
    points,
    polyline: points
      .map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`)
      .join(" "),
    min,
    max,
    firstTimestamp: readings[0].timestamp,
    lastTimestamp: readings[readings.length - 1].timestamp,
  };
}
