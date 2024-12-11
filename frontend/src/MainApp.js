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
    const [userTypedText, setUserTypedText] = useState('');
    const [shiftPressed, setShiftPressed] = useState(false);
    const quillRef = useRef(null);
    const { user, logout } = useAuth();


    // Add effect to track shift key state
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Shift') {
                setShiftPressed(true);
            }
        };
        
        const handleKeyUp = (e) => {
            if (e.key === 'Shift') {
                setShiftPressed(false);
            }
        };
        
        window.addEventListener('keydown', handleKeyDown);
        window.addEventListener('keyup', handleKeyUp);
        
        return () => {
            window.removeEventListener('keydown', handleKeyDown);
            window.removeEventListener('keyup', handleKeyUp);
        };
    }, []);

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
    
        // Store the content and cursor position before applying the suggestion
        setContentBeforeSuggestion(quillEditor.getContents());
        setCursorPositionBeforeSuggestion(range.index);
        setUserTypedText('');  // Reset typed text when new suggestion appears

        // Show the first suggestion
        const suggestionText = event.suggestions[0];
        const suggestionStyle = { 
            color: '#888',
            backgroundColor: '#f0f0f0',
         };  // Define your style
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
        const range = quillEditor.getSelection();

        switch (event.key) {
            case 'ArrowDown':
            case 'ArrowUp': {
                event.preventDefault();
                
                // Remove previous suggestion
                if (cursorPositionBeforeSuggestion) {
                    quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestions[suggestionIndex].length);
                }

                const newIndex = event.key === 'ArrowDown'
                    ? (suggestionIndex + 1) % suggestions.length
                    : (suggestionIndex - 1 + suggestions.length) % suggestions.length;
                
                // Insert new suggestion
                const newSuggestion = suggestions[newIndex];
                const tempFormat = {
                    color: '#888',
                    backgroundColor: '#f0f0f0',
                };

                quillEditor.insertText(cursorPositionBeforeSuggestion, newSuggestion, tempFormat);
                quillEditor.setSelection(cursorPositionBeforeSuggestion, 0);

                setSuggestionIndex(newIndex);
                break;
            } case 'Enter':
            case 'Tab': {
                event.preventDefault();

                if (!cursorPositionBeforeSuggestion) return;
                // Accept the current suggestion
                const suggestion = suggestions[suggestionIndex];
                // Remove the temporary formatting
                quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestion.length);
                
                // Insert the final text with normal formatting
                quillEditor.insertText(cursorPositionBeforeSuggestion, suggestion, {
                    color: 'black',
                    background: 'transparent'
                });

                // Move cursor to end of inserted text
                quillEditor.setSelection(cursorPositionBeforeSuggestion + suggestion.length, 0);

                // Clean up suggestion state
                setShowSuggestions(false);
                setContentBeforeSuggestion(null);
                setCursorPositionBeforeSuggestion(null);
                setUserTypedText('');
                break;
            } case 'Shift': {
                // Ignore shift key presses
                break;
            } default: {
                 // Skip if it's a modifier key or non-character key
                 if (event.key.length !== 1 && event.key !== 'Backspace') {
                    return;
                }

                event.preventDefault();
                
                let newTypedText = userTypedText;
                if (event.key === 'Backspace') {
                    newTypedText = userTypedText.slice(0, -1);
                } else {
                    newTypedText = userTypedText + event.key;
                }
                setUserTypedText(newTypedText);

                // Check if typed text matches the start of the current suggestion
                const currentSuggestion = suggestions[suggestionIndex];
                if (currentSuggestion.startsWith(newTypedText)) {
                    // Update the display with partially accepted suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length);
                    }
                    
                    // Insert accepted part in black
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, {
                        color: 'black',
                        background: 'transparent'
                    });

                    // Insert remaining suggestion in gray
                    const remainingSuggestion = currentSuggestion.slice(newTypedText.length);
                    quillEditor.insertText(
                        cursorPositionBeforeSuggestion + newTypedText.length,
                        remainingSuggestion,
                        {
                            color: '#888',
                            backgroundColor: '#f0f0f0'
                        }
                    );
                    
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0);
                    
    
                } else {
                    // If there's a mismatch, remove the suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length);
                    }
                    
                    // Insert the typed text
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, {
                        color: 'black',
                        background: 'transparent'
                    });
                    
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0);
                    
                    // Clean up suggestion state
                    setShowSuggestions(false);
                    setContentBeforeSuggestion(null);
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
        console.log('Editor change source: ', source, 'delta', delta, 'showSuggestions', showSuggestions)
        if (source === 'user') {
            if (ignoreNextSuggestion) {  // Check the flag
                setIgnoreNextSuggestion(false); // Reset the flag
                setEditorContent(content);
                return; // Ignore this suggestion event
            }

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
    }, [documentId, ignoreNextSuggestion, emit]);

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

