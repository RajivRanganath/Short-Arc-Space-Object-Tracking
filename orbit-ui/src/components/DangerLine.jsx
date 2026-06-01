import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import * as THREE from 'three'

export default function DangerLine({ conjunction, tracks }) {
    const { t1, t2, risk_level } = conjunction
    const sat1 = tracks.find(t => t.id === t1)
    const sat2 = tracks.find(t => t.id === t2)
    const materialRef = useRef()

    if (!sat1 || !sat2) return null

    const points = useMemo(() => [
        sat1.position,
        sat2.position
    ], [sat1.position, sat2.position])

    const isRed = risk_level === 'RED'
    const color = isRed ? '#ff0044' : '#ffaa00'

    // Animate dash offset for scanning effect + pulse opacity for RED
    useFrame(() => {
        if (materialRef.current) {
            materialRef.current.dashOffset -= 0.02
            if (isRed) {
                materialRef.current.opacity = 0.5 + Math.sin(Date.now() * 0.008) * 0.4
            }
        }
    })

    return (
        <Line
            ref={materialRef}
            points={points}
            color={color}
            lineWidth={isRed ? 3 : 2}
            transparent
            opacity={isRed ? 0.9 : 0.7}
            dashed={true}
            dashSize={0.15}
            gapSize={0.08}
        />
    )
}
