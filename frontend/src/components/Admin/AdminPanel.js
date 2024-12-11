// frontend/src/components/Admin/AdminPanel.js
import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

import '../../styles/adminPanel.css';

const UserManagement = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const { token } = useAuth(); // Get the token from useAuth
    const navigate = useNavigate();

    useEffect(() => {
        const fetchUsers = async () => {
            try {
                const response = await fetch('http://localhost:5000/api/admin/users', {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch users');
                }
                const data = await response.json();
                setUsers(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchUsers();
    }, [token]);

    const handleDeleteUser = async (userId) => {
        if (!window.confirm('Are you sure you want to delete this user? This will also delete all of his documents')) return;

        try {
            const response = await fetch(`http://localhost:5000/api/admin/users/${userId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to delete user');
            }
            // Update the users list after deletion
            setUsers(users.filter(user => user.id !== userId));
        } catch (err) {
            console.error(err);
            alert('Failed to delete user.');
        }
    };

    // Function to make a user an admin
    const handleMakeAdmin = async (userId) => {
        try {
            const response = await fetch(`http://localhost:5000/api/admin/users/${userId}/make-admin`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ is_admin: true }), // Send the updated admin status
            });
    
            if (!response.ok) {
                throw new Error('Failed to update user admin status');
            }
    
            // Update the local users list to reflect the change
            setUsers(users.map(user => user.id === userId ? { ...user, is_admin: true } : user));
        } catch (err) {
            console.error(err);
            alert('Failed to update user admin status.');
        }
    };

    // Function to remove admin rights from a user
    const handleRemoveAdmin = async (userId) => {
        try {
            const response = await fetch(`http://localhost:5000/api/admin/users/${userId}/remove-admin`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ is_admin: false }), // Send the updated admin status
            });
    
            if (!response.ok) {
                throw new Error('Failed to update user admin status');
            }
    
            // Update the local users list to reflect the change
            setUsers(users.map(user => user.id === userId ? { ...user, is_admin: false } : user));
        } catch (err) {
            console.error(err);
            alert('Failed to update user admin status.');
        }
    };

    return (
        <div>
            <h2>User Management</h2>
            {loading && <p>Loading users...</p>}
            {error && <p>Error: {error}</p>}
            {!loading && !error && (
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Email</th>
                            <th>Admin</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id}>
                                <td>{user.id}</td>
                                <td>{user.email}</td>
                                <td>{user.is_admin ? 'Yes' : 'No'}</td>
                                <td>
                                    <button onClick={() => handleDeleteUser(user.id)}>Delete</button>
                                    {user.is_admin ? (
                                        <button onClick={() => handleRemoveAdmin(user.id)}>Remove Admin</button>
                                    ) : (
                                        <button onClick={() => handleMakeAdmin(user.id)}>Make Admin</button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};

const DocumentManagement = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedDocumentContent, setSelectedDocumentContent] = useState(null); // State to store the content of the selected document
    const [selectedDocumentId, setSelectedDocumentId] = useState(null);
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
            const response = await fetch(`http://localhost:5000/api/admin/documents/${documentId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch document content');
            }
            const data = await response.json();
            setSelectedDocumentContent(data.content);
            setSelectedDocumentId(documentId);
            
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
                                <th>User ID</th>
                                <th>Created At</th>
                                <th>Read Access</th>
                                <th>Edit Access</th>
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
                                    <td>{doc.user_id}</td>
                                    <td>{new Date(doc.created_at).toLocaleString()}</td>
                                    <td>
                                        <ul>
                                            {doc.read_access_entries.map(entry => (
                                                <li key={entry.id}>
                                                User ID: {entry.user_id},  
                                                Email: {entry.user ? entry.user.email : 'N/A'}, 
                                                Granted At: {new Date(entry.granted_at).toLocaleString()}
                                            </li>
                                            ))}
                                        </ul>
                                    </td>
                                    <td>
                                        <ul>
                                            {doc.edit_access_entries.map(entry => (
                                                <li key={entry.id}>
                                                User ID: {entry.user_id}, 
                                                Email: {entry.user ? entry.user.email : 'N/A'}, 
                                                Granted At: {new Date(entry.granted_at).toLocaleString()}
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
                            <h3>Selected Document {selectedDocumentId} Content:</h3>
                            {/* You might need to format the content appropriately */}
                            <pre>{JSON.stringify(selectedDocumentContent, null, 2)}</pre>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export const AdminPanel = () => {
    const { logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login'); // Redirect to login after logout
    };

    const handleToMainPage = useCallback(() => {
        navigate('/');
    });

    return (
        <div className="admin-panel">
            <h1>Admin Panel</h1>
            <nav>
                <ul>
                    <li><Link to="/admin/users">User Management</Link></li>
                    <li><Link to="/admin/documents">Document Management</Link></li>
                    <li><button onClick={handleLogout}>Logout</button></li>
                    <li><button onClick={handleToMainPage}>Back to Main Page</button></li>
                </ul>
            </nav>

            <Routes>
                <Route path="users" element={<UserManagement />} />
                <Route path="documents" element={<DocumentManagement />} />
            </Routes>
        </div>
    );
};