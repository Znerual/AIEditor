// src/App.js
import React from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { MainApp } from './MainApp';
import { AuthForm } from './components/Login/AuthForm';
import { useAuth } from './contexts/AuthContext';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'; // Import routing 

const AppContent = () => {
  const { token } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<AuthForm />} />
      <Route
        path="/"
        element={token ? <MainApp /> : <AuthForm />} // Or a loading/splash component
      />
    </Routes>
  );
};

const App = () => {

  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
};

export default App;