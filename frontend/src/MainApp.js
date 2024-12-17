import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useAuth } from './contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Plus, Trash2, Upload } from 'lucide-react';
import './styles/mainApp.css'; // Make sure to create this CSS file
import { Button } from './components/ui/button';

export const MainApp = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [searchMode, setSearchMode] = useState('keyword'); // 'keyword' or 'embedding'
    const [searchTerm, setSearchTerm] = useState('');
    const [showConfirmation, setShowConfirmation] = useState(false);
    const [documentToDelete, setDocumentToDelete] = useState(null);
    const [thumbnailURLs, setThumbnailURLs] = useState({}); // Store object URLs for thumbnails
    const { token } = useAuth();
    const fileInputRef = useRef(null);
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

    const fetchThumbnail = useCallback(async (documentId, thumbnailId) => {
        try {
            const response = await fetch(`http://localhost:5000/api/thumbnails/${thumbnailId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch thumbnail: ${response.status}`);
            }

            const blob = await response.blob();
            const objURL = URL.createObjectURL(blob);

            // Update the thumbnailURLs state
            setThumbnailURLs(prevURLs => ({
                ...prevURLs,
                [documentId]: objURL
            }));
        } catch (error) {
            console.error('Error fetching thumbnail:', error);
            // Handle error appropriately (e.g., set a default image URL)
        }
    }, [token]);


    useEffect(() => {
        const fetchDocuments = async () => {
            setLoading(true);
            try {
                let url = 'http://localhost:5000/api/user/documents';
                if (searchMode === 'embedding' && searchTerm) {
                    url = `http://localhost:5000/api/user/search_documents?search_term=${encodeURIComponent(searchTerm)}`;
                }

                const response = await fetch(url, {
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
    }, [token, searchMode, searchTerm]);

    useEffect(() => {
        const cleanupURLs = {};

        // Fetch thumbnails for documents with thumbnail_id
        documents.forEach(doc => {
            if (doc.thumbnail_id) {
                fetchThumbnail(doc.id, doc.thumbnail_id)
                    .then(objURL => {
                        cleanupURLs[doc.id] = objURL; // Store URL for cleanup later
                    });
            }
        });

        // Cleanup function to revoke object URLs
        return () => {
            for (const url of Object.values(cleanupURLs)) {
                URL.revokeObjectURL(url);
            }
        };
    }, [documents, fetchThumbnail]);

    const filteredDocuments = (searchMode == 'keyword' ? 
        documents.filter(doc =>
        doc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (doc.title && doc.title.toLowerCase().includes(searchTerm.toLowerCase())) ||
        new Date(doc.created_at).toLocaleString().toLowerCase().includes(searchTerm.toLowerCase())) :
        (documents)
    );

    const handleSearchModeChange = () => {
        setSearchMode(searchMode === 'keyword' ? 'embedding' : 'keyword');
    };


    const handleThumbnailUpload = async (event) => {
        const file = event.target.files[0];
        const documentId = event.target.dataset.documentId; // Get documentId from data attribute
        if (file) {
            try {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const base64Image = e.target.result.split(',')[1]; // Remove data URL prefix
                    const response = await fetch('http://localhost:5000/api/thumbnails', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            document_id: documentId,
                            image_data: base64Image,
                        })
                    });
    
                    if (!response.ok) {
                        throw new Error('Failed to upload thumbnail');
                    }
    
                    const data = await response.json();
    
                    // Update the document with the new thumbnail ID
                    setDocuments(prevDocuments => prevDocuments.map(doc => {
                        if (doc.id === documentId) {
                            return { ...doc, thumbnail_id: data.thumbnail_id };
                        }
                        return doc;
                    }));
                };
                reader.readAsDataURL(file);
            } catch (error) {
                console.error('Error uploading thumbnail:', error);
                // Handle error appropriately (e.g., show an error message to the user)
            }
        }
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
                                <label htmlFor={`thumbnail-upload-${doc.id}`} className="upload-thumbnail-container">
                                    <Upload className="upload-thumbnail-icon" />
                                </label>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    style={{ display: 'none' }}
                                    onChange={handleThumbnailUpload}
                                    accept="image/*"
                                    data-document-id={doc.id}
                                    id={`thumbnail-upload-${doc.id}`}
                                />
                                <Trash2
                                    className="delete-icon"
                                    onClick={(e) => {
                                        e.stopPropagation(); // Prevent card click
                                        handleDeleteClick(doc.id);
                                    }}
                                />
                                <div className='document-card-clickable' onClick={() => handleDocumentSelect(doc.id)}>
                                    <input
                                        type="file"
                                        ref={fileInputRef}
                                        style={{ display: 'none' }}
                                        onChange={handleThumbnailUpload}
                                        accept="image/*"
                                    />
                                    <div className="document-preview">
                                        {/* Placeholder for document preview image */}
                                        {doc.thumbnail_id ? (
                                            <img
                                                src={thumbnailURLs[doc.id]}
                                                alt="Thumbnail"
                                                width="128"
                                                height="128"
                                                
                                            />
                                        ) : (
                                            <div className="preview-image-placeholder"></div>
                                        )}
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