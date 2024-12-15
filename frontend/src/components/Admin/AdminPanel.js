// frontend/src/components/Admin/AdminPanel.js
import React, { useCallback } from 'react';
import { Routes, Route, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { UserManagement } from './UserManagement';
import { DocumentManagement } from './DocumentManagement';
import { FileContentManagement } from './FileContentManagement';
import { FileEmbeddingManagement } from './FileEmbeddingManagement';
import '../../styles/adminPanel.css';


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
                    <li><Link to="/admin/file_contents">File Content Management</Link></li>
                    <li><Link to="/admin/file_embeddings">File Embedding Management</Link></li>
                    <li><button onClick={handleLogout}>Logout</button></li>
                    <li><button onClick={handleToMainPage}>Back to Main Page</button></li>
                </ul>
            </nav>

            <Routes>
                <Route path="users" element={<UserManagement />} />
                <Route path="documents" element={<DocumentManagement />} />
                <Route path="file_contents" element={<FileContentManagement />} />
                <Route path="file_embeddings" element={<FileEmbeddingManagement />} />
            </Routes>
        </div>
    );
};