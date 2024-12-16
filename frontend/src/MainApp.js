// src/App.js
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill, { Quill } from 'react-quill';
import SuggestionBlot from './components/Editor/SuggestionBlot';
import { useWebSocket } from './hooks/useWebSocket';
import { Headerbar } from './components/Headerbar/Headerbar';
import { StructurUpload } from './components/Sidebar/StructureUpload';
import { ContentUpload } from './components/Sidebar/ContentUpload';
import { ChatWindow } from './components/Chat/ChatWindow';
import { DebugPanel } from './components/Debug/DebugPanel';
import { useAuth } from './contexts/AuthContext';
import 'react-quill/dist/quill.snow.css';

// Import CSS files
import './styles/App.css';
import './styles/components.css';
import './styles/globals.css'; 
import './styles/editor.css';

// const Delta = Quill.import('delta');
Quill.register(SuggestionBlot);

export const MainApp = () => {
    // State management
    const [uploadedStructureFile, setUploadedStructureFile] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [debugEvents, setDebugEvents] = useState([]);
    const [chatMessages, setChatMessages] = useState([]);
    const [editorContent, setEditorContent] = useState('');
    const [documentId, setDocumentId] = useState('');
    const [currentDocumentTitle, setCurrentDocumentTitle] = useState('');
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestionIndex, setSuggestionIndex] = useState(0);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [cursorPositionBeforeSuggestion, setCursorPositionBeforeSuggestion] = useState(null);
    const [userTypedText, setUserTypedText] = useState('');
    const [suggestedEdits, setSuggestedEdits] = useState([]);
    const lastRequestIdRef = useRef(null); // Use a ref to allow for latest updates without rerendering
    const debounceTimerRef = useRef(null);
    const pendingRequestRef = useRef(null);
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

    const DEBOUNCE_WAITING_TIME = 100; // Time in milliseconds to wait before sending a request

    const handleAuthenticationFailed = useCallback((event) => {
        console.log("Authentication failed", event);
        logout();
    }, []);

    const handleDocumentTitleGenerated = useCallback((event) => {
        console.log("Document title generated", event);
        setCurrentDocumentTitle(event.title);
    }, []);

    const handleTitleChange = useCallback((newTitle) => {
        setCurrentDocumentTitle(newTitle);
        // Only emit the change if the title was not set automatically
        emit('client_title_change', {
            title: newTitle,
            documentId: documentId,
        });
        
    }, [documentId]);
    
    const handleTitleEditCommit = (newTitle) => {
        setIsEditingTitle(false);
        // Emit title change when editing is finished
        handleTitleChange(newTitle);
    };

    const handleEditApplied = useCallback((event) => {
        const { edit_id, status } = event;
        // Remove the applied edit from the state
        setSuggestedEdits(prevEdits => prevEdits.filter(edit => edit.id !== edit_id));

        // Optionally, update the editor content or other UI elements based on the status
        if (status === 'accepted') {
            // Refresh or update the document content
            // This might involve re-fetching the document or applying the changes locally if you're tracking them
        }
    }, []);


    const handleStructureParsed = useCallback((newContent) => {
        setEditorContent(newContent);
    }, []);

    const handleStructureUpload = useCallback((file) => {
        console.log("Handling structure upload", file);
        setUploadedStructureFile(file);
        // Implementation for structure upload
    }, []);

    const handleContentUpload = useCallback((extractedContent) => {
        // Update state with extracted content
        emit('client_content_changes', extractedContent);
        // You can now do something with the extractedContent, like sending it to a server or storing it
        console.log("Extracted content:", extractedContent);

    }, []);

    const handleChatAnswer = useCallback((data) => {
        const { response, suggested_edits } = data;
        console.log('Received chat answer:', response, suggested_edits);
        setChatMessages(prev => [...prev, { text: response, sender: 'server' }]);
        setSuggestedEdits(suggested_edits); // Assuming you still want to store them in state

        const quill = quillRef.current.getEditor();
        let range = quill.getSelection();
        let insertIndex = range ? range.index : 0; // Default to 0 if no selection

        if (suggested_edits && suggested_edits.length > 0) {
            suggested_edits.forEach(edit => {
            console.log('[handleChatAnswer] Processing edit:', edit);
            if (edit.name === 'insert_text') {
                const insertData = {
                id: edit.name, // Or a unique ID from the backend
                type: 'insert',
                text: edit.arguments.text,
                position: edit.arguments.position
                };
                console.log('[handleChatAnswer] Inserting suggestion with data:', insertData);
            
                // Insert a placeholder for the suggestion
                console.log('[handleChatAnswer] Inserting suggestion embed');
                quill.insertText(insertData.position, "*", 'api');
                quill.insertEmbed(insertData.position, 'suggestion', insertData, 'api');

                // Log the DOM after insertion
                console.log('[handleChatAnswer] DOM after insertion:', 
                    quill.root.querySelector('.suggestion-debug'));
            } else if (edit.name === 'delete_text') {
                const deleteData = {
                id: edit.name, // Unique ID for the suggestion
                type: 'delete',
                start: edit.arguments.start,
                end: edit.arguments.end
                };
                quill.insertText(deleteData.start, "*", 'api');
                quill.insertEmbed(deleteData.start, 'suggestion', deleteData, 'api');
                
            } else if (edit.name === 'replace_text') {
                const replaceData = {
                id: edit.name, // Unique ID for the suggestion
                type: 'replace',
                start: edit.arguments.start,
                end: edit.arguments.end,
                text: edit.arguments.new_text
                };
               
                quill.insertText(replaceData.start, "*", 'api');
                quill.insertEmbed(replaceData.start, 'suggestion', replaceData, 'api');
 
            }
            });
        }
    }, []);

    const handleAutocompletion = useCallback((event) => {
        if (event.requestId !== lastRequestIdRef.current) {
            console.log("Ignoring outdated suggestion response", lastRequestIdRef.current, event.requestId);
            return; // Ignore outdated responses
        }

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
                quillEditor.insertText(cursorPositionBeforeSuggestion, suggestion, 'silent');

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
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, 'silent');

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
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, 'silent');
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
        disconnect: () => console.log('disconnected'),
        server_disconnects: () => console.log('server disconnected'),
        server_authentication_failed: handleAuthenticationFailed,
        server_document_created: handleDocumentCreated,
        server_sent_document_content: handleGetContent,
        server_autocompletion_suggestions: handleAutocompletion,
        server_document_title_generated: handleDocumentTitleGenerated,
        server_chat_answer: handleChatAnswer,
        server_edit_applied: handleEditApplied,
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
                const index = range.index;
                emit('client_text_change', {
                    delta: delta.ops,
                    documentId: documentId,
                });

                // use execution guard to prevent multiple requests
                // Update the latest pending request data
                lastRequestIdRef.current = Date.now();
                pendingRequestRef.current = {
                    documentId,
                    cursorPosition: index,
                    requestId: lastRequestIdRef.current, // Generate a unique request ID
                };

                // Clear the previous timer
                if (debounceTimerRef.current) {
                    clearTimeout(debounceTimerRef.current);
                }


                // Set up a new debounce timer
                debounceTimerRef.current = setTimeout(() => {

                    if (pendingRequestRef.current) {
                        const { documentId, cursorPosition, requestId } = pendingRequestRef.current;
    
                        // Emit the latest pending request
                        console.log("Emitting latest request:", requestId);
                        emit('client_request_suggestions', {
                            documentId,
                            cursorPosition,
                            requestId,
                        });
    
                        // Clear the pending request data after emitting
                        pendingRequestRef.current = null;
                    }
                }, DEBOUNCE_WAITING_TIME);
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

    // Suggestion Logic

    // Custom Event Handlers (in MainApp)
    const handleAcceptSuggestion = useCallback((event) => {
        const { suggestionId, suggestionType, text, original, start, end } = event.detail;
        const quill = quillRef.current.getEditor();

        console.log("Accepting suggestion ", suggestionId, suggestionType, text, original, start, end);

        // Find the suggestion blot by its ID
        const blot = quill.scroll.find(event.target);

        if (!blot) {
            console.error('Suggestion blot not found!');
            return;
        }

        // Calculate the range based on the blot's position
        const blotIndex = quill.getIndex(blot);
        const blotLength = blot.length();
        const range = { index: blotIndex - 1, length: blotLength + 2 };

        if (suggestionType === 'insert') {
            quill.deleteText(range.index, range.length);
            quill.insertText(range.index, text);
        } else if (suggestionType === 'delete') {
            quill.deleteText(range.index, range.length);
            quill.deleteText(start, end - start);
        } else if (suggestionType === 'replace') {
            quill.deleteText(range.index, range.length);
            quill.deleteText(start, end - start);
            quill.insertText(start, text);
        }

        // Emit event to backend
        emit('client_apply_edit', {
            documentId,
            edit_id: suggestionId,
            accepted: true,
        });
    }, [documentId, emit]);

    const handleRejectSuggestion = useCallback((event) => {
        const { suggestionId } = event.detail;
        const quill = quillRef.current.getEditor();

        console.log("Rejecting suggestion ", suggestionId);

        // Find the suggestion blot by its ID
        const blot = quill.scroll.find(event.target);
        
        if (!blot) {
            console.error('Suggestion blot not found!');
            return;
        }

        // Calculate the range based on the blot's position
        const blotIndex = quill.getIndex(blot);
        const blotLength = blot.length();
        const range = { index: blotIndex - 1, length: blotLength + 2 };
        
        // Remove the suggestion
        quill.deleteText(range.index, range.length);

        // Emit event to backend
        emit('client_apply_edit', {
            documentId,
            edit_id: suggestionId,
            accepted: false,
        });
    }, [documentId, emit]);

    const modules = useMemo(() => ({
        toolbar: [
            [{ header: [1, 2, 3, false] }],
            ['bold', 'italic', 'underline', 'strike'],
            [{ list: 'ordered' }, { list: 'bullet' }],
            [{ color: [] }, { background: [] }],
            ['clean']
        ],
    }), []);

    useEffect(() => {
        console.log('[MainApp] Registered Quill formats:', Quill.imports);
        console.log('[MainApp] SuggestionBlot registered:', Quill.imports['formats/suggestion']);
    }, []);


    useEffect(() => {
        const quill = quillRef.current.getEditor();

        // Attach custom event listeners to the Quill editor
        quill.root.addEventListener('accept-suggestion', handleAcceptSuggestion);
        quill.root.addEventListener('reject-suggestion', handleRejectSuggestion);

        return () => {
            // Clean up event listeners when the component unmounts
            quill.root.removeEventListener('accept-suggestion', handleAcceptSuggestion);
            quill.root.removeEventListener('reject-suggestion', handleRejectSuggestion);
        };
    }, [handleAcceptSuggestion, handleRejectSuggestion]);

    return (
        <div className="app-container">
            <Headerbar 
                onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
                sidebarOpen={sidebarOpen}
                title={currentDocumentTitle}
                isEditingTitle={isEditingTitle}
                onTitleChange={handleTitleChange}
                onTitleEditCommit={handleTitleEditCommit}
                onStartTitleEdit={() => setIsEditingTitle(true)}
            />
            
            <div className="main-content">
                <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
                    <div className="sidebar-content">
                        <StructurUpload
                            title="Structure Template" 
                            onUpload={handleStructureUpload}
                            uploadedFile={uploadedStructureFile}
                        />
                        <ContentUpload
                            key="content-upload"
                            title="Content Files" 
                            onUpload={handleContentUpload}
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
                        //onChangeSelection={handleEditorSelectionChange}
                        modules={modules}
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

