import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
 
 export const FileContentManagement = () => {
    const [fileContents, setFileContents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedFileContent, setSelectedFileContent] = useState(null); // State to store the content of the selected document
    const [selectedFile, setSelectedFile] = useState(null);
    const { token } = useAuth();

    useEffect(() => {
        const fetchFileContents = async () => {
            try {
                const response = await fetch('http://localhost:5000/api/admin/file_contents', {
                    method: 'GET',
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch file contents');
                }
                const data = await response.json();
                setFileContents(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchFileContents();
    }, [token]);

    const handleDeleteFileContent = async (fileContentId) => {
        if (!window.confirm('Are you sure you want to delete this File?')) return;

        try {
            const response = await fetch(`http://localhost:5000/api/admin/file_contents/${fileContentId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to delete content');
            }
            // Update the documents list after deletion
            setFileContents(fileContents.filter(con => con.id !== fileContentId));
        } catch (err) {
            console.error(err);
            alert('Failed to delete content.');
        }
    };

    const handleFileContentClick = async (fileContentId) => {
        try {
            console.log("FileContent click");
            const response = await fetch(`http://localhost:5000/api/admin/file_contents/${fileContentId}`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error('Failed to fetch file content');
            }
            const data = await response.json();
            console.log("Data ", data)
            setSelectedFile(data);
            setSelectedFileContent(data.text_content);
            
        } catch (err) {
            console.error(err);
            alert('Failed to fetch content.');
        }
    };
    
    return (
        <div className="file-content-management">
            <h2>File Content Management</h2>
            {loading && <p>Loading file contents...</p>}
            {error && <p>Error: {error}</p>}
            {!loading && !error && (
                <>
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Filepath</th>
                                <th>Size</th>
                                <th>File Type</th>
                                <th>Last Modified</th>
                                <th>Creation Date</th>
                                <th>Text Content Hash</th>
                                <th>Content Hash</th>
                                <th>User ID</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {fileContents.map(fileContent => (
                                <tr key={fileContent.id}>
                                    <td>
                                        <button onClick={() => handleFileContentClick(fileContent.id)}>
                                            {fileContent.id}
                                        </button>
                                    </td>
                                    <td>{fileContent.filepath}</td>
                                    <td>{fileContent.size}</td>
                                    <td>{fileContent.file_type}</td>
                                    <td>{fileContent.last_modified ? new Date(fileContent.last_modified).toLocaleString() : 'N/A'}</td>
                                    <td>{fileContent.creation_date ? new Date(fileContent.creation_date).toLocaleString() : 'N/A'}</td>
                                    <td>{fileContent.text_content_hash}</td>
                                    <td>{fileContent.content_hash}</td>
                                    <td>{fileContent.user_id}</td>
                                    <td>
                                        <button onClick={() => handleDeleteFileContent(fileContent.id)}>Delete</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {/* Display the selected file content */}
                    {selectedFileContent && (
                        <div className="selected-file-content">
                            <h3>Selected File Content:</h3>
                            {/* You might need to format the content appropriately */}
                            <pre>{JSON.stringify(selectedFileContent, null, 2)}</pre>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};