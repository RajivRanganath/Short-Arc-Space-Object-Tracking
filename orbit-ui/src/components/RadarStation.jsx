import { useRef, useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Html } from '@react-three/drei'

/**
 * A radar ground station on Earth's surface.
 * Shows a small marker + animated scan pulse. Label on hover only.
 */
export default function RadarStation({ station }) {
    const markerRef = useRef()
    const pulseRef = useRef()
    const [hovered, setHovered] = useState(false)

    const position = useMemo(() => new THREE.Vector3(...station.position), [station.position])

    // Pulse animation
    useFrame((_, delta) => {
        if (pulseRef.current) {
            pulseRef.current.scale.x += delta * 0.3
            pulseRef.current.scale.y += delta * 0.3
            pulseRef.current.scale.z += delta * 0.3
            pulseRef.current.material.opacity -= delta * 0.15

            if (pulseRef.current.material.opacity <= 0) {
                pulseRef.current.scale.set(1, 1, 1)
                pulseRef.current.material.opacity = 0.5
            }
        }
    })

    return (
        <group position={position}>
            {/* Station marker - small glowing diamond */}
            <mesh
                ref={markerRef}
                onPointerOver={() => { setHovered(true); document.body.style.cursor = 'pointer' }}
                onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default' }}
            >
                <octahedronGeometry args={[0.02, 0]} />
                <meshStandardMaterial
                    color="#00ff88"
                    emissive="#00ff88"
                    emissiveIntensity={2}
                />
            </mesh>

            {/* Scan pulse ring */}
            <mesh ref={pulseRef} rotation={[Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.015, 0.03, 16]} />
                <meshBasicMaterial
                    color="#00ff88"
                    transparent
                    opacity={0.5}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Station label — hover only */}
            {hovered && (
                <Html
                    position={[0, 0.06, 0]}
                    center
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                    <div style={{
                        background: 'rgba(0, 255, 136, 0.1)',
                        border: '1px solid rgba(0, 255, 136, 0.25)',
                        borderRadius: '3px',
                        padding: '1px 5px',
                        fontSize: '7px',
                        fontFamily: "'Inter', monospace",
                        color: '#00ff88',
                        whiteSpace: 'nowrap',
                        letterSpacing: '0.5px',
                        textTransform: 'uppercase',
                    }}>
                        📡 {station.name}
                    </div>
                </Html>
            )}
        </group>
    )
}
