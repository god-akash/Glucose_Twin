"use client";

import { Suspense, useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import Human from "./Human";

// Pull the camera back on narrow screens so the whole platform stays in view.
function Rig({ compact }) {
  const { camera, size } = useThree();
  useEffect(() => {
    const aspect = size.width / size.height;
    camera.position.set(0, 1.2, compact ? 4.6 : Math.max(4.2, 4.4 / aspect));
    camera.updateProjectionMatrix();
  }, [camera, compact, size.width, size.height]);
  return null;
}

export default function HeroScene({ active, setActive, unhover, compact = false }) {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 1.2, 4.2], fov: 34 }}>
      <Rig compact={compact} />
      <Suspense fallback={null}>
        <Human active={active} setActive={setActive} unhover={unhover} showPlatform={!compact} />
      </Suspense>
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        target={[0, 0.88, 0]}
        minPolarAngle={Math.PI / 3}
        maxPolarAngle={Math.PI / 2.05}
      />
    </Canvas>
  );
}