import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill, { Quill } from 'react-quill';
import SuggestionBlot from './SuggestionBlot';
import CompletionBlot from './CompletionBlot';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Headerbar } from '../../components/Headerbar/Headerbar';
import { StructurUpload } from '../../components/Sidebar/StructureUpload';
import { ContentUpload } from '../../components/Sidebar/ContentUpload';
import { ChatWindow } from '../../components/Chat/ChatWindow';
import { DebugPanel } from '../../components/Debug/DebugPanel';
import { useAuth } from '../../contexts/AuthContext';
import 'react-quill/dist/quill.snow.css';
import { Alert, AlertDescription, AlertTitle } from '../../components/ui/alert';
import { AlertCircle, Check, X  } from 'lucide-react';
import { Button } from '../ui/button';

// Import CSS files
import '../../styles/components.css';
import '../../styles/globals.css'; 
import '../../styles/editor.css';

const Delta = Quill.import('delta');
Quill.register(SuggestionBlot);
Quill.register(CompletionBlot);

// Debugging flags
const DEBUG_FLAGS = {
    AUTH: false,
    ERROR: true,
    TITLE: false,
    STRUCTURE: false,
    CONTENT: false,
    CHAT: true,
    AUTOCOMPLETION: true,
    GET_CONTENT: true,
    USER_EVENTS: false,
    SERVER_EVENTS: true,
    EDITOR_CHANGE: true,
    SUGGESTION_LOGIC: true,
};

const log = (flag, message, ...args) => {
    if (DEBUG_FLAGS[flag]) {
        const stackTrace = new Error().stack;
        const callerLine = stackTrace.split('@')[0].split('.').pop().trim(); // Get the second line (caller)
        
        console.log(`[${flag}](${callerLine}) ${message}`, ...args);
    }
};

export const Editor = ({ documentId }) => {
    // State management
    const [showAlert, setShowAlert] = useState(false);
    const [alertMessage, setAlertMessage ] = useState('');
    const [activeUsers, setActiveUsers] = useState([]);
    const [uploadedStructureFile, setUploadedStructureFile] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [debugEvents, setDebugEvents] = useState([]);
    const [chatMessages, setChatMessages] = useState([]);
    const [editorContent, setEditorContentD] = useState('');
    const [currentDocumentTitle, setCurrentDocumentTitle] = useState('');
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [autocomplationSuggestions, setAutocompletionSuggestions] = useState([]);
    const [autocompletionSuggestionIndex, setAutocompletionSuggestionIndex] = useState(0);
    const [showAutocompletionSuggestions, setShowAutocompletionSuggestions] = useState(false);
    const [cursorPositionBeforeSuggestion, setCursorPositionBeforeSuggestion] = useState(null);
    const [userTypedText, setUserTypedText] = useState('');
    const [suggestedEdits, setSuggestedEdits] = useState([]);
    const [showStructureConfirmation, setShowStructureConfirmation] = useState(false);
    const [restructuredDocument, setRestructuredDocument] = useState('');
    const lastRequestIdRef = useRef(null); // Use a ref to allow for latest updates without rerendering
    const debounceTimerRef = useRef(null);
    const pendingRequestRef = useRef(null);
    const quillRef = useRef(null);
    const { user, logout } = useAuth();

    // const autocompletionSuggestionStyle = { 
    //     color: '#888',
    //     backgroundColor: '#f0f0f0',
    // };

    const DEBOUNCE_WAITING_TIME = 100; // Time in milliseconds to wait before sending a request

    const handleAuthenticationFailed = useCallback((event) => {
        log('AUTH', "Authentication failed", event);
        logout();
    }, []);

    const handleError = useCallback((event) => {
        log('ERROR', "Socket Error:", event);
        setAlertMessage(event.message || 'An unexpected error occurred.');
        setShowAlert(true);
    }, []);

    const handleDocumentTitleGenerated = useCallback((event) => {
        log('TITLE', "Document title generated", event);
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

    const handleStructureParsed = useCallback((newContent) => {
        quillRef.current.getEditor().setContents(newContent, 'silent');
        //setEditorContent(newContent);
    }, []);

    const handleStructureUpload = useCallback(async (data) => {
        log('STRUCTURE', "Handling structure upload", data);
        if (data) {
            emit('client_structure_uploaded', data);
        }
        
      }, []);

    const handleContentUpload = useCallback((extractedContent) => {
        log('CONTENT', "Extracted content:", extractedContent);
        // Update state with extracted content
        emit('client_content_changes', extractedContent);
        // You can now do something with the extractedContent, like sending it to a server or storing it

    }, []);

    const handleChatAnswer = useCallback((data) => {
        const { response, suggested_edits } = data;
        log('CHAT', 'Received chat answer:', response, suggested_edits);
        setChatMessages(prev => [...prev, { text: response, sender: 'server' }]);
        setSuggestedEdits(suggested_edits); // Assuming you still want to store them in state

        const quill = quillRef.current.getEditor();
        const currentLength = quill.getText().length;
        
        if (suggested_edits && suggested_edits.length > 0) {
            suggested_edits.forEach(edit => {
            log('CHAT', 'Processing edit:', edit);
            if (edit.name === 'insert_text') {
                const position = Math.min(edit.arguments.position, currentLength);
                const insertData = {
                id: edit.name, // Or a unique ID from the backend
                type: 'insert',
                text: edit.arguments.text,
                position: position
                };
                log('CHAT', 'Inserting suggestion with data:', insertData);
            
                // Insert a placeholder for the suggestion
                quill.insertText(insertData.position, "*", 'suggestion', insertData);
               
            } else if (edit.name === 'delete_text') {
                const start = Math.min(edit.arguments.start, currentLength);
                const end = Math.min(edit.arguments.end, currentLength);
                const deleteData = {
                id: edit.name, // Unique ID for the suggestion
                type: 'delete',
                start: start,
                end: end
                };
                const suggestionTextROI = quill.getText(start, end - start);
                quill.formatText(start, end - start, 'suggestion', deleteData);
                //quill.deleteText(start, end - start, 'api');
                //quill.insertText(start, suggestionTextROI, 'suggestion', deleteData);
                
            } else if (edit.name === 'replace_text') {
                const start = Math.min(edit.arguments.start, currentLength);
                const end = Math.min(edit.arguments.end, currentLength);
                const replaceData = {
                id: edit.name, // Unique ID for the suggestion
                type: 'replace',
                start: start,
                end: end,
                text: edit.arguments.new_text
                };
               
                const suggestionTextROI = quill.getText(start, end - start);
                quill.formatText(start, end - start, 'suggestion', replaceData);
                //quill.deleteText(start, end - start, 'api');
                //quill.insertText(start, suggestionTextROI, 'suggestion', replaceData);
               
            }
            });
        }
    }, []);

    const handleAutocompletion = useCallback((event) => {
        if (event.requestId !== lastRequestIdRef.current) {
            log('AUTOCOMPLETION', "Ignoring outdated suggestion response", lastRequestIdRef.current, event.requestId);
            return; // Ignore outdated responses
        }

        log('AUTOCOMPLETION', "Show Autocompletion", event);
        if (!event.cursorPosition || !event.suggestions || event.suggestions.length === 0) {
            log('AUTOCOMPLETION', "No suggestions or cursor position available. Hiding suggestions.");
            setShowAutocompletionSuggestions(false);
            setAutocompletionSuggestions([]);
            setAutocompletionSuggestionIndex(0);
            return;
        }
    
        const quillEditor = quillRef.current.getEditor();
        const range = quillEditor.getSelection();
        if (!range) {
            log('AUTOCOMPLETION', "No selection found. Aborting autocompletion.");
            setShowAutocompletionSuggestions(false);
            return;
        }

        const suggestionText = event.suggestions[0];
        const insertIndex = range.index;

        // Remove any existing suggestion before inserting a new one
        if (cursorPositionBeforeSuggestion !== null) {
            const existingSuggestionLength = autocomplationSuggestions[autocompletionSuggestionIndex]?.length || 0;
            
            // Adjust deletion to account for the space before the suggestion
            quillEditor.deleteText(cursorPositionBeforeSuggestion, existingSuggestionLength, 'silent');
            
            
        }
        
    
        setShowAutocompletionSuggestions(true);
        // Store the cursor position before applying the suggestion
        setCursorPositionBeforeSuggestion(insertIndex);
        setUserTypedText('');  // Reset typed text when new suggestion appears

        // Show the first suggestion
        
        quillEditor.insertText(insertIndex, suggestionText, 'completion', 'silent'); // Insert with custom formats
        quillEditor.setSelection(insertIndex + suggestionText.length, 0, 'silent');
    
        setAutocompletionSuggestions(event.suggestions);
        setAutocompletionSuggestionIndex(0); // Reset to the first suggestion
    }, [autocomplationSuggestions, autocompletionSuggestionIndex, cursorPositionBeforeSuggestion]);

    const handleChatSubmit = useCallback((message) => {
        if (message.trim()) {
          setChatMessages([...chatMessages, { text: message, sender: 'user' }]);
          emit('client_chat', { text: message });
        }
      }, [chatMessages]);

   

    const handleGetContent = useCallback((event) => {
        log('GET_CONTENT', "Received document", event); // event has document_id and content fields
        if (event && event.content) {
            if (event.documentId != documentId) {
                log('GET_CONTENT', "Document ID mismatch");
            }
            const currentDelta = new Delta({ops : event.content});
            log('GET_CONTENT', "Event content:", currentDelta);

           
            quillRef.current.getEditor().setContents(currentDelta, 'silent');
            //setEditorContent(event.content);
            setCurrentDocumentTitle(event.title);
        }
    }, []);

    const handleGetStructure = useCallback((event) => {
        log('STRUCTURE', "Received structure", event); // event has document_id and content fields
        if (event && event.content) {
            if (event.documentId != documentId) {
                log('STRUCTURE', "Document ID mismatch");
            }
            setRestructuredDocument(event);
            setShowStructureConfirmation(true);
        }
    }, [documentId]);

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
        if (!showAutocompletionSuggestions) return;
        log('SUGGESTION_LOGIC', "Show suggestions ", showAutocompletionSuggestions);
       
        const quillEditor = quillRef.current.getEditor();
        switch (event.key) {
            case 'ArrowDown':
            case 'ArrowUp': {
                event.preventDefault();
                
                // Remove previous suggestion
                if (cursorPositionBeforeSuggestion) {
                    quillEditor.deleteText(cursorPositionBeforeSuggestion, autocomplationSuggestions[autocompletionSuggestionIndex].length);
                }

                const newIndex = event.key === 'ArrowDown'
                    ? (autocompletionSuggestionIndex + 1) % autocomplationSuggestions.length
                    : (autocompletionSuggestionIndex - 1 + autocomplationSuggestions.length) % autocomplationSuggestions.length;
                
                // Insert new suggestion
                const newSuggestion = autocomplationSuggestions[newIndex];
                quillEditor.insertText(cursorPositionBeforeSuggestion, newSuggestion, 'completion', 'silent');
                quillEditor.setSelection(cursorPositionBeforeSuggestion + newSuggestion.length, 0, 'silent');

                setAutocompletionSuggestionIndex(newIndex);
                setUserTypedText('');
                break;
            } case 'Enter':
            case 'Tab': {
                event.preventDefault();
                if (!cursorPositionBeforeSuggestion) return;

                
                // Accept the current suggestion
                const suggestionText = autocomplationSuggestions[autocompletionSuggestionIndex];
                // Remove the temporary formatting
                const textAtPosition = quillEditor.getText(cursorPositionBeforeSuggestion, suggestionText.length);
                log('SUGGESTION_LOGIC', "Debug - Suggestion text:", JSON.stringify(suggestionText));
                log('SUGGESTION_LOGIC', "Debug - Text at position:", JSON.stringify(textAtPosition));

                log('SUGGESTION_LOGIC', "Deleting text at position ", cursorPositionBeforeSuggestion, " with length ", suggestionText.length);
                quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestionText.length + 1, 'silent');
                log('SUGGESTION_LOGIC', "Deleted text at position ", cursorPositionBeforeSuggestion, " with length ", suggestionText.length);
                // Insert the final text with normal formatting
                quillEditor.insertText(cursorPositionBeforeSuggestion, suggestionText, 'silent');
                //quillEditor.removeFormat(cursorPositionBeforeSuggestion, suggestionText.length, 'silent');
                log('SUGGESTION_LOGIC', "Inserted text at position ", cursorPositionBeforeSuggestion, " with text ", suggestionText);
                // Move cursor to end of inserted text
                quillEditor.setSelection(cursorPositionBeforeSuggestion + suggestionText.length, 0, 'silent');
                log('SUGGESTION_LOGIC', "Cursor position set to ", cursorPositionBeforeSuggestion + suggestionText.length);
                
                // Delete the created tab/enter character when accepting the suggestion
                //quillEditor.deleteText(cursorPositionBeforeSuggestion + suggestionText.length, 1, 'silent');
                //log('SUGGESTION_LOGIC', "Delete first character at current position:", JSON.stringify(cursorPositionBeforeSuggestion + suggestionText.length))

                // Clean up suggestion state
                const delta = new Delta();
                delta.retain(cursorPositionBeforeSuggestion);
                delta.insert(suggestionText);
                emit('client_text_change', {
                    delta: delta.ops,
                    documentId: documentId,
                });

                setShowAutocompletionSuggestions(false);
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

                
                let newTypedText = userTypedText;
                if (event.key === 'Backspace') {
                    if (userTypedText.length > 0) {
                        newTypedText = userTypedText.slice(0, -1);
                        setUserTypedText(newTypedText);
                        return;
                    } else {
                        const cursorPosition = Math.max(0, cursorPositionBeforeSuggestion - 1);
                        setCursorPositionBeforeSuggestion(cursorPosition);
                        return;
                    }
                } else if (event.key === 'Escape') {
                    newTypedText = '';
                } else {
                    newTypedText = userTypedText + event.key;
                }
                event.preventDefault();
                setUserTypedText(newTypedText);

                // Check if typed text matches the start of the current suggestion
                const currentSuggestion = autocomplationSuggestions[autocompletionSuggestionIndex];
                if (matchesSuggestion(newTypedText, currentSuggestion) && event.key !== 'Escape') {

                    // check if completion is typed out
                    if (newTypedText.length >= currentSuggestion.length) {
                        const delta = new Delta();
                        delta.retain(cursorPositionBeforeSuggestion);
                        delta.insert(newTypedText);
                        emit('client_text_change', {
                            delta: delta.ops,
                            documentId: documentId,
                        });

                        // Clean up suggestion state
                        setShowAutocompletionSuggestions(false);
                        setCursorPositionBeforeSuggestion(null);
                        setUserTypedText('');

                        return;
                    }

                    // Update the display with partially accepted suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length, 'silent');
                        //quillEditor.removeFormat(cursorPositionBeforeSuggestion, newTypedText.length, 'silent');
                    }
                    
                    // Insert accepted part in black
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, 'silent');

                    // Insert remaining suggestion in gray
                    const remainingSuggestion = currentSuggestion.slice(newTypedText.length);
                    quillEditor.insertText(
                        cursorPositionBeforeSuggestion + newTypedText.length,
                        remainingSuggestion,
                        'completion',
                        'silent'
                    );
                    
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0, 'silent');
                     
    
                } else {
                    // If there's a mismatch, remove the suggestion
                    if (cursorPositionBeforeSuggestion) {
                        quillEditor.deleteText(cursorPositionBeforeSuggestion, currentSuggestion.length, 'silent');
                    }
                    
                    // Insert the typed text
                    quillEditor.insertText(cursorPositionBeforeSuggestion, newTypedText, 'silent');
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0, 'silent');
                    
                    const delta = new Delta();
                    delta.retain(cursorPositionBeforeSuggestion);
                    delta.insert(newTypedText);
                    emit('client_text_change', {
                        delta: delta.ops,
                        documentId: documentId,
                    });

                    // Clean up suggestion state
                    setShowAutocompletionSuggestions(false);
                    setCursorPositionBeforeSuggestion(null);
                    setUserTypedText('');
                }
                break;
            }
                
        }
    }, [showAutocompletionSuggestions, autocomplationSuggestions, autocompletionSuggestionIndex, cursorPositionBeforeSuggestion, userTypedText]);

    const handleUserJoined = useCallback((event) => {
        log('USER_EVENTS', "User joined", event);
        setActiveUsers(prevUsers => [...prevUsers, event.username]);
    }, []);

    const handleUserLeft = useCallback((event) => {
        log('USER_EVENTS', "User left", event);
        setActiveUsers(prevUsers => prevUsers.filter(u => u !== event.username));
    }, []);

    const handleServerTitleChange = useCallback((data) => {
        log('SERVER_EVENTS', "Server title change", data);
        if (data.documentId === documentId) {
            setCurrentDocumentTitle(data.title);
        }
    }, [documentId]);

    const handleServerContentChange = useCallback((data) => {
        log('SERVER_EVENTS', "Server content change", data);
        if (data.documentId === documentId) {
            // Todo, set the ContentUpload and add the content file to the list of files
        }
    }, [documentId])

    const handleServerSentStructure = useCallback((data) => {
        log('SERVER_EVENTS', "Server sent structure", data);
        if (!data || !data.documentId || !data.content) {
            log('SERVER_EVENTS', 'No structure sent');
            return;
        }
        if (data.documentId !== documentId) {
            log('SERVER_EVENTS', 'Wrong documentId in server sent structure');
            return;
        }
        quillRef.current.getEditor().setContents(data.content, 'silent');
        //setEditorContent(data.content);
        setShowStructureConfirmation(false);
        // Optionally, clear the restructuredDocument state if you don't need it anymore
        
        setRestructuredDocument('');
    }, [documentId]);

    const handleServerEditApplied = useCallback((data) => {
        log('SERVER_EVENTS', "Server edit applied", data);
        if (data.documentId !== documentId) {
            log('SERVER_EVENTS', 'Wrong documentId in server edit applied');
            return;
        }

        if (data.deltas_ops.length === 0) {
            log('SERVER_EVENTS', 'No deltas_ops in server edit applied');
            return;
        }

        const quill = quillRef.current;
        data.deltas_ops.forEach((delta) => {
            quill.updateContents(delta);
        });
    },[]);

    const handleServerTextChange = useCallback((data) => {
        if (data.documentId !== documentId) return; // Ignore changes for other documents
        log('SERVER_EVENTS', "Server text change", data);
        const quill = quillRef.current;
        
        // Apply the delta received from the server
        quill.updateContents(data.delta, 'silent');
      }, [documentId]);

    const socketEvents = useMemo(() => ({
        server_connects: () => emit('client_get_document', { documentId: documentId }),
        disconnect: () => log('NETWORK', 'disconnected'),
        server_disconnects: () => log('NETWORK', 'server disconnected'),
        server_error: handleError,

        // Multi User Events
        server_user_joined: handleUserJoined,
        server_user_left: handleUserLeft,
        server_title_change: handleServerTitleChange,
        server_text_change: handleServerTextChange,
        server_content_changes: handleServerContentChange,
        server_sent_accepted_new_structure: handleServerSentStructure,
        server_edit_applied: handleServerEditApplied,

        // Single User Events
        server_authentication_failed: handleAuthenticationFailed,
        server_sent_document_content: handleGetContent,
        server_sent_new_structure: handleGetStructure,
        server_autocompletion_suggestions: handleAutocompletion,
        server_document_title_generated: handleDocumentTitleGenerated,
        server_chat_answer: handleChatAnswer,
        structure_parsed: handleStructureParsed,
    }), []); // Add any dependencies that might change the handlers, for example handleAutocompletion, handleChatAnswer, handleStructureParsed

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
        log('EDITOR_CHANGE', "Editor change triggered", source);
        log('EDITOR_CHANGE', 'content', content);  
        log('EDITOR_CHANGE', 'delta content', editor.getContents());
        log('EDITOR_CHANGE', 'delta', delta);
        setEditorContentD(content);
        if (source === 'user' && !showAutocompletionSuggestions) {
            const range = editor.getSelection();
            if (!range) {
                log('EDITOR_CHANGE', "Editor change triggered, no range");
                return;
            }
         
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
                    log('EDITOR_CHANGE', "Emitting latest request:", requestId);
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
        
        //quillRef.current.getEditor().setContents(content, 'silent');

        // if (process.env.REACT_APP_DEBUG) {
        //     setDebugEvents(prev => [...prev, { 
        //         type: 'editor_change',
        //         content,
        //         delta,
        //         timestamp: new Date()
        //     }]);
        // }
    }, [documentId, emit, showAutocompletionSuggestions]);

    // Suggestion Logic

    // Custom Event Handlers (in MainApp)
    const handleAcceptSuggestion = useCallback((event) => {
        const data = event.detail;
        if (!data) {
            log('SUGGESTION_LOGIC', 'Accept suggestion event data is missing');
            return;
        }
        const quill = quillRef.current.getEditor();

        if (data.type === 'insert') {
            quill.deleteText(data.position, 1, 'silent');
            quill.insertText(data.position, data.text, 'silent');
        } else if (data.type === 'delete') {
            quill.deleteText(data.start, data.end - data.start, 'silent');
        } else if (data.type === 'replace') {
            quill.deleteText(data.start, data.end - data.start, 'silent');
            quill.insertText(data.start, data.text, 'silent');
        } else {
            log('SUGGESTION_LOGIC', 'Invalid suggestion type:', data.type);
        }

        // Emit event to backend
        emit('client_apply_edit', {
            documentId,
            edit_id: data.id,
            accepted: true,
        });
    }, [documentId, emit]);

    const handleRejectSuggestion = useCallback((event) => {
        const data = event.detail;
        if (!data) {
            log('SUGGESTION_LOGIC', 'Reject suggestion event data is missing');
            return;
        }
        const quill = quillRef.current.getEditor();

        log('SUGGESTION_LOGIC', "Rejecting suggestion ", data.id);
        log('SUGGESTION_LOGIC', "With data ", event);
        if (data.type === 'insert') {
            quill.deleteText(data.position, 1, 'silent');
        } else if (data.type === 'delete') {
            const suggestionTextROI = quill.getText(data.start, data.end - data.start);
            quill.deleteText(data.start, data.end - data.start, 'silent');
            quill.insertText(data.start, suggestionTextROI, 'silent');
        } else if (data.type === 'replace') {
            const suggestionTextROI = quill.getText(data.start, data.end - data.start);
            quill.deleteText(data.start, data.end - data.start, 'silent');
            quill.insertText(data.start, data.text, suggestionTextROI, 'silent');
        } else {
            log('SUGGESTION_LOGIC', 'Invalid suggestion type:', data.type);
        }
        
        emit('client_apply_edit', {
            documentId,
            edit_id: data.id,
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

    const handleAcceptStructure = useCallback(() => {
        if (!restructuredDocument) {
            log('STRUCTURE', 'No restructuredDocument found');
            return;
        }
        quillRef.current.setText(restructuredDocument, 'silent');
        setShowStructureConfirmation(false);
        // Optionally, clear the restructuredDocument state if you don't need it anymore
        setRestructuredDocument('');
        emit('client_structure_accepted', );
    }, [restructuredDocument]);
    
    const handleRejectStructure = useCallback(() => {
        setShowStructureConfirmation(false);
        // Optionally, clear the restructuredDocument state
        setRestructuredDocument('');
        emit('client_structure_rejected');
    }, []);



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
                {showAlert && (
                    <Alert className="mb-4 fixed top-4 right-4 z-50" variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertTitle>Error</AlertTitle>
                        <AlertDescription>
                            {alertMessage}
                        </AlertDescription>
                    </Alert>
                )}
                <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
                    <div className="sidebar-content">
                        <StructurUpload
                            title="Structure Template" 
                            onUpload={handleStructureUpload}
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
                {showStructureConfirmation && (
                    <div className="structure-preview">
                        <h3>Proposed Structure</h3>
                        <ReactQuill
                        value={restructuredDocument.content}
                        readOnly={true}
                        theme="bubble"
                        />
                        <div className="button-group">
                        <Button className="accept" variant="success" onClick={handleAcceptStructure}>
                            <Check className="h-4 w-4 mr-2" /> Accept
                        </Button>
                        <Button className="reject" variant="destructive" onClick={handleRejectStructure}>
                            <X className="h-4 w-4 mr-2" /> Reject
                        </Button>
                        </div>
                    </div>
                )}

                {/* {process.env.REACT_APP_DEBUG_PANE && (
                    <DebugPanel 
                        events={debugEvents}
                        socketStatus={status}
                    />
                )} */}
            </div>
        </div>
    );
};