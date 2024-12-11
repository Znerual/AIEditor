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
    const [suggestions, setSuggestions] = useState([]);
    const [suggestionIndex, setSuggestionIndex] = useState(0);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [cursorPositionBeforeSuggestion, setCursorPositionBeforeSuggestion] = useState(null);
    const [userTypedText, setUserTypedText] = useState('');
    const quillRef = useRef(null);
    const { user, logout } = useAuth();

    const suggestionStyle = { 
        color: '#888',
        backgroundColor: '#f0f0f0',
    };
    const textStyle = {
        color: 'black',
        background: 'transparent'
    };

    const handleAuthenticationFailed = useCallback((event) => {
        console.log("Authentication failed", event);
        logout();
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
    
        // Store the cursor position before applying the suggestion
        setCursorPositionBeforeSuggestion(range.index);
        setUserTypedText('');  // Reset typed text when new suggestion appears

        // Show the first suggestion
        const suggestionText = event.suggestions[0];
        quillEditor.insertText(range.index, suggestionText, suggestionStyle, 'silent'); // Insert with custom formats
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

    const matchesSuggestion = (typed, suggestion) => {
        if (!typed || !suggestion) return false;
        
        // Case-sensitive match for explicitly typed capitals
        if (/[A-Z]/.test(typed)) {
            return suggestion.startsWith(typed);
        }
        
        // Case-insensitive match for lowercase typing
        return suggestion.toLowerCase().startsWith(typed.toLowerCase());
    };

    const handleKeyDown = useCallback((event) => {
        if (!showSuggestions) return;
        console.log("[KeyDown] Show suggestions ", showSuggestions);
       
        const quillEditor = quillRef.current.getEditor();
        switch (event.key) {
            case 'ArrowDown':
            case 'ArrowUp': {
                event.preventDefault();
                
                // Remove previous suggestion
                if (cursorPositionBeforeSuggestion) {
                    quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestions[suggestionIndex].length + 1);
                }

                const newIndex = event.key === 'ArrowDown'
                    ? (suggestionIndex + 1) % suggestions.length
                    : (suggestionIndex - 1 + suggestions.length) % suggestions.length;
                
                // Insert new suggestion
                const newSuggestion = suggestions[newIndex];
                quillEditor.insertText(cursorPositionBeforeSuggestion, newSuggestion, suggestionStyle, 'silent');
                quillEditor.setSelection(cursorPositionBeforeSuggestion, 0, 'silent');

                setSuggestionIndex(newIndex);
                setUserTypedText('');
                break;
            } case 'Enter':
            case 'Tab': {
                event.preventDefault();

                if (!cursorPositionBeforeSuggestion) return;
                // Accept the current suggestion
                const suggestion = suggestions[suggestionIndex];
                // Remove the temporary formatting
                quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestion.length + 1, 'silent');
                
                // Insert the final text with normal formatting
                quillEditor.insertText(cursorPositionBeforeSuggestion, suggestion, textStyle, 'silent');

                // Move cursor to end of inserted text
                quillEditor.setSelection(cursorPositionBeforeSuggestion + suggestion.length, 0, 'silent');

                // Clean up suggestion state
                setShowSuggestions(false);
                setCursorPositionBeforeSuggestion(null);
                setUserTypedText('');
                break;
            } case 'Shift': {
                // Ignore shift key presses
                break;
            } default: {
                 // Skip if it's a modifier key or non-character key
                 if (event.key.length !== 1 && event.key !== 'Backspace' && event.key !== 'Escape') {
                    return;
                }

                event.preventDefault();
                
                let newTypedText = userTypedText;
                if (event.key === 'Backspace') {
                    newTypedText = userTypedText.slice(0, -1);
                } else if (event.key === 'Escape') {
                    newTypedText = '';
                } else {
                    newTypedText = userTypedText + event.key;
                }
                setUserTypedText(newTypedText);

                // Check if typed text matches the start of the current suggestion
                const currentSuggestion = suggestions[suggestionIndex];
                if (matchesSuggestion(newTypedText, currentSuggestion) && event.key !== 'Escape') {
                    // Update the display with partially accepted suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length + 1, 'silent');
                    }
                    
                    // Insert accepted part in black
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, textStyle, 'silent');

                    // Insert remaining suggestion in gray
                    const remainingSuggestion = currentSuggestion.slice(newTypedText.length);
                    quillEditor.insertText(
                        cursorPositionBeforeSuggestion + newTypedText.length,
                        remainingSuggestion,
                        suggestionStyle,
                        'silent'
                    );
                    
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0, 'silent');
                    
    
                } else {
                    // If there's a mismatch, remove the suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length + 1, 'silent');
                    }
                    
                    // Insert the typed text
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, textStyle, 'silent');
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0, 'silent');
                    
                    // Clean up suggestion state
                    setShowSuggestions(false);
                    setCursorPositionBeforeSuggestion(null);
                    setUserTypedText('');
                }
                break;
            }
                
        }
    }, [showSuggestions, suggestions, suggestionIndex, cursorPositionBeforeSuggestion, userTypedText]);

    const socketEvents = useMemo(() => ({
        server_connects: () => console.log('server connected'),
        server_disconnects: () => console.log('server disconnected'),
        server_authentication_failed: handleAuthenticationFailed,
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
        if (source === 'user') {

            const range = editor.getSelection();
            if (range) {
                emit('client_text_change', {
                    delta: delta.ops,
                    documentId: documentId,
                    cursorPosition: range.index
                });
            }
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
    }, [documentId, emit]);



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
                        //onChangeSelection={handleEditorSelectionChange}
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

