/**
 * Compact event feed — color-coded borders, no emoji clutter.
 */
export default function EventFeed({ events }) {
    if (!events || events.length === 0) return null

    const typeStyles = {
        new_track: { color: '#00e5ff', prefix: 'ACQ' },
        pruned: { color: '#ff4466', prefix: 'LOST' },
        warning: { color: '#ffaa00', prefix: 'WARN' },
        success: { color: '#00ff88', prefix: 'OK' },
        info: { color: '#8888cc', prefix: 'SYS' },
        complete: { color: '#00e5ff', prefix: 'DONE' },
        maneuver: { color: '#ff00ff', prefix: 'MNVR' },
    }

    // Show only 4 most recent events
    const recent = events.slice(-4)

    return (
        <div className="event-feed glass-panel">
            <h2 className="event-feed-title">Event Log</h2>
            <div className="event-feed-list">
                {recent.map((ev, i) => {
                    const style = typeStyles[ev.type] || typeStyles.info
                    // Strip emoji from message for cleaner look
                    const cleanMsg = ev.message.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FEFF}]/gu, '').trim()
                    return (
                        <div
                            key={i}
                            className="event-item"
                            style={{
                                borderLeftColor: style.color,
                                animation: i === recent.length - 1 ? 'fadeSlideIn 0.3s ease-out' : 'none',
                            }}
                        >
                            <span className="event-type-tag" style={{ color: style.color }}>
                                {style.prefix}
                            </span>
                            <span className="event-text">
                                {cleanMsg}
                            </span>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
