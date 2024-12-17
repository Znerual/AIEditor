// src/components/Editor/Editor.js
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill, { Quill } from 'react-quill';
import SuggestionBlot from './SuggestionBlot';
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

// const Delta = Quill.import('delta');
Quill.register(SuggestionBlot);

export const Editor = ({ documentId }) => {
    // State management
    const [showAlert, setShowAlert] = useState(false);
    const [ alertMessage, setAlertMessage ] = useState('');
    const [uploadedStructureFile, setUploadedStructureFile] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [debugEvents, setDebugEvents] = useState([]);
    const [chatMessages, setChatMessages] = useState([]);
    const [editorContent, setEditorContent] = useState('');
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

    const autocompletionSuggestionStyle = { 
        color: '#888',
        backgroundColor: '#f0f0f0',
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

    const handleStructureParsed = useCallback((newContent) => {
        setEditorContent(newContent);
    }, []);

    const handleStructureUpload = useCallback(async (data) => {
        console.log("Handling structure upload", data);
        if (data) {
            emit('client_structure_uploaded', data);
        }
        
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
        const currentLength = quill.getText().length;
        
        if (suggested_edits && suggested_edits.length > 0) {
            suggested_edits.forEach(edit => {
            console.log('[handleChatAnswer] Processing edit:', edit);
            if (edit.name === 'insert_text') {
                const position = Math.min(edit.arguments.position, currentLength);
                const insertData = {
                id: edit.name, // Or a unique ID from the backend
                type: 'insert',
                text: edit.arguments.text,
                position: position
                };
                console.log('[handleChatAnswer] Inserting suggestion with data:', insertData);
            
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
                quill.deleteText(start, end - start, 'api');
                quill.insertText(start, suggestionTextROI, 'suggestion', deleteData);
                
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
                quill.deleteText(start, end - start, 'api');
                quill.insertText(start, suggestionTextROI, 'suggestion', replaceData);
               
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
            setShowAutocompletionSuggestions(false);
            setAutocompletionSuggestions([]);
            setAutocompletionSuggestionIndex(0);
            return;
        }
    
        const quillEditor = quillRef.current.getEditor();
        const range = quillEditor.getSelection();
        if (!range) {
            console.warn("No selection found. Aborting autocompletion.");
            setShowAutocompletionSuggestions(false);
            return;
        }
    
        // Store the cursor position before applying the suggestion
        setCursorPositionBeforeSuggestion(range.index);
        setUserTypedText('');  // Reset typed text when new suggestion appears

        // Show the first suggestion
        const suggestionText = event.suggestions[0];
        quillEditor.insertText(range.index, suggestionText, autocompletionSuggestionStyle, 'silent'); // Insert with custom formats
        quillEditor.setSelection(range.index, 0, 'silent');
    
        setAutocompletionSuggestions(event.suggestions);
        setAutocompletionSuggestionIndex(0); // Reset to the first suggestion
        setShowAutocompletionSuggestions(true);
    }, []);

    const handleChatSubmit = useCallback((message) => {
        if (message.trim()) {
          setChatMessages([...chatMessages, { text: message, sender: 'user' }]);
          emit('client_chat', { text: message });
        }
      }, [chatMessages]);

   

    const handleGetContent = useCallback((event) => {
        console.log("Received document", event); // event has document_id and content fields
        if (event && event.content) {
            if (event.documentId != documentId) {
                console.error("Document ID mismatch");
            }
            setEditorContent(event.content);
            setCurrentDocumentTitle(event.title);
        }
    }, [setEditorContent]);

    const handleGetStructure = useCallback((event) => {
        console.log("Received structure", event); // event has document_id and content fields
        if (event && event.content) {
            if (event.documentId != documentId) {
                console.error("Document ID mismatch");
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
        console.log("[KeyDown] Show suggestions ", showAutocompletionSuggestions);
       
        const quillEditor = quillRef.current.getEditor();
        switch (event.key) {
            case 'ArrowDown':
            case 'ArrowUp': {
                event.preventDefault();
                
                // Remove previous suggestion
                if (cursorPositionBeforeSuggestion) {
                    quillEditor.deleteText(cursorPositionBeforeSuggestion, autocomplationSuggestions[autocompletionSuggestionIndex].length + 1);
                }

                const newIndex = event.key === 'ArrowDown'
                    ? (autocompletionSuggestionIndex + 1) % autocomplationSuggestions.length
                    : (autocompletionSuggestionIndex - 1 + autocomplationSuggestions.length) % autocomplationSuggestions.length;
                
                // Insert new suggestion
                const newSuggestion = autocomplationSuggestions[newIndex];
                quillEditor.insertText(cursorPositionBeforeSuggestion, newSuggestion, autocompletionSuggestionStyle, 'silent');
                quillEditor.setSelection(cursorPositionBeforeSuggestion, 0, 'silent');

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
                console.log("Deleting text at position ", cursorPositionBeforeSuggestion, " with length ", suggestionText.length + 1);
                quillEditor.deleteText(cursorPositionBeforeSuggestion, suggestionText.length + 1, 'silent');
                console.log("Deleted text at position ", cursorPositionBeforeSuggestion, " with length ", suggestionText.length + 1);
                // Insert the final text with normal formatting
                quillEditor.insertText(cursorPositionBeforeSuggestion, suggestionText, 'silent');
                console.log("Inserted text at position ", cursorPositionBeforeSuggestion, " with text ", suggestionText);
                // Move cursor to end of inserted text
                quillEditor.setSelection(cursorPositionBeforeSuggestion + suggestionText.length, 0, 'silent');
                console.log("Cursor position set to ", cursorPositionBeforeSuggestion + suggestionText.length);
                // Clean up suggestion state
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
                const currentSuggestion = autocomplationSuggestions[autocompletionSuggestionIndex];
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
                        autocompletionSuggestionStyle,
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
                    setShowAutocompletionSuggestions(false);
                    setCursorPositionBeforeSuggestion(null);
                    setUserTypedText('');
                }
                break;
            }
                
        }
    }, [showAutocompletionSuggestions, autocomplationSuggestions, autocompletionSuggestionIndex, cursorPositionBeforeSuggestion, userTypedText]);

    const socketEvents = useMemo(() => ({
        server_connects: () => emit('client_get_document', { documentId: documentId }),
        disconnect: () => console.log('disconnected'),
        server_disconnects: () => console.log('server disconnected'),
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
        console.log("Editor change triggered", source);
        if (source === 'user') {
            const range = editor.getSelection();
            console.log("Range ", range);
            let index;
            if (!range) {
                console.log("Editor change triggered, no range");
                index = editor.getLength();
            } else {
                index = range.index;
            }
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
        const data = event.detail;
        if (!data) {
            console.error('Accept suggestion event data is missing');
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
            console.error('Invalid suggestion type:', data.type);
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
            console.error('Reject suggestion event data is missing');
            return;
        }
        const quill = quillRef.current.getEditor();

        console.log("Rejecting suggestion ", data.id);
        console.log("With data ", event);
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
            console.error('Invalid suggestion type:', data.type);
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
            console.error('No restructuredDocument found');
            return;
        }
        setEditorContent(restructuredDocument.content);
        setShowStructureConfirmation(false);
        // Optionally, clear the restructuredDocument state if you don't need it anymore
        setRestructuredDocument('');
        emit('client_structure_accepted', );
    }, [restructuredDocument, setEditorContent]);
    
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
                        <Button variant="success" onClick={handleAcceptStructure}>
                            <Check className="h-4 w-4 mr-2" /> Accept
                        </Button>
                        <Button variant="destructive" onClick={handleRejectStructure}>
                            <X className="h-4 w-4 mr-2" /> Reject
                        </Button>
                        </div>
                    </div>
                )}

                {process.env.REACT_APP_DEBUG_PANE && (
                    <DebugPanel 
                        events={debugEvents}
                        socketStatus={status}
                    />
                )}
            </div>
        </div>
    );
};

