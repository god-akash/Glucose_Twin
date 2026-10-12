"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { DEFAULT, REGIONS } from "./regions";

// public/models/twin.glb: real adult anatomy (BodyParts3D, CC BY 4.0) – skin, skeleton, heart,
// brain, digestive + urinary organs, airways. Lungs are generated to fit the rib cage.
const MODEL = "/models/twin.glb";
const BONE = new THREE.Color("#e9e6d6");

const vertexShader = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vY;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = -mv.xyz;
    vY = (modelMatrix * vec4(position, 1.0)).y;
    gl_Position = projectionMatrix * mv;
  }
`;

// Skin: glass body, bright at the silhouette, with a slow scan band and fine contour lines.
const skinFragment = /* glsl */ `
  uniform vec3 core;
  uniform vec3 rim;
  uniform float uTime;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vY;
  void main() {
    float f = pow(1.0 - abs(dot(normalize(vNormal), normalize(vView))), 2.0);
    float scan = mod(uTime * 0.28, 2.2) - 0.25;
    float band = smoothstep(0.12, 0.0, abs(vY - scan));
    float lines = smoothstep(0.9, 1.0, fract(vY * 36.0)) * 0.04;
    float a = mix(0.04, 0.8, f) + band * 0.3 + lines;
    vec3 c = mix(core, rim, clamp(f + band * 0.8, 0.0, 1.0));
    gl_FragColor = vec4(c, clamp(a, 0.0, 1.0));
    #include <colorspace_fragment>
  }
`;

// Organs and bones: lit surface with a soft rim, opacity driven from JS.
const shapeFragment = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uBase;
  uniform float uLit;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vY;
  void main() {
    vec3 n = normalize(vNormal);
    float f = pow(1.0 - abs(dot(n, normalize(vView))), 1.7);
    float diffuse = 0.4 + 0.6 * max(dot(n, normalize(vec3(0.3, 0.6, 0.8))), 0.0);
    float lit = mix(1.0, diffuse, uLit);
    vec3 c = uColor * lit * (0.8 + 0.55 * f);
    gl_FragColor = vec4(c, uOpacity * mix(uBase, 1.0, f));
    #include <colorspace_fragment>
  }
`;

function shape(color, { base, lit, side = THREE.FrontSide, depthWrite = true }) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uOpacity: { value: 0 },
      uBase: { value: base },
      uLit: { value: lit },
    },
    vertexShader,
    fragmentShader: shapeFragment,
    transparent: true,
    depthWrite,
    side,
  });
}

const ORGANS = ["gut", "lungs", "heart", "brain"];

export default function Human({ active, setActive, unhover }) {
  const spin = useRef();
  const speed = useRef(0.6);
  const reduced = useRef(false);
  const { nodes } = useGLTF(MODEL);

  const theme = active ? REGIONS[active] : DEFAULT;
  const target = useMemo(() => new THREE.Color(theme.accent), [theme.accent]);

  const mats = useMemo(() => {
    const m = {
      skin: new THREE.ShaderMaterial({
        uniforms: {
          core: { value: new THREE.Color(DEFAULT.accent).multiplyScalar(0.45) },
          rim: { value: new THREE.Color(DEFAULT.accent) },
          uTime: { value: 0 },
        },
        vertexShader,
        fragmentShader: skinFragment,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
      skeleton: shape(BONE, { base: 0.3, lit: 0.5, side: THREE.DoubleSide, depthWrite: false }),
      joints: shape(BONE, { base: 0.3, lit: 0.5, side: THREE.DoubleSide, depthWrite: false }),
      hit: new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
    };
    ORGANS.forEach((r) => { m[r] = shape(REGIONS[r].accent, { base: 0.6, lit: 1 }); });
    return m;
  }, []);

  const ring = useMemo(() => new THREE.MeshBasicMaterial({ color: DEFAULT.accent }), []);
  const inner = useMemo(() => new THREE.MeshBasicMaterial({ color: DEFAULT.accent, transparent: true, opacity: 0.5 }), []);
  const disc = useMemo(() => new THREE.MeshBasicMaterial({ color: DEFAULT.accent, transparent: true, opacity: 0.08, depthWrite: false }), []);

  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    const map = { skin: mats.skin, skeleton: mats.skeleton, joints: mats.joints, joints_hit: mats.hit, gut: mats.gut, lungs: mats.lungs, heart: mats.heart, brain: mats.brain };
    Object.entries(map).forEach(([name, material]) => {
      const n = nodes[name];
      if (!n) return;
      n.material = material;
      n.frustumCulled = false;
    });
  }, [nodes, mats]);

  const tmp = useMemo(() => new THREE.Color(), []);

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime;
    const k = 1 - Math.exp(-5 * dt);

    // Everything eases toward the hovered system's accent.
    mats.skin.uniforms.uTime.value = t;
    mats.skin.uniforms.rim.value.lerp(target, k);
    mats.skin.uniforms.core.value.copy(mats.skin.uniforms.rim.value).multiplyScalar(0.45);
    ring.color.lerp(target, k);
    inner.color.lerp(target, k);
    disc.color.lerp(target, k);

    // Organs: normal -> bright when hovered -> dim when something else is hovered.
    ORGANS.forEach((r) => {
      const u = mats[r].uniforms;
      const goal = active == null ? 0.9 : active === r ? 1 : 0.2;
      u.uOpacity.value = THREE.MathUtils.damp(u.uOpacity.value, goal, 6, dt);
      tmp.set(REGIONS[r].accent);
      if (active === r) tmp.multiplyScalar(1.3);
      u.uColor.value.lerp(tmp, k);
    });
    const sk = mats.skeleton.uniforms.uOpacity;
    sk.value = THREE.MathUtils.damp(sk.value, active == null ? 0.55 : active === "joints" ? 0.3 : 0.16, 6, dt);
    const jt = mats.joints.uniforms;
    jt.uOpacity.value = THREE.MathUtils.damp(jt.uOpacity.value, active == null ? 0.55 : active === "joints" ? 1 : 0.16, 6, dt);
    tmp.set(active === "joints" ? REGIONS.joints.accent : "#e9e6d6");
    jt.uColor.value.lerp(tmp, k);

    // Heartbeat (~72 bpm) and slow breathing.
    const beat = Math.pow(Math.max(0, Math.sin(t * 7.54)), 6);
    nodes.heart?.scale.setScalar(1 + beat * (active === "heart" ? 0.1 : 0.04));
    const br = (Math.sin(t * 1.4) + 1) / 2;
    nodes.lungs?.scale.set(1 + 0.02 * br, 1 + 0.03 * br, 1 + 0.025 * br);

    speed.current = THREE.MathUtils.damp(speed.current, active || reduced.current ? 0 : 0.6, 3, dt);
    spin.current.rotation.y += dt * speed.current;
  });

  const bind = (region) => ({
    onPointerOver: (e) => { e.stopPropagation(); setActive(region, { x: e.clientX, y: e.clientY }); },
    onPointerOut: () => unhover(region),
  });

  const TICKS = useMemo(
    () => Array.from({ length: 48 }, (_, i) => {
      const a = (i / 48) * Math.PI * 2;
      const long = i % 6 === 0;
      return { a, long, r: long ? 0.93 : 0.98, len: long ? 0.15 : 0.065 };
    }),
    []
  );

  return (
    <group ref={spin}>
      <primitive object={nodes.skin} />
      <primitive object={nodes.skeleton} />
      <primitive object={nodes.joints} />
      <primitive object={nodes.gut} {...bind("gut")} />
      <primitive object={nodes.lungs} {...bind("lungs")} />
      <primitive object={nodes.heart} {...bind("heart")} />
      <primitive object={nodes.brain} {...bind("brain")} />
      {/* slightly inflated, invisible copy of the limb bones so thin bones are easy to hover */}
      <primitive object={nodes.joints_hit} {...bind("joints")} />

      {/* Platform */}
      <mesh position={[0, -0.03, 0]} material={disc}>
        <cylinderGeometry args={[1.1, 1.1, 0.06, 96]} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.002, 0]} material={ring}>
        <torusGeometry args={[1.1, 0.012, 8, 128]} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.002, 0]} material={inner}>
        <torusGeometry args={[0.7, 0.006, 8, 128]} />
      </mesh>
      {TICKS.map(({ a, long, r, len }, i) => (
        <mesh key={i} material={long ? ring : inner} position={[Math.cos(a) * r, 0.003, Math.sin(a) * r]} rotation={[0, -a, 0]}>
          <boxGeometry args={[len, 0.004, 0.012]} />
        </mesh>
      ))}
    </group>
  );
}

useGLTF.preload(MODEL);