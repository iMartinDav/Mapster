import React, { useState, useEffect, useRef } from 'react';

const LocationAutocomplete = ({ onSelect, initialQuery = '' }) => {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const wrapperRef = useRef(null);

  useEffect(() => {
    // Close dropdown if clicked outside
    const handleClickOutside = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (!query || query.length < 3) {
      setSuggestions([]);
      return;
    }

    const delayDebounceFn = setTimeout(async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&addressdetails=1`, {
          headers: {
            'Accept-Language': 'en-US,en;q=0.9',
          }
        });
        const data = await response.json();
        setSuggestions(data);
        setShowDropdown(true);
      } catch (error) {
        console.error('Error fetching locations:', error);
      } finally {
        setIsLoading(false);
      }
    }, 500);

    return () => clearTimeout(delayDebounceFn);
  }, [query]);

  const handleSelect = (place) => {
    setQuery(place.display_name);
    setShowDropdown(false);
    onSelect(place);
  };

  return (
    <div ref={wrapperRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: 'rgba(255, 255, 255, 0.05)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '8px',
        padding: '0 12px',
        transition: 'all 0.2s ease',
        boxShadow: showDropdown ? '0 0 0 2px var(--accent-glow)' : 'none'
      }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => setShowDropdown(true)}
          placeholder="Search location (e.g. Lyon)..."
          style={{ 
            width: '100%', 
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            padding: '12px 10px',
            fontSize: '0.95rem'
          }}
        />
      </div>
      {isLoading && (
        <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)' }}>
          <span className="loading-spinner" style={{ width: '16px', height: '16px', display: 'inline-block' }}></span>
        </div>
      )}
      
      {showDropdown && suggestions.length > 0 && (
        <ul style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          left: 0,
          right: 0,
          backgroundColor: '#0f172a', /* Dark modern background */
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: '8px',
          listStyle: 'none',
          padding: 0,
          margin: 0,
          zIndex: 1000,
          boxShadow: '0 10px 40px rgba(0,0,0,0.8)',
          maxHeight: '250px',
          overflowY: 'auto'
        }}>
          {suggestions.map((place, idx) => (
            <li
              key={idx}
              onClick={() => handleSelect(place)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderBottom: idx === suggestions.length - 1 ? 'none' : '1px solid rgba(255,255,255,0.05)',
                fontSize: '0.9rem',
                color: 'rgba(255,255,255,0.9)',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--accent)';
                  e.currentTarget.style.color = '#fff';
              }}
              onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'rgba(255,255,255,0.9)';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.7 }}>
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
              </svg>
              {place.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default LocationAutocomplete;
