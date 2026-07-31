// API base URL - reads from Vite env var at build time, falls back to localhost for dev
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export { API_URL };
