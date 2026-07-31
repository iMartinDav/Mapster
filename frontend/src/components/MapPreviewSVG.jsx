import React from 'react';
import { TransformWrapper, TransformComponent, useControls } from 'react-zoom-pan-pinch';
import { PlusIcon, MinusIcon, MaximizeIcon, RotateCcwIcon } from 'lucide-react';

const Controls = () => {
  const { zoomIn, zoomOut, resetTransform, fitToView } = useControls();

  return (
    <div style={{ position: 'absolute', right: '24px', top: '24px', zIndex: 1000 }}>
      <div className="glass-control-group">
        <button
          className="glass-btn glass-btn-divider"
          onClick={() => zoomIn()}
          title="Zoom In"
        >
          <PlusIcon size={20} />
        </button>
        <button
          className="glass-btn glass-btn-divider"
          onClick={() => zoomOut()}
          title="Zoom Out"
        >
          <MinusIcon size={20} />
        </button>
        <button
          className="glass-btn glass-btn-divider"
          onClick={() => fitToView()}
          title="Fit to Screen"
        >
          <MaximizeIcon size={20} />
        </button>
        <button
          className="glass-btn"
          onClick={() => resetTransform()}
          title="Reset"
        >
          <RotateCcwIcon size={20} />
        </button>
      </div>
    </div>
  );
};

const MapPreviewSVG = ({ colors, previewData, visibility, format = 'poster_vertical', isLoading = false, progressMessage = '' }) => {
    const { bg, water, parks, road_primary, road_secondary, road_motorway, road_tertiary, road_residential, accent } = colors;

    if (!previewData) {
        return (
            <div className={`generating-placeholder ${isLoading ? 'is-loading' : ''}`} style={{ backgroundColor: '#0a0a0f', width: '100%', height: '100%' }}>
                <div className="grid-overlay" />
                <div className="placeholder-content">
                    <h3 className="placeholder-title">
                        {isLoading ? 'Crafting Your Map...' : 'Ready to Map'}
                    </h3>
                    <p className="placeholder-subtitle">
                        {isLoading ? (progressMessage || 'Initializing...') : 'Enter a city and click "Create Preview"'}
                    </p>
                </div>
            </div>
        );
    }

    const { viewBox, parks: parkPaths, roads, info } = previewData;

    const ratios = {
        'poster_vertical': '3 / 4',
        'poster_horizontal': '4 / 3',
        'desktop': '16 / 9',
        'phone': '9 / 16'
    };

    const [, , vw, vh] = viewBox.split(' ').map(Number);

    const cssVars = {
        '--map-bg': bg,
        '--map-water': water,
        '--map-ocean': colors.ocean || '#D8F0FA',
        '--map-parks': parks,
        '--map-road-primary': road_primary,
        '--map-road-secondary': road_secondary,
        '--map-road-tertiary': road_tertiary,
        '--map-road-residential': road_residential,
        '--map-road-motorway': road_motorway,
        '--map-accent': accent
    };

    const isWideFormat = format === 'desktop' || format === 'poster_horizontal';

    return (
        <div
            className="map-preview-svg"
            style={{
                ...cssVars,
                width: isWideFormat ? '100%' : 'auto',
                height: isWideFormat ? 'auto' : '100%',
                maxWidth: '100%',
                maxHeight: '100%',
                aspectRatio: ratios[format] || '3 / 4',
                margin: '0 auto',
                backgroundColor: 'var(--map-bg)',
                position: 'relative',
                overflow: 'hidden',
                boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            }}
        >
            <TransformWrapper
                initialScale={1}
                minScale={0.5}
                maxScale={10}
                centerOnInit={true}
                wheel={{ step: 0.1 }}
                smooth={true}
                panning={{ velocityDisabled: true }}
            >
                {/* Custom Glass Controls */}
                <Controls />
                
                <div style={{
                    position: 'absolute',
                    top: '1.5rem',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(15, 23, 42, 0.65)',
                    padding: '0.4rem 1.2rem',
                    borderRadius: '9999px',
                    color: 'rgba(255, 255, 255, 0.9)',
                    fontSize: '0.7rem',
                    fontWeight: '600',
                    pointerEvents: 'none',
                    backdropFilter: 'blur(12px)',
                    letterSpacing: '0.1em',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
                    zIndex: 20,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                }}>
                    INTERACTIVE PREVIEW
                </div>

                <TransformComponent wrapperStyle={{ width: '100%', height: '100%' }}>
                    <svg width="100%" height="100%" viewBox={viewBox} preserveAspectRatio="xMidYMid meet" style={{ display: 'block', fontFamily: 'Inter, sans-serif' }}>
                        {/* Background */}
                        <rect x="-50%" y="-50%" width="200%" height="200%" fill="var(--map-bg)" />

                        {/* Water Bodies */}
                        <g>
                            {(visibility?.ocean ?? true) && previewData?.ocean?.length > 0 && (
                                <path d={previewData.ocean.join(' ')} fill="var(--map-ocean)" fillRule="evenodd" stroke="none" />
                            )}
                            {(visibility?.water ?? true) && previewData?.water?.length > 0 && (
                                <path d={previewData.water.join(' ')} fill="var(--map-water)" fillRule="evenodd" stroke="none" />
                            )}
                        </g>

                        {/* Parks */}
                        <g style={{ display: visibility?.parks === false ? 'none' : 'block' }}>
                            {parkPaths && parkPaths.length > 0 && (
                                <path d={parkPaths.join(' ')} fill="var(--map-parks)" fillRule="evenodd" stroke="none" />
                            )}
                        </g>

                        {/* Roads */}
                        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
                            <g style={{ display: visibility?.road_residential === false ? 'none' : 'block' }}>
                                {roads.residential && roads.residential.length > 0 && (
                                    <path d={roads.residential.join(' ')} stroke="var(--map-road-residential)" strokeWidth="0.4" opacity="0.6" />
                                )}
                            </g>
                            <g style={{ display: visibility?.road_tertiary === false ? 'none' : 'block' }}>
                                {roads.tertiary && roads.tertiary.length > 0 && (
                                    <path d={roads.tertiary.join(' ')} stroke="var(--map-road-tertiary)" strokeWidth="0.6" />
                                )}
                            </g>
                            <g style={{ display: visibility?.road_secondary === false ? 'none' : 'block' }}>
                                {roads.secondary && roads.secondary.length > 0 && (
                                    <path d={roads.secondary.join(' ')} stroke="var(--map-road-secondary)" strokeWidth="0.8" />
                                )}
                            </g>
                            <g style={{ display: visibility?.road_primary === false ? 'none' : 'block' }}>
                                {roads.primary && roads.primary.length > 0 && (
                                    <path d={roads.primary.join(' ')} stroke="var(--map-road-primary)" strokeWidth="1.2" />
                                )}
                            </g>
                            <g style={{ display: visibility?.road_motorway === false ? 'none' : 'block' }}>
                                {roads.motorway && roads.motorway.length > 0 && (
                                    <path d={roads.motorway.join(' ')} stroke="var(--map-road-motorway)" strokeWidth="2.5" />
                                )}
                            </g>
                        </g>

                        {/* Typography Overlay */}
                        <g style={{ pointerEvents: 'none' }}>
                            {(() => {
                                const cityText = info?.spaced_city || info?.city || 'CITY';
                                const baseSize = vh * 0.052;
                                const charCount = cityText.replace(/\s+/g, '').length;
                                const scaleFactor = charCount > 10 ? Math.max(0.5, 10 / charCount) : 1;
                                const fontSize = baseSize * scaleFactor;

                                return (
                                    <text
                                        x={vw / 2}
                                        y={vh * (1 - 0.14)}
                                        fill="var(--map-accent)"
                                        fontSize={fontSize}
                                        fontWeight="900"
                                        textAnchor="middle"
                                        style={{
                                            textTransform: 'uppercase',
                                            textShadow: '0 0 15px var(--map-bg)',
                                            whiteSpace: 'pre'
                                        }}
                                    >
                                        {cityText}
                                    </text>
                                );
                            })()}

                            <line
                                x1={vw * 0.4}
                                y1={vh * (1 - 0.125)}
                                x2={vw * 0.6}
                                y2={vh * (1 - 0.125)}
                                stroke="var(--map-accent)"
                                strokeWidth={vh * 0.0015}
                                opacity="0.8"
                            />

                            <text
                                x={vw / 2}
                                y={vh * (1 - 0.095)}
                                fill="var(--map-accent)"
                                fontSize={vh * 0.019}
                                fontWeight="300"
                                textAnchor="middle"
                                opacity="0.8"
                                style={{
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.2em'
                                }}
                            >
                                {info?.country || 'COUNTRY'}
                            </text>

                            <text
                                x={vw / 2}
                                y={vh * (1 - 0.065)}
                                fill="var(--map-accent)"
                                fontSize={vh * 0.012}
                                fontWeight="400"
                                textAnchor="middle"
                                opacity="0.6"
                                style={{ letterSpacing: '0.1em' }}
                            >
                                {info?.coordinates || '0.0000° N / 0.0000° E'}
                            </text>

                            <text
                                x={vw * 0.98}
                                y={vh * (1 - 0.02)}
                                fill="var(--map-accent)"
                                fontSize={vh * 0.006}
                                textAnchor="end"
                                opacity="0.3"
                            >
                                © OpenStreetMap contributors
                            </text>
                        </g>
                    </svg>
                </TransformComponent>
            </TransformWrapper>
        </div>
    );
};

export default MapPreviewSVG;

// Inject pure CSS for glass controls
if (typeof document !== 'undefined') {
  if (!document.getElementById('map-preview-styles')) {
    const style = document.createElement('style');
    style.id = 'map-preview-styles';
    style.innerHTML = `
      .glass-control-group {
        display: flex;
        flex-direction: column;
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 9999px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        overflow: hidden;
      }
      .glass-btn {
        background: transparent !important;
        border: none !important;
        color: rgba(255,255,255,0.85) !important;
        padding: 0.75rem !important;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease !important;
        line-height: 1 !important;
      }
      .glass-btn:hover:not(:disabled) {
        background: rgba(255,255,255,0.1) !important;
        color: white !important;
      }
      .glass-btn-divider {
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      }
      .react-transform-wrapper {
        width: 100% !important;
        height: 100% !important;
      }
      .react-transform-component {
        width: 100% !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
      }
    `;
    document.head.appendChild(style);
  }
}
