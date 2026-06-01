/**
 * Persistent visual legend — explains what every element on screen means.
 * Always visible in top-right corner during simulation.
 */
export default function Legend() {
    return (
        <div className="legend glass-panel">
            <h3 className="legend-title">What You're Seeing</h3>
            <div className="legend-items">
                <div className="legend-item">
                    <span className="legend-dot" style={{ background: '#00ff88', boxShadow: '0 0 6px #00ff88' }} />
                    <span>Stable track (confident)</span>
                </div>
                <div className="legend-item">
                    <span className="legend-dot" style={{ background: '#ffb800', boxShadow: '0 0 6px #ffb800' }} />
                    <span>Acquiring (uncertain)</span>
                </div>
                <div className="legend-item">
                    <span className="legend-dot" style={{ background: '#555555' }} />
                    <span>Signal lost (coasting)</span>
                </div>
                <div className="legend-item">
                    <span className="legend-line" style={{ background: '#00ff88' }} />
                    <span>Predicted orbit path</span>
                </div>
                <div className="legend-item">
                    <span className="legend-halo" />
                    <span>Position uncertainty</span>
                </div>
                <div className="legend-item">
                    <span className="legend-line legend-line-dashed" style={{ background: '#ff3366' }} />
                    <span>Collision warning</span>
                </div>
            </div>
        </div>
    )
}
