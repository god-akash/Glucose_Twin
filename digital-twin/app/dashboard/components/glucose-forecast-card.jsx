
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getPrimaryRisk, formatTaskTitle } from "@/lib/api/dashboard";
import styles from "../dashboard.module.css";

const LEFT = 58;
const RIGHT = 650;
const TOP = 18;
const BOTTOM = 142;

const COLORS = {
  normal: "#14b8a6",
  alert: "#ef4444",
  low: "#94a3b8",
  high: "#f59e0b",
  critical: "#ef4444",
  risk: "#8b5cf6",
  grid: "#64748b",
  text: "#94a3b8",
};

const THRESHOLDS = [
  { value: 70, color: COLORS.low, label: "Low · 70" },
  { value: 140, color: COLORS.high, label: "High · 140" },
  { value: 180, color: COLORS.critical, label: "Critical · 180" },
];

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
}

function buildChart(history) {
  const readings = history
    .filter(
      (r) =>
        Number.isFinite(r.glucose) &&
        Number.isFinite(Date.parse(r.timestamp))
    )
    .slice(-24);

  if (!readings.length) return null;

  const values = readings.map((r) => r.glucose);
  const min = Math.min(40, Math.floor(Math.min(...values) / 10) * 10);
  const max = Math.max(200, Math.ceil(Math.max(...values) / 10) * 10);

  const t0 = Date.parse(readings[0].timestamp);
  const t1 = Date.parse(readings[readings.length - 1].timestamp);

  const x = (timestamp) =>
    t1 > t0
      ? LEFT +
        ((Date.parse(timestamp) - t0) / (t1 - t0)) * (RIGHT - LEFT)
      : (LEFT + RIGHT) / 2;

  const y = (value) =>
    BOTTOM - ((value - min) / (max - min)) * (BOTTOM - TOP);

  const points = readings.map((r) => ({
    x: x(r.timestamp),
    y: y(r.glucose),
    r,
    alert: Object.values(r.tasks || {}).some(
      (task) => task.level === "alert"
    ),
  }));

  const step = 50;
  const yTicks = [];

  for (let value = Math.ceil(min / step) * step; value <= max; value += step) {
    yTicks.push(value);
  }

  THRESHOLDS.forEach(({ value }) => {
    if (value >= min && value <= max && !yTicks.includes(value)) {
      yTicks.push(value);
    }
  });

  yTicks.sort((a, b) => a - b);

  const xTicks = Array.from({ length: 5 }, (_, i) => {
    const timestamp = t0 + ((t1 - t0) * i) / 4;
    return {
      x: t1 > t0 ? x(new Date(timestamp).toISOString()) : (LEFT + RIGHT) / 2,
      label: formatTime(timestamp),
    };
  });

  return {
    points,
    y,
    min,
    max,
    yTicks,
    xTicks,
    polyline: points
      .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
      .join(" "),
  };
}

export default function GlucoseForecastCard({
  className,
  history = [],
  tasks = {},
}) {
  const chart = buildChart(history);
  const primary = getPrimaryRisk(tasks);

  const curve =
    primary && !primary.risk.inEvent && primary.task.risk
      ? Object.entries(primary.task.risk)
          .map(([h, p]) => ({ h: Number(h), p: Number(p) }))
          .filter(
            ({ h, p }) =>
              Number.isFinite(h) &&
              Number.isFinite(p) &&
              h >= 0 &&
              h <= 360 &&
              p >= 0 &&
              p <= 1
          )
          .sort((a, b) => a.h - b.h)
      : null;

  const rx = (minutes) => LEFT + (minutes / 360) * (RIGHT - LEFT);
  const ry = (probability) =>
    BOTTOM - probability * (BOTTOM - TOP);

  return (
    <Card className={cn(styles.panel, styles.forecastPanel, className)}>
      <div className={styles.panelHeading}>
        <p className={styles.eyebrow}>
          Measured glucose · latest 24 readings
        </p>
        {chart && (
          <span className={styles.updates}>
            {chart.min}–{chart.max} mg/dL
          </span>
        )}
      </div>

      {chart ? (
        <>
          <svg
            className={styles.historyChart}
            viewBox="0 0 680 190"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="Measured glucose history with time and glucose axes"
          >
            <text
              x="12"
              y="88"
              fill={COLORS.text}
              fontSize="10"
              textAnchor="middle"
              transform="rotate(-90 12 88)"
            >
              Glucose (mg/dL)
            </text>

            {chart.yTicks.map((value) => (
              <g key={value}>
                <line
                  x1={LEFT}
                  y1={chart.y(value)}
                  x2={RIGHT}
                  y2={chart.y(value)}
                  stroke={COLORS.grid}
                  strokeOpacity="0.25"
                  strokeDasharray="3 4"
                />
                <text
                  x={LEFT - 8}
                  y={chart.y(value) + 3}
                  textAnchor="end"
                  fontSize="10"
                  fill={COLORS.text}
                >
                  {value}
                </text>
              </g>
            ))}

            {THRESHOLDS.filter(
              ({ value }) => value >= chart.min && value <= chart.max
            ).map(({ value, color }) => (
              <line
                key={value}
                x1={LEFT}
                y1={chart.y(value)}
                x2={RIGHT}
                y2={chart.y(value)}
                stroke={color}
                strokeDasharray="5 4"
                strokeWidth="1.4"
                strokeOpacity="0.9"
              />
            ))}

            <line
              x1={LEFT}
              y1={TOP}
              x2={LEFT}
              y2={BOTTOM}
              stroke={COLORS.grid}
              strokeOpacity="0.65"
            />
            <line
              x1={LEFT}
              y1={BOTTOM}
              x2={RIGHT}
              y2={BOTTOM}
              stroke={COLORS.grid}
              strokeOpacity="0.65"
            />

            <polyline
              points={chart.polyline}
              fill="none"
              stroke={COLORS.normal}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />

            {chart.points.map(({ x, y, r, alert }) => (
              <circle
                key={r.timestamp}
                cx={x}
                cy={y}
                r={alert ? 5 : 3.5}
                fill={alert ? COLORS.alert : COLORS.normal}
                stroke={alert ? "#ffffff" : "none"}
                strokeWidth={alert ? 1 : 0}
              >
                <title>
                  {`${formatTime(r.timestamp)} · ${r.glucose} mg/dL · ${
                    alert ? "Alert" : "No alert"
                  }`}
                </title>
              </circle>
            ))}

            {chart.xTicks.map((tick, i) => (
              <g key={`${tick.label}-${i}`}>
                <line
                  x1={tick.x}
                  y1={BOTTOM}
                  x2={tick.x}
                  y2={BOTTOM + 4}
                  stroke={COLORS.grid}
                />
                <text
                  x={tick.x}
                  y={BOTTOM + 17}
                  fontSize="10"
                  fill={COLORS.text}
                  textAnchor={
                    i === 0 ? "start" : i === 4 ? "end" : "middle"
                  }
                >
                  {tick.label}
                </text>
              </g>
            ))}
          </svg>

          <div className={styles.forecastLegend}>
            <span>
              <i style={{ background: COLORS.normal }} />
              No alert
            </span>
            <span>
              <i style={{ background: COLORS.alert }} />
              Alert
            </span>
            {THRESHOLDS.map(({ value, color, label }) => (
              <span key={value}>
                <i
                  className={styles.legendDash}
                  style={{ borderColor: color }}
                />
                {label}
              </span>
            ))}
          </div>
        </>
      ) : (
        <p className={styles.noData}>
          No measured glucose history is available for this patient.
        </p>
      )}

      <div className={styles.panelHeading} style={{ marginTop: 16 }}>
        <p className={styles.eyebrow}>
          {primary
            ? `Risk over the next 6 h · ${formatTaskTitle(
                primary.name,
                primary.task
              )}`
            : "Risk over the next 6 h"}
        </p>
      </div>

      {curve?.length ? (
        <>
          <svg
            className={styles.historyChart}
            viewBox="0 0 680 190"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="Predicted threshold-crossing risk by forecast time"
          >
            <text
              x="12"
              y="85"
              fill={COLORS.text}
              fontSize="10"
              textAnchor="middle"
              transform="rotate(-90 12 85)"
            >
              Probability (%)
            </text>

            {[0, 0.25, 0.5, 0.75, 1].map((p) => (
              <g key={p}>
                <line
                  x1={LEFT}
                  y1={ry(p)}
                  x2={RIGHT}
                  y2={ry(p)}
                  stroke={COLORS.grid}
                  strokeOpacity="0.3"
                  strokeDasharray="3 4"
                />
                <text
                  x={LEFT - 8}
                  y={ry(p) + 3}
                  fontSize="10"
                  textAnchor="end"
                  fill={COLORS.text}
                >
                  {Math.round(p * 100)}%
                </text>
              </g>
            ))}

            <line
              x1={LEFT}
              y1={TOP}
              x2={LEFT}
              y2={BOTTOM}
              stroke={COLORS.grid}
              strokeOpacity="0.65"
            />
            <line
              x1={LEFT}
              y1={BOTTOM}
              x2={RIGHT}
              y2={BOTTOM}
              stroke={COLORS.grid}
              strokeOpacity="0.65"
            />

            <polyline
              fill="none"
              stroke={COLORS.risk}
              strokeWidth="2.5"
              strokeLinejoin="round"
              points={curve
                .map(({ h, p }) => `${rx(h)},${ry(p)}`)
                .join(" ")}
            />

            {curve.map(({ h, p }) => (
              <circle
                key={h}
                cx={rx(h)}
                cy={ry(p)}
                r="3.5"
                fill={COLORS.risk}
              >
                <title>{`${h} minutes · ${Math.round(p * 100)}% estimated risk`}</title>
              </circle>
            ))}

            {[0, 60, 120, 180, 240, 300, 360].map((h) => (
              <g key={h}>
                <line
                  x1={rx(h)}
                  y1={BOTTOM}
                  x2={rx(h)}
                  y2={BOTTOM + 4}
                  stroke={COLORS.grid}
                />
                <text
                  x={rx(h)}
                  y={BOTTOM + 17}
                  fontSize="10"
                  fill={COLORS.text}
                  textAnchor={
                    h === 0 ? "start" : h === 360 ? "end" : "middle"
                  }
                >
                  {h === 0 ? "Now" : `${h / 60}h`}
                </text>
              </g>
            ))}
          </svg>
          <div className={styles.forecastLegend}>
            <span>
              <i style={{ background: COLORS.risk }} />
              Estimated threshold-crossing probability
            </span>
          </div>
        </>
      ) : (
        <p className={styles.noData}>
          {primary?.risk.inEvent
            ? "The threshold is already crossed. A future risk curve is not shown."
            : "No risk curve available yet."}
        </p>
      )}

      <p className={styles.dataNote}>
        Thresholds are reference levels, not a diagnosis. Risk curves estimate
        threshold-crossing probability; they do not directly predict glucose
        values or the exact time a threshold will be crossed.
      </p>
    </Card>
  );
}
