import { useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Float, Sparkles } from '@react-three/drei';
import * as THREE from 'three';

type Point = [number, number, number];

interface SegmentProps {
  start: Point;
  end: Point;
  radius: number;
  color?: string;
  opacity?: number;
}

function segmentTransform(start: Point, end: Point) {
  const from = new THREE.Vector3(...start);
  const to = new THREE.Vector3(...end);
  const direction = to.clone().sub(from);
  const midpoint = from.clone().add(to).multiplyScalar(0.5);
  const quaternion = new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    direction.clone().normalize(),
  );
  return { midpoint, quaternion, length: direction.length() };
}

function Bone({ start, end, radius, color = '#d9fbff', opacity = 0.92 }: SegmentProps) {
  const transform = useMemo(() => segmentTransform(start, end), [start, end]);
  return (
    <mesh position={transform.midpoint} quaternion={transform.quaternion}>
      <cylinderGeometry args={[radius, radius, transform.length, 10]} />
      <meshStandardMaterial
        color={color}
        emissive="#22d3ee"
        emissiveIntensity={0.22}
        roughness={0.35}
        metalness={0.25}
        transparent
        opacity={opacity}
      />
    </mesh>
  );
}

function Muscle({ start, end, radius, color = '#a855f7', opacity = 0.72 }: SegmentProps) {
  const transform = useMemo(() => segmentTransform(start, end), [start, end]);
  return (
    <mesh
      position={transform.midpoint}
      quaternion={transform.quaternion}
      scale={[radius, transform.length * 0.52, radius]}
    >
      <sphereGeometry args={[1, 18, 18]} />
      <meshPhysicalMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.38}
        roughness={0.42}
        clearcoat={0.35}
        transparent
        opacity={opacity}
      />
    </mesh>
  );
}

function Joint({ position, scale = 0.11 }: { position: Point; scale?: number }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[scale, 16, 16]} />
      <meshStandardMaterial color="#ecfeff" emissive="#22d3ee" emissiveIntensity={0.5} />
    </mesh>
  );
}

function AnatomicalFigure() {
  const figure = useRef<THREE.Group>(null);
  const { viewport } = useThree();
  const reducedMotion = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  );

  useFrame(({ clock }) => {
    if (!figure.current) return;
    const elapsed = clock.getElapsedTime();
    figure.current.rotation.y = reducedMotion ? -0.25 : elapsed * 0.24;
    figure.current.rotation.z = Math.sin(elapsed * 0.55) * 0.025;
  });

  const xPosition = viewport.width >= 8 ? Math.min(viewport.width * 0.25, 2.8) : 0;

  const joints: Point[] = [
    [0, 2.12, 0], [-0.78, 1.92, 0], [0.78, 1.92, 0],
    [-1.16, 1.08, 0], [1.16, 1.08, 0], [-1.28, 0.2, 0], [1.28, 0.2, 0],
    [-0.34, -0.02, 0], [0.34, -0.02, 0], [-0.42, -1.38, 0], [0.42, -1.38, 0],
    [-0.43, -2.55, 0], [0.43, -2.55, 0],
  ];

  return (
    <group position={[xPosition, 0.05, 0]} scale={viewport.width < 8 ? 0.78 : 0.92}>
      <Float speed={1.1} rotationIntensity={0.03} floatIntensity={0.16}>
        <group ref={figure} rotation={[0.04, -0.35, 0]}>
          {/* Skull, jaw and central skeleton */}
          <mesh position={[0, 2.64, 0]} scale={[0.36, 0.45, 0.32]}>
            <sphereGeometry args={[1, 24, 24]} />
            <meshPhysicalMaterial color="#e8fcff" emissive="#22d3ee" emissiveIntensity={0.16} roughness={0.32} />
          </mesh>
          <mesh position={[0, 2.31, 0.05]} scale={[0.27, 0.18, 0.25]}>
            <sphereGeometry args={[1, 18, 18]} />
            <meshStandardMaterial color="#c9f7fb" roughness={0.4} />
          </mesh>
          <Bone start={[0, 2.2, 0]} end={[0, 0.02, 0]} radius={0.085} />
          <Bone start={[-0.34, -0.02, 0]} end={[0.34, -0.02, 0]} radius={0.11} />
          <Bone start={[-0.78, 1.92, 0]} end={[0.78, 1.92, 0]} radius={0.075} />

          {/* Arms */}
          <Bone start={[-0.78, 1.92, 0]} end={[-1.16, 1.08, 0]} radius={0.07} />
          <Bone start={[-1.16, 1.08, 0]} end={[-1.28, 0.2, 0]} radius={0.06} />
          <Bone start={[0.78, 1.92, 0]} end={[1.16, 1.08, 0]} radius={0.07} />
          <Bone start={[1.16, 1.08, 0]} end={[1.28, 0.2, 0]} radius={0.06} />

          {/* Legs and feet */}
          <Bone start={[-0.34, -0.02, 0]} end={[-0.42, -1.38, 0]} radius={0.085} />
          <Bone start={[-0.42, -1.38, 0]} end={[-0.43, -2.55, 0]} radius={0.07} />
          <Bone start={[0.34, -0.02, 0]} end={[0.42, -1.38, 0]} radius={0.085} />
          <Bone start={[0.42, -1.38, 0]} end={[0.43, -2.55, 0]} radius={0.07} />
          <Bone start={[-0.43, -2.55, 0]} end={[-0.43, -2.62, 0.35]} radius={0.065} />
          <Bone start={[0.43, -2.55, 0]} end={[0.43, -2.62, 0.35]} radius={0.065} />

          {/* Rib cage */}
          {[0, 1, 2, 3].map(index => (
            <mesh key={index} position={[0, 1.22 + index * 0.19, 0]} scale={[0.78 - index * 0.06, 0.43, 0.42]}>
              <torusGeometry args={[0.62, 0.035, 8, 32]} />
              <meshStandardMaterial color="#d9fbff" emissive="#22d3ee" emissiveIntensity={0.28} transparent opacity={0.8} />
            </mesh>
          ))}

          {/* Major muscle groups */}
          <Muscle start={[-0.72, 1.82, 0.02]} end={[-1.13, 1.12, 0.02]} radius={0.15} color="#c026d3" />
          <Muscle start={[0.72, 1.82, 0.02]} end={[1.13, 1.12, 0.02]} radius={0.15} color="#c026d3" />
          <Muscle start={[-1.17, 1.0, 0.02]} end={[-1.28, 0.28, 0.02]} radius={0.11} color="#7c3aed" />
          <Muscle start={[1.17, 1.0, 0.02]} end={[1.28, 0.28, 0.02]} radius={0.11} color="#7c3aed" />
          <Muscle start={[-0.28, -0.12, 0.04]} end={[-0.4, -1.3, 0.04]} radius={0.19} color="#a855f7" />
          <Muscle start={[0.28, -0.12, 0.04]} end={[0.4, -1.3, 0.04]} radius={0.19} color="#a855f7" />
          <Muscle start={[-0.42, -1.48, 0.02]} end={[-0.43, -2.46, 0.02]} radius={0.13} color="#6d28d9" />
          <Muscle start={[0.42, -1.48, 0.02]} end={[0.43, -2.46, 0.02]} radius={0.13} color="#6d28d9" />

          {/* Pectoral and abdominal muscle plates */}
          {[-0.27, 0.27].map(x => (
            <mesh key={`pec-${x}`} position={[x, 1.69, 0.23]} scale={[0.32, 0.28, 0.12]}>
              <sphereGeometry args={[1, 18, 18]} />
              <meshPhysicalMaterial color="#d946ef" emissive="#a21caf" emissiveIntensity={0.35} transparent opacity={0.7} />
            </mesh>
          ))}
          {[1.31, 1.04, 0.77, 0.5].map(y => (
            <group key={y}>
              <Muscle start={[-0.14, y + 0.09, 0.18]} end={[-0.14, y - 0.09, 0.18]} radius={0.115} color="#9333ea" opacity={0.68} />
              <Muscle start={[0.14, y + 0.09, 0.18]} end={[0.14, y - 0.09, 0.18]} radius={0.115} color="#9333ea" opacity={0.68} />
            </group>
          ))}

          {joints.map((position, index) => <Joint key={index} position={position} />)}

          {/* Scanning halo */}
          <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -2.7, 0]}>
            <torusGeometry args={[1.45, 0.012, 8, 80]} />
            <meshBasicMaterial color="#22d3ee" transparent opacity={0.55} />
          </mesh>
        </group>
      </Float>
    </group>
  );
}

export default function ThreeHero() {
  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden opacity-30 lg:opacity-80" aria-hidden="true">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_48%,rgba(34,211,238,0.10),transparent_30%),radial-gradient(circle_at_72%_55%,rgba(168,85,247,0.12),transparent_42%)]" />
      <Canvas camera={{ position: [0, 0, 7.5], fov: 44 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.65} />
        <directionalLight position={[4, 6, 5]} intensity={2.2} color="#bffcff" />
        <pointLight position={[-3, 1, 4]} intensity={28} distance={10} color="#a855f7" />
        <pointLight position={[3, -2, 3]} intensity={20} distance={9} color="#22d3ee" />
        <Sparkles count={55} scale={[8, 6, 3]} size={1.8} speed={0.25} color="#67e8f9" opacity={0.45} />
        <AnatomicalFigure />
      </Canvas>
    </div>
  );
}
