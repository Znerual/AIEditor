import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';

export const FileEmbeddingManagement = () => {
    const [fileEmbeddings, setFileEmbeddings] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedFileEmbedding, setSelectedFileEmbedding] = useState(null);
    const [selectedSequence, setSelectedSequence] = useState(null);
    const [showEmbedding, setShowEmbedding] = useState(false);
    const { token } = useAuth();

    useEffect(() => {
        const fetchFileEmbeddings = async () => {
            setLoading(true);
            try {
                const response = await fetch('http://localhost:5000/api/admin/file_embeddings', {
                    method: 'GET',
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch file embeddings');
                }
                const data = await response.json();
                setFileEmbeddings(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchFileEmbeddings();
    }, [token]);

    const handleFileEmbeddingClick = async (fileEmbeddingId) => {
        try {
            const response = await fetch(`http://localhost:5000/api/admin/file_embeddings/${fileEmbeddingId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch file embedding');
            }
            const data = await response.json();
            setSelectedFileEmbedding(data);
            setSelectedSequence(data.sequences); // Reset selected sequence when selecting a new file embedding
        } catch (err) {
            console.error(err);
            alert('Failed to fetch file embedding.');
        }
    };

    const handleDeleteFileEmbedding = async (fileEmbeddingId) => {
        if (!window.confirm('Are you sure you want to delete this file embedding?')) return;

        try {
            const response = await fetch(`http://localhost:5000/api/admin/file_embeddings/${fileEmbeddingId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to delete file embedding');
            }
            setFileEmbeddings(fileEmbeddings.filter(fe => fe.id !== fileEmbeddingId));
            setSelectedFileEmbedding(null); // Clear selected file embedding
        } catch (err) {
            console.error(err);
            alert('Failed to delete file embedding.');
        }
    };

    const handleSequenceClick = async (sequence) => {
        // If the same sequence is clicked again, toggle the embedding visibility
        if (selectedSequence && selectedSequence.id === sequence.id) {
            setShowEmbedding(!showEmbedding);
        } else {
            setSelectedSequence(sequence);
            setShowEmbedding(true); // Show embedding when a new sequence is selected
        }
    };

    const toggleShowEmbedding = () => {
        setShowEmbedding(!showEmbedding);
    };

    return (
        <div className="file-embedding-management">
            <h2>File Embedding Management</h2>
            {loading && <p>Loading file embeddings...</p>}
            {error && <p>Error: {error}</p>}
            {!loading && !error && (
                <div className="file-embedding-container">
                    <div className="file-embedding-list">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Document ID</th>
                                    <th>Content ID</th>
                                    <th>Creation Date</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fileEmbeddings.map(fileEmbedding => (
                                    <tr key={fileEmbedding.id}>
                                        <td>
                                            <button onClick={() => handleFileEmbeddingClick(fileEmbedding.id)}>
                                                {fileEmbedding.id}
                                            </button>
                                        </td>
                                        <td>{fileEmbedding.document_id}</td>
                                        <td>{fileEmbedding.content_id}</td>
                                        <td>{new Date(fileEmbedding.creation_date).toLocaleString()}</td>
                                        <td>
                                            <button onClick={() => handleDeleteFileEmbedding(fileEmbedding.id)}>
                                                Delete
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="file-embedding-details">
                        {selectedFileEmbedding && (
                            <>
                                <h3>Selected File Embedding (ID: {selectedFileEmbedding.id})</h3>
                                <div className="sequence-list">
                                    <h4>Sequences</h4>
                                    <ul>
                                        {selectedFileEmbedding.sequences.map(sequence => (
                                            <li key={sequence.id} onClick={() => handleSequenceClick(sequence)}
                                                className={selectedSequence && selectedSequence.id === sequence.id ? 'selected' : ''}>
                                                {sequence.id} - {sequence.sequence_hash}
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                {selectedSequence && (
                                    <div className="sequence-details">
                                        <h4>Selected Sequence (ID: {selectedSequence.id})</h4>
                                        <div><strong>Sequence Hash:</strong> {selectedSequence.sequence_hash}</div>
                                        <div><strong>Sequence Text:</strong> <p>{selectedSequence.sequence_text}</p></div>
                                        {showEmbedding && (
                                            <div>
                                                <strong>Embedding:</strong> 
                                                <textarea readOnly value={JSON.stringify(selectedSequence.embedding)} />
                                            </div>
                                        )}
                                        <button onClick={toggleShowEmbedding}>
                                            {showEmbedding ? 'Hide Embedding' : 'Show Embedding'}
                                        </button>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};