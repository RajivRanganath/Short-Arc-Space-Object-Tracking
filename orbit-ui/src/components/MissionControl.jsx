import { useState } from 'react'

/**
 * Mission Control panel — auto-collapses when running.
 * Only speed slider + stop button visible during simulation.
 */
export default function MissionControl({ onConfigChange, isRunning, config, visibility, onVisibilityChange }) {
    const [localConfig, setLocalConfig] = useState({
        nObjects: config?.nObjects ?? 5,
        duration: config?.duration ?? 300,
        speed: config?.speed ?? 0.5,
        method: config?.method ?? 'jpda',
    })

    const handleSlider = (key, value) => {
        const updated = { ...localConfig, [key]: value }
        setLocalConfig(updated)

        // Live speed update while running
        if (key === 'speed' && isRunning && onConfigChange) {
            onConfigChange({ action: 'update_speed', speed: value })
        }
    }

    const handleMethodToggle = (method) => {
        setLocalConfig(prev => ({ ...prev, method }))
    }

    const handleStartStop = () => {
        if (onConfigChange) {
            onConfigChange({
                ...localConfig,
                action: isRunning ? 'stop' : 'start',
            })
        }
    }

    // Collapsed view during simulation
    if (isRunning) {
        return (
            <div className="mission-control glass-panel">
                <h2 className="mission-control-title">Mission Control</h2>

                {/* Speed Slider — always accessible */}
                <div className="mc-slider-group">
                    <label className="mc-label">
                        <span>Speed</span>
                        <span className="mc-value">{localConfig.speed.toFixed(1)}x</span>
                    </label>
                    <input
                        type="range"
                        className="mc-slider"
                        min={0.1}
                        max={2.0}
                        step={0.1}
                        value={localConfig.speed}
                        onChange={(e) => handleSlider('speed', parseFloat(e.target.value))}
                    />
                </div>

                {/* Visibility Toggles — compact row */}
                <div className="mc-toggles">
                    <label className="mc-toggle">
                        <input type="checkbox" checked={visibility?.uncertainty ?? true}
                            onChange={(e) => onVisibilityChange?.('uncertainty', e.target.checked)} />
                        <span className="mc-toggle-check">✓</span><span>Uncertainty</span>
                    </label>
                    <label className="mc-toggle">
                        <input type="checkbox" checked={visibility?.orbits ?? true}
                            onChange={(e) => onVisibilityChange?.('orbits', e.target.checked)} />
                        <span className="mc-toggle-check">✓</span><span>Orbits</span>
                    </label>
                    <label className="mc-toggle">
                        <input type="checkbox" checked={visibility?.conjunctions ?? true}
                            onChange={(e) => onVisibilityChange?.('conjunctions', e.target.checked)} />
                        <span className="mc-toggle-check">✓</span><span>Alerts</span>
                    </label>
                </div>

                {/* Stop Button */}
                <button className="mc-start-btn mc-running" onClick={handleStartStop}>
                    ⏹ STOP SIMULATION
                </button>
            </div>
        )
    }

    // Full view when idle
    return (
        <div className="mission-control glass-panel">
            <h2 className="mission-control-title">Mission Control</h2>

            <div className="mc-slider-group">
                <label className="mc-label">
                    <span>Debris Objects</span>
                    <span className="mc-value">{localConfig.nObjects}</span>
                </label>
                <input
                    type="range" className="mc-slider"
                    min={1} max={10} step={1}
                    value={localConfig.nObjects}
                    onChange={(e) => handleSlider('nObjects', parseInt(e.target.value))}
                />
            </div>

            <div className="mc-slider-group">
                <label className="mc-label">
                    <span>Duration (sec)</span>
                    <span className="mc-value">{localConfig.duration}s</span>
                </label>
                <input
                    type="range" className="mc-slider"
                    min={60} max={600} step={30}
                    value={localConfig.duration}
                    onChange={(e) => handleSlider('duration', parseInt(e.target.value))}
                />
            </div>

            <div className="mc-slider-group">
                <label className="mc-label">
                    <span>Speed</span>
                    <span className="mc-value">{localConfig.speed.toFixed(1)}x</span>
                </label>
                <input
                    type="range" className="mc-slider"
                    min={0.1} max={2.0} step={0.1}
                    value={localConfig.speed}
                    onChange={(e) => handleSlider('speed', parseFloat(e.target.value))}
                />
            </div>

            <div className="mc-method-group">
                <span className="mc-method-label">Association</span>
                <div className="mc-method-buttons">
                    <button
                        className={`mc-method-btn ${localConfig.method === 'jpda' ? 'mc-method-active' : ''}`}
                        onClick={() => handleMethodToggle('jpda')}
                    >JPDA</button>
                    <button
                        className={`mc-method-btn ${localConfig.method === 'gnn' ? 'mc-method-active' : ''}`}
                        onClick={() => handleMethodToggle('gnn')}
                    >GNN</button>
                </div>
            </div>

            <div className="mc-toggles">
                <label className="mc-toggle">
                    <input type="checkbox" checked={visibility?.uncertainty ?? true}
                        onChange={(e) => onVisibilityChange?.('uncertainty', e.target.checked)} />
                    <span className="mc-toggle-check">✓</span><span>Uncertainty</span>
                </label>
                <label className="mc-toggle">
                    <input type="checkbox" checked={visibility?.orbits ?? true}
                        onChange={(e) => onVisibilityChange?.('orbits', e.target.checked)} />
                    <span className="mc-toggle-check">✓</span><span>Orbits</span>
                </label>
                <label className="mc-toggle">
                    <input type="checkbox" checked={visibility?.conjunctions ?? true}
                        onChange={(e) => onVisibilityChange?.('conjunctions', e.target.checked)} />
                    <span className="mc-toggle-check">✓</span><span>Collision Alerts</span>
                </label>
            </div>

            <button className="mc-start-btn" onClick={handleStartStop}>
                🚀 START SIMULATION
            </button>
        </div>
    )
}
