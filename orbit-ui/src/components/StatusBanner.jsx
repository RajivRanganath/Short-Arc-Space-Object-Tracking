import { useState, useEffect, useRef } from 'react'

/**
 * Natural-language status banner that tells viewers what's happening right now.
 * Auto-cycles through recent events, fading in/out smoothly.
 */
export default function StatusBanner({ events, tracks, conjunctions, isRunning, stations }) {
    const [message, setMessage] = useState('')
    const [visible, setVisible] = useState(false)
    const timerRef = useRef(null)
    const lastEventRef = useRef('')

    useEffect(() => {
        if (!isRunning) {
            setMessage('')
            setVisible(false)
            return
        }

        // Priority: conjunction > latest event > tracking summary
        let newMsg = ''

        // 1. Active collision warning (highest priority)
        if (conjunctions && conjunctions.length > 0) {
            const c = conjunctions[0]
            const tca = c.tca_seconds
            const tcaStr = tca > 60 ? `${Math.floor(tca / 60)}m ${Math.floor(tca % 60)}s` : `${Math.floor(tca)}s`
            newMsg = `⚠️ Collision risk: TRK-${String(c.t1).padStart(2, '0')} ↔ TRK-${String(c.t2).padStart(2, '0')} — closest approach in ${tcaStr}`
        }
        // 2. Latest event
        else if (events && events.length > 0) {
            const latest = events[events.length - 1]
            if (latest.type === 'new_track') {
                const id = latest.trackId ?? '??'
                newMsg = `🔍 New object detected — initializing track TRK-${String(id).padStart(2, '0')}`
            } else if (latest.type === 'pruned') {
                const id = latest.trackId ?? '??'
                newMsg = `📉 TRK-${String(id).padStart(2, '0')} signal lost — coasting on predictions`
            } else if (latest.type === 'complete') {
                newMsg = `✅ Simulation complete — all frames processed`
            }
        }

        // 3. Default tracking summary
        if (!newMsg && tracks && tracks.length > 0) {
            const stationCount = stations?.length || 3
            newMsg = `📡 Tracking ${tracks.length} debris object${tracks.length !== 1 ? 's' : ''} across ${stationCount} ground station${stationCount !== 1 ? 's' : ''}`
        }

        // Only update if message changed
        if (newMsg && newMsg !== lastEventRef.current) {
            lastEventRef.current = newMsg
            setVisible(false)

            // Brief fade-out then show new message
            setTimeout(() => {
                setMessage(newMsg)
                setVisible(true)
            }, 200)

            // Auto-dismiss after 6s (except collision warnings)
            clearTimeout(timerRef.current)
            if (!newMsg.startsWith('⚠️')) {
                timerRef.current = setTimeout(() => setVisible(false), 6000)
            }
        }

        return () => clearTimeout(timerRef.current)
    }, [events, conjunctions, tracks, stations, isRunning])

    if (!message || !isRunning) return null

    return (
        <div className={`status-banner ${visible ? 'status-banner-visible' : 'status-banner-hidden'}`}>
            <div className="status-banner-dot" />
            <span className="status-banner-text">{message}</span>
        </div>
    )
}
