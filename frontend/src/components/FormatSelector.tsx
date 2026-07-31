import React from 'react';

const FormatSelector = ({ selectedFormat, onSelect }) => {
    const formats = [
        { id: 'poster_vertical', name: 'Portrait', icon: '▮', ratio: '3:4' },
        { id: 'poster_horizontal', name: 'Landscape', icon: '▬', ratio: '4:3' },
        { id: 'desktop', name: 'Desktop', icon: '💻', ratio: '16:9' },
        { id: 'phone', name: 'Phone', icon: '📱', ratio: '9:16' }
    ];

    return (
        <div className="input-group">
            <label>Format</label>
            <div className="format-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'clamp(6px, 1.5vw, 8px)' }}>
                {formats.map(fmt => (
                    <button
                        key={fmt.id}
                        type="button"
                        className={`format-btn ${selectedFormat === fmt.id ? 'active' : ''}`}
                        onClick={() => onSelect(fmt.id)}
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: 'clamp(6px, 1.5vw, 8px) clamp(3px, 1vw, 4px)',
                            background: selectedFormat === fmt.id ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)',
                            border: selectedFormat === fmt.id ? '1px solid rgba(255,255,255,0.5)' : '1px solid transparent',
                            borderRadius: 'clamp(4px, 1vw, 6px)',
                            cursor: 'pointer',
                            color: 'white',
                            fontSize: 'clamp(0.75rem, 1.2vw, 0.8rem)',
                            transition: 'all 0.2s ease',
                            boxSizing: 'border-box'
                        }}
                    >
                        <span style={{ fontSize: 'clamp(1rem, 2vw, 1.2rem)', marginBottom: 'clamp(2px, 0.5vw, 4px)' }}>{fmt.icon}</span>
                        <span style={{ fontSize: 'clamp(0.65rem, 1vw, 0.7rem)' }}>{fmt.name}</span>
                    </button>
                ))}
            </div>
        </div>
    );
};

export default FormatSelector;
