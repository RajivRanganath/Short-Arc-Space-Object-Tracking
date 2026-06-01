import { useState, useEffect } from 'react'

export default function ConjunctionPanel({ conjunctions }) {
    const [now, setNow] = useState(Date.now())

    // Tick every second for TCA countdown
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 1000)
        return () => clearInterval(timer)
    }, [])

    if (!conjunctions || conjunctions.length === 0) return null

    const formatTCA = (seconds) => {
        if (!seconds || seconds <= 0) return 'NOW'
        const h = Math.floor(seconds / 3600)
        const m = Math.floor((seconds % 3600) / 60)
        const s = Math.floor(seconds % 60)
        if (h > 0) return `T-${h}h${m}m`
        if (m > 0) return `T-${m}m${s}s`
        return `T-${s}s`
    }

    // Pc bar width: log scale between 1e-8 (0%) and 1e-2 (100%)
    const pcToWidth = (pc) => {
        if (pc <= 0) return 0
        const logPc = Math.log10(pc)
        return Math.max(0, Math.min(100, ((logPc + 8) / 6) * 100))
    }

    return (
        <div className="conjunction-panel glass-panel">
            <h3 className="conjunction-title">⚠ ACTIVE THREATS</h3>
            <div className="conjunction-list">
                {conjunctions.slice(0, 3).map((c, i) => (
                    <div key={i} className={`conjunction-card ${c.risk_level.toLowerCase()}`}>
                        <div className="conj-header">
                            <span className="conj-ids">
                                TRK-{String(c.t1).padStart(2, '0')} ↔ TRK-{String(c.t2).padStart(2, '0')}
                            </span>
                            <span className={`conj-risk conj-risk-${c.risk_level.toLowerCase()}`}>
                                {c.risk_level}
                            </span>
                        </div>
                        <div className="conj-details">
                            <div className="conj-stat">
                                <span className="conj-label">TCA</span>
                                <span className="conj-value conj-tca">{formatTCA(c.tca_seconds)}</span>
                            </div>
                            <div className="conj-stat">
                                <span className="conj-label">MISS</span>
                                <span className="conj-value">{c.miss_distance?.toFixed(1)} km</span>
                            </div>
                            <div className="conj-stat">
                                <span className="conj-label">Pc</span>
                                <span className="conj-value">{c.pc?.toExponential(1)}</span>
                            </div>
                        </div>
                        {/* Pc visual bar */}
                        <div className="conj-pc-bar">
                            <div
                                className={`conj-pc-fill conj-pc-${c.risk_level.toLowerCase()}`}
                                style={{ width: `${pcToWidth(c.pc)}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
