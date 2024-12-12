// src/components/Login/LoginForm.js
import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import Confetti from 'react-confetti';

export const AuthForm  = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false); // State to toggle between login and register
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    try {
        if (isRegistering) {
            const response = await register(email, password, isAdmin);
            if (response && response.message !== 'User registered successfully') {
                throw new Error(response.message || 'Registration failed');
            }
            // Play success animation
            setSuccess(true);

            // Switch to login after animation
            setTimeout(() => {
                setIsRegistering(false);
                setSuccess(false);
                navigate('/');
            }, 8000);

        } else {
            const data = await login(email, password);
            if (data && data.user.isAdmin) { // Check if the user is an admin
                navigate('/admin'); // Redirect to admin panel
            } else {
                navigate('/'); // Redirect to regular user view
            }
        }

    } catch (err) {
        console.log("Error in handleSubmit: ", err);
        setError(err.message || (isRegistering ? 'Registration failed' : 'Login failed'));
    }
};

return (
    <div className="login-container">
        <form onSubmit={handleSubmit} className="login-form">
            {success && <Confetti />} {/* Display confetti when success is true */}
            {success && <div className="success-message">Registration Successful!</div>}
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
            <div className="button-group">
                <button type="submit">{isRegistering ? 'Register' : 'Login'}</button>
                <button type="button" onClick={() => setIsRegistering(!isRegistering)}>
                    {isRegistering ? 'Switch to Login' : 'Switch to Register'}
                </button>
                <button type="button" onClick={() => setIsAdmin(!isAdmin)}>{isAdmin ? 'Admin' : 'User'}</button>
            </div>
        </form>
    </div>
);
};