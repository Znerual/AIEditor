import React, { useState, useEffect } from 'react';

export const UserManagement = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const { token } = useAuth(); // Get the token from useAuth

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