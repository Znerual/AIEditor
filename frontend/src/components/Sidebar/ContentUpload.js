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
    Link
} from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { AddWebsiteModal } from './AddWebsiteModel';
import { SelectDocumentModal } from './SelectDocumentModal';
import { PdfParser } from '../../utils/pdfUtils';
import { DocxParser } from '../../utils/wordUtils';
import { WebsiteParser } from '../../utils/websiteUtils';
import { documentParser } from '../../utils/documentUtils';
import '../../styles/uploadSections.css';


export const ContentUpload = ({ title, onUpload, uploadedFiles = [] }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]); // State to track selected files
    const [fileSelections, setFileSelections] = useState({}); // Track selection state of each file
    const [showDocumentModal, setShowDocumentModal] = useState(false);
    const [showWebsiteModal, setShowWebsiteModal] = useState(false);
    const [showFileContentModal, setShowFileContentModal] = useState(false);
    const [currentFileContent, setCurrentFileContent] = useState(null);
    const [currentExtractedText, setCurrentExtractedText] = useState(null);
    const [currentFileName, setCurrentFileName] = useState(null);

    const { token } = useAuth();

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    useEffect(() => {
      // Filter fileSelections to only include selected files (where value is true)
      const selectedFileNames = Object.entries(fileSelections)
          .filter(([key, value]) => value)
          .map(([key]) => key);

      // Filter selectedFiles to only include files that are selected
      const updatedFiles = selectedFiles.filter(file => selectedFileNames.includes(file.name));
      
      uploadedFiles = updatedFiles; // Pass only the selected files to onUpload 
    }, [selectedFiles, fileSelections, onUpload]);


    const extract_text_from_image = async (file) => {
      console.log("Simulating text extraction from image:", file.name);
      // Replace this with your actual image-to-text logic (e.g., using an OCR library)
      return new Promise((resolve) => {
          setTimeout(() => {
          resolve("Extracted text from image: " + file.name);
          }, 1000);
      });
    };


    const handleFilesChange = useCallback(async (filesOrEvent) => {
        let newFiles;
        console.log("handleFilesChange filesOrEvent", filesOrEvent);
        // Check if it's an event from an input element or a direct array of files
        if (filesOrEvent.target && filesOrEvent.target.files) {
            newFiles = Array.from(filesOrEvent.target.files);
        } else {
            newFiles = Array.from(filesOrEvent); // Assume it's an array of files
        }


        // If it was an event, we pass it through, otherwise, we create a fake one
        const eventToPass = filesOrEvent.target ? filesOrEvent : { target: { files: newFiles } };
        console.log("handleFileChange eventToPass", eventToPass);
        const files = eventToPass.target.files;
        console.log("Handling content upload", files);
        if (!files) return;
        
        let extractedContent = [];

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fileExtension = file.name.split('.').pop().toLowerCase();

            if (fileExtension === 'pdf') {
                // Extract text from PDF
                try {
                    const text = await PdfParser.readPdf(file);
                    extractedContent.push({ file, text:text });
                } catch (error) {
                    console.error("Error extracting text from PDF", file.name, error);
                }
            } else if (['txt', 'md'].includes(fileExtension)) { 
                // Extract text from text file
                try {
                    let fr = new FileReader();
                    fr.onload = function() {
                        const text = fr.result;
                        extractedContent.push({ file, text:text });
                    };
                    fr.readAsText(file);
                } catch (error) {
                    console.error("Error extracting text from text file", file.name, error);
                }
            } else if (fileExtension === 'docx') {
                // Extract text from PDF, DOC, DOCX
                try {
                    const text = await DocxParser.readDocx(file);
                    extractedContent.push({ file, text:text });
                } catch (error) {
                    console.error("Error extracting text from Docx", file.name, error);
                }
            } else if (fileExtension === 'doc') {
                // Extract text from PDF, DOC, DOCX
                try {
                    console.log("Extracting text from DOC file is currently not supported."); 
                } catch (error) {
                    console.error("Error extracting text from Doc", file.name, error);
                }
            } else {
                // Assume it's an image and extract text from image
                try {
                    const text = await extract_text_from_image(file);
                    extractedContent.push({ file, text:text });
                } catch (error) {
                    console.error("Error extracting text from image", file.name, error);
                }
            }
        }

        extractedContent = structuredClone(extractedContent); // Deep copy the array

        setSelectedFiles((prevFiles) => {
            console.log("Set Selected Files ", prevFiles, " new Files ",newFiles);
            const currentFiles = Array.isArray(prevFiles) ? prevFiles : [];
            return [...currentFiles, ...extractedContent];
        });

        setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            extractedContent.forEach((file) => {
                newSelections[file.name] = true;
            });
            return newSelections;
        });

        // Update state with extracted content
        onUpload(extractedContent);

        // You can now do something with the extractedContent, like sending it to a server or storing it
        console.log("Extracted content:", extractedContent);
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
      let extractedContent = [];
      const id = document.id;
      try {
          const text = await documentParser.readDocument(document);
          extractedContent.push({ file:{ name:id, file:document.content, lastModified: new Date()}, text:text });
      } catch (error) {
          console.error("Error extracting text from Document", document.id, error);
      }
      extractedContent = structuredClone(extractedContent); // Deep copy the array
      setSelectedFiles((prevFiles) => {
        return [...prevFiles, ...extractedContent];
      });

      setFileSelections((prevSelections) => {
          const newSelections = { ...prevSelections };
          newSelections[id] = true;
        
          return newSelections;
      });
      
    }, []);


    const handleAddWebsite = useCallback(async (url) =>  {
        // Handle the added website
        console.log("Added website:", url);
        setShowWebsiteModal(false);
        let extractedContent = [];
        try {
            const text = await WebsiteParser.readWebsite(url);
            extractedContent.push({ file:{ name:url, file:url, lastModified: new Date()}, text:text });
        } catch (error) {
            console.error("Error extracting text from Website", url, error);
        }

        onUpload(extractedContent);
        extractedContent = structuredClone(extractedContent); // Deep copy the array
        setSelectedFiles((prevFiles) => {
            return [...prevFiles, ...extractedContent];
        });

        setFileSelections((prevSelections) => {
            const newSelections = { ...prevSelections };
            newSelections[url] = true;
            return newSelections;
        });

        console.log("Add website ", fileSelections, selectedFiles)

    }, [selectedFiles, fileSelections, onUpload]);

    const handleFileClick = (file) => {
      setCurrentFileName(file.name);
      setCurrentFileContent(file.file); 
      setCurrentExtractedText(file.text);
      setShowFileContentModal(true);
    };
  
    const closeFileContentModal = () => {
      setShowFileContentModal(false);
      setCurrentFileContent(null);
      setCurrentExtractedText(null);
    };

    return (
        <div className="upload-section">
          {/* File Content Modal */}
          {showFileContentModal && (
            <div className="file-content-modal-backdrop">
              <div className="file-content-modal">
                <div className="file-content-header">
                  <h2>{currentFileName}</h2>
                  <button onClick={closeFileContentModal} className="close-modal-button">
                    <X size={20} />
                  </button>
                </div>
                <div className="file-content-body">
                  <div className="file-content">
                    {/* Display the content of the file here */}
                    <pre>{currentFileContent ? currentFileContent.toString() : 'Loading...'}</pre>
                  </div>
                  <div className="extracted-text">
                    {/* Display the extracted text here */}
                    <pre>{currentExtractedText || 'Loading...'}</pre>
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
                          onClick={() => toggleFileSelection(file.file.name)}
                        >
                          {fileSelections[file.file.name] ? (
                            <CheckSquare />
                          ) : (
                            <Square />
                          )}
                        </div>
                        <span
                          className={
                            fileSelections[file.file.name] ? "selected-file" : ""
                          }
                          onClick={() => handleFileClick(file.file)}
                        >
                          {file.file.name}
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