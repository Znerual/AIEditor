// src/components/Login/LoginForm.js
import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export const AuthForm  = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegistering, setIsRegistering] = useState(false); // State to toggle between login and register
  const [error, setError] = useState('');
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
        if (isRegistering) {
            const response = await register(email, password);
            if (response && response.message !== 'User registered successfully') {
                throw new Error(response.message || 'Registration failed');
            }
            // After registering and login redirect to application
            navigate('/');

        } else {
            await login(email, password);
            navigate('/');
        }

    } catch (err) {
        setError(err.message || (isRegistering ? 'Registration failed' : 'Login failed'));
    }
};

return (
    <div className="login-container">
        <form onSubmit={handleSubmit} className="login-form">
            {error && <div className="error-message">{error}</div>}
            <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
            </div>
            <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                    type="password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
            </div>
            {/* Conditional rendering of buttons */}
            <div>
                <button type="submit">{isRegistering ? 'Register' : 'Login'}</button>
                <button type="button" onClick={() => setIsRegistering(!isRegistering)}>
                    {isRegistering ? 'Switch to Login' : 'Switch to Register'}
                </button>
            </div>
        </form>
    </div>
);
};