// src/App.js
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill, { Quill } from 'react-quill';
import { useWebSocket } from './hooks/useWebSocket';
import { EditorToolbar } from './components/Editor/EditorToolbar';
import { FileUpload } from './components/Sidebar/FileUpload';
import { ChatWindow } from './components/Chat/ChatWindow';
import { DebugPanel } from './components/Debug/DebugPanel';
import { useAuth } from './contexts/AuthContext';
import 'react-quill/dist/quill.snow.css';

// Import CSS files
import './styles/App.css';
import './styles/components.css';
import './styles/globals.css'; 

// const Delta = Quill.import('delta');

export const MainApp = () => {
    // State management
    const [uploadedStructureFile, setUploadedStructureFile] = useState();
    const [uploadedContentFiles, setUploadedContentFiles] = useState([]);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [debugEvents, setDebugEvents] = useState([]);
    const [chatMessages, setChatMessages] = useState([]);
    const [editorContent, setEditorContent] = useState('');
    const [documentId, setDocumentId] = useState('');
    const [cursorPosition, setCursorPosition] = useState(null);
    const [ignoreNextSuggestion, setIgnoreNextSuggestion] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestionIndex, setSuggestionIndex] = useState(0);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [contentBeforeSuggestion, setContentBeforeSuggestion] = useState(null);
    const [cursorPositionBeforeSuggestion, setCursorPositionBeforeSuggestion] = useState(null);
    const quillRef = useRef(null);
    const { user, logout } = useAuth();

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

    const handleChatAnswer = useCallback((answer) => {
        console.log('Received chat answer:', answer);
        setChatMessages(prev => [...prev, { text: answer, sender: 'server' }]);
    }, []);

    const handleAutocompletion = useCallback((event) => {
        console.log("Show Autocompletion", event);
        if (!event.cursorPosition || !event.suggestions || event.suggestions.length === 0) {
            console.log("No suggestions or cursor position available. Hiding suggestions.");
            setShowSuggestions(false);
            setSuggestions([]);
            setSuggestionIndex(0);
            return;
        }
    
        const quillEditor = quillRef.current.getEditor();
        const range = quillEditor.getSelection();
        if (!range) {
            console.warn("No selection found. Aborting autocompletion.");
            setShowSuggestions(false);
            return;
        }
    
        // Store the content and cursor position before applying the suggestion
        setContentBeforeSuggestion(quillEditor.getContents());
        setCursorPositionBeforeSuggestion(range.index);
    
        // Apply the first suggestion immediately
        const suggestionText = event.suggestions[0];
        const suggestionStyle = { color: '#888' };  // Define your style
        quillEditor.insertText(range.index, suggestionText, suggestionStyle); // Insert with custom formats
        quillEditor.setSelection(range.index, 0, 'silent');
    
        setSuggestions(event.suggestions);
        setSuggestionIndex(0); // Reset to the first suggestion
        setShowSuggestions(true);
    }, []);

    const handleChatSubmit = useCallback((message) => {
        if (message.trim()) {
          setChatMessages([...chatMessages, { text: message, sender: 'user' }]);
          emit('client_chat', { text: message });
        }
      }, [chatMessages]);

    const handleDocumentCreated = useCallback((event) => {
        console.log("Received document id ",event.documentId);
        setDocumentId(event.documentId);
        emit('client_get_document', { documentId: event.documentId });
    }, [setDocumentId]);

    const handleGetContent = useCallback((event) => {
        console.log("Received document", event); // event has document_id and content fields
        if (event && event.content) {
            setEditorContent(event.content);
            setDocumentId(event.documentId);
        }
    }, [setDocumentId, setEditorContent]);

    const handleKeyDown = useCallback((event) => {
        console.log("[KeyDown] Show suggestions ", showSuggestions);
        if (showSuggestions) {
            const quillEditor = quillRef.current.getEditor();
            const range = quillEditor.getSelection();

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                const newIndex = (suggestionIndex + 1) % suggestions.length;
                
                // Revert to the content before the suggestion
                quillEditor.setContents(contentBeforeSuggestion, 'silent');

                // Insert the new suggestion
                const suggestionText = suggestions[newIndex];
                const suggestionStyle = { color: '#888' };  // Define your style
                quillEditor.insertText(range.index, suggestionText, suggestionStyle); // Insert with custom formats
                quillEditor.setSelection(range.index + suggestionText.length, 0, 'silent');
                setSuggestionIndex(newIndex);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                const newIndex = (suggestionIndex - 1 + suggestions.length) % suggestions.length;
                
                // Revert to the content before the suggestion
                quillEditor.setContents(contentBeforeSuggestion, 'user');

                // Insert the new suggestion
                const suggestionText = suggestions[newIndex];
                const suggestionStyle = { color: '#888' };  // Define your style
                quillEditor.insertText(range.index, suggestionText, suggestionStyle); // Insert with custom formats
                quillEditor.setSelection(range.index + suggestionText.length, 0, 'silent');
                setSuggestionIndex(newIndex);

                setSuggestionIndex(newIndex);
            } else if (event.key === 'Enter') {
                event.preventDefault();
              
                quillEditor.formatText(range.index - suggestions[suggestionIndex].length, suggestions[suggestionIndex].length, {color : '#FFF'}, 'silent');

                setShowSuggestions(false);
                setContentBeforeSuggestion(null);
                setCursorPositionBeforeSuggestion(null);
            } else if (event.key === 'Escape') {
                event.preventDefault();
                // Revert to the content before the suggestion
                quillEditor.setContents(contentBeforeSuggestion, 'user');
                quillEditor.setSelection(cursorPositionBeforeSuggestion, 0, 'user');

                setShowSuggestions(false);
                setContentBeforeSuggestion(null); // Clear the stored content
                setCursorPositionBeforeSuggestion(null);
                setIgnoreNextSuggestion(true);
            }
        }
    }, [showSuggestions, suggestions, suggestionIndex, contentBeforeSuggestion]);

    const socketEvents = useMemo(() => ({
        server_connects: () => console.log('server connected'),
        server_disconnects: () => console.log('server disconnected'),
        server_document_created: handleDocumentCreated,
        server_sent_document_content: handleGetContent,
        disconnect: () => console.log('disconnected'),
        server_autocompletion_suggestions: handleAutocompletion,
        server_chat_answer: handleChatAnswer,
        structure_parsed: handleStructureParsed,
        test: () => console.log("Test Event"),
    }), [handleDocumentCreated]); // Add any dependencies that might change the handlers, for example handleAutocompletion, handleChatAnswer, handleStructureParsed

    useEffect(() => {
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handleKeyDown]);

    const { emit, status, debugEvents: wsDebugEvents } = useWebSocket(socketEvents);

    // Update debug events whenever websocket events occur
    useEffect(() => {
        setDebugEvents(wsDebugEvents);
    }, [wsDebugEvents]);

    const handleEditorChange = useCallback((content, delta, source, editor) => {
        console.log('Editor change source: ', source, 'delta', delta, 'showSuggestions', showSuggestions)
        if (source === 'user') {
            if (ignoreNextSuggestion) {  // Check the flag
                setIgnoreNextSuggestion(false); // Reset the flag
                setEditorContent(content);
                return; // Ignore this suggestion event
            }
            const ops = delta.ops;
            const range = editor.getSelection();
            let index = range ? range.index : null;
            if (showSuggestions && index != null) {
                const quillEditor = quillRef.current.getEditor();
                quillEditor.formatText(cursorPositionBeforeSuggestion, quillEditor.getLength() - cursorPositionBeforeSuggestion, {
                    'suggestion': false, // Clear the custom format
                    'suggestion-index': false,
                }, 'silent');
            }
            emit('client_text_change', { delta: ops, documentId: documentId, cursorPosition: cursorPosition });
        }
        setEditorContent(content);

        if (process.env.REACT_APP_DEBUG) {
            setDebugEvents(prev => [...prev, { 
                type: 'editor_change',
                content,
                delta,
                timestamp: new Date()
            }]);
        }
    }, [documentId, cursorPosition, showSuggestions, contentBeforeSuggestion, cursorPositionBeforeSuggestion, ignoreNextSuggestion]);

    const handleEditorSelectionChange = useCallback((range, source, editor) => {
        console.log("Selection changed", range);
        if (range) {
            setCursorPosition(range.index);
        }
    }, []);


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
                      <button onClick={logout}>Logout</button>
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

