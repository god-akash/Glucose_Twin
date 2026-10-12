import { REGIONS } from "./regions";

// Dark base + one coloured "wave" per body system.
// The active wave expands out of the point you hovered (see .wave in globals.css).
export default function Backdrop({ active, origins }) {
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="layer base" />
      {Object.values(REGIONS).map((r) => (
        <div
          key={r.id}
          className="layer wave"
          data-on={active === r.id}
          style={{ "--deep": r.deep, "--glow": r.glow, ...(origins[r.id] ? { "--o": origins[r.id] } : {}) }}
        />
      ))}
      <div className="layer vignette" />
      <div className="layer grain" />
    </div>
  );
}