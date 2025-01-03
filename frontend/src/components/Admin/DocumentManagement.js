import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';

export const DocumentManagement = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedDocumentContent, setSelectedDocumentContent] = useState(null); // State to store the content of the selected document
    const [selectedDocument, setSelectedDocument] = useState(null);
    const { token } = useAuth();

    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                const response = await fetch('http://localhost:5000/api/admin/documents', {
                    method: 'GET',
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

    const handleDeleteDocument = async (documentId) => {
        if (!window.confirm('Are you sure you want to delete this document?')) return;

        try {
            const response = await fetch(`http://localhost:5000/api/admin/documents/${documentId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to delete document');
            }
            // Update the documents list after deletion
            setDocuments(documents.filter(doc => doc.id !== documentId));
        } catch (err) {
            console.error(err);
            alert('Failed to delete document.');
        }
    };

    const handleDocumentClick = async (documentId) => {
        try {
            console.log("Document click");
            const response = await fetch(`http://localhost:5000/api/admin/documents/${documentId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch document content');
            }
            const data = await response.json();
            console.log("Data ", data)
            setSelectedDocument(data);
            setSelectedDocumentContent(data.content);
            
        } catch (err) {
            console.error(err);
            alert('Failed to fetch document content.');
        }
    };


    return (
        <div>
            <h2>Document Management</h2>
            {loading && <p>Loading documents...</p>}
            {error && <p>Error: {error}</p>}
            {!loading && !error && (
                <>
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Title</th>
                                <th>User ID</th>
                                <th>Created At</th>
                                <th>Last Modified</th>
                                <th>Size (KB)</th>
                                <th>Collaborators</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {documents.map(doc => (
                                <tr key={doc.id}>
                                    <td>
                                        <button onClick={() => handleDocumentClick(doc.id)}>
                                            {doc.id}
                                        </button>
                                    </td>
                                    <td>{doc.title} Man. set {doc.title_manually_set}</td>
                                    <td>{doc.user_id}</td>
                                    <td>{new Date(doc.created_at).toLocaleString()}</td>
                                    <td>{new Date(doc.last_modified).toLocaleString()}</td>
                                    <td>{doc.size_kb}</td>
                                    <td>
                                        <ul>
                                            {doc.collaborators.map(entry => (
                                                <li key={entry.id}>
                                                User ID: {entry.user_id},  
                                                Email: {entry.email}, 
                                                Access: {entry.access}
                                            </li>
                                            ))}
                                        </ul>
                                    </td>
                                    <td>
                                        <button onClick={() => handleDeleteDocument(doc.id)}>Delete</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {/* Display the selected document's content */}
                    {selectedDocumentContent && (
                        <div className="selected-document">
                            <h3>Selected Document {selectedDocument.title} ({selectedDocument.id}):</h3> 
                            {/* You might need to format the content appropriately */}
                            <pre>{JSON.stringify(selectedDocument.content, null, 2)}</pre>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};
