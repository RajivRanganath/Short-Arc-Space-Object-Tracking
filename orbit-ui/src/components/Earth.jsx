import { useRef } from 'react'
import { useLoader, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

export default function Earth() {
    const earthRef = useRef()
    const atmosphereRef = useRef()

    const [colorMap, bumpMap, specularMap] = useLoader(THREE.TextureLoader, [
        'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg',
        'https://unpkg.com/three-globe/example/img/earth-topology.png',
        'https://unpkg.com/three-globe/example/img/earth-water.png'
    ])

    // Use frame removed - we are in ECEF coordinates, so the Earth 
    // surface must remain absolutely fixed relative to the scene.
    // The camera controls provide the necessary rotation.
    useFrame((_, delta) => {
        // Only atmosphere spins slightly for cosmetic effect
        if (atmosphereRef.current) {
            atmosphereRef.current.rotation.y += delta * 0.005
        }
    })

    return (
        <group>
            {/* Earth */}
            {/* Note: -Math.PI / 2 aligns the central Prime Meridian texture at the +X axis to match the backend lat_lon_to_3d math */}
            <mesh ref={earthRef} rotation={[0, -Math.PI / 2, 0]}>
                <sphereGeometry args={[2, 64, 64]} />
                <meshPhongMaterial
                    map={colorMap}
                    bumpMap={bumpMap}
                    bumpScale={0.015}
                    specularMap={specularMap}
                    specular={new THREE.Color('grey')}
                />
            </mesh>

            {/* Inner atmosphere glow */}
            <mesh ref={atmosphereRef} scale={[1.012, 1.012, 1.012]}>
                <sphereGeometry args={[2, 64, 64]} />
                <meshBasicMaterial
                    color="#4488ff"
                    transparent
                    opacity={0.12}
                    side={THREE.BackSide}
                />
            </mesh>

            {/* Rim light layer */}
            <mesh scale={[1.025, 1.025, 1.025]}>
                <sphereGeometry args={[2, 64, 64]} />
                <meshBasicMaterial
                    color="#88aaff"
                    transparent
                    opacity={0.06}
                    side={THREE.BackSide}
                />
            </mesh>

            {/* Outer halo */}
            <mesh scale={[1.05, 1.05, 1.05]}>
                <sphereGeometry args={[2, 64, 64]} />
                <meshBasicMaterial
                    color="#6699ff"
                    transparent
                    opacity={0.025}
                    side={THREE.BackSide}
                />
            </mesh>
        </group>
    )
}
