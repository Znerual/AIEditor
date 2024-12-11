// src/components/Sidebar/FileUpload.js
import { useState, useEffect } from 'react';
import { Card } from '../ui/card'
import { Upload, 
    ChevronDown, 
    ChevronUp, 
    CheckSquare,
    Square,
    X,
    Trash2, 
    CheckCircle2
} from 'lucide-react';

import '../../styles/uploadSections.css';

export const ContentUpload = ({ title, onUpload, uploadedFiles = [] }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]); // State to track selected files
    const [fileSelections, setFileSelections] = useState({}); // Track selection state of each file

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    const handleFilesChange = (event) => {
        const newFiles = Array.from(event.target.files);
        // Add files to selectedFiles, ensuring it's always treated as an array
        setSelectedFiles((prevFiles) => {
            const currentFiles = Array.isArray(prevFiles) ? prevFiles : []; // Ensure prevFiles is an array
            return [...currentFiles, ...newFiles];
        });

        setFileSelections((prevSelections) => {
        const newSelections = { ...prevSelections };
        newFiles.forEach((file) => {
            newSelections[file.name] = true;
        });
        return newSelections;
        });

        onUpload(event);
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

    // Update selectedFiles when uploadedFiles prop changes
    useEffect(() => {
        // Ensure uploadedFiles is an array before updating the state
        if (Array.isArray(uploadedFiles)) {
            setSelectedFiles(uploadedFiles);

            const initialSelections = {};
            uploadedFiles.forEach((file) => {
                initialSelections[file.name] = false; // Not selected initially
            });
            setFileSelections(initialSelections);
        }
    }, [uploadedFiles]);

    return (
        <div className="upload-section">
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
              <Card className="upload-card">
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
                      ? `${selectedFiles.length} files selected`
                      : "Upload Template"}
                  </label>
                </div>
              </Card>
    
              {selectedFiles.length > 0 && (
                <div className="file-list-container">
                  <div className="file-list">
                    {selectedFiles.map((file, index) => (
                      <div
                        key={index}
                        className="file-item"
                        onClick={() => toggleFileSelection(file.name)}
                      >
                        <div className="file-checkbox">
                          {fileSelections[file.name] ? (
                            <CheckSquare />
                          ) : (
                            <Square />
                          )}
                        </div>
                        <span
                          className={
                            fileSelections[file.name] ? "selected-file" : ""
                          }
                        >
                          {file.name}
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