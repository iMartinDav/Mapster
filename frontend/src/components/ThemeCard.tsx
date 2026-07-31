import { useState, useRef, memo } from 'react'

const RETRY_DELAY_MS = 2500 // Consistent retry delay
const MAX_RETRIES = 3

const ThemeCard = memo(({ id, src, alt, isActive, onSelect, variant = 'desktop' }) => {
  const [imageSrc, setImageSrc] = useState(src)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)
  const [retryCount, setRetryCount] = useState(0)
  const imgRef = useRef(null)

  const [prevSrc, setPrevSrc] = useState(src)
  if (prevSrc !== src) {
    setPrevSrc(src)
    setImageSrc(src)
    setError(false)
    setRetryCount(0)
    setLoading(true)
  }

  const handleError = () => {
    if (retryCount >= MAX_RETRIES) {
      setLoading(false)
      setError(true)
      return
    }

    setLoading(true)
    const nextRetry = retryCount + 1
    setRetryCount(nextRetry)

    setTimeout(() => {
      setImageSrc(`${src}?retry=${nextRetry}`)
    }, RETRY_DELAY_MS)
  }

  const handleLoad = () => {
    setLoading(false)
    setError(false)
  }

  const className = variant === 'mobile' 
    ? `mobile-theme-chip ${isActive ? 'active' : ''}`
    : `theme-card ${isActive ? 'active' : ''}`

  const showLoader = variant === 'desktop' && (loading || error)
  const opacity = variant === 'mobile' 
    ? ((loading || error) ? 0.3 : 1)
    : ((loading || error) ? 0 : 1)

  return (
    <div className={className} onClick={() => onSelect(id)}>
      {showLoader && (
        <div className="card-loader">
          <div className="loading-spinner small"></div>
          {loading && <span className="generating-text">Generating...</span>}
          {error && !loading && (
            <span 
              className="error-text" 
              style={{ fontSize: 'clamp(0.55rem, 1vw, 0.6rem)', color: '#ff4444' }}
            >
              Failed
            </span>
          )}
        </div>
      )}

      <img
        ref={imgRef}
        src={imageSrc}
        alt={alt}
        loading="lazy"
        onLoad={handleLoad}
        onError={handleError}
        style={{ opacity }}
      />
      <span>{alt}</span>
    </div>
  )
})

ThemeCard.displayName = 'ThemeCard'

export default ThemeCard
