import React, { useMemo, useEffect, useRef } from 'react';
import Map, { NavigationControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

const LiveMapLibre = (props: any) => {
  const { colors, visibility, initialCenter = [-0.1278, 51.5074], format, onViewportChange, previewData } = props;
    const mapRef = useRef(null);

    // Fly to new location when previewData changes (e.g., user searches a city)
    useEffect(() => {
        if (mapRef.current && previewData?.info?.center) {
            mapRef.current.flyTo({
                center: [previewData.info.center.lon, previewData.info.center.lat],
                zoom: 12,
                duration: 2000
            });
        }
    }, [previewData]);

    // Determine aspect ratio for the container
    const ratios = {
        'poster_vertical': '3 / 4',
        'poster_horizontal': '4 / 3',
        'desktop': '16 / 9',
        'phone': '9 / 16'
    };
    const isWideFormat = format === 'desktop' || format === 'poster_horizontal';

    // Map custom themes to MapLibre style layers
    const mapStyle = useMemo(() => {
        return {
            version: 8,
            sources: {
                carto: {
                    type: 'vector',
                    url: 'https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/tiles.json'
                }
            },
            layers: [
                // Background
                {
                    id: 'background',
                    type: 'background',
                    paint: { 'background-color': colors.bg }
                },
                
                // Landuse & Parks
                {
                    id: 'landcover',
                    type: 'fill',
                    source: 'carto',
                    'source-layer': 'landcover',
                    paint: { 'fill-color': colors.bg }
                },
                {
                    id: 'landuse',
                    type: 'fill',
                    source: 'carto',
                    'source-layer': 'landuse',
                    paint: { 'fill-color': colors.bg }
                },
                {
                    id: 'park',
                    type: 'fill',
                    source: 'carto',
                    'source-layer': 'park',
                    layout: { visibility: visibility?.parks === false ? 'none' : 'visible' },
                    paint: { 'fill-color': colors.parks }
                },

                // Water
                {
                    id: 'water',
                    type: 'fill',
                    source: 'carto',
                    'source-layer': 'water',
                    layout: { visibility: visibility?.water === false ? 'none' : 'visible' },
                    paint: { 'fill-color': colors.water }
                },
                {
                    id: 'waterway',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'waterway',
                    layout: { visibility: visibility?.water === false ? 'none' : 'visible' },
                    paint: { 
                        'line-color': colors.water,
                        'line-width': 1.5
                    }
                },

                // Transportation (Roads)
                // Residential / Street
                {
                    id: 'road_residential',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'transportation',
                    filter: ['in', 'class', 'street', 'street_limited', 'pedestrian', 'path', 'track'],
                    layout: { visibility: visibility?.road_residential === false ? 'none' : 'visible' },
                    paint: {
                        'line-color': colors.road_residential,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.2, 16, 1.5],
                        'line-opacity': 0.6
                    }
                },
                // Tertiary
                {
                    id: 'road_tertiary',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'transportation',
                    filter: ['==', 'class', 'tertiary'],
                    layout: { visibility: visibility?.road_tertiary === false ? 'none' : 'visible' },
                    paint: {
                        'line-color': colors.road_tertiary,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.2, 16, 2]
                    }
                },
                // Secondary
                {
                    id: 'road_secondary',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'transportation',
                    filter: ['==', 'class', 'secondary'],
                    layout: { visibility: visibility?.road_secondary === false ? 'none' : 'visible' },
                    paint: {
                        'line-color': colors.road_secondary,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.2, 16, 3]
                    }
                },
                // Primary
                {
                    id: 'road_primary',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'transportation',
                    filter: ['==', 'class', 'primary'],
                    layout: { visibility: visibility?.road_primary === false ? 'none' : 'visible' },
                    paint: {
                        'line-color': colors.road_primary,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.5, 16, 4]
                    }
                },
                // Motorway
                {
                    id: 'road_motorway',
                    type: 'line',
                    source: 'carto',
                    'source-layer': 'transportation',
                    filter: ['in', 'class', 'motorway', 'trunk'],
                    layout: { visibility: visibility?.road_motorway === false ? 'none' : 'visible' },
                    paint: {
                        'line-color': colors.road_motorway,
                        'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 16, 6]
                    }
                }
            ]
        };
    }, [colors, visibility]);

    return (
        <div 
            style={{
                width: isWideFormat ? '100%' : 'auto',
                height: isWideFormat ? 'auto' : '100%',
                aspectRatio: ratios[format] || '3 / 4',
                margin: '0 auto',
                position: 'relative',
                overflow: 'hidden',
                boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
                borderRadius: '8px'
            }}
        >
            {/* The actual MapLibre WebGL canvas */}
            <Map
                ref={mapRef}
                initialViewState={{
                    longitude: initialCenter[0],
                    latitude: initialCenter[1],
                    zoom: previewData ? 12 : 1.5 // Zoom out for globe view if no city selected
                }}
                mapStyle={mapStyle}
                style={{ width: '100%', height: '100%' }}
                interactive={true}
                dragPan={true}
                scrollZoom={true}
                attributionControl={false}
                onMoveEnd={(e) => {
                    if (onViewportChange) {
                        const { lng, lat } = e.viewState;
                        const zoom = e.viewState.zoom;
                        // Approximate distance in meters based on zoom level
                        // zoom 12 is roughly 15000m, zoom 14 is 6000m, etc.
                        const distance = Math.round(15000 / Math.pow(2, Math.max(0, zoom - 12)));
                        onViewportChange({ lat, lon: lng, distance });
                    }
                }}
            >
                <NavigationControl 
                    position="top-right" 
                    showCompass={false}
                    style={{
                        margin: '24px',
                        borderRadius: '9999px',
                        overflow: 'hidden',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                        background: 'rgba(15, 23, 42, 0.65)',
                        backdropFilter: 'blur(12px)',
                        border: '1px solid rgba(255, 255, 255, 0.1)'
                    }} 
                />
            </Map>

            {/* Typography Overlay (Fixed to screen center) */}
            {/* We recreate the poster text overlay as absolute divs so it stays centered while map pans underneath */}
            {previewData?.info?.spaced_city && (
                <div style={{
                    position: 'absolute',
                    bottom: '10%',
                    left: '0',
                    right: '0',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    pointerEvents: 'none',
                    color: colors.accent,
                    fontFamily: 'Inter, sans-serif'
                }}>
                    <h1 style={{
                        fontSize: 'clamp(3rem, 5vw, 6rem)',
                        fontWeight: 900,
                        textTransform: 'uppercase',
                        margin: 0,
                        lineHeight: 1,
                        textShadow: `0 0 15px ${colors.bg}`,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '90%'
                    }}>
                        {previewData.info.spaced_city}
                    </h1>
                    
                    <div style={{
                        width: '20%',
                        height: '2px',
                        background: colors.accent,
                        margin: '1.5rem 0 1rem 0',
                        opacity: 0.8
                    }} />
                    
                    <h2 style={{
                        fontSize: 'clamp(1rem, 2vw, 2rem)',
                        fontWeight: 300,
                        textTransform: 'uppercase',
                        letterSpacing: '0.2em',
                        margin: '0 0 0.5rem 0',
                        opacity: 0.8
                    }}>
                        {previewData.info.country}
                    </h2>
                    
                    <p style={{
                        fontSize: 'clamp(0.6rem, 1vw, 1rem)',
                        fontWeight: 400,
                        letterSpacing: '0.1em',
                        margin: 0,
                        opacity: 0.6
                    }}>
                        PAN TO EXPLORE • ZOOM FOR DETAIL
                    </p>
                </div>
            )}

            {/* Interactive Badge */}
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
                LIVE MAP ACTIVE
            </div>
        </div>
    );
};

export default LiveMapLibre;
