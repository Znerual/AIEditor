// src/components/Sidebar/FileUpload.js
import { useState, useEffect, useCallback } from 'react';
import { Card } from '../ui/card'
import { Upload, 
    ChevronDown, 
    ChevronUp, 
    CheckSquare,
    Square,
    X,
    Trash2, 
    CheckCircle2,
    FilePlus,
    Link,
    FolderPlus
} from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { AddWebsiteModal } from './AddWebsiteModel';
import { SelectDocumentModal } from './SelectDocumentModal';
import { AddContentModal } from './AddContentModal';
import { documentParser } from '../../utils/documentUtils';
import '../../styles/uploadSections.css';


export const ContentUpload = ({ title, onUpload }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]); // State to track selected files
    const [fileSelections, setFileSelections] = useState({}); // Track selection state of each file
    const [showDocumentModal, setShowDocumentModal] = useState(false);
    const [showWebsiteModal, setShowWebsiteModal] = useState(false);
    const [showFileContentModal, setShowFileContentModal] = useState(false);
    const [showAddContentModal, setShowAddContentModal] = useState(false);
    const [currentFile, setCurrentFile] = useState(null);

    const { token } = useAuth();

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    useEffect(() => {
      console.log("Trigger updating the updatedFiles");
      // Filter fileSelections to only include selected files (where value is true)
      const selectedFileNames = Object.entries(fileSelections)
          .filter(([key, value]) => value)
          .map(([key]) => key);

      console.log("selectedFileNames", selectedFileNames);

      // Filter selectedFiles to only include files that are selected
      const updatedFiles = selectedFiles.filter(file => selectedFileNames.includes(file.filename));
      
      
      onUpload(updatedFiles);
    }, [selectedFiles, fileSelections, onUpload]);

    const handleFilesChange = useCallback(async (filesOrEvent) => {
        let newFiles;
        console.log("handleFilesChange filesOrEvent", filesOrEvent);
        // Check if it's an event from an input element or a direct array of files
        if (!(filesOrEvent.target && filesOrEvent.target.files)) {
            newFiles = Array.from(filesOrEvent); // Assume it's an array of files
        } else {
            newFiles = filesOrEvent;
        }

        // If it was an event, we pass it through, otherwise, we create a fake one
        const eventToPass = filesOrEvent.target ? filesOrEvent : { target: { files: newFiles } };
        console.log("handleFileChange eventToPass", eventToPass);
        const files = eventToPass.target.files;
        console.log("Handling content upload", files);
        if (!files) return;
        
        try {
          const formData = new FormData();
          files.forEach(file => {
            formData.append('files', file);
            formData.append(`${file.name}.lastModified`, file.lastModified);
          });
    
          const response = await fetch('http://localhost:5000/api/extract_text', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
          });
          console.log("Response ", response);
    
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
    
          const data = await response.json();

          console.log("Data ", data);
          if (data.success !== true) {
            throw new Error('Failed to extract text from files');
          }

          // Add the raw file to each successful result
          const resultsWithRawFiles = data.results.map((result, index) => {
            if (result.success) {
              return {
                ...result,
                raw: files[index]
              };
            }
            return result;
          });
          
          setSelectedFiles((prevFiles) => {
            const currentFiles = Array.isArray(prevFiles) ? prevFiles : [];
            const newFiles = Array.isArray(resultsWithRawFiles) ? resultsWithRawFiles : [];
            console.log("Set Selected Files ", prevFiles, " new Files ",newFiles);
            return [...currentFiles, ...newFiles];
          });

          setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            resultsWithRawFiles.forEach((file) => {
                newSelections[file.filename] = true;
            });
            return newSelections;
          });

          // // Update state with extracted content
          // onUpload(uploadedFiles);


        } catch (err) {
          throw new Error('Failed to upload files ', err);
        }
    }, []);

    const handleDrop = useCallback((event) => {
      event.preventDefault();
      const files = event.dataTransfer.files;
      handleFilesChange(files);
    }, [handleFilesChange]);

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

    const toggleFileSelection = (fileName) => {
        setFileSelections((prevSelections) => ({
            ...prevSelections,
            [fileName]: !prevSelections[fileName],
        }));
    };

    const uncheckAllFiles = () => {
        setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            for (const fileName in newSelections) {
              newSelections[fileName] = false;
            }
            return newSelections;
        });
    };
    
    
    const clearSelectedFiles = () => {
        setSelectedFiles((prevFiles) =>
            prevFiles.filter((file) => !fileSelections[file.name])
        );

        setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            for (const fileName in prevSelections) {
                if (prevSelections[fileName]) {
                    delete newSelections[fileName];
                }
            }
            return newSelections;
        });
    };

    const selectAllFiles = () => {
        setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            for (const fileName in newSelections) {
                newSelections[fileName] = true;
            }
          return newSelections;
        });
    };

    const handleSelectDocument = useCallback(async (document) => {
      // Handle the selected document
      console.log("Selected document:", document);
      setShowDocumentModal(false);
  
      const id = document.id;
      try {
          const text = await documentParser.readDocument(document);
          const result = { filename: id, raw:document.content, document_id: id, success: true, text_extracted: text, message: 'Document extracted', content_type: 'document' };
          setSelectedFiles((prevFiles) => {
            return [...prevFiles, result];
          });
          setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            newSelections[id] = true;
          
            return newSelections;
          });
          // onUpload(uploadedFiles);
          
      } catch (error) {
          console.error("Error extracting text from Document", document.id, error);
      }
    }, [onUpload]);


    const handleAddWebsite = useCallback(async (url) =>  {
        // Handle the added website
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
          setSelectedFiles((prevFiles) => {
            return [...prevFiles, data];
          });
  
          setFileSelections((prevSelections) => {
              const newSelections = { ...prevSelections };
              newSelections[data.filename] = true;
              return newSelections;
          });
          // onUpload(data);
        } catch (error) {
            console.error("Error extracting text from Website", url, error);
        }  

        console.log("Add website ", fileSelections, selectedFiles)

    }, [onUpload]);

    const handleFileClick = (file) => {
      console.log("File click ", file);
      setCurrentFile(file);
      setShowFileContentModal(true);
    };
  
    const closeFileContentModal = () => {
      setShowFileContentModal(false);
      setCurrentFile(null);
    };

    const handleAddContent = useCallback(async (content) => {
      // Handle the added content
      setShowAddContentModal(false);
  
      try {
        // Assuming content is an array of file-like objects
        const newFile = {
          filename: content.filepath,
          raw: {
            size: content.size,
            type: content.type,
            lastModified: content.lastModified,
          },
          success: true,
          text_extracted: content.text_content,
          message: 'Content added',
        };
    
  
        setSelectedFiles(prevFiles => [...prevFiles, newFile]);
        setFileSelections(prevSelections => {
          const newSelections = { ...prevSelections };
          newSelections[newFile.filename] = true;
          return newSelections;
        });
        // onUpload(newFile);
  
      } catch (error) {
        console.error("Error adding content", content, error);
      }
  }, []);

    return (
        <div className="upload-section">
          {/* File Content Modal */}
          {showFileContentModal && (
            <div className="file-content-modal-backdrop">
              <div className="file-content-modal">
                <div className="file-content-header">
                  <h2>{currentFile.filename}</h2>
                  <button onClick={closeFileContentModal} className="close-modal-button">
                    <X size={20} />
                  </button>
                </div>
                <div className="file-content-body">
                  <div className="file-content">
                    {/* Display the content of the file here */}
                    {currentFile.raw && (
                      <div className="file-content-details">
                        <pre>{currentFile.raw.type ? currentFile.raw.type.toString() : 'Unknown Type'}</pre>
                        <pre>{currentFile.raw.lastModified ? new Date(currentFile.raw.lastModified).toDateString() : 'No Creation Date'}</pre>
                        <pre>{currentFile.raw.size ? currentFile.raw.size : 'Unknown Size'}</pre>
                      </div>
                    )}
                  </div>
                  <div className="file-content-extracted-text">
                    {/* Display the extracted text here */}
                    <pre>{currentFile.text_extracted || 'No text extracted'}</pre>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div className="upload-header" onClick={toggleCollapse}>
            <h2 className="font-medium">{title}</h2>
            {isCollapsed ? (
              <ChevronUp className="collapse-icon" />
            ) : (
              <ChevronDown className="collapse-icon" />
            )}
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
                  <Upload className="upload-icon" />
                  <input
                    type="file"
                    onChange={handleFilesChange}
                    className="hidden-input"
                    id="content-upload"
                    multiple={true}
                  />
                  <label htmlFor="content-upload" className="upload-label">
                    {selectedFiles.length > 0
                      ? `${selectedFiles.length} files uploaded`
                      : "Upload Template"}
                  </label>
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
              {selectedFiles.length > 0 && (
                <div className="file-list-container">
                  <div className="file-list">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={index}
                        className="file-item"
                      >
                        <div 
                          className="file-checkbox"
                          onClick={() => toggleFileSelection(file.filename)}
                        >
                          {fileSelections[file.filename] ? (
                            <CheckSquare />
                          ) : (
                            <Square />
                          )}
                        </div>
                        <span
                          className={
                            fileSelections[file.filename] ? "selected-file" : ""
                          }
                          onClick={() => handleFileClick(file)}
                        >
                          {file.filename}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="buttons-container">
                    <button
                      className="select-all-button"
                      onClick={selectAllFiles}
                      aria-label="Select All" // Add aria-label for tooltip
                    >
                      <CheckCircle2 className="select-all-icon" />
                      <span className="tooltip">Select All</span> {/* Tooltip text */}
                    </button>
                    <button
                      className="clear-files-button"
                      onClick={uncheckAllFiles} // Call uncheckAllFiles
                      aria-label="Uncheck All" // Add aria-label for tooltip
                    >
                      <X className="clear-icon" />
                      <span className="tooltip">Uncheck All</span> {/* Tooltip text */}
                    </button>
                    <button
                      className="delete-selected-button"
                      onClick={clearSelectedFiles}
                      aria-label="Delete Selected" // Add aria-label for tooltip
                    >
                      <Trash2 className="delete-icon" />
                      <span className="tooltip">Delete Selected</span> {/* Tooltip text */}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      );
    };