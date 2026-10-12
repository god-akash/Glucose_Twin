"use client";

import { useCallback, useEffect, useState } from "react";
import Backdrop from "./Backdrop";
import HeroScene from "./HeroScene";
import { DEFAULT, REGIONS } from "./regions";
import Link from 'next/Link'

export default function Twin() {
  const [active, setActive] = useState(null);
  const [origins, setOrigins] = useState({});
  const t = active ? REGIONS[active] : DEFAULT;

  // Hover from the 3D body passes the pointer position, so the colour wave starts there.
  const hover = useCallback((id, point) => {
    if (id && point) setOrigins((o) => ({ ...o, [id]: `${point.x}px ${point.y}px` }));
    setActive(id);
  }, []);

  // Clear only if this system is still the active one (moving between organs fires "over" before "out").
  const unhover = useCallback((id) => setActive((cur) => (id == null || cur === id ? null : cur)), []);

  useEffect(() => {
    document.body.style.cursor = active ? "pointer" : "";
    return () => { document.body.style.cursor = ""; };
  }, [active]);

  return (
    <>
      <Backdrop active={active} origins={origins} />
      <main className="hero" style={{ "--accent": t.accent }}>
        <div className="glow" aria-hidden="true" />

        <div className="copy">
          <p className="brand">Digital Twin</p>

          <div className="story" key={t.id ?? "home"} aria-live="polite">
            <h1>{t.title}</h1>
            <p className="lede">{t.text}</p>
            {t.reading && <p className="reading">{t.reading}</p>}
          </div>

          <div className="chips" role="group" aria-label="Body systems">
            {Object.values(REGIONS).map((r) => (
              <button
                key={r.id}
                type="button"
                className="chip"
                data-on={active === r.id}
               
                onFocus={() => hover(r.id)}
                onBlur={() => unhover(r.id)}
                onClick={() => hover(r.id)}
              >
                {r.name}
              </button>
            ))}
          </div>

          <div className="actions">
            <Link className="btn" href={'/dashboard'}>Create your twin</Link>
            
          </div>
        </div>

        <p className="credit">
          Anatomy: <a href="https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html">BodyParts3D</a>, © DBCLS, CC BY 4.0
        </p>

        <div className="stage" role="img" aria-label="A transparent 3D body with a heart, lungs, brain, gut and joints. Hover an organ to explore it.">
          <HeroScene active={active} setActive={hover} unhover={unhover} />
        </div>
      </main>
    </>
  );
}