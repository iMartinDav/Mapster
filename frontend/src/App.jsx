// Mapster v1.1 - Hobby plan optimizations
import { useState, useEffect, useCallback } from 'react'
import './App.css'
import { API_URL } from './config'
import LiveMapLibre from './components/LiveMapLibre'
import HistoryModal from './components/HistoryModal'
import FormatSelector from './components/FormatSelector'
import MobileLayout from './components/MobileLayout'
import ThemeCard from './components/ThemeCard'
import useIsMobile from './hooks/useIsMobile'
import { useHistoryRestore } from './hooks/useHistoryRestore'
import LocationAutocomplete from './components/LocationAutocomplete'

const LoadingProgress = ({ progress, message }) => {
  return (
    <div style={{ width: 'min(240px, 80vw)', maxWidth: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'clamp(8px, 1.5vw, 12px)' }}>
      <div className="loading-spinner"></div>
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 'clamp(4px, 1vw, 6px)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'clamp(0.75rem, 1.2vw, 0.8rem)', color: '#aaa', gap: '0.5rem' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{message || 'Processing...'}</span>
          <span style={{ flexShrink: 0 }}>{Math.round(progress)}%</span>
        </div>
        <div style={{ width: '100%', height: 'clamp(3px, 0.5vw, 4px)', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
          <div style={{
            width: `${progress}%`,
            height: '100%',
            background: 'var(--accent)',
            boxShadow: '0 0 10px var(--accent-glow)',
            transition: 'width 0.3s ease-out'
          }}></div>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [themes, setThemes] = useState([])
  const [input, setInput] = useState({
    location: '', // combined location query
    city: '',
    country: '',
    lat: null,
    lon: null,
    theme: 'terracotta',
    distance: 12000,
    format: 'poster_vertical'
  })

  /* Removed broken code block */
  // Helper for fetch with timeout (prevents hanging requests)
  const fetchWithTimeout = async (url, options = {}, timeoutMs = 60000) => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      return response
    } catch (error) {
      clearTimeout(timeoutId)
      if (error.name === 'AbortError') {
        throw new Error('Request timed out')
      }
      throw error
    }
  }

  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState(null)
  const [previewData, setPreviewData] = useState(null)
  const [error, setError] = useState(null)
  const [showHistory, setShowHistory] = useState(false)
  const [isRestoring] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [expandedSection, setExpandedSection] = useState('themes') // 'themes' or 'colors' or null
  const [editMode, setEditMode] = useState(true) // true = show input form, false = show expanded preview
  const [autoDistance, setAutoDistance] = useState(null) // auto-computed distance from city bbox
  const [distanceManuallySet, setDistanceManuallySet] = useState(false) // true if user touched the slider
  const isMobile = useIsMobile()

  function updateColorsFromTheme(theme) {
    setCustomColors({
      bg: theme.bg || '#000000',
      water: theme.water || '#1A1A1A',
      ocean: theme.ocean || '#D8F0FA',
      parks: theme.parks || '#202020',
      road_primary: theme.road_primary || '#FFFFFF',
      road_secondary: theme.road_secondary || '#555555',
      road_tertiary: theme.road_tertiary || theme.road_secondary || '#444444',
      road_residential: theme.road_residential || theme.road_secondary || '#333333',
      road_motorway: theme.road_motorway || '#FF0000',
      accent: theme.accent || theme.text || '#FFFFFF'
    })
  }
  const pollJob = async (jobId, enableLivePreview = true) => {
    return new Promise((resolve, reject) => {
      let attempts = 0
      let consecutiveErrors = 0
      const MAX_ATTEMPTS = 600        // ~5 min at 500ms
      const MAX_CONSECUTIVE_ERRORS = 3
      const POLL_INTERVAL = 500

      const check = async () => {
        attempts++
        if (attempts > MAX_ATTEMPTS) {
          reject(new Error('Job timed out — please try again.'))
          return
        }
        try {
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 10000) // 10s timeout for polling
          
          const res = await fetch(`${API_URL}/job-status/${jobId}`, { signal: controller.signal })
          clearTimeout(timeoutId)
          
          if (res.status === 404) {
            reject(new Error('Job not found — the server may have restarted. Please try again.'))
            return
          }
          if (!res.ok) throw new Error(`Server error (${res.status})`)
          consecutiveErrors = 0  // Reset on success

          const status = await res.json()
          setProgress(status.progress || 0)
          setProgressMsg(status.message || 'Processing...')

          // Live preview: update previewData with partial results as they come in
          if (enableLivePreview && status.partial_data) {
            setPreviewData(status.partial_data)
          }

          if (status.status === 'completed') {
            resolve(status.result)
          } else if (status.status === 'failed') {
            reject(new Error(status.error || 'Job failed'))
          } else {
            setTimeout(check, POLL_INTERVAL)
          }
        } catch (e) {
          consecutiveErrors++
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            reject(e)
          } else {
            // Back off on transient errors, then retry
            setTimeout(check, POLL_INTERVAL * 2)
          }
        }
      }
      check()
    })
  }

  // Customization State
  const [customColors, setCustomColors] = useState({
    bg: '#000000',
    water: '#1A1A1A',
    ocean: '#D8F0FA',
    parks: '#202020',
    road_primary: '#FFFFFF',
    road_secondary: '#555555',
    road_tertiary: '#444444',
    road_residential: '#333333',
    road_motorway: '#FF0000',
    accent: '#FF0000'
  })

  // Layer Visibility State
  const [layerVisibility, setLayerVisibility] = useState({
    water: true,
    ocean: true,
    parks: true,
    road_motorway: true,
    road_primary: true,
    road_secondary: true,
    road_tertiary: true,
    road_residential: true
  })

  // Load themes
  useEffect(() => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000)
    
    fetch(`${API_URL}/themes`, { signal: controller.signal })
      .then(res => {
        clearTimeout(timeoutId)
        return res.json()
      })
      .then(data => {
        setThemes(data.themes)
        if (data.themes.length > 0) {
          const defaultTheme = data.themes.find(t => t.id === 'terracotta') || data.themes[0]
          updateColorsFromTheme(defaultTheme)
        }
      })
      .catch(err => {
        clearTimeout(timeoutId)
        if (err.name !== 'AbortError') {
          console.error("Failed to load themes", err)
        }
      })
  }, [])

  // Update custom colors when theme changes - REMOVED to avoid conflict with history restore
  // logic moved to handleThemeSelect

  const handleColorChange = (key, value) => {
    setCustomColors(prev => ({ ...prev, [key]: value }))
  }

  const handleThemeSelect = useCallback((themeId) => {
    setInput(prev => ({ ...prev, theme: themeId }))
    const selectedTheme = themes.find(t => t.id === themeId)
    if (selectedTheme) {
      updateColorsFromTheme(selectedTheme)
    }
  }, [themes])

  // History restore hook
  const { handleHistorySelect } = useHistoryRestore({
    input,
    previewData,
    setResult,
    setPreviewData,
    setLoading,
    setEditMode,
    setProgress,
    setProgressMsg,
    setShowHistory,
    setInput,
    setDistanceManuallySet,
    setCustomColors,
    setLayerVisibility,
    themes,
    updateColorsFromTheme,
    pollJob,
    setError
  })

  // Smart Defaults: specific logic for zoom levels
  // Smart Defaults: residential roads disabled to prevent OOM on dense cities
  // (previously auto-enabled residential for small zoom levels)

  const fetchPreview = async (params) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setPreviewData(null)
    setEditMode(false)
    setProgress(100)
    setProgressMsg('Flying to location...')

    try {
      if (!params.lat || !params.lon) {
        throw new Error('Please select a valid location from the dropdown')
      }
      
      // We set a mock previewData that tells LiveMapLibre and the UI we are ready
      setPreviewData({
        info: {
          center: { lat: params.lat, lon: params.lon },
          city: params.city,
          country: params.country,
          spaced_city: (params.city || '').split('').join(' ')
        }
      })
    } catch (err) {
      setError(err.message)
      setEditMode(true)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    fetchPreview(input)
  }

  const handleFormatChange = (fmt) => {
    // Skip if same format already selected
    if (fmt === input.format) return

    const updatedInput = { ...input, format: fmt }
    setInput(updatedInput)

    // SVG paths are format-specific (different viewport dimensions & coordinate
    // transforms), so we must re-fetch when switching formats. The Level 1 data
    // cache is format-independent, so this only regenerates SVG paths — fast.
    if (previewData && !loading) {
      fetchPreview(updatedInput)
    }
  }

  const handleGenerateHighRes = async () => {
    setGenerating(true)
    setError(null)
    setProgress(0)
    setProgressMsg('Initializing generation...')

    const payload = {
      ...input,
      lat: input.lat || previewData?.info?.center?.lat,
      lon: input.lon || previewData?.info?.center?.lon,
      custom_colors: customColors,
      layer_visibility: layerVisibility,
      use_cache: true
    }

    try {
      const res = await fetchWithTimeout(`${API_URL}/start-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }, 60000)

      if (!res.ok) throw new Error('Generation failed - check backend logs')

      const { job_id } = await res.json()
      const data = await pollJob(job_id)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  // Handler for "New Map" button
  const handleNewMap = () => {
    setEditMode(true)
    setPreviewData(null)
    setResult(null)
    setError(null)
    setDistanceManuallySet(false)
    setAutoDistance(null)
  }

  // Render mobile-specific history modal wrapper that passes onSelect through
  const MobileHistoryModal = ({ onClose }) => (
    <HistoryModal
      onClose={onClose}
      onSelect={handleHistorySelect}
    />
  )

  if (isMobile) {
    return (
      <MobileLayout
        input={input} setInput={setInput}
        themes={themes}
        customColors={customColors} setCustomColors={setCustomColors}
        layerVisibility={layerVisibility} setLayerVisibility={setLayerVisibility}
        loading={loading} generating={generating} result={result}
        previewData={previewData}
        error={error} setError={setError}
        progress={progress} progressMsg={progressMsg}
        editMode={editMode}
        autoDistance={autoDistance} distanceManuallySet={distanceManuallySet}
        showHistory={showHistory} setShowHistory={setShowHistory}
        handleSubmit={handleSubmit}
        handleThemeSelect={handleThemeSelect}
        handleColorChange={handleColorChange}
        handleFormatChange={handleFormatChange}
        handleGenerateHighRes={handleGenerateHighRes}
        handleNewMap={handleNewMap}
        updateColorsFromTheme={updateColorsFromTheme}
        fetchPreview={fetchPreview}
        HistoryModal={MobileHistoryModal}
      />
    )
  }

  return (
    <div className="container">
      <main className="main-content with-sidebar">
        {/* Left Panel */}
        <div className="left-panel glass-panel">
          {editMode ? (
            /* Edit mode: City input form */
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div className="sidebar-header" style={{
                marginBottom: 'clamp(0.75rem, 1.5vw, 1rem)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'clamp(0.5rem, 1.5vw, 0.75rem)'
              }}>
                <h1 className="logo" style={{ fontSize: 'clamp(1.5rem, 4vw, 1.8rem)', margin: 0 }}>Map<span>ster</span></h1>
                <a href="https://x.com/MartinDAVILA" target="_blank" rel="noopener noreferrer" className="creator-credit">
                  created by MartinDAVILA
                </a>
                <a
                  href="https://ko-fi.com/P5P51SSYA9"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-block',
                    transition: 'transform 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
                  onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                >
                  <img
                    src="https://ko-fi.com/img/githubbutton_sm.svg"
                    alt="Support me on Ko-fi"
                    style={{ height: 'clamp(28px, 3vw, 32px)', border: 'none', maxWidth: '100%' }}
                  />
                </a>
              </div>

              <div className="input-group">
                <label>Search Location</label>
                <LocationAutocomplete 
                  initialQuery={input.location}
                  onSelect={(place) => {
                    const address = place.address || {};
                    const city = address.city || address.town || address.village || address.state || address.country || '';
                    const country = address.country || '';
                    const lat = parseFloat(place.lat);
                    const lon = parseFloat(place.lon);
                    
                    // compute distance from boundingbox if available
                    let dist = 12000;
                    if (place.boundingbox) {
                        const [lat1, lat2, lon1, lon2] = place.boundingbox.map(parseFloat);
                        const dLat = (lat2 - lat1) * 111000; // rough meters
                        const dLon = (lon2 - lon1) * 111000 * Math.cos(lat * Math.PI / 180);
                        dist = Math.max(Math.round(Math.max(dLat, dLon) / 2), 2000);
                        if (dist > 500000) dist = 500000; // cap at 500km
                    }

                    const updatedInput = { 
                      ...input, 
                      location: place.display_name,
                      city, 
                      country,
                      lat,
                      lon,
                      distance: dist
                    };
                    setInput(updatedInput);
                    setError(null);
                    // Instantly trigger preview
                    fetchPreview(updatedInput);
                    return updatedInput;
                  }}
                />
                {input.lat && input.lon && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '8px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>Coordinates</span>
                    <span style={{ fontFamily: 'monospace' }}>{input.lat.toFixed(4)}°, {input.lon.toFixed(4)}°</span>
                  </div>
                )}
              </div>

              <FormatSelector
                selectedFormat={input.format}
                onSelect={handleFormatChange}
              />

              <div className="input-group">
                <label>
                  Zoom Level / Radius ({input.distance.toLocaleString()}m)
                  {!distanceManuallySet && <span style={{ opacity: 0.5, fontSize: '0.8em', marginLeft: '0.5em' }}>auto</span>}
                </label>
                <input
                  type="range"
                  min="2000"
                  max="500000"
                  step="1000"
                  value={input.distance}
                  onChange={e => {
                    setDistanceManuallySet(true)
                    setInput({ ...input, distance: parseInt(e.target.value) })
                  }}
                  style={{ width: '100%' }}
                />
                <div className="range-labels">
                  <span>Detailed</span>
                  <span>City</span>
                  <span>Region/Country</span>
                </div>
              </div>

              <button type="submit" className="generate-btn" disabled={loading || generating || !!error}>
                {loading ? 'LOADING MAP...' : 'CREATE PREVIEW'}
              </button>

              {error && <div className="error">{error}</div>}

              <p style={{ opacity: 0.5, fontSize: 'clamp(0.65rem, 1vw, 0.7rem)', textAlign: 'center', marginTop: 'auto' }}>
                Create stunning city map posters in seconds.
              </p>
            </form>
          ) : (
            /* Preview mode: Themes + New Map button */
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <button
                className="new-map-btn"
                onClick={handleNewMap}
              >
                ← New Map
              </button>

              <h3 style={{ fontSize: 'clamp(0.85rem, 1.2vw, 0.95rem)', marginBottom: '0.75rem' }}>Themes</h3>
              <div className="theme-grid" style={{ flex: 1, overflowY: 'auto' }}>
                {themes.map(t => (
                  <ThemeCard key={t.id} id={t.id} src={t.preview_url} alt={t.name} isActive={input.theme === t.id} onSelect={handleThemeSelect} variant="desktop" />
                ))}
              </div>

              <FormatSelector
                selectedFormat={input.format}
                onSelect={handleFormatChange}
              />
            </div>
          )}
        </div>

        <div className="preview-area">
          {generating ? (
            <div className="placeholder glass-panel">
              <LoadingProgress
                progress={progress}
                message={progressMsg}
              />
            </div>
          ) : result ? (
            <div className="result fade-in">
              <img src={`${API_URL}${result.image_url}`} alt="Map Poster" />
              <div className="actions">
                <button
                  className="secondary-btn"
                  onClick={() => setResult(null)}
                  disabled={isRestoring}
                  style={{ opacity: isRestoring ? 0.7 : 1, cursor: isRestoring ? 'wait' : 'pointer' }}
                >
                  {isRestoring ? 'Restoring...' : 'Edit Design'}
                </button>
                <a
                  href={`${API_URL}${result.image_url}`}
                  download={result.filename}
                  className="download-btn"
                >
                  Download High-Res
                </a>
              </div>
            </div>
          ) : (
            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ flex: 1, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(2px, 0.5vw, 4px)', position: 'relative' }}>
                <LiveMapLibre
                  colors={customColors}
                  visibility={layerVisibility}
                  format={input.format}
                  initialCenter={previewData?.info?.center ? [previewData.info.center.lon, previewData.info.center.lat] : [-0.1278, 51.5074]}
                  previewData={previewData}
                  onViewportChange={({ lat, lon, distance }) => {
                    setInput(prev => ({ ...prev, lat, lon, distance }));
                  }}
                />
                {/* Loading overlay - shows progress while preview renders live */}
                {loading && (
                  <div style={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    background: 'linear-gradient(transparent, rgba(0,0,0,0.8))',
                    padding: 'clamp(1rem, 2vw, 1.5rem)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '0.5rem'
                  }}>
                    <div style={{ fontSize: 'clamp(0.7rem, 1vw, 0.8rem)', opacity: 0.9 }}>{progressMsg}</div>
                    <div style={{ width: '80%', height: '4px', background: 'rgba(255,255,255,0.2)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ width: `${progress}%`, height: '100%', background: 'linear-gradient(90deg, #667eea, #764ba2)', transition: 'width 0.3s ease' }} />
                    </div>
                  </div>
                )}
              </div>
              {previewData && !loading && (
                <div className="preview-bottom-bar">
                  <button
                    className="bottom-bar-btn secondary"
                    onClick={() => setShowHistory(true)}
                  >
                    <span className="btn-text">History</span>
                  </button>
                  <button
                    className="bottom-bar-btn primary"
                    onClick={handleGenerateHighRes}
                  >
                    <span className="btn-text">Generate High-Res PNG</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className={`right-panel glass-panel ${!editMode ? 'preview-mode-panel' : ''}`}>
          {/* In edit mode: show themes and colors */}
          {editMode && (
            <div className={`accordion-section theme-section ${expandedSection === 'themes' ? 'expanded' : 'collapsed'}`}>
              <div
                className="accordion-header"
                onClick={() => setExpandedSection(expandedSection === 'themes' ? null : 'themes')}
              >
                <h3>Theme</h3>
                <span className="accordion-icon">{expandedSection === 'themes' ? '▼' : '▶'}</span>
              </div>
              <div className="accordion-content">
                <div className="theme-grid">
                  {themes.length === 0 && <div className="loading-themes">Loading themes...</div>}
                  {themes.map(t => (
                    <ThemeCard key={t.id} id={t.id} src={t.preview_url} alt={t.name} isActive={input.theme === t.id} onSelect={handleThemeSelect} variant="desktop" />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className={`accordion-section color-controls ${!editMode ? 'expanded' : (expandedSection === 'colors' ? 'expanded' : 'collapsed')}`}>
            {editMode ? (
              <div
                className="accordion-header"
                onClick={() => setExpandedSection(expandedSection === 'colors' ? null : 'colors')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <h3>Custom Colors</h3>
                  <button
                    type="button"
                    className="reset-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      const selectedTheme = themes.find(t => t.id === input.theme)
                      if (selectedTheme) updateColorsFromTheme(selectedTheme)
                    }}
                    title="Reset to theme defaults"
                  >
                    ⟳ Reset
                  </button>
                </div>
                <span className="accordion-icon">{expandedSection === 'colors' ? '▼' : '▶'}</span>
              </div>
            ) : (
              <div className="color-header-simple">
                <h3>Colors & Layers</h3>
                <button
                  type="button"
                  className="reset-btn"
                  onClick={() => {
                    const selectedTheme = themes.find(t => t.id === input.theme)
                    if (selectedTheme) updateColorsFromTheme(selectedTheme)
                  }}
                  title="Reset to theme defaults"
                >
                  ⟳ Reset
                </button>
              </div>
            )}
            <div className="accordion-content">
              <div className="color-grid">
              <div className="color-item">
                <span>Background</span>
                <input type="color" value={customColors.bg} onChange={e => handleColorChange('bg', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.water} onChange={e => setLayerVisibility(prev => ({ ...prev, water: e.target.checked }))} title="Toggle visibility" />
                  <span>Water Bodies</span>
                </div>
                <input type="color" value={customColors.water} onChange={e => handleColorChange('water', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.ocean} onChange={e => setLayerVisibility(prev => ({ ...prev, ocean: e.target.checked }))} title="Toggle visibility" />
                  <span>Ocean / Coast</span>
                </div>
                <input type="color" value={customColors.ocean} onChange={e => handleColorChange('ocean', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.parks} onChange={e => setLayerVisibility(prev => ({ ...prev, parks: e.target.checked }))} title="Toggle visibility" />
                  <span>Parks / Green</span>
                </div>
                <input type="color" value={customColors.parks} onChange={e => handleColorChange('parks', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.road_motorway} onChange={e => setLayerVisibility(prev => ({ ...prev, road_motorway: e.target.checked }))} title="Toggle visibility" />
                  <span>Motorways</span>
                </div>
                <input type="color" value={customColors.road_motorway} onChange={e => handleColorChange('road_motorway', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.road_primary} onChange={e => setLayerVisibility(prev => ({ ...prev, road_primary: e.target.checked }))} title="Toggle visibility" />
                  <span>Main Roads</span>
                </div>
                <input type="color" value={customColors.road_primary} onChange={e => handleColorChange('road_primary', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.road_secondary} onChange={e => setLayerVisibility(prev => ({ ...prev, road_secondary: e.target.checked }))} title="Toggle visibility" />
                  <span>Secondary Roads</span>
                </div>
                <input type="color" value={customColors.road_secondary} onChange={e => handleColorChange('road_secondary', e.target.value)} />
              </div>
              <div className="color-item">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" checked={layerVisibility.road_tertiary} onChange={e => setLayerVisibility(prev => ({ ...prev, road_tertiary: e.target.checked }))} title="Toggle visibility" />
                  <span>Tertiary Roads</span>
                </div>
                <input type="color" value={customColors.road_tertiary} onChange={e => handleColorChange('road_tertiary', e.target.value)} />
              </div>
              {/* Residential roads hidden — skipped in fetch to prevent OOM on dense cities */}
              <div className="color-item">
                <span>Accent Color</span>
                <input type="color" value={customColors.accent} onChange={e => handleColorChange('accent', e.target.value)} />
              </div>
            </div>
            </div>
          </div>

          {/* History button - only in edit mode */}
          {editMode && (
            <button
              className="history-btn"
              onClick={() => setShowHistory(true)}
            >
              <span>🕒</span> Previously Generated Maps
            </button>
          )}
        </div>
      </main>

      {showHistory && (
        <HistoryModal
          onClose={() => setShowHistory(false)}
          onSelect={handleHistorySelect}
        />
      )}
    </div>
  )
}

export default App
