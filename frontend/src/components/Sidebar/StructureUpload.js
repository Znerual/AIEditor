// frontend/src/components/Sidebar/StructureUpload.js
import { useState, useCallback } from 'react';
import { Card } from '../ui/card'
import { Upload, ChevronDown, ChevronUp, X, FolderPlus, FilePlus, Link } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { AddContentModal } from './AddContentModal';
import { SelectDocumentModal } from './SelectDocumentModal';
import { AddWebsiteModal } from './AddWebsiteModel';
import { useAuth } from '../../contexts/AuthContext';
import { documentParser } from '../../utils/documentUtils';

import '../../styles/uploadSections.css';

export const StructurUpload = ({ title, onUpload }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null); // State to track selected files
    const [showFileContentModal, setShowFileContentModal] = useState(false);
    const [showDocumentModal, setShowDocumentModal] = useState(false);
    const [showWebsiteModal, setShowWebsiteModal] = useState(false);
    const [showAddContentModal, setShowAddContentModal] = useState(false);

    const { token } = useAuth();

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    const handleFileChange = useCallback(async (event) => {
        const files = event.target.files;
        if (files.length > 0) {
          const file = files[0];
          setSelectedFile(file);
          try {
            const formData = new FormData();
            formData.append('files', file);
            formData.append(`${file.name}.lastModified`, file.lastModified);
      
            const response = await fetch('http://localhost:5000/api/extract_text', {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${token}` },
              body: formData
            });
      
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
      
            const data = await response.json();
            if (data.success !== true || data.results.length === 0) {
              throw new Error('Failed to extract text from files');
            }
      
            const result = data.results[0];
            if (result.success) {
              onUpload(result);
              setSelectedFile(result);
            } else {
              console.error('Error processing file:', result.error);
            }
          } catch (error) {
            console.error('Error during file upload:', error);
          }
        } else {
          setSelectedFile(null);
        }
      }, [onUpload, token]);

      const handleDrop = useCallback(async (event) => {
        event.preventDefault();
        const files = event.dataTransfer.files;
        if (files.length > 0) {
          const file = files[0];
          setSelectedFile(file);
          try {
            const formData = new FormData();
            formData.append('files', file);
            formData.append(`${file.name}.lastModified`, file.lastModified);
      
            const response = await fetch('http://localhost:5000/api/extract_text', {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${token}` },
              body: formData
            });
      
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
      
            const data = await response.json();
            if (data.success !== true || data.results.length === 0) {
              throw new Error('Failed to extract text from files');
            }
      
            const result = data.results[0];
            if (result.success) {
              onUpload(result);
              setSelectedFile(result);
            } else {
              console.error('Error processing file:', result.error);
            }
          } catch (error) {
            console.error('Error during file upload:', error);
          }
        } else {
          setSelectedFile(null);
        }
      }, [onUpload, token]);


    const handleDragOver = (event) => {
        event.preventDefault();
    };

    const handleDragEnter = (event) => {
        event.preventDefault();
        event.currentTarget.classList.add('drag-over');
    };

    const handleDragLeave = (event) => {
        event.preventDefault();
        event.currentTarget.classList.remove('drag-over');
    };

    const handleRemoveFile = () => {
        setSelectedFile(null);
        onUpload(null); // Notify the parent component that the file has been removed
    };

    const handleFileClick = () => {
        setShowFileContentModal(true);
    };
    
    const closeFileContentModal = () => {
        setShowFileContentModal(false);
    };

    const handleSelectDocument = useCallback(async (document) => {
        console.log("Selected document:", document);
        setShowDocumentModal(false);
        const id = document.file_id ;
        try {
            const text = await documentParser.readDocument(document);
            const result = { filename: id, raw:document.content, file_id: document.id, success: true, text_extracted: text, message: 'Document extracted', content_type: 'document' };
            onUpload(result);
            setSelectedFile(result);
        } catch (error) {
            console.error("Error extracting text from Document", document.id, error);
        }
      }, [onUpload]);
  
      const handleAddWebsite = useCallback(async (url) =>  {
          console.log("Added website:", url);
          setShowWebsiteModal(false);
          try {
            const response = await fetch('http://localhost:5000/api/extract_text_website', 
              {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url })
            });
  
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
          
            const data = await response.json();
            if (data.success !== true) {
              throw new Error('Failed to extract text from website');
            }
            
            onUpload(data);
            setSelectedFile(data);
          } catch (error) {
              console.error("Error extracting text from Website", url, error);
          }  
      }, [onUpload, token]);
  
      const handleAddContent = useCallback(async (content) => {
          setShowAddContentModal(false);
          try {
            const newFile = {
                file_id: content.file_id,
                filename: content.filepath,
                raw: {
                  size: content.size,
                  type: content.type,
                  lastModified: content.lastModified,
                },
                success: true,
                text_extracted: content.text_content,
                message: 'Content added',
                content_type: 'file_content',
              };
              onUpload(newFile);
              setSelectedFile(newFile);
          } catch (error) {
            console.error("Error adding content", content, error);
          }
    }, [onUpload]);

    return (
        <div className="upload-section">
            {/* File Content Modal */}
            {showFileContentModal && selectedFile && (
                <Dialog open={showFileContentModal} onOpenChange={setShowFileContentModal}>
                    <DialogContent className="file-content-modal">
                        <DialogHeader>
                            <DialogTitle>{selectedFile.name}</DialogTitle>
                            <DialogDescription>
                                {/* Display file details or other relevant information here */}
                            </DialogDescription>
                        </DialogHeader>
                        <div className="file-content-body">
                            <div className="file-content-extracted-text">
                                {/* Display the extracted text here */}
                                <pre>{selectedFile.text_content || 'No text extracted'}</pre>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button onClick={closeFileContentModal}>
                                Close
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
            <div className="upload-header" onClick={toggleCollapse}>
                <h2 className="font-medium">{title}</h2>
                {isCollapsed ? <ChevronUp className="collapse-icon" /> : <ChevronDown className="collapse-icon" />}
            </div>
            {!isCollapsed && (
                <>
                    <Card 
                        className="upload-card"
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                    >
                        <div className="upload-container">
                            {!selectedFile && (
                                <>
                                    <Upload className="upload-icon" />
                                    <input
                                        type="file"
                                        onChange={handleFileChange}
                                        className="hidden-input"
                                        id="structure-upload"
                                    />
                                    <label htmlFor="structure-upload" className="upload-label">
                                        {/* Show filename or default label */}
                                        Upload Structure File
                                    </label>
                                </>
                            )}
                            {selectedFile && (
                                <div className="file-item" onClick={handleFileClick}>
                                    <span>{selectedFile.filename}</span>
                                    <span className="file-remove-button" onClick={handleRemoveFile}>
                                        <X size={20} />
                                    </span>
                                </div>
                            )}
                        </div>
                        <div className="icon-buttons-container">
                            <button
                                className="icon-button"
                                onClick={() => setShowAddContentModal(true)}
                                aria-label="Add Content"
                            >
                                <FolderPlus className="icon-button-icon" />
                                <span className="icon-button-tooltip">Add Content</span>
                            </button>  
                            <button
                                className="icon-button"
                                onClick={() => setShowDocumentModal(true)}
                                aria-label="Add Existing Document"
                            >
                                <FilePlus className="icon-button-icon" />
                                <span className="icon-button-tooltip">Add Existing Document</span>
                            </button>
                            <button
                                className="icon-button"
                                onClick={() => setShowWebsiteModal(true)}
                                aria-label="Add External Website"
                            >
                                <Link className="icon-button-icon" />
                                <span className="icon-button-tooltip">Add External Website</span>
                            </button>
                        </div>
                    </Card>
                    <SelectDocumentModal
                        isOpen={showDocumentModal}
                        onClose={() => setShowDocumentModal(false)}
                        onSelect={handleSelectDocument}
                        token={token}
                    />
                    <AddWebsiteModal
                        isOpen={showWebsiteModal}
                        onClose={() => setShowWebsiteModal(false)}
                        onAdd={handleAddWebsite}
                    />
                    <AddContentModal
                        isOpen={showAddContentModal}
                        onClose={() => setShowAddContentModal(false)}
                        onAdd={handleAddContent}
                        token={token}
                    />
                </>
            )}
        </div>
    );
};