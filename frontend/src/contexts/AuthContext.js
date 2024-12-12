// src/contexts/AuthContext.js
import React, { createContext, useState, useContext, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const defaultUser = {
  id: null,
  email: null,
  isAdmin: false
};

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));


  const login = useCallback(async (email, password) => {
    try {
      const response = await fetch('http://localhost:5000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();
      setUser(data.user);
      setToken(data.token);
      localStorage.setItem('token', data.token);
      return data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }, []);

  const register = useCallback(async (email, password, isAdmin) => {
    try {
      
      const response = await fetch('http://localhost:5000/api/register', { // API endpoint for registration
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, isAdmin })
      });
      
      if (!response.ok) {
        const errorData = await response.json(); // Get error details from response
        throw new Error(errorData.message || 'Registration failed'); // Throw error with message
      }

      // Registration successful, you might want to redirect to login here
      return await response.json();

    } catch (error) {
        // Handle specific errors, if necessary
        console.error('Registration error:', error);
        throw error; // Re-throw the error to be caught by the component
    }
  }, []);

  const authenticateToken = useCallback(async (token) => {
    try {
      const response = await fetch('http://localhost:5000/api/authenticate_token', {
        method: 'GET',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
      });

      if (!response.ok) {
        throw new Error('Token authentication failed');
      }

      const data = await response.json();
      setUser(data.user);
      return data.user;
      
    } catch (error) {
      console.error('Authentication error:', error);
      setUser(null);
      setToken(null);
      localStorage.removeItem('token');
      navigate('/login');
      throw error;
    }
  },[navigate]);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
    navigate('/login');
  }, []);

  useEffect(() => {
    if (token && !user) {
      authenticateToken(token).catch(console.error);
    }
  }, [token, user, authenticateToken]);

  return (
    <AuthContext.Provider value={{ user: user || defaultUser, token, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};