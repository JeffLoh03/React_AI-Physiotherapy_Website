import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { TorusKnot, Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

function RotatingShape() {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.getElapsedTime() * 0.2;
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.3;
    }
  });

  return (
    <group>
      <TorusKnot ref={meshRef} args={[1, 0.3, 128, 16]} position={[0, 0, 0]}>
        <meshStandardMaterial 
          color="#b026ff" 
          emissive="#b026ff"
          emissiveIntensity={0.5}
          roughness={0.1}
          metalness={0.8}
          wireframe
        />
      </TorusKnot>
      <Sphere args={[0.5, 32, 32]}>
         <MeshDistortMaterial
            color="#00f3ff"
            emissive="#00f3ff"
            emissiveIntensity={0.8}
            distort={0.4}
            speed={2}
         />
      </Sphere>
    </group>
  );
}

export default function ThreeHero() {
  return (
    <div className="w-full h-full absolute inset-0 -z-10 opacity-60">
      <Canvas camera={{ position: [0, 0, 4] }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} color="#00f3ff" />
        <pointLight position={[-10, -10, -10]} intensity={1} color="#b026ff" />
        <RotatingShape />
      </Canvas>
    </div>
  );
}
