/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState
} from 'react'
import { renderToString } from 'react-dom/server'
import L from 'leaflet'
import {
  MapContainer as LeafletMapContainer,
  TileLayer as LeafletTileLayer,
  Marker as LeafletMarker,
  Popup as LeafletPopup,
  Tooltip as LeafletTooltip,
  Circle as LeafletCircle,
  CircleMarker as LeafletCircleMarker,
  Polyline as LeafletPolyline,
  Polygon as LeafletPolygon,
  Rectangle as LeafletRectangle,
  LayerGroup as LeafletLayerGroup,
  FeatureGroup as LeafletFeatureGroup,
  useMap,
  useMapEvents
} from 'react-leaflet'

import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet.fullscreen/dist/Control.FullScreen.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import {
  CircleIcon,
  LayersIcon,
  LoaderCircleIcon,
  MapPinIcon,
  MaximizeIcon,
  MinimizeIcon,
  MinusIcon,
  NavigationIcon,
  PenLineIcon,
  PentagonIcon,
  PlusIcon,
  SquareIcon,
  WaypointsIcon
} from 'lucide-react'

// Pure CSS for premium glassmorphic UI (No Tailwind required)
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.innerHTML = `
    .leaflet-container { background: transparent !important; }
    
    /* Map Controls UI */
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
      transition: all 0.3s ease;
    }
    
    .glass-control-row {
      display: flex;
      flex-direction: row;
      gap: 0.5rem;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-radius: 9999px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 0.25rem;
    }

    /* Important override for Vite's default button styles */
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
      border-radius: 0 !important;
      line-height: 1 !important;
    }
    .glass-btn:hover:not(:disabled) {
      background: rgba(255,255,255,0.1) !important;
      color: white !important;
    }
    .glass-btn:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }
    .glass-btn-divider {
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .glass-btn-round {
      border-radius: 9999px !important;
      padding: 0.75rem !important;
    }
    .glass-btn-round.active {
      background: rgba(34, 211, 238, 0.2) !important;
      color: #22d3ee !important;
      box-shadow: 0 0 15px rgba(34, 211, 238, 0.3);
      border: 1px solid rgba(34, 211, 238, 0.5) !important;
    }

    .glass-fab {
      background: rgba(15, 23, 42, 0.65) !important;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-radius: 50% !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      padding: 0.75rem !important;
      color: white !important;
      box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .glass-fab:hover {
      background: rgba(30, 41, 59, 0.8) !important;
      transform: scale(1.05);
      border-color: rgba(255, 255, 255, 0.2) !important;
    }
    .glass-fab.active {
      background: rgba(34, 211, 238, 0.2) !important;
      border-color: rgba(34, 211, 238, 0.5) !important;
      color: #22d3ee !important;
      box-shadow: 0 0 20px rgba(34, 211, 238, 0.4) !important;
    }

    /* Popups */
    .custom-glass-popup .leaflet-popup-content-wrapper {
      background: rgba(15, 23, 42, 0.75) !important;
      backdrop-filter: blur(12px) !important;
      -webkit-backdrop-filter: blur(12px) !important;
      border: 1px solid rgba(255, 255, 255, 0.1) !important;
      color: white !important;
      border-radius: 1rem !important;
      box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5) !important;
      padding: 0.25rem !important;
    }
    .custom-glass-popup .leaflet-popup-tip {
      background: rgba(15, 23, 42, 0.85) !important;
      border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
      border-left: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    .custom-glass-popup .leaflet-popup-close-button {
      color: rgba(255,255,255,0.7) !important;
      top: 10px !important;
      right: 10px !important;
    }
    .custom-glass-popup .leaflet-popup-close-button:hover {
      color: white !important;
    }
  `;
  document.head.appendChild(style);
}

// Main Map Container
export function Map({ zoom = 13, maxZoom = 19, className = '', children, ...props }) {
  return (
    <LeafletMapContainer
      zoom={zoom}
      maxZoom={maxZoom}
      attributionControl={false}
      zoomControl={false}
      className={`relative w-full h-full min-h-[350px] flex-1 rounded-md overflow-hidden bg-transparent ${className}`}
      style={{ width: '100%', height: '100%', backgroundColor: 'transparent' }}
      {...props}
    >
      {children}
    </LeafletMapContainer>
  )
}

// Markers & Popups
export function MapMarker({
  icon,
  iconAnchor = [12, 12],
  popupAnchor = [0, -12],
  tooltipAnchor,
  children,
  ...props
}) {
  const defaultIcon = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '24px', height: '24px' }}>
       <div style={{ position: 'absolute', width: '16px', height: '16px', background: '#22d3ee', borderRadius: '50%', boxShadow: '0 0 15px rgba(34,211,238,0.8)', border: '2px solid white' }} />
    </div>
  )

  const divIcon = L.divIcon({
    html: renderToString(icon || defaultIcon),
    iconAnchor,
    className: 'custom-leaflet-marker',
    ...(popupAnchor ? { popupAnchor } : {}),
    ...(tooltipAnchor ? { tooltipAnchor } : {})
  })

  return (
    <LeafletMarker icon={divIcon} riseOnHover {...props}>
      {children}
    </LeafletMarker>
  )
}

export function MapPopup({ children, className = '', ...props }) {
  return (
    <LeafletPopup className={`custom-glass-popup ${className}`} {...props}>
      {children}
    </LeafletPopup>
  )
}

export function MapTooltip({ children, side = 'top', className = '', ...props }) {
  return (
    <LeafletTooltip direction={side} className={`custom-leaflet-tooltip ${className}`} {...props}>
      {children}
    </LeafletTooltip>
  )
}

// Vector Shapes
export function MapCircle({ className = '', ...props }) {
  return <LeafletCircle className={className} {...props} />
}

export function MapCircleMarker({ className = '', ...props }) {
  return <LeafletCircleMarker className={className} {...props} />
}

export function MapPolyline({ className = '', ...props }) {
  return <LeafletPolyline className={className} {...props} />
}

export function MapPolygon({ className = '', ...props }) {
  return <LeafletPolygon className={className} {...props} />
}

export function MapRectangle({ className = '', ...props }) {
  return <LeafletRectangle className={className} {...props} />
}

// Controls
export function MapControlContainer({ children, style, ...props }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    L.DomEvent.disableClickPropagation(containerRef.current)
    L.DomEvent.disableScrollPropagation(containerRef.current)
  }, [])

  return (
    <div
      ref={containerRef}
      style={{ zIndex: 1000, cursor: 'default', ...style }}
      {...props}
    >
      {children}
    </div>
  )
}

export function MapZoomControl({ style }) {
  const map = useMap()
  const [zoom, setZoom] = useState(map ? map.getZoom() : 13)

  useMapEvents({
    zoomend: () => {
      if (map) setZoom(map.getZoom())
    }
  })

  return (
    <MapControlContainer style={style}>
      <div className="glass-control-group">
        <button
          type="button"
          onClick={() => map.zoomIn()}
          disabled={map && zoom >= map.getMaxZoom()}
          className="glass-btn glass-btn-divider"
          title="Zoom In"
        >
          <PlusIcon size={20} />
        </button>
        <button
          type="button"
          onClick={() => map.zoomOut()}
          disabled={map && zoom <= map.getMinZoom()}
          className="glass-btn"
          title="Zoom Out"
        >
          <MinusIcon size={20} />
        </button>
      </div>
    </MapControlContainer>
  )
}

export function MapFullscreenControl({ style }) {
  const map = useMap()
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    if (!map) return
    let fullscreenControl = null
    import('leaflet.fullscreen').then(mod => {
      const FullScreen = mod.default || mod
      if (L.Control && !L.Control.FullScreen) {
        L.Control.FullScreen = FullScreen
      }
      fullscreenControl = new L.Control.FullScreen()
      fullscreenControl.addTo(map)
      const container = fullscreenControl.getContainer()
      if (container) container.style.display = 'none'
    })

    const onEnter = () => setIsFullscreen(true)
    const onExit = () => setIsFullscreen(false)
    map.on('enterFullscreen', onEnter)
    map.on('exitFullscreen', onExit)

    return () => {
      if (fullscreenControl) fullscreenControl.remove()
      map.off('enterFullscreen', onEnter)
      map.off('exitFullscreen', onExit)
    }
  }, [map])

  return (
    <MapControlContainer style={style}>
      <button
        type="button"
        onClick={() => map.toggleFullscreen && map.toggleFullscreen()}
        className="glass-fab"
        title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
      >
        {isFullscreen ? <MinimizeIcon size={20} /> : <MaximizeIcon size={20} />}
      </button>
    </MapControlContainer>
  )
}

export function MapLocateControl({ style, onLocationFound }) {
  const map = useMap()
  const [isLocating, setIsLocating] = useState(false)
  const [hasLocation, setHasLocation] = useState(false)

  function startLocating() {
    setIsLocating(true)
    map.locate({ setView: true, maxZoom: 16 })
    map.once('locationfound', e => {
      setIsLocating(false)
      setHasLocation(true)
      if (onLocationFound) onLocationFound(e)
    })
    map.once('locationerror', () => {
      setIsLocating(false)
    })
  }

  return (
    <MapControlContainer style={style}>
      <button
        type="button"
        onClick={startLocating}
        disabled={isLocating}
        className={`glass-fab ${hasLocation ? 'active' : ''}`}
        title="Find My Location"
      >
        {isLocating ? (
          <LoaderCircleIcon size={20} className="animate-spin" />
        ) : (
          <NavigationIcon size={20} />
        )}
      </button>
    </MapControlContainer>
  )
}

// Drawing Control Context & Components
const MapDrawContext = createContext(null)

export function useMapDrawContext() {
  return useContext(MapDrawContext)
}

export function MapDrawControl({ style, onLayersChange, children }) {
  const map = useMap()
  const featureGroupRef = useRef(null)
  const [activeMode, setActiveMode] = useState(null)

  useEffect(() => {
    if (!map) return
    let handleCreated = null
    import('leaflet-draw').then(() => {
      handleCreated = (e) => {
        if (!featureGroupRef.current) return
        featureGroupRef.current.addLayer(e.layer)
        if (onLayersChange) onLayersChange(featureGroupRef.current)
        setActiveMode(null)
      }
      map.on(L.Draw.Event.CREATED, handleCreated)
    })

    return () => {
      if (handleCreated) map.off(L.Draw.Event.CREATED, handleCreated)
    }
  }, [map, onLayersChange])

  return (
    <MapDrawContext.Provider
      value={{
        featureGroupRef,
        activeMode,
        setActiveMode
      }}
    >
      <LeafletFeatureGroup ref={featureGroupRef} />
      <MapControlContainer style={style}>
        <div className="glass-control-row">
          {children}
        </div>
      </MapControlContainer>
    </MapDrawContext.Provider>
  )
}

export function MapDrawPolyline() {
  const drawContext = useMapDrawContext()
  const map = useMap()
  const isActive = drawContext?.activeMode === 'polyline'

  useEffect(() => {
    if (!isActive || !map) return
    let polylineDrawer = null
    import('leaflet-draw').then(() => {
      polylineDrawer = new L.Draw.Polyline(map, {
        shapeOptions: { color: '#22d3ee', weight: 4 }
      })
      polylineDrawer.enable()
    })
    return () => {
      if (polylineDrawer) polylineDrawer.disable()
    }
  }, [isActive, map])

  return (
    <button
      type="button"
      onClick={() => drawContext?.setActiveMode(isActive ? null : 'polyline')}
      className={`glass-btn glass-btn-round ${isActive ? 'active' : ''}`}
      title="Draw Route"
    >
      <WaypointsIcon size={18} />
    </button>
  )
}

export function MapDrawPolygon() {
  const drawContext = useMapDrawContext()
  const map = useMap()
  const isActive = drawContext?.activeMode === 'polygon'

  useEffect(() => {
    if (!isActive || !map) return
    let polygonDrawer = null
    import('leaflet-draw').then(() => {
      polygonDrawer = new L.Draw.Polygon(map, {
        shapeOptions: { color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.3, weight: 3 }
      })
      polygonDrawer.enable()
    })
    return () => {
      if (polygonDrawer) polygonDrawer.disable()
    }
  }, [isActive, map])

  return (
    <button
      type="button"
      onClick={() => drawContext?.setActiveMode(isActive ? null : 'polygon')}
      className={`glass-btn glass-btn-round ${isActive ? 'active' : ''}`}
      title="Draw Zone"
    >
      <PentagonIcon size={18} />
    </button>
  )
}

export function MapDrawCircle() {
  const drawContext = useMapDrawContext()
  const map = useMap()
  const isActive = drawContext?.activeMode === 'circle'

  useEffect(() => {
    if (!isActive || !map) return
    let circleDrawer = null
    import('leaflet-draw').then(() => {
      circleDrawer = new L.Draw.Circle(map, {
        shapeOptions: { color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.3, weight: 3 }
      })
      circleDrawer.enable()
    })
    return () => {
      if (circleDrawer) circleDrawer.disable()
    }
  }, [isActive, map])

  return (
    <button
      type="button"
      onClick={() => drawContext?.setActiveMode(isActive ? null : 'circle')}
      className={`glass-btn glass-btn-round ${isActive ? 'active' : ''}`}
      title="Draw Radius"
    >
      <CircleIcon size={18} />
    </button>
  )
}

export function MapDrawRectangle() {
  const drawContext = useMapDrawContext()
  const map = useMap()
  const isActive = drawContext?.activeMode === 'rectangle'

  useEffect(() => {
    if (!isActive || !map) return
    let rectangleDrawer = null
    import('leaflet-draw').then(() => {
      rectangleDrawer = new L.Draw.Rectangle(map, {
        shapeOptions: { color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.3, weight: 3 }
      })
      rectangleDrawer.enable()
    })
    return () => {
      if (rectangleDrawer) rectangleDrawer.disable()
    }
  }, [isActive, map])

  return (
    <button
      type="button"
      onClick={() => drawContext?.setActiveMode(isActive ? null : 'rectangle')}
      className={`glass-btn glass-btn-round ${isActive ? 'active' : ''}`}
      title="Draw Bounds"
    >
      <SquareIcon size={18} />
    </button>
  )
}
