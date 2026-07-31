import React, { useEffect, useState } from 'react';
import { API_URL } from '../config';
import '../App.css';

const HistoryModal = ({ onClose, onSelect }) => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        fetch(`${API_URL}/history`, { signal: controller.signal })
            .then(res => {
                clearTimeout(timeoutId);
                return res.json();
            })
            .then(data => {
                setHistory(data.history);
                setLoading(false);
            })
            .catch(err => {
                clearTimeout(timeoutId);
                if (err.name !== 'AbortError') {
                    console.error("Failed to load history", err);
                }
                setLoading(false);
            });
    }, []);

    const handleDelete = async (e, filename) => {
        e.stopPropagation();
        if (!confirm('Are you sure you want to delete this map?')) return;

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000);
            
            const res = await fetch(`${API_URL}/history/${filename}`, {
                method: 'DELETE',
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);

            if (res.ok) {
                setHistory(prev => prev.filter(item => item.filename !== filename));
            } else {
                console.error("Failed to delete map");
            }
        } catch (err) {
            if (err.name === 'AbortError') {
                console.error("Delete request timed out");
            } else {
                console.error("Error deleting map:", err);
            }
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>Previously Generated Maps</h2>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <div className="history-grid">
                    {loading && <div className="loading-text">Loading history...</div>}
                    {!loading && history.length === 0 && (
                        <div className="empty-history">No maps generated yet.</div>
                    )}

                    {history.map((item, index) => (
                        <div
                            key={index}
                            className="history-item"
                            onClick={() => {
                                onSelect(item);
                                onClose();
                            }}
                        >
                            <button
                                className="history-delete-btn"
                                onClick={(e) => handleDelete(e, item.filename)}
                                title="Delete map"
                            >
                                ×
                            </button>
                            <img
                                src={
                                    (item.thumbnail_url || item.url || '').startsWith('http')
                                        ? ((item.thumbnail_url || item.url))
                                        : `${API_URL}${item.thumbnail_url || item.url}?t=${item.timestamp}`
                                }
                                alt={item.filename}
                                loading="lazy"
                            />
                            <div className="history-info">
                                <span className="history-date">
                                    {new Date(item.timestamp * 1000).toLocaleDateString()}
                                </span>
                                <span className="history-name">
                                    {item.filename.split('_')[0]}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div >
    );
};

export default HistoryModal;
