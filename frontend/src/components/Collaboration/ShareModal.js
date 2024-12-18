import React, { useState, useCallback } from 'react';
import '../../styles/shareModal.css';

export const ShareModal = ({ token, isOpen, onClose, selectedDocumentId }) => {
    const [email, setEmail] = useState('');
    const [rights, setRights] = useState('read');
    

    const handleSubmit = () => {
        handleAddCollaborator(email, rights);
        setEmail('');
        setRights('read');
    };

    const handleAddCollaborator = useCallback(async (email, rights) => {
        // Send request to backend to add collaborator
        try {
            const response = await fetch(`http://localhost:5000/api/documents/${selectedDocumentId}/collaborators`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                rights: rights,
            }),
            });

            if (!response.ok) {
                onClose();
                throw new Error('Failed to add collaborator', response);
            }

            // Handle successful addition
            console.log('Collaborator added successfully');
            // Optionally close the modal and refresh the document list
            onClose();

        

            // Refresh the document list or update the specific document's collaborator list
            // TODO: Refresh the document list
        } catch (error) {
            console.error('Error adding collaborator:', error);
            // Handle error
        }
    }, []);

  if (!isOpen) return null;

  return (
    <div className="share-modal">
      <div className="share-modal__overlay">
        <div className="share-modal__content">
          <h2 className="share-modal__title">Share Document</h2>
          
          <div className="share-modal__form">
            <div className="share-modal__field">
              <label 
                htmlFor="collaborator-email" 
                className="share-modal__label"
              >
                Collaborator's Email:
              </label>
              <input
                type="email"
                id="collaborator-email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter collaborator's email"
                className="share-modal__input"
              />
            </div>

            <div className="share-modal__field">
              <label 
                htmlFor="collaborator-rights" 
                className="share-modal__label"
              >
                Access Rights:
              </label>
              <select
                id="collaborator-rights"
                value={rights}
                onChange={(e) => setRights(e.target.value)}
                className="share-modal__select"
              >
                <option value="read">Read</option>
                <option value="edit">Edit</option>
              </select>
            </div>

            <div className="share-modal__actions">
              <button
                onClick={onClose}
                className="share-modal__button share-modal__button--secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                className="share-modal__button share-modal__button--primary"
              >
                Add Collaborator
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};