// frontend/src/components/Editor/Editor.js
import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill, { Quill } from 'react-quill';
import SuggestionBlot from './SuggestionBlot';
import CompletionBlot from './CompletionBlot';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Headerbar } from '../../components/Headerbar/Headerbar';
import { StructurUpload } from '../../components/Sidebar/StructureUpload';
import { ContentUpload } from '../../components/Sidebar/ContentUpload';
import { ChatWindow } from '../../components/Chat/ChatWindow';
import { SuggestionIndicator } from './SuggestionIndicator';
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
    AUTOCOMPLETION: false,
    GET_CONTENT: false,
    USER_EVENTS: false,
    SERVER_EVENTS: false,
    EDITOR_CHANGE: false,
    SUGGESTION_LOGIC: true,
};

const log = (flag, message, ...args) => {
    if (DEBUG_FLAGS[flag]) {
        const stackTrace = new Error().stack;
        const callerLine = stackTrace.split('@')[0].split('.').pop().trim();
        
        console.log(`[${flag}](${callerLine}) ${message}`, ...args);
    }
};

export const Editor = ({ documentId }) => {
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
    const requestCounter = useRef(0);
    const lastRequestIdRef = useRef(null);
    const debounceTimerRef = useRef(null);
    const pendingRequestRef = useRef(null);
    const quillRef = useRef(null);
    const suggestionIndicatorRef = useRef(null);
    const { user, logout } = useAuth();

    const DEBOUNCE_WAITING_TIME = 500; // Time in milliseconds to wait before sending a request

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
       
    }, []);

    const handleChatAnswerIntermediary = useCallback((data) => {
        log('CHAT', 'Received intermediary chat answer:', data);
        if (!data || !data.status) {
            log('ERROR', 'No status found in intermediary chat answer');
            return;
        }

        let message = '';

        switch (data.status) {
            case 'generated action plan':
                message = `Generated action plan: ${data.action_plan}`;
                break;
            case 'Found text position, pre_running actions':
                
                message = `Pre-running action plan, found the following variables ${JSON.stringify(data.positions)}`;
                break;
            case 'pre_run_actions':

                message = `Pre-ran the action plan, found the following actions to be taken: ${data.actions}`;
                break;
            case 'evaluating action plan':
               
                message = `Evaluating action plan...`;
                break;
            case 'fixing action_plan variable naming problems':
                
                message = `Fixing action plan variable naming problems: ${JSON.stringify(data.variable_naming_problems)}`;
                break;
            case 'fixing action_plan variable position mistakes':
                
                message = `Fixing action plan variable position mistakes: ${JSON.stringify(data.variable_position_mistakes)}`;
                break;
            case 'fixed action_plan variable naming problems':
               
                message = `Fixed action plan variable naming problems.`;
                break;
            case 'fixed action_plan find_text action problems':
                
                message = `Fixed action plan find text action problems.`;
                break;    
            case 'Failed to generate action plan, could not parse it':
                message = 'Could not generate naming plan because of json problems';
                break;
            case "Fail to generate action_plan because of naming problems":
                message = "Fail to generate action_plan because of naming problems";
                break

            case "Fixing match ambigouities":
                message = `Fixing match ambigouities: ${JSON.stringify(data.problem)}, choice: ${data.selection}`
            case 'accepted':
                message = `Suggestion accepted.`;
                break;
            default:
                log('ERROR', `Unknown status: ${data.status}`);
                console.error(`Unknown status: ${data.status}`);
                message = `Unknown status: ${data.status}`;
                break;
        }

        // Add a new message to the chat window for each intermediary status
        setChatMessages(prev => [...prev, { text: message, sender: 'system' }]);
    }, []);


    const showSuggestedEdits = useCallback((suggested_edits) => {
        
    
        const quill = quillRef.current.getEditor();
        const currentLength = quill.getText().length;
        let combinedEdits = new Delta();
        let insertOffset = 0;
        if (suggested_edits && suggested_edits.length > 0) {
            suggested_edits.forEach(edit => {
                log('CHAT', 'Processing edit:', edit);
                log('CHAT', 'Edit id:', edit.id);
                if (edit.name === 'insert_text') {
                    const position = Math.min(edit.arguments.position, currentLength) - insertOffset;
                    const insertData = {
                        action_id: edit.id, // Or a unique ID from the backend
                        action_type: 'insert_text',
                        text: edit.arguments.text,
                        explanation: edit.arguments.explanation,
                    };
                    insertOffset += edit.arguments.text.length - 1;
                    log('CHAT', 'Inserting suggestion with data:', insertData);
                    const new_delta = new Delta().retain(position).insert("*", { "suggestion": insertData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quillRef.current.getEditor().updateContents(new_delta, 'api');
    
                } else if (edit.name === 'delete_text') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const deleteData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'delete_text',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': deleteData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'replace_text') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const replaceData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'replace_text',
                        text: edit.arguments.new_text,
                        explanation: edit.arguments.explanation,
                    };

                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': replaceData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
                } else if (edit.name === 'change_heading_level_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const changeHeadingLevelData = {
                        action_id: edit.id,
                        action_type: 'change_heading_level_formatting',
                        level: edit.arguments.level,
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end-start, {'suggestion' : changeHeadingLevelData});
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
                } else if (edit.name === 'make_list_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const makeListData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'make_list_formatting',
                        list_type: edit.arguments.list_type,
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': makeListData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_list_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeListData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_list_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeListData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'insert_code_block_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const insertCodeBlockData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'insert_code_block_formatting',
                        language: edit.arguments.language,
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': insertCodeBlockData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_code_block_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeCodeBlockData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_code_block_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeCodeBlockData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'make_bold_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const makeBoldData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'make_bold_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': makeBoldData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_bold_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeBoldData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_bold_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeBoldData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'make_italic_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const makeItalicData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'make_italic_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': makeItalicData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_italic_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeItalicData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_italic_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeItalicData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'make_strikethrough_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const makeStrikethroughData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'make_strikethrough_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': makeStrikethroughData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_strikethrough_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeStrikethroughData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_strikethrough_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeStrikethroughData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'make_underline_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const makeUnderlineData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'make_underline_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': makeUnderlineData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
    
                } else if (edit.name === 'remove_underline_formatting') {
                    const start = Math.min(edit.arguments.start, currentLength) - insertOffset;
                    const end = Math.min(edit.arguments.end, currentLength) - insertOffset;
                    const removeUnderlineData = {
                        action_id: edit.id, // Unique ID for the suggestion
                        action_type: 'remove_underline_formatting',
                        explanation: edit.arguments.explanation,
                    };
    
                    insertOffset += edit.arguments.end - edit.arguments.start - 1;
                    const new_delta = new Delta().retain(start).retain(end - start, { 'suggestion': removeUnderlineData });
                    combinedEdits = combinedEdits.compose(new_delta);
                    //quill.updateContents(new_delta, 'api');
                } else {
                    console.error('Invalid action type:', edit.action_type);
                }
    
                suggestionIndicatorRef.current?.updateIndicators();
    
            });
            console.log("Combining edits:", combinedEdits);
            quill.updateContents(combinedEdits, 'api');
        }

    }, []);

    const handleChatAnswerFinal = useCallback((data) => {
        log('CHAT', 'Received chat answer:', data);
        const { response, suggested_edits } = data;
        log('CHAT', 'Received chat answer:', response, suggested_edits);
        setChatMessages(prev => [...prev, { text: response, sender: 'server' }]);
        setSuggestedEdits(suggested_edits);
        showSuggestedEdits(suggested_edits);
    }, []);

    const handleAutocompletion = useCallback((event) => {
        if (event.requestId !== lastRequestIdRef.current) {
            log('AUTOCOMPLETION', "Ignoring outdated suggestion response", lastRequestIdRef.current, event.requestId);
            return;
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
        const new_delta = new Delta().retain(insertIndex).insert(suggestionText, {'completion' : true});
        quillEditor.updateContents(new_delta, 'silent');
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
            setCurrentDocumentTitle(event.title);
        }
    }, []);

    const handleGetChatHistory = useCallback((event) => {
        log('CHAT_HISTORY', "Received chat history", event); // event has document_id and content fields
        if (event && event.messages) {
            if (event.documentId != documentId) {
                log('CHAT_HISTORY', "Document ID mismatch");
            }
            setChatMessages(event.messages);
            setSuggestedEdits(event.unresolved_edits);
            showSuggestedEdits(event.unresolved_edits);
          
        }
    }, [documentId]);

    const handleGetStructure = useCallback((event) => {
        log('STRUCTURE', "Received structure", event); // event has document_id and content fields
        if (event && event.content) {
            if (event.documentId != documentId) {
                log('STRUCTURE', "Document ID mismatch");
            }
            setRestructuredDocument(event.content);
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
                
                const oldLength = autocomplationSuggestions[autocompletionSuggestionIndex].length;
                const newIndex = event.key === 'ArrowDown'
                    ? (autocompletionSuggestionIndex + 1) % autocomplationSuggestions.length
                    : (autocompletionSuggestionIndex - 1 + autocomplationSuggestions.length) % autocomplationSuggestions.length;
                const newText = autocomplationSuggestions[newIndex];
            

                const new_delta = new Delta().retain(cursorPositionBeforeSuggestion).delete(oldLength).insert(newText, {'completion' : true});
                quillEditor.updateContents(new_delta, 'silent');
                quillEditor.setSelection(cursorPositionBeforeSuggestion + newText.length, 0, 'silent');

                setAutocompletionSuggestionIndex(newIndex);
                setUserTypedText('');
                break;
            } case 'Enter':
            case 'Tab': {
                event.preventDefault();
                if (!cursorPositionBeforeSuggestion) return;

                
                // Accept the current suggestion
                const suggestionText = autocomplationSuggestions[autocompletionSuggestionIndex];
                
                const new_delta = new Delta().retain(cursorPositionBeforeSuggestion).retain(suggestionText.length, {'completion' : null}).delete(1); 
                quillEditor.updateContents(new_delta, 'silent');

                // Move cursor to end of inserted text
                quillEditor.setSelection(cursorPositionBeforeSuggestion + suggestionText.length, 0, 'silent');
        
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

                    const new_delta = new Delta().retain(cursorPositionBeforeSuggestion).retain(newTypedText.length, {'completion' : null});
                    quillEditor.updateContents(new_delta, 'silent');               
                    quillEditor.setSelection(cursorPositionBeforeSuggestion + newTypedText.length, 0, 'silent');
                     
    
                } else {
                   
                    const new_delta = new Delta().retain(cursorPositionBeforeSuggestion).delete(currentSuggestion.length).insert(newTypedText);
                    quillEditor.updateContents(new_delta, 'silent');

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
        setShowStructureConfirmation(false);
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
            quill.updateContents(delta, 'silent');
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
        server_sent_chat_history: handleGetChatHistory,
        server_sent_new_structure: handleGetStructure,
        server_autocompletion_suggestions: handleAutocompletion,
        server_document_title_generated: handleDocumentTitleGenerated,
        server_chat_answer_final: handleChatAnswerFinal,
        server_chat_answer_intermediary: handleChatAnswerIntermediary,
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
        log('EDITOR_CHANGE', "showAutocompletionSuggestion", showAutocompletionSuggestions);
        log('EDITOR_CHANGE', 'content', content);  
        log('EDITOR_CHANGE', 'delta content', editor.getContents());
        log('EDITOR_CHANGE', 'delta', delta);
        setEditorContentD(content);
        if (source === 'user' && !showAutocompletionSuggestions) {
            
            emit('client_text_change', {
                delta: delta.ops,
                documentId: documentId,
            });

            const range = editor.getSelection();
            if (!range) {
                log('EDITOR_CHANGE', "Editor change triggered, no range");
                return;
            }
            const index = range.index;
            
            // Clear the previous timer
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }

            // Update the latest pending request data
            // use execution guard to prevent multiple requests
            lastRequestIdRef.current = Date.now();
            pendingRequestRef.current = {
                documentId,
                cursorPosition: index,
                requestId: lastRequestIdRef.current,
            };

            

            // Set up a new debounce timer
            debounceTimerRef.current = setTimeout(() => {

                if (pendingRequestRef.current) {
                    const { documentId, cursorPosition, requestId } = pendingRequestRef.current;

                    if (requestId === lastRequestIdRef.current) {
                        // Emit the latest pending request
                        requestCounter.current = requestCounter.current + 1;
                        log('AUTOCOMPLETION', "Emitting latest request:", requestId, " total, ", requestCounter.current, " requests emitted.");
                        emit('client_request_suggestions', {
                            documentId,
                            cursorPosition,
                            requestId,
                        });
                    } else {
                        log('AUTOCOMPLETION', "Discarding outdated request:", requestId);
                    }

                    // Clear the pending request data after emitting
                    pendingRequestRef.current = null;
                }
            }, DEBOUNCE_WAITING_TIME);
        }
        
    }, [documentId, emit, showAutocompletionSuggestions]);

    // Suggestion Logic
    const handleAcceptSuggestion = useCallback((event) => {
        log('SUGGESTION_LOGIC', "Accept suggestion event triggered", event);
        const data = event.detail;
        if (!data) {
            log('SUGGESTION_LOGIC', 'Accept suggestion event data is missing');
            return;
        }
        const quill = quillRef.current.getEditor();
        
        if (data.action_type === 'insert_text') {
            const new_delta = new Delta().retain(data.start).delete(1).insert(data.text);
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'delete_text') {
            const new_delta = new Delta().retain(data.start).delete(data.end - data.start);
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'replace_text') {
            const new_delta = new Delta().retain(data.start).delete(data.end - data.start).insert(data.text);
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_list_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'list': data.list_type, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
            emit('client_apply_edit', {
                documentId,
                edit_id: data.action_id,
                accepted: true,
                action_type: data.action_type,
                text: data.text,
                start: data.start,
                end: data.end,
                list_type: data.list_type,
            });
            return;
        } else if (data.action_type === 'remove_list_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'list': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'insert_code_block_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'code': data.language, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
            emit('client_apply_edit', {
                documentId,
                edit_id: data.action_id,
                accepted: true,
                action_type: data.action_type,
                text: data.text,
                start: data.start,
                end: data.end,
                language: data.language,
            });
            return;
        } else if (data.action_type === 'remove_code_block_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'code': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_bold_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'bold': true, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_bold_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'bold': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_italic_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'italic': true, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_italic_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'italic': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_strikethrough_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'strike': true, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_strikethrough_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'strike': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_underline_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'underline': true, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_underline_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'underline': null, 'suggestion': null });
            quill.updateContents(new_delta, 'silent');
        } else {
            console.error('Invalid suggestion type:', data.action_type);
            log('SUGGESTION_LOGIC', 'Invalid suggestion type:', data.action_type);
        }
        

        suggestionIndicatorRef.current?.updateIndicators();


        // Emit event to backend
        emit('client_apply_edit', {
            documentId,
            edit_id: data.action_id,
            accepted: true,
            action_type: data.action_type,
            text: data.text,
            start: data.start,
            end: data.end,
        });
    }, [documentId, emit]);

    const handleRejectSuggestion = useCallback((event) => {
        const data = event.detail;
        if (!data) {
            log('SUGGESTION_LOGIC', 'Reject suggestion event data is missing');
            return;
        }
        const quill = quillRef.current.getEditor();

        log('SUGGESTION_LOGIC', "Rejecting suggestion ", data);
        log('SUGGESTION_LOGIC', "With data ", event);
        if (data.action_type === 'insert_text') {
            const new_delta = new Delta().retain(data.start).delete(1)
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'delete_text') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'replace_text') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_list_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
            emit('client_apply_edit', {
                documentId,
                edit_id: data.action_id,
                accepted: false,
                action_type: data.action_type,
                text: data.text,
                start: data.start,
                end: data.end,
                list_type: data.list_type,
            });
            return;
        } else if (data.action_type === 'remove_list_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'insert_code_block_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
            emit('client_apply_edit', {
                documentId,
                edit_id: data.action_id,
                accepted: false,
                action_type: data.action_type,
                text: data.text,
                start: data.start,
                end: data.end,
                language: data.language,
            });
            return;
        } else if (data.action_type === 'remove_code_block_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_bold_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, {'suggestion' : null} );
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_bold_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_italic_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_italic_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_strikethrough_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_strikethrough_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'make_underline_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else if (data.action_type === 'remove_underline_formatting') {
            const new_delta = new Delta().retain(data.start).retain(data.end - data.start, { 'suggestion' : null });
            quill.updateContents(new_delta, 'silent');
        } else {
            console.error('Invalid suggestion type:', data.action_type);
            log('SUGGESTION_LOGIC', 'Invalid suggestion type:', data.action_type);
        }

        suggestionIndicatorRef.current?.updateIndicators();
        
        emit('client_apply_edit', {
            documentId,
            edit_id: data.action_id,
            accepted: false,
            action_type: data.action_type,
            text: data.text,
            start: data.start,
            end: data.end,
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
        setEditorContentD(restructuredDocument);
        setShowStructureConfirmation(false);
        
        emit('client_structure_accepted', {'documentId' : documentId, 'content': restructuredDocument});
        setRestructuredDocument('');
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
                            setMessages={setChatMessages}
                            onSend={handleChatSubmit}
                        />
                    </div>
                </div>
                <div className="editor-container">
                    <ReactQuill
                        ref={quillRef}
                        value={editorContent}
                        onChange={handleEditorChange}
                        onChangeSelection={(selection, s, e) => {console.log("[QuillEditor] Selection changed", selection)}}
                        modules={modules}
                    />
                    <SuggestionIndicator quillRef={quillRef} ref={suggestionIndicatorRef}  />
                </div>
                {showStructureConfirmation && (
                    <div className="structure-preview">
                        <h3>Proposed Structure</h3>
                        <ReactQuill
                        value={restructuredDocument}
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

            </div>
        </div>
    );
};