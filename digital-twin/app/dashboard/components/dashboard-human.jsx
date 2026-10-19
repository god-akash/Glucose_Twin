"use client";

import { useCallback, useState } from "react";
import HeroScene from "@/components/HeroScene";

export default function DashboardHuman() {
  const [active, setActive] = useState(null);
  const handleActive = useCallback((region) => setActive(region), []);
  const handleUnhover = useCallback((region) => {
    setActive((current) => (current === region ? null : current));
  }, []);

  return <HeroScene active={active} setActive={handleActive} unhover={handleUnhover} compact />;
}
