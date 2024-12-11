// src/components/Sidebar/FileUpload.js
import { useState } from 'react';
import { Card } from '../ui/card'
import { Upload, ChevronDown, ChevronUp } from 'lucide-react';

import '../../styles/uploadSections.css';

export const StructurUpload = ({ title, onUpload, uploadedFile }) => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [selectedFile, setSelectedFile] = useState(uploadedFile); // State to track selected files

    const toggleCollapse = () => {
        setIsCollapsed(!isCollapsed);
    };

    const handleFileChange = (event) => {
        const files = Array.from(event.target.files);
        setSelectedFile(files); // Update state with selected files
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
                            />
                            <label htmlFor="structure-upload" className="upload-label">
                                {/* Show filename or default label */}
                                {selectedFile && selectedFile.length > 0
                                ? selectedFile[0].name
                                : "Upload Template"}
                            </label>
                        </div>
                    </Card>
                </>
            )}
        </div>
    );
};