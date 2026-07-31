import React, { useState } from 'react'
import { API_URL } from '../config'
import LiveMapLibre from './LiveMapLibre'
import FormatSelector from './FormatSelector'
import ThemeCard from './ThemeCard'
import LocationAutocomplete from './LocationAutocomplete'

const MobileLayout = (props: any) => {
  const {
  // State
  input, setInput,
  themes,
  customColors,
  layerVisibility, setLayerVisibility,
  loading, generating, result,
  previewData,
  error, setError,
  progress, progressMsg,
  editMode,
  distanceManuallySet,
  showHistory, setShowHistory,
  // Handlers
  handleSubmit,
  handleThemeSelect,
  handleColorChange,
  handleFormatChange,
  handleGenerateHighRes,
  handleNewMap,
  updateColorsFromTheme,
  fetchPreview,
  // History modal component
  // eslint-disable-next-line no-unused-vars
  HistoryModal: HistoryModalComponent
} = props;
  const [showCustomize, setShowCustomize] = useState(false)
  const [activeTab, setActiveTab] = useState('themes') // 'themes' | 'colors'

  // -- INPUT SCREEN --
  if (editMode) {
    return (
      <div className="mobile-container">
        <form onSubmit={handleSubmit} className="mobile-input-screen">
          <div className="mobile-header">
            <h1 className="logo" style={{ fontSize: '1.8rem', margin: 0 }}>Map<span>ster</span></h1>
            <a href="https://x.com/MartinDAVILA" target="_blank" rel="noopener noreferrer" className="creator-credit">
              created by MartinDAVILA
            </a>
          </div>

          <div className="mobile-form-fields">
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
                  
                  let dist = 12000;
                  if (place.boundingbox) {
                      const [lat1, lat2, lon1, lon2] = place.boundingbox.map(parseFloat);
                      const dLat = (lat2 - lat1) * 111000;
                      const dLon = (lon2 - lon1) * 111000 * Math.cos(lat * Math.PI / 180);
                      dist = Math.max(Math.round(Math.max(dLat, dLon) / 2), 2000);
                      if (dist > 500000) dist = 500000;
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
                  if (setError) setError(null);
                  
                  // Instantly trigger preview
                  if (fetchPreview) fetchPreview(updatedInput);
                  
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
                Zoom ({input.distance.toLocaleString()}m)
                {!distanceManuallySet && <span style={{ opacity: 0.5, fontSize: '0.8em', marginLeft: '0.5em' }}>auto</span>}
              </label>
              <input
                type="range"
                min="2000"
                max="500000"
                step="1000"
                value={input.distance}
                onChange={e => setInput({ ...input, distance: parseInt(e.target.value) })}
                style={{ width: '100%' }}
              />
              <div className="range-labels">
                <span>Detailed</span>
                <span>City</span>
                <span>Region/Country</span>
              </div>
            </div>
          </div>

          <div className="mobile-form-actions">
            <button type="submit" className="generate-btn" disabled={loading || generating || !!error}>
              {loading ? 'LOADING MAP...' : 'CREATE PREVIEW'}
            </button>

            <button
              type="button"
              className="mobile-history-btn"
              onClick={() => setShowHistory(true)}
            >
              Previously Generated Maps
            </button>
          </div>

          {error && <div className="error">{error}</div>}
        </form>

        {showHistory && (
          <HistoryModalComponent onClose={() => setShowHistory(false)} />
        )}
      </div>
    )
  }

  // -- RESULT SCREEN --
  if (result) {
    return (
      <div className="mobile-container">
        <div className="mobile-result-screen">
          <div className="mobile-result-image">
            <img src={`${API_URL}${result.image_url}`} alt="Map Poster" />
          </div>
          <div className="mobile-result-actions">
            <button className="mobile-action-btn secondary" onClick={() => handleNewMap()}>
              New Map
            </button>
            <a
              href={`${API_URL}${result.image_url}`}
              download={result.filename}
              className="mobile-action-btn primary"
            >
              Download PNG
            </a>
          </div>
        </div>
      </div>
    )
  }

  // -- GENERATING SCREEN --
  if (generating) {
    return (
      <div className="mobile-container">
        <div className="mobile-generating">
          <div className="loading-spinner"></div>
          <div className="mobile-progress-text">{progressMsg || 'Processing...'}</div>
          <div className="mobile-progress-bar">
            <div className="mobile-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="mobile-progress-pct">{Math.round(progress)}%</div>
        </div>
      </div>
    )
  }

  // -- PREVIEW SCREEN --
  return (
    <div className="mobile-container">
      <div className="mobile-preview-screen">
        {/* Top bar */}
        <div className="mobile-preview-topbar">
          <button className="mobile-back-btn" onClick={handleNewMap}>
            ← Back
          </button>
          <span className="mobile-city-label">{input.city}</span>
        </div>

        {/* Map preview - takes remaining space */}
        <div className="mobile-preview-map">
          <LiveMapLibre
            colors={customColors}
            visibility={layerVisibility}
            format={input.format}
            initialCenter={previewData?.info?.center ? [previewData.info.center.lon, previewData.info.center.lat] : [-0.1278, 51.5074]}
            previewData={previewData}
            onViewportChange={({ lat, lon, distance }) => {
              // Update input distance and center for poster generation
              setInput(prev => ({ ...prev, lat, lon, distance }));
            }}
          />
          {loading && (
            <div className="mobile-loading-overlay">
              <div style={{ fontSize: '0.8rem', opacity: 0.9 }}>{progressMsg}</div>
              <div className="mobile-loading-bar">
                <div className="mobile-loading-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
        </div>

        {/* Bottom action bar - always visible */}
        {previewData && !loading && (
          <div className="mobile-action-bar">
            <button
              className="mobile-action-btn secondary"
              onClick={() => setShowCustomize(prev => !prev)}
            >
              Customize
            </button>
            <button
              className="mobile-action-btn primary"
              onClick={handleGenerateHighRes}
            >
              Generate PNG
            </button>
          </div>
        )}

        {/* Backdrop overlay when customize panel is open */}
        {previewData && !loading && showCustomize && (
          <div
            className="mobile-customize-backdrop"
            onClick={() => setShowCustomize(false)}
          />
        )}

        {/* Customize panel (replaces old bottom sheet) */}
        {previewData && !loading && (
          <div className={`mobile-customize-panel ${showCustomize ? 'open' : 'closed'}`}>
            <div className="mobile-panel-header">
              <div className="mobile-sheet-tabs">
                <button
                  className={`mobile-tab ${activeTab === 'themes' ? 'active' : ''}`}
                  onClick={() => setActiveTab('themes')}
                >
                  Themes
                </button>
                <button
                  className={`mobile-tab ${activeTab === 'colors' ? 'active' : ''}`}
                  onClick={() => setActiveTab('colors')}
                >
                  Colors & Layers
                </button>
              </div>
              <button
                className="mobile-panel-close"
                onClick={() => setShowCustomize(false)}
                aria-label="Close customize panel"
              >
                ✕
              </button>
            </div>

            <div className="mobile-sheet-content">
              {activeTab === 'themes' && (
                <div className="mobile-theme-scroll">
                  {themes.map(t => (
                    <ThemeCard
                      key={t.id}
                      id={t.id}
                      src={t.preview_url}
                      alt={t.name}
                      isActive={input.theme === t.id}
                      onSelect={handleThemeSelect}
                      variant="mobile"
                    />
                  ))}
                </div>
              )}

              {activeTab === 'colors' && (
                <div className="mobile-colors-list">
                  <div className="mobile-color-row">
                    <span>Background</span>
                    <input type="color" value={customColors.bg} onChange={e => handleColorChange('bg', e.target.value)} />
                  </div>
                  {[
                    { key: 'water', label: 'Water', vis: 'water' },
                    { key: 'ocean', label: 'Ocean', vis: 'ocean' },
                    { key: 'parks', label: 'Parks', vis: 'parks' },
                    { key: 'road_motorway', label: 'Motorways', vis: 'road_motorway' },
                    { key: 'road_primary', label: 'Main Roads', vis: 'road_primary' },
                    { key: 'road_secondary', label: 'Secondary', vis: 'road_secondary' },
                    { key: 'road_tertiary', label: 'Tertiary', vis: 'road_tertiary' },
                    { key: 'road_residential', label: 'Residential', vis: 'road_residential' },
                  ].map(({ key, label, vis }) => (
                    <div key={key} className="mobile-color-row">
                      <div className="mobile-color-label">
                        <input
                          type="checkbox"
                          checked={layerVisibility[vis]}
                          onChange={e => setLayerVisibility(prev => ({ ...prev, [vis]: e.target.checked }))}
                        />
                        <span>{label}</span>
                      </div>
                      <input type="color" value={customColors[key]} onChange={e => handleColorChange(key, e.target.value)} />
                    </div>
                  ))}
                  <div className="mobile-color-row">
                    <span>Accent</span>
                    <input type="color" value={customColors.accent} onChange={e => handleColorChange('accent', e.target.value)} />
                  </div>
                  <button
                    className="mobile-reset-colors"
                    onClick={() => {
                      const selectedTheme = themes.find(t => t.id === input.theme)
                      if (selectedTheme) updateColorsFromTheme(selectedTheme)
                    }}
                  >
                    Reset to Theme Defaults
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showHistory && (
        <HistoryModalComponent onClose={() => setShowHistory(false)} />
      )}

      {error && (
        <div className="mobile-error-toast">{error}</div>
      )}
    </div>
  )
}

export default MobileLayout
