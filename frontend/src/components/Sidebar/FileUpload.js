// src/components/Sidebar/FileUpload.js
import { useState } from 'react';
import { Card } from '../ui/card'
import { Upload, ChevronDown, ChevronUp } from 'lucide-react';

export const FileUpload = ({ title, onUpload, multiple = false, uploadedFiles = []}) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState(uploadedFiles); // State to track selected files

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    const handleFileChange = (event) => {
        const files = Array.from(event.target.files);
        setSelectedFiles(files); // Update state with selected files
        onUpload(event); // Call the original onUpload handler
      };

    return (
        <div className="upload-section">
            <div className="upload-header" onClick={toggleCollapse}>
                <h2 className="font-medium">{title}</h2>
                {isCollapsed ? <ChevronUp className="collapse-icon" /> : <ChevronDown className="collapse-icon" />}
            </div>
            {!isCollapsed && (
                <>
                    <Card className="upload-card">
                        <div className="upload-container">
                            <Upload className="upload-icon" />
                            <input
                                type="file"
                                onChange={handleFileChange}
                                className="hidden-input"
                                id="structure-upload"
                                {...(multiple ? { multiple: true } : {})} // Add multiple attribute if true
                            />
                            <label htmlFor="structure-upload" className="upload-label">
                                {/* Show filename or default label */}
                                {selectedFiles.length > 0
                                ? multiple
                                    ? `${selectedFiles.length} files selected`
                                    : selectedFiles[0].name
                                : "Upload Template"}
                            </label>
                        </div>
                    </Card>
                    {multiple && (
                         <div className="file-list">
                         {selectedFiles.map((file, index) => (
                           <div key={index} className="file-item">
                             {file.name}
                           </div>
                         ))}
                       </div>
                    )}
                </>
            )}
        </div>
    );
};