// src/components/Sidebar/FileUpload.js
import { Card } from '../ui/card'
import { Upload } from 'lucide-react';

export const FileUpload = ({ title, onUpload, multiple = false, uploadedFiles = []}) => {
    return (
        <div className="upload-section">
            <h2 className="font-medium mb-4">{title}</h2>
            <Card className="upload-card">
            <div className="upload-container">
                <Upload className="upload-icon" />
                <input
                type="file"
                onChange={onUpload}
                className="hidden"
                id="structure-upload"
                {...(multiple ? { multiple: true } : {})} // Add multiple attribute if true
                />
                <label
                htmlFor="structure-upload"
                className="upload-label"
                >
                Upload Template
                </label>
            </div>
            </Card>
            {multiple && ( // Conditionally render file-list only if multiple is true
                <div className="file-list">
                    {uploadedFiles.map((file, index) => (
                        <div key={index} className="file-item">
                            {file.name}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};