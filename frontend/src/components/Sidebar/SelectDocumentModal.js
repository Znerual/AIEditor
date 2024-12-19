// frontend/src/components/Sidebar/SelectDocumentModal.js
import { useState, useEffect } from 'react';

// Modal component for selecting existing documents
export const SelectDocumentModal = ({ isOpen, onClose, onSelect, token }) => {
    const [searchTerm, setSearchTerm] = useState('');
    const [documents, setDocuments] = useState([]);
  
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
                console.error(err);
            }
        };
  
        if (isOpen) {
            fetchDocuments();
        }
    }, [isOpen, token]);
  
    const filteredDocuments = documents.filter(doc => 
        doc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        new Date(doc.created_at).toLocaleString().toLowerCase().includes(searchTerm.toLowerCase())
    );
  
    return (
        isOpen && (
            <div className="modal-backdrop">
                <div className="modal-content">
                    <h2>Select Existing Document</h2>
                    <input
                        type="text"
                        placeholder="Search by document title, id or creation date..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="modal-search-input"
                    />
                    <div className="modal-document-list">
                        {filteredDocuments.map(doc => (
                            <div key={doc.id} className="modal-document-item" onClick={() => onSelect(doc)}>
                                <span>{doc.id}</span>
                                <span>{doc.title}</span>
                                <span className="modal-document-date">
                                    {new Date(doc.created_at).toLocaleString()}
                                </span>
                            </div>
                        ))}
                    </div>
                    <button onClick={onClose} className="modal-close-button">
                        Close
                    </button>
                </div>
            </div>
        )
    );
  };