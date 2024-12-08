// src/App.js
import React from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { MainApp } from './components/MainApp';
import { LoginForm } from './components/Login/LoginForm';
import { useAuth } from './contexts/AuthContext';

const AppContent = () => {
  const { token } = useAuth();

  if (!token) {
    return <LoginForm />;
  }

  return <MainApp />;
};

const App = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;