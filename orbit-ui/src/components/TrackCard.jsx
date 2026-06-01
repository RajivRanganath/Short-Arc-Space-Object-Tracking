/**
 * Compact telemetry cards with EKF confidence bar.
 */
export default function TrackCard({ tracks }) {
    if (!tracks || tracks.length === 0) return null

    const statusConfig = {
        stable: { label: 'STABLE', color: '#00ff88', bg: 'rgba(0, 255, 136, 0.1)' },
        acquiring: { label: 'ACQ', color: '#ffaa00', bg: 'rgba(255, 170, 0, 0.1)' },
        unstable: { label: 'UNSTABLE', color: '#ff4466', bg: 'rgba(255, 68, 102, 0.1)' },
    }

    return (
        <div className="track-cards glass-panel">
            <h2 className="track-cards-title">Telemetry</h2>
            <div className="track-cards-list">
                {tracks.map(t => {
                    const cfg = statusConfig[t.status] || statusConfig.acquiring
                    const conf = t.confidence || 0
                    return (
                        <div key={t.id} className="track-card">
                            <div className="track-card-header">
                                <span className="track-card-id">TRK-{String(t.id).padStart(2, '0')}</span>
                                <span
                                    className="track-card-badge"
                                    style={{ color: cfg.color, background: cfg.bg }}
                                >
                                    {cfg.label}
                                </span>
                            </div>
                            <div className="track-card-metrics">
                                <div className="track-metric">
                                    <span className="track-metric-label">ALT</span>
                                    <span className="track-metric-value">{t.altitude?.toFixed(0)} km</span>
                                </div>
                                <div className="track-metric">
                                    <span className="track-metric-label">SPD</span>
                                    <span className="track-metric-value">{t.speed?.toFixed(1)} km/s</span>
                                </div>
                                <div className="track-metric">
                                    <span className="track-metric-label">CONF</span>
                                    <span className="track-metric-value">{conf}%</span>
                                </div>
                                <div className="track-metric">
                                    <span className="track-metric-label">REGIME</span>
                                    <span className="track-metric-value" style={{ color: '#00d4ff', fontWeight: 'bold' }}>
                                        {t.regime || '—'}
                                    </span>
                                </div>
                            </div>
                            {/* EKF Confidence bar */}
                            <div className="track-confidence-bar">
                                <div
                                    className="track-confidence-fill"
                                    style={{
                                        width: `${conf}%`,
                                        backgroundColor: cfg.color,
                                    }}
                                />
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
