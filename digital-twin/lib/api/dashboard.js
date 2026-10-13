export function formatTaskTitle(name, task) {
  const direction = task?.direction === "below" ? "Low glucose" : "High glucose";
  return task?.threshold == null
    ? name.replace(/([a-z])(\d)/i, "$1 $2")
    : `${direction} ${task.direction === "below" ? "<" : ">"} ${task.threshold} mg/dL`;
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
  return Object.entries(tasks)
    .map(([name, task]) => ({ name, task, risk: getTaskRisk(task) }))
    .filter(({ risk }) => risk)
    .sort((a, b) => {
      if (a.risk.inEvent !== b.risk.inEvent) return a.risk.inEvent ? -1 : 1;
      return (b.risk.probability || 0) - (a.risk.probability || 0);
    })[0] || null;
}

export function getRiskStates(tasks = {}) {
  return Object.entries(tasks).map(([name, task]) => {
    const risk = getTaskRisk(task);
    return {
      name,
      title: formatTaskTitle(name, task),
      value: risk?.probability == null ? null : risk.probability * 100,
      horizon: risk?.horizon,
      status: risk?.inEvent ? "In event" : task.level || task.status || "Unavailable",
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

export function getGlucoseChange(history = []) {
  const readings = history.filter((reading) => Number.isFinite(reading.glucose));
  if (readings.length < 2) return null;

  const current = readings[readings.length - 1];
  const previous = readings[readings.length - 2];
  const minutes = (Date.parse(current.timestamp) - Date.parse(previous.timestamp)) / 60_000;
  if (!Number.isFinite(minutes) || minutes <= 0) return null;

  const change = current.glucose - previous.glucose;
  return { change, perMinute: change / minutes };
}

export function getAlertTimeline(history = []) {
  const previousLevels = new Map();
  const alerts = [];

  for (const reading of history) {
    for (const [name, task] of Object.entries(reading.tasks || {})) {
      const risk = getTaskRisk(task);
      if (!risk && !["ok", "watch", "alert"].includes(task.level)) continue;

      const level = risk?.inEvent ? "in_event" : task.level || "ok";
      const severity = level === "in_event" || level === "alert" ? 2 : level === "watch" ? 1 : 0;
      const previous = previousLevels.get(name) || 0;

      if (severity !== previous && (severity > 0 || previous > 0)) {
        alerts.push({
          key: `${reading.timestamp}-${name}-${severity}`,
          timestamp: reading.timestamp,
          title: formatTaskTitle(name, task),
          detail: severity === 0
            ? "Risk returned to the model's OK level"
            : risk?.inEvent
              ? "Threshold event reported by the model"
              : `${task.level} risk · ${Math.round(risk.probability * 100)}% within ${risk.horizon} min`,
          color: severity === 2 ? "amber" : severity === 1 ? "purple" : "green",
          current: severity > 0,
        });
      }

      previousLevels.set(name, severity);
    }
  }

  return alerts.reverse().slice(0, 8);
}

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
    const x = duration > 0
      ? ((Date.parse(reading.timestamp) - firstTime) / duration) * width
      : readings.length === 1
        ? width / 2
        : (index / (readings.length - 1)) * width;
    const y = height - ((reading.glucose - min) / range) * height;
    return { x, y, reading };
  });

  return {
    points,
    polyline: points.map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" "),
    min,
    max,
    firstTimestamp: readings[0].timestamp,
    lastTimestamp: readings[readings.length - 1].timestamp,
  };
}
