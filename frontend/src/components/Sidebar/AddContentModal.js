// frontend/src/components/Sidebar/AddContentModal.js
import { useState, useEffect, useCallback } from 'react';

export const AddContentModal = ({ isOpen, onClose, onAdd, token }) => {
  const [content, setContent] = useState([]);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/user/content', {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) {
          throw new Error('Failed to fetch content');
        }
        const data = await response.json();
        setContent(data);
      } catch (err) {
        console.error(err);
      }
    };

    if (isOpen) {
      fetchContent();
    }
  }, [isOpen, token]);

  const handleAdd = useCallback(async (selectedContent) => {
    try {
        const response = await fetch(`http://localhost:5000/api/content/${selectedContent.file_id}`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!response.ok) {
            throw new Error('Failed to fetch content');
        }
        const data = await response.json();
        onAdd(data);
    } catch (error) {
      console.error(error);
    }
    //onClose();
    }, []);

  return (
    isOpen && (
      <div className="modal-backdrop">
        <div className="modal-content">
          <h2>Select Content to Add</h2>
          <div className="modal-content-list">
            {content.map(item => (
              <div key={item.file_id} className="modal-content-item" onClick={() => handleAdd(item)}>
                <span>{item.filepath}</span>
                <span className="modal-content-date">
                  {item.lastModified && new Date(item.lastModified).toLocaleString()}
                  {new Date(item.creation_date).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
          <button onClick={onClose} className="modal-close-button">
            Close
          </button>
        </div>
      </div>
    )
  );
};