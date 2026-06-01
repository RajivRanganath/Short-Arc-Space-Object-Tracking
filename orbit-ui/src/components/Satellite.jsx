import { useRef, useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { Html } from '@react-three/drei'

const STATUS_COLORS = {
    stable: '#00ff88',
    acquiring: '#ffb800',
    unstable: '#ff3366',
}

const STATUS_LABELS = {
    stable: 'Stable',
    acquiring: 'Acquiring',
    unstable: 'Signal Lost',
}

/**
 * Single smooth uncertainty glow — replaces the old 200-particle cloud.
 * Scale grows with uncertainty, opacity fades as uncertainty increases.
 */
function UncertaintyGlow({ position, uncertainty, status }) {
    const glowRef = useRef()
    const color = STATUS_COLORS[status] || STATUS_COLORS.acquiring

    // Scale: 0.05 (very confident) to 0.4 (very uncertain)
    const scale = Math.max(0.05, Math.min(0.4, (uncertainty || 30) / 100 * 0.4))
    // Opacity: brighter when confident (low uncertainty), dimmer when uncertain
    const opacity = Math.max(0.03, 0.12 - (uncertainty || 30) / 100 * 0.1)

    useFrame((_, delta) => {
        if (glowRef.current) {
            // Gentle breathing animation
            const breathe = 1 + Math.sin(Date.now() * 0.002) * 0.08
            glowRef.current.scale.setScalar(scale * breathe)
        }
    })

    return (
        <mesh ref={glowRef} position={position}>
            <sphereGeometry args={[1, 24, 24]} />
            <meshBasicMaterial
                color={color}
                transparent
                opacity={opacity}
                depthWrite={false}
                side={THREE.BackSide}
            />
        </mesh>
    )
}

export default function Satellite({ data, showUncertainty = true, isActive = false, onClick }) {
    const meshRef = useRef()
    const ringRef = useRef()
    const confidenceRingRef = useRef()
    const [hovered, setHovered] = useState(false)
    const target = useMemo(() => new THREE.Vector3(...data.position), [data.position])

    const color = STATUS_COLORS[data.status] || STATUS_COLORS.acquiring
    const statusLabel = STATUS_LABELS[data.status] || 'Unknown'
    const isNew = (data.updates || 0) < 3
    const isUnstable = data.status === 'unstable'
    const showLabel = hovered || isActive

    // Confidence from filter (0-100, higher = more converged)
    const confidence = (data.confidence || 0) / 100

    useFrame((_, delta) => {
        if (meshRef.current) {
            const dampFactor = 1 - Math.pow(0.001, delta)
            meshRef.current.position.lerp(target, dampFactor)
        }
        if (ringRef.current && isActive) {
            ringRef.current.rotation.x += delta * 1.5
            ringRef.current.rotation.y += delta * 2.0
        }
        if (confidenceRingRef.current) {
            confidenceRingRef.current.rotation.z += delta * 0.5
        }
        if (isUnstable && meshRef.current) {
            const flash = Math.sin(Date.now() * 0.01) > 0 ? '#ff0000' : '#ff3366'
            meshRef.current.material.color.set(flash)
            meshRef.current.material.emissive.set(flash)
        }
    })

    return (
        <group>
            {/* Main satellite dot */}
            <mesh
                ref={meshRef}
                onClick={(e) => { e.stopPropagation(); if (onClick) onClick(); }}
                onPointerOver={() => { setHovered(true); document.body.style.cursor = 'pointer' }}
                onPointerOut={() => { setHovered(false); document.body.style.cursor = 'default' }}
            >
                <sphereGeometry args={[0.04, 16, 16]} />
                <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={isUnstable ? 3 : 2}
                />

                {/* Selection Ring */}
                {isActive && (
                    <mesh ref={ringRef}>
                        <torusGeometry args={[0.12, 0.006, 16, 64]} />
                        <meshBasicMaterial color="#00d4ff" transparent opacity={0.8} />
                    </mesh>
                )}

                {/* Confidence Ring */}
                {confidence > 0.05 && (
                    <mesh ref={confidenceRingRef}>
                        <torusGeometry args={[0.08, 0.003, 8, 32]} />
                        <meshBasicMaterial
                            color={color}
                            transparent
                            opacity={confidence * 0.6}
                        />
                    </mesh>
                )}
            </mesh>

            {/* Uncertainty Glow — replaces individual particle dots */}
            {showUncertainty && (
                <UncertaintyGlow
                    position={target}
                    uncertainty={data.uncertainty}
                    status={data.status}
                />
            )}

            {/* Hover / Active Tooltip — plain language */}
            {showLabel && (
                <Html
                    position={[target.x, target.y + 0.12, target.z]}
                    center
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                    <div style={{
                        background: 'rgba(6, 8, 18, 0.88)',
                        border: `1px solid ${color}40`,
                        borderRadius: '6px',
                        padding: '5px 8px',
                        fontSize: '9px',
                        fontFamily: "'Inter', sans-serif",
                        color: '#ffffff',
                        whiteSpace: 'nowrap',
                        textAlign: 'left',
                        minWidth: '110px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    }}>
                        <div style={{
                            fontWeight: 700,
                            fontSize: '10px',
                            letterSpacing: '0.5px',
                            color: color,
                            marginBottom: 3,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                        }}>
                            <span>TRK-{String(data.id).padStart(2, '0')}</span>
                            <span style={{
                                fontSize: '7px',
                                padding: '1px 4px',
                                borderRadius: '3px',
                                background: `${color}20`,
                                color: color,
                                fontWeight: 600,
                            }}>{statusLabel}</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', color: '#ccccdd' }}>
                            <span>Altitude</span>
                            <span style={{ color: '#fff', fontWeight: 500, textAlign: 'right' }}>{data.altitude?.toFixed(0)} km</span>
                            <span>Speed</span>
                            <span style={{ color: '#fff', fontWeight: 500, textAlign: 'right' }}>{data.speed?.toFixed(1)} km/s</span>
                            <span>Convergence</span>
                            <span style={{ color: color, fontWeight: 600, textAlign: 'right' }}>{data.confidence || 0}%</span>
                        </div>
                    </div>
                </Html>
            )}
        </group>
    )
}
