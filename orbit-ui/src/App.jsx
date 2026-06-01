import { Canvas } from '@react-three/fiber'
import { OrbitControls, Stars } from '@react-three/drei'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import { useEffect, useState, useRef, useCallback, Suspense } from 'react'

import Earth from './components/Earth'
import Satellite from './components/Satellite'
import OrbitTrail from './components/OrbitTrail'
import RadarStation from './components/RadarStation'
import EventFeed from './components/EventFeed'
import TrackCard from './components/TrackCard'
import MissionControl from './components/MissionControl'
import ConjunctionPanel from './components/ConjunctionPanel'
import DangerLine from './components/DangerLine'
import Legend from './components/Legend'
import StatusBanner from './components/StatusBanner'
import ExplainModal from './components/ExplainModal'

const STATUS_COLORS = {
  stable: '#00ff88',
  acquiring: '#ffb800',
  unstable: '#ff3366',
}

export default function App() {
  const [tracks, setTracks] = useState([])
  const [stations, setStations] = useState([])
  const [events, setEvents] = useState([])
  const [conjunctions, setConjunctions] = useState([])
  const [activeTrack, setActiveTrack] = useState(null)
  const [stats, setStats] = useState({})
  const [phase, setPhase] = useState('Connecting to Live Tracker...')
  const [isConnected, setIsConnected] = useState(false)
  const [simRunning, setSimRunning] = useState(false)
  const [showExplain, setShowExplain] = useState(false)
  const [visibility, setVisibility] = useState({
    uncertainty: true,
    orbits: true,
    conjunctions: true,
  })
  const [missionConfig, setMissionConfig] = useState({
    nObjects: 5,
    duration: 300,
    speed: 0.5,
    method: 'jpda',
  })
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  useEffect(() => {
    let isMounted = true

    function connect() {
      if (!isMounted) return
      const ws = new WebSocket("ws://localhost:8000/ws")
      wsRef.current = ws

      ws.onopen = () => {
        console.log("Connected to Orbit Guard AI!")
        if (isMounted) setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (isMounted) {
            setTracks(data.tracks || [])
            setStations(data.stations || [])
            setEvents(data.events || [])
            setStats(data.stats || {})
            setPhase(data.phase || '')
            setConjunctions(data.conjunctions || [])
            if (data.simRunning !== undefined) {
              setSimRunning(data.simRunning)
            }
          }
        } catch (e) {
          console.error("Parse error", e)
        }
      }

      ws.onclose = () => {
        console.log("Disconnected.")
        if (isMounted) {
          setIsConnected(false)
          setSimRunning(false)
          setPhase('Reconnecting...')
          reconnectTimer.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      isMounted = false
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  const handleConfigChange = useCallback((newConfig) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(newConfig))

      if (newConfig.action === 'start') {
        setMissionConfig({
          nObjects: newConfig.nObjects,
          duration: newConfig.duration,
          speed: newConfig.speed,
          method: newConfig.method,
        })
      }
    }
  }, [])

  const handleVisibilityChange = useCallback((key, value) => {
    setVisibility(prev => ({ ...prev, [key]: value }))
  }, [])

  const progressPct = stats.totalFrames
    ? Math.round((stats.frame / stats.totalFrames) * 100)
    : 0

  // Determine status text
  const statusText = simRunning
    ? (phase.includes('Complete') ? 'COMPLETE' : 'TRACKING')
    : (isConnected ? 'READY' : 'OFFLINE')
  const statusColor = simRunning ? '#00ff88' : (isConnected ? '#00d4ff' : '#ff3366')

  return (
    <>
      {/* ── HUD Overlay ─────────────────────────────────────── */}
      <div className="ui-overlay">
        {/* Top Bar */}
        <div className="header glass-panel">
          <div className="header-left">
            <h1 className="header-title">
              <div
                className={isConnected ? "live-indicator" : ""}
                style={{
                  width: 8, height: 8, borderRadius: '50%',
                  backgroundColor: isConnected ? "var(--accent-red)" : "var(--text-secondary)",
                  boxShadow: isConnected ? undefined : "none",
                  animation: isConnected ? undefined : "none",
                  flexShrink: 0,
                }}
              />
              ORBIT GUARD <span style={{ color: 'var(--accent-blue)', fontWeight: 400 }}>AI</span>
            </h1>
            <div className="phase-indicator">
              {phase}
            </div>
          </div>
          <div className="stats-container">
            <div className="stat-box">
              <span className="stat-label">Status</span>
              <span className="stat-value" style={{ color: statusColor, fontSize: '0.75rem', fontWeight: 700 }}>
                {statusText}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Tracks</span>
              <span className="stat-value" style={{ color: '#00ff88' }}>
                {stats.activeTracks || stats.totalTracks || tracks.length}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Method</span>
              <span className="stat-value" style={{ color: '#00d4ff', fontSize: '0.75rem' }}>
                {(stats.method || '—').toUpperCase()}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Association Density</span>
              <span className="stat-value" style={{
                color: (stats.associationRate || 0) >= 85 ? '#00ff88'
                  : (stats.associationRate || 0) >= 70 ? '#ffb800' : '#ff3366'
              }}>
                {stats.associationRate || 0}%
              </span>
            </div>
            {stats.activeStation && (
              <div className="stat-box">
                <span className="stat-label">📡 Station</span>
                <span className="stat-value" style={{ color: '#00ff88', fontSize: '0.65rem' }}>
                  {stats.activeStation}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Status Banner — natural language */}
        <StatusBanner
          events={events}
          tracks={tracks}
          conjunctions={conjunctions}
          stations={stations}
          isRunning={simRunning}
        />

        {/* Legend — always visible during simulation */}
        {simRunning && <Legend />}

        {/* Conjunction Panel */}
        {visibility.conjunctions && conjunctions.length > 0 && (
          <ConjunctionPanel conjunctions={conjunctions} />
        )}

        {/* Progress bar */}
        {stats.totalFrames > 0 && (
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
          </div>
        )}

        {/* Bottom panels */}
        <div className="bottom-panels">
          <div className="bottom-left-stack">
            <MissionControl
              onConfigChange={handleConfigChange}
              isRunning={simRunning}
              config={missionConfig}
              visibility={visibility}
              onVisibilityChange={handleVisibilityChange}
            />
            <EventFeed events={events} />
          </div>

          <div className="bottom-right-stack">
            <TrackCard tracks={tracks} />
            {/* Pause & Explain button */}
            {simRunning && (
              <button
                className="explain-btn glass-panel"
                onClick={() => setShowExplain(true)}
              >
                ⓘ What am I watching?
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Explain Modal overlay */}
      {showExplain && (
        <ExplainModal onClose={() => setShowExplain(false)} />
      )}

      {/* ── 3D Canvas ───────────────────────────────────────── */}
      <Canvas camera={{ position: [0, 3, 8], fov: 45 }}>
        <color attach="background" args={['#030308']} />

        <ambientLight intensity={0.15} />
        <directionalLight position={[5, 3, 5]} intensity={1.8} color="#ffffff" />
        <directionalLight position={[-3, -1, -3]} intensity={0.3} color="#4488ff" />

        <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={0.3} />

        <Suspense fallback={null}>
          <Earth />
        </Suspense>

        {/* Radar Stations — rotated to match Earth texture alignment */}
        <group rotation={[0, -Math.PI / 2, 0]}>
          {stations.map((s, i) => (
            <RadarStation key={i} station={s} />
          ))}
        </group>

        {/* Orbit Trails */}
        {visibility.orbits && tracks.map((sat) => (
          <OrbitTrail
            key={`trail-${sat.id}`}
            trail={sat.trail}
            color={STATUS_COLORS[sat.status] || '#00d4ff'}
          />
        ))}

        {/* Conjunction Danger Lines */}
        {visibility.conjunctions && conjunctions.map((conj, i) => (
          <DangerLine key={`conj-${i}`} conjunction={conj} tracks={tracks} />
        ))}

        {/* Satellites */}
        {tracks.map((sat) => (
          <Satellite
            key={sat.id}
            data={sat}
            showUncertainty={visibility.uncertainty}
            isActive={activeTrack === sat.id}
            onClick={() => setActiveTrack(activeTrack === sat.id ? null : sat.id)}
          />
        ))}

        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          autoRotate={true}
          autoRotateSpeed={0.3}
          minDistance={4}
          maxDistance={20}
        />

        <EffectComposer>
          <Bloom luminanceThreshold={0.8} mipmapBlur intensity={1.2} />
        </EffectComposer>
      </Canvas>
    </>
  )
}