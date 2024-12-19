import React, { useState, useCallback, useEffect } from 'react';
import { User, X } from 'lucide-react';
import '../../styles/shareModal.css';

export const ShareModal = ({ token, isOpen, onClose, selectedDocumentId }) => {
  const [email, setEmail] = useState('');
  const [rights, setRights] = useState('read');
  const [collaborators, setCollaborators] = useState([]);
  const [error, setError] = useState('');

  const fetchCollaborators = useCallback(async () => {
    try {
      const response = await fetch(`http://localhost:5000/api/documents/${selectedDocumentId}/collaborators`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch collaborators');
      }
      
      const data = await response.json();
      const collabList = [];
      if (data.status === 'owner') {
        data.read_access_entries?.forEach(entry => {
          collabList.push({ email: entry.user.email, access: 'read' });
        });
        
        data.edit_access_entries?.forEach(entry => {
          collabList.push({ email: entry.user.email, access: 'edit' });
        });
        setCollaborators(collabList);
        return;
      }
      
      collabList.push({ email: data.owner.email, access: 'owner' });
      setCollaborators(collabList);
    } catch (error) {
      console.error('Error fetching collaborators:', error);
      setError('Failed to load collaborators');
    }
  }, [selectedDocumentId, token]);

  useEffect(() => {
    if (isOpen) {
      fetchCollaborators();
    }
  }, [isOpen, fetchCollaborators]);

  const handleAddCollaborator = async (email, rights) => {
    try {
      const response = await fetch(`http://localhost:5000/api/documents/${selectedDocumentId}/collaborators`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          rights,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to add collaborator');
      }

      fetchCollaborators();
      setEmail('');
      setRights('read');
      setError('');
    } catch (error) {
      console.error('Error adding collaborator:', error);
      setError('Failed to add collaborator');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="share-modal">
      <div className="share-modal__container">
        <div className="share-modal__content">
          <div className="share-modal__header">
            <h2 className="share-modal__title">Share Document</h2>
            <button
              onClick={onClose}
              className="share-modal__close-button"
            >
              <X size={20} />
            </button>
          </div>

          {error && (
            <div className="share-modal__error">
              {error}
            </div>
          )}

          <div className="share-modal__form">
            <div className="share-modal__form-group">
              <label className="share-modal__label">
                Collaborator's Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter email address"
                className="share-modal__input"
              />
            </div>

            <div className="share-modal__form-group">
              <label className="share-modal__label">
                Access Rights
              </label>
              <select
                value={rights}
                onChange={(e) => setRights(e.target.value)}
                className="share-modal__select"
              >
                <option value="read">Read Only</option>
                <option value="edit">Can Edit</option>
              </select>
            </div>

            <button
              onClick={() => handleAddCollaborator(email, rights)}
              className="share-modal__submit-button"
            >
              Add Collaborator
            </button>
          </div>

          {collaborators.length > 0 && (
            <div className="share-modal__collaborators">
              <h3 className="share-modal__collaborators-title">Current Collaborators</h3>
              <div className="share-modal__collaborators-list">
                {collaborators.map((collaborator, index) => (
                  <div
                    key={index}
                    className="share-modal__collaborator"
                  >
                    <div className="share-modal__collaborator-info">
                      <User size={18} className="share-modal__collaborator-icon" />
                      <span className="share-modal__collaborator-email">{collaborator.email}</span>
                    </div>
                    <span
                      className={`share-modal__collaborator-badge ${
                        collaborator.access === 'edit'
                          ? 'share-modal__collaborator-badge--editor'
                          : collaborator.access === 'owner'
                          ? 'share-modal__collaborator-badge--owner'
                          : 'share-modal__collaborator-badge--viewer'
                      }`}
                    >
                      {collaborator.access === 'edit'
                        ? 'Editor'
                        : collaborator.access === 'owner'
                        ? 'Owner'
                        : 'Viewer'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
