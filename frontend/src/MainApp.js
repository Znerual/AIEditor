import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useAuth } from './contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

import './styles/mainApp.css';

export const MainApp = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const { user, logout, token } = useAuth();
    const navigate = useNavigate();

    const handleDocumentSelect = useCallback((documentId) => {
        navigate(`/editor/${documentId}`);
    }, [navigate]);

    const handleCreateNewDocument = useCallback(async () => {
        try {
            const response = await fetch('http://localhost:5000/api/user/create_new_document', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
            });
            if (!response.ok) {
                throw new Error('Failed to create document');
            }
            const data = await response.json();
            navigate(`/editor/${data.documentId}`);
        } catch (error) {
            console.error('Error creating new document:', error);
        }
    }, [navigate, token]);

    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                const response = await fetch('http://localhost:5000/api/user/documents', {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch documents');
                }
                const data = await response.json();
                setDocuments(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchDocuments();
    }, [token]);

    const filteredDocuments = documents.filter(doc =>
        doc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (doc.title && doc.title.toLowerCase().includes(searchTerm.toLowerCase())) ||
        new Date(doc.created_at).toLocaleString().toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="app-container">
            <div className='container'>
                <h1>Your Documents</h1>
                {loading && <p>Loading documents...</p>}
                {error && <p>Error: {error}</p>}
                {!loading && !error && (
                    <>
                        <input
                            type="text"
                            placeholder="Search by document title, id or creation date..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="search-input"
                        />
                        <div className="document-list">
                            {filteredDocuments.map(doc => (
                                <div key={doc.id} className="document-item" onClick={() => handleDocumentSelect(doc.id)}>
                                    <h2>{doc.title}</h2>
                                    <p>ID: {doc.id}</p>
                                    <p>Created At: {new Date(doc.created_at).toLocaleString()}</p>
                                    <p>Last Modified: {new Date(doc.updated_at).toLocaleString()}</p>
                                    <p>User ID: {doc.user_id}</p>
                                    <div className='document-collaborators'>
                                        <p>Colaborators:</p>
                                        <div className='collaborators-list'>
                                            {/* Map over collaborators when available */}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <button onClick={handleCreateNewDocument} className="create-new-document-button">Create New Document</button>
                    </>
                )}
            </div>
        </div>
    );
};