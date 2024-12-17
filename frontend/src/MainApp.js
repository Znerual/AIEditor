import React, { useState, useCallback, useEffect } from 'react';
import { useAuth } from './contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Plus, Trash2 } from 'lucide-react';
import './styles/mainApp.css'; // Make sure to create this CSS file

export const MainApp = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchMode, setSearchMode] = useState('keyword'); // 'keyword' or 'embedding'
    const [searchTerm, setSearchTerm] = useState('');
    const [showConfirmation, setShowConfirmation] = useState(false);
    const [documentToDelete, setDocumentToDelete] = useState(null);
    const { token } = useAuth();
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

    const handleDeleteClick = (documentId) => {
        setDocumentToDelete(documentId);
        setShowConfirmation(true);
    };

    const confirmDelete = async () => {
        try {
            const response = await fetch(`http://localhost:5000/api/user/document/${documentToDelete}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });
            if (!response.ok) {
                throw new Error('Failed to delete document');
            }
            // Remove the deleted document from the state
            setDocuments(documents.filter(doc => doc.id !== documentToDelete));
            setShowConfirmation(false);
            setDocumentToDelete(null);
        } catch (error) {
            console.error('Error deleting document:', error);
            setError(error.message)
        }
    };

    const cancelDelete = () => {
        setShowConfirmation(false);
        setDocumentToDelete(null);
    };


    useEffect(() => {
        const fetchDocuments = async () => {
            setLoading(true);
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

    const handleSearchModeChange = () => {
        setSearchMode(searchMode === 'keyword' ? 'embedding' : 'keyword');
    };

    return (
        <div className="app-container">
            <div className="main-header">
                <button 
                    variant="ghost"
                    onClick={handleCreateNewDocument} 
                    className="create-new-document-button"
                ><Plus/></button>
                <input
                    type="text"
                    placeholder="Search by document title, id or creation date..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                />
                <button onClick={handleSearchModeChange} className="search-mode-button">
                    {searchMode === 'keyword' ? 'Keyword' : 'Embedding'}
                </button>
            </div>
            <div className='container'>
                <h1>Your Documents</h1>
                {loading && <p className="loading">Loading documents...</p>}
                {error && <p className="error">Error: {error}</p>}
                {!loading && !error && (
                    <div className="document-grid">
                        {filteredDocuments.map(doc => (
                            <div key={doc.id} className="document-card">
                                {/* Delete Icon */}
                                <Trash2
                                    className="delete-icon"
                                    onClick={(e) => {
                                        e.stopPropagation(); // Prevent card click
                                        handleDeleteClick(doc.id);
                                    }}
                                />
                                <div className='document-card-clickable' onClick={() => handleDocumentSelect(doc.id)}>
                                    <div className="document-preview">
                                        {/* Placeholder for document preview image */}
                                        <div className="preview-image"></div>
                                    </div>
                                    <div className="document-info">
                                        <h2>{doc.title}</h2>
                                        {!doc.title && <p>ID: {doc.id}</p>}
                                        <p>Created: {new Date(doc.created_at).toLocaleString()}</p>
                                        <p>Modified: {new Date(doc.updated_at).toLocaleString()}</p>
                                        <p>User ID: {doc.user_id}</p>
                                        <div className='document-collaborators'>
                                            <p>Collaborators:</p>
                                            <div className='collaborators-list'>
                                                {/* Map over collaborators when available */}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                {/* Confirmation Dialog */}
                {showConfirmation && (
                    <div className="confirmation-dialog">
                        <div className="confirmation-dialog-content">
                            <p>Are you sure you want to delete this document?</p>
                            <div className='confirmation-dialog-buttons'>
                                <button onClick={confirmDelete} className='confirm-delete'>Yes</button>
                                <button onClick={cancelDelete} className='cancel-delete'>No</button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};