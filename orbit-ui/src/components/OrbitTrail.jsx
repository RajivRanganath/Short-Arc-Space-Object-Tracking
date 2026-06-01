import { useMemo } from 'react'
import * as THREE from 'three'
import { Line } from '@react-three/drei'

/**
 * Glowing orbit trail behind a satellite.
 * Shows the last N positions as a thick fading line.
 */
export default function OrbitTrail({ trail, color = '#00e5ff' }) {
    const { points, colors } = useMemo(() => {
        if (!trail || trail.length < 2) return { points: [], colors: [] }

        const baseColor = new THREE.Color(color)
        const pts = []
        const cols = []

        for (let i = 0; i < trail.length; i++) {
            pts.push(new THREE.Vector3(...trail[i]))

            // Fade out the tail by mixing with black (additive blending makes black = invisible)
            const alpha = i / (trail.length - 1)
            // Quadratic fade makes the head brighter and the tail fade smoother
            const mixAlpha = alpha * alpha

            const c = baseColor.clone().multiplyScalar(mixAlpha)
            cols.push([c.r, c.g, c.b])
        }

        return { points: pts, colors: cols }
    }, [trail, color])

    if (!points || points.length < 2) return null

    return (
        <Line
            points={points}
            vertexColors={colors}
            lineWidth={2.5}
            transparent={true}
            opacity={0.8}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
        />
    )
}

