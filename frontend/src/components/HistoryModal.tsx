import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API_URL } from '../config';
import '../App.css';

const HistoryModal = (props: any) => {
    const { onClose, onSelect } = props;
    const queryClient = useQueryClient();

    const { data: historyData, isLoading: loading } = useQuery({
        queryKey: ['history'],
        queryFn: async () => {
            const res = await fetch(`${API_URL}/history`);
            if (!res.ok) throw new Error('Network response was not ok');
            return res.json();
        }
    });

    const history = historyData?.history || [];

    const deleteMutation = useMutation({
        mutationFn: async (filename: string) => {
            const res = await fetch(`${API_URL}/history/${filename}`, {
                method: 'DELETE',
            });
            if (!res.ok) throw new Error('Failed to delete map');
            return filename;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['history'] });
        },
        onError: (err) => {
            console.error("Error deleting map:", err);
        }
    });

    const handleDelete = async (e: React.MouseEvent, filename: string) => {
        e.stopPropagation();
        if (!confirm('Are you sure you want to delete this map?')) return;
        deleteMutation.mutate(filename);
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
