import { useCallback } from 'react'
import { API_URL } from '../config'

/**
 * Shared hook for restoring maps from history in both desktop and mobile layouts
 * @param {Object} params
 * @param {Object} params.input - Current input state
 * @param {Object} params.previewData - Current preview data
 * @param {Function} params.setResult - Setter for result state
 * @param {Function} params.setPreviewData - Setter for preview data
 * @param {Function} params.setLoading - Setter for loading state
 * @param {Function} params.setEditMode - Setter for edit mode (optional, desktop only)
 * @param {Function} params.setProgress - Setter for progress state
 * @param {Function} params.setProgressMsg - Setter for progress message
 * @param {Function} params.setShowHistory - Setter for history modal visibility
 * @param {Function} params.setInput - Setter for input state
 * @param {Function} params.setDistanceManuallySet - Setter for distance manual flag
 * @param {Function} params.setCustomColors - Setter for custom colors
 * @param {Function} params.setLayerVisibility - Setter for layer visibility
 * @param {Array} params.themes - Available themes array
 * @param {Function} params.updateColorsFromTheme - Function to update colors from theme
 * @param {Function} params.pollJob - Function to poll job status
 * @param {Function} params.setError - Setter for error state
 */
export const useHistoryRestore = ({
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
}) => {
  const handleHistorySelect = useCallback(async (item) => {
    const imageUrl = item.image_url || item.url
    if (!item || !imageUrl) return

    // Skip reload if same city is already loaded
    if (item.city && item.city === input.city && item.country === input.country && previewData) {
      setShowHistory(false)
      return
    }

    // Reset state
    setResult(null)
    setPreviewData(null)
    setLoading(true)
    if (setEditMode) setEditMode(false) // Desktop only
    setProgress(0)
    setProgressMsg('Restoring interactive preview...')
    setShowHistory(false)

    // Restore inputs
    if (item.city) {
      const newInput = {
        city: item.city,
        country: item.country || '',
        distance: item.distance || 12000,
        theme: item.theme || 'terracotta',
        format: item.format || 'poster_vertical'
      }
      setInput(newInput)
      setDistanceManuallySet(true)

      // Restore colors
      if (item.custom_colors) {
        setCustomColors(item.custom_colors)
      } else if (item.theme) {
        const themeData = themes.find(t => t.id === item.theme)
        if (themeData) updateColorsFromTheme(themeData)
      }

      // Restore layer visibility
      if (item.layer_visibility) {
        setLayerVisibility(item.layer_visibility)
      }

      // Fetch SVG preview data using async job endpoint
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 60000) // 60s timeout

        const res = await fetch(`${API_URL}/start-restore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: item.filename }),
          signal: controller.signal
        })

        clearTimeout(timeoutId)

        if (!res.ok) throw new Error('Restore failed - check backend logs')

        const { job_id } = await res.json()
        const data = await pollJob(job_id)
        setPreviewData(data)
      } catch (e) {
        if (e.name === 'AbortError') {
          console.error('Restore request timed out')
          setError('Request timed out. Please try again.')
        } else {
          console.error('Failed to restore preview', e)
          setError('Failed to restore interactive map. Please try again.')
        }
      } finally {
        setLoading(false)
      }
    }
  }, [
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
  ])

  return { handleHistorySelect }
}
