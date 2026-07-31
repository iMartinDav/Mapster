# Map2Poster High Priority Fixes - Feb 1, 2026

## 🔴 HIGH PRIORITY ISSUES RESOLVED

### 1. ✅ Duplicate Code: ThemePreview & MobileThemeCard
**Problem:** Nearly identical theme card components in App.jsx and MobileLayout.jsx (~115 lines duplicated)

**Solution:**
- Created shared `ThemeCard` component (`frontend/src/components/ThemeCard.jsx`)
- Supports both desktop and mobile variants via `variant` prop
- Consolidated retry logic with consistent `RETRY_DELAY_MS` (2500ms)
- Replaced `ThemePreview` in App.jsx with `ThemeCard` (variant="desktop")
- Replaced `MobileThemeCard` in MobileLayout.jsx with `ThemeCard` (variant="mobile")

**Files changed:**
- `frontend/src/components/ThemeCard.jsx` (new)
- `frontend/src/App.jsx` (imports and component usage)
- `frontend/src/components/MobileLayout.jsx` (imports and component usage)

---

### 2. ✅ Duplicate History Restore Logic
**Problem:** ~40 lines of history restoration code duplicated in App.jsx (desktop) and MobileHistoryModal

**Solution:**
- Created `useHistoryRestore` hook (`frontend/src/hooks/useHistoryRestore.js`)
- Centralizes all history restore logic with proper error handling
- **Includes request timeout protection (60s)** for restore endpoint
- Updated both App.jsx HistoryModal and MobileHistoryModal to use the shared hook
- Eliminated ~80 lines of duplicate code

**Files changed:**
- `frontend/src/hooks/useHistoryRestore.js` (new)
- `frontend/src/App.jsx` (uses hook, simplified both modals)

---

### 3. ✅ Memory Leak Risk: Daemon Threads
**Problem:** Background cloud uploads used `daemon=True` threads. If main process exits during upload, data is lost.

**Solution:**
- Replaced daemon threads with `ThreadPoolExecutor` (max_workers=2)
- Added `cleanup()` method to MapPosterGenerator class
- Executor can wait for pending uploads to complete on shutdown
- Prevents data loss while maintaining non-blocking behavior

**Files changed:**
- `create_map_poster.py`:
  - Added `_upload_executor` in `__init__`
  - Replaced `threading.Thread(..., daemon=True)` with `executor.submit()`
  - Added `cleanup(wait=True, timeout=30)` method

---

### 4. ✅ No Request Timeout on Frontend Fetches
**Problem:** Fetch calls had no timeout. Hanging backend = frozen UI forever.

**Solution:**
- Added `fetchWithTimeout` helper function to App.jsx (60s default timeout)
- Applied timeouts to all critical fetches:
  - `/start-preview` (60s)
  - `/start-generate` (60s)
  - `/auto-distance` (30s)
  - `/job-status/{id}` (10s, polling)
  - `/themes` (30s)
  - `/history` (30s, in HistoryModal)
  - `/history/{filename}` DELETE (15s, in HistoryModal)
  - `/start-restore` (60s, in useHistoryRestore hook)
- All timeouts use `AbortController` with proper cleanup

**Files changed:**
- `frontend/src/App.jsx` (helper + all main fetches)
- `frontend/src/components/HistoryModal.jsx` (history list + delete)
- `frontend/src/hooks/useHistoryRestore.js` (restore endpoint)

---

## Summary

**Lines removed:** ~195 (duplicate code)  
**Lines added:** ~220 (shared components, hooks, timeout handling, cleanup)  
**Net benefit:** More maintainable, safer, timeout-protected

All 4 high priority issues from the code review are now resolved. 🎉

## Next Steps (Medium/Low Priority)

Remaining issues from the code review:
- 🟢 TypeScript migration
- 🟢 API rate limiting
- 🟢 Environment variable validation
- 🟢 Preview JSON size optimization
- 🟢 Accessibility improvements
- 🟢 Loading states dead code

---

**Completed by:** Wiz 🧙‍♂️  
**Date:** February 1, 2026

---

## Feb 1, 2026 - Medium Priority Fixes

### 🟡 1. Unreachable Code (DONE)
- Deleted dead code in `create_map_poster.py` (~15 lines after `return result`)
- Code was after function return, never executed

### 🟡 2. SVG Thumbnail Text Escaping (DONE)
- Added `_xml_escape()` method to sanitize city, country, and coordinates
- Prevents XSS/injection via malicious city names like `<script>alert(1)</script>`
- Escapes: `<`, `>`, `&`, `"`, `'`

### 🟡 3. Job Cleanup Only on New Requests (DONE)
- Added background thread in `api.py` for periodic cleanup
- Runs every 5 minutes regardless of incoming requests
- Uses daemon thread, won't block server shutdown
- Existing TTL-based cleanup (30 min) still applies

### 🟡 4. Hardcoded Retry Delays (DONE - previously)
- Already addressed in ThemeCard with `RETRY_DELAY_MS = 2500`

### 🟡 5. CSS Duplicate Media Queries (ADDRESSED)
- Media queries at 1600px, 1400px, 1200px, 1024px serve different purposes
- Progressive adjustments for responsive grid, not duplicates
- Refactoring would provide minimal gain

### 🟡 6. Inconsistent Error Handling (ADDRESSED)
- All main fetch operations already use `setError()` consistently
- Console logs are for debugging, user-facing errors are standardized
- Error display uses consistent `.error` CSS class

---

**Summary:** All medium priority issues resolved or addressed. 🎉
