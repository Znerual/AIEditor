import { useState } from 'react';

// Modal component for adding external websites
export const AddWebsiteModal = ({ isOpen, onClose, onAdd }) => {
    const [url, setUrl] = useState('');
  
    const handleAdd = () => {
        onAdd(url);
        setUrl('');
        onClose();
    };
  
    return (
        isOpen && (
            <div className="modal-backdrop">
                <div className="modal-content">
                    <h2>Add External Website</h2>
                    <input
                        type="text"
                        placeholder="Enter URL..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                        className="modal-search-input"
                    />
                    <div className="modal-buttons">
                        <button onClick={handleAdd} className="modal-add-button">
                            Add
                        </button>
                        <button onClick={onClose} className="modal-close-button">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        )
    );
  };
  