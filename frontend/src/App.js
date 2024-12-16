// src/App.js
import React from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { MainApp } from './MainApp';
import { AuthForm } from './components/Login/AuthForm';
import { useAuth } from './contexts/AuthContext';
import { AdminPanel } from './components/Admin/AdminPanel';
import { Editor } from './components/Editor/Editor';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom'; // Import routing 

// A wrapper for <Route> that redirects to the login
// screen if you're not yet authenticated.
function PrivateRoute({ children, adminRequired = false }) {
  const { token, user } = useAuth();

  return token ? (
    adminRequired ? (
      user?.isAdmin ? (
        children
        ) : (
        <Navigate to="/" replace />
        )
    ) : (
      children
    )
  ) : (
    <Navigate to="/login" replace />
  );
}

const EditorWrapper = () => {
  const { documentId } = useParams();
  return <Editor documentId={documentId} />;
};

const AppContent = () => {
  
  return (
    <Routes>
      <Route path="/login" element={<AuthForm />} />
      <Route
        path="/admin/*"
        element={
          <PrivateRoute adminRequired>
            <AdminPanel />
          </PrivateRoute>
        }
      />
      <Route
            path="/editor/:documentId"
            element={
                <PrivateRoute>
                <EditorWrapper />
                </PrivateRoute>
            }
        />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainApp />
          </PrivateRoute>
        }
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