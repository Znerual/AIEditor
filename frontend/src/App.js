// src/App.js
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill from 'react-quill';
import { useWebSocket } from './hooks/useWebSocket';
import { EditorToolbar } from './components/Editor/EditorToolbar';
import { FileUpload } from './components/Sidebar/FileUpload';
import { ChatWindow } from './components/Chat/ChatWindow';
import { DebugPanel } from './components/Debug/DebugPanel';
import 'react-quill/dist/quill.snow.css';

// Import CSS files
import './styles/App.css';
import './styles/components.css';
import './styles/globals.css'; 

const App = () => {
    // State management
    const [uploadedStructureFile, setUploadedStructureFile] = useState();
    const [uploadedContentFiles, setUploadedContentFiles] = useState([]);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [debugEvents, setDebugEvents] = useState([]);
    const [chatMessages, setChatMessages] = useState([]);
    const [editorContent, setEditorContent] = useState('');
    const quillRef = useRef(null);
    
    // Handler functions
    const handleAutocompletion = (event) => {
        console.log("Show Autocompletion", event);
        // Implementation for autocompletion
    };

    const handleChatAnswer = useCallback((answer) => {
        console.log('Received chat answer:', answer);
        setChatMessages(prev => [...prev, { text: answer, sender: 'server' }]);
    }, []);

    const handleStructureParsed = useCallback((newContent) => {
        setEditorContent(newContent);
    }, []);

    const handleStructureUpload = useCallback((file) => {
        console.log("Handling structure upload", file);
        setUploadedStructureFile(file);
        // Implementation for structure upload
    }, []);

    const handleContentUpload = useCallback((files) => {
        console.log("Handling content upload", files);
        setUploadedContentFiles(files);
        // Implementation for content upload
    }, []);

    const handleEditorSelectionChange = useCallback((range, source, editor) => {
        console.log('Selection changed', range);
        // Implementation for selection change
    }, []);


    // WebSocket event handlers
    const socketEvents = useMemo(() => ({
        connect: () => console.log('connected'),
        disconnect: () => console.log('disconnected'),
        autocompletion: handleAutocompletion,
        chat_answer: handleChatAnswer,
        structure_parsed: handleStructureParsed,
        test: () => console.log("Test Event"),
    }), []); // Add any dependencies that might change the handlers, for example handleAutocompletion, handleChatAnswer, handleStructureParsed


    const { emit, status, debugEvents: wsDebugEvents } = useWebSocket(socketEvents);

    // Update debug events whenever websocket events occur
    useEffect(() => {
        setDebugEvents(wsDebugEvents);
    }, [wsDebugEvents]);

    // Event handlers
    const handleEditorChange = useCallback((content, delta, source, editor) => {
        const ops = delta.ops
        emit('text_change', ops );
        setEditorContent(content);
        if (process.env.REACT_APP_DEBUG) {
            setDebugEvents(prev => [...prev, { 
                type: 'editor_change',
                content,
                delta,
                timestamp: new Date()
            }]);
        }
    }, [emit, setEditorContent]);

    const handleChatSubmit = useCallback((message) => {
      if (message.trim()) {
        setChatMessages([...chatMessages, { text: message, sender: 'user' }]);
        emit('chat', { text: message });
      }
    }, [emit, chatMessages]);

    return (
        <div className="app-container">
            <EditorToolbar 
                onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
                sidebarOpen={sidebarOpen}
            />
            
            <div className="main-content">
                <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
                  <div className="sidebar-content">
                      <FileUpload 
                          title="Structure Template" 
                          onUpload={handleStructureUpload}
                          uploadedFiles={uploadedStructureFile}
                      />
                      <FileUpload 
                          title="Content Files" 
                          onUpload={handleContentUpload}
                          multiple 
                          uploadedFiles={uploadedContentFiles}
                      />
                      <ChatWindow 
                          messages={chatMessages}
                          onSend={handleChatSubmit}
                      />
                  </div>
                </div>
                <div className="editor-container">
                    <ReactQuill
                        ref={quillRef}
                        value={editorContent}
                        onChange={handleEditorChange}
                        onChangeSelection={handleEditorSelectionChange}
                        modules={{
                            toolbar: [
                                [{ header: [1, 2, 3, false] }],
                                ['bold', 'italic', 'underline', 'strike'],
                                [{ list: 'ordered' }, { list: 'bullet' }],
                                [{ color: [] }, { background: [] }],
                                ['clean']
                            ]
                        }}
                    />
                </div>

                {process.env.REACT_APP_DEBUG && (
                    <DebugPanel 
                        events={debugEvents}
                        socketStatus={status}
                    />
                )}
            </div>
        </div>
    );
};

export default App;