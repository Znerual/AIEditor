// src/components/Chat/ChatWindow.js
import { useCallback, useState } from 'react';
import ReactQuill from 'react-quill';
import { Button } from '../ui/button';
import { Send } from 'lucide-react';

import '../../styles/chatSection.css';

export const ChatWindow = ({ messages, onSend }) => {
    const [input, setInput] = useState('');

    const handleSubmit = useCallback(() => {
        if (input.trim()) {
            onSend(input);
            setInput('');
        }
    }, [input, onSend]);

    return (
        <div className="chat-section">
            <h2 className="font-medium mb-4">Chat</h2>
            <div className="chat-messages">
            {messages.map((message, index) => (
                <div
                key={index}
                className={`message ${
                    message.sender === 'user' ? 'message-user' : 'message-other'
                }`}
                >
                {message.text}
                </div>
            ))}
            </div>
            <div className="chat-input-container">
            <ReactQuill
            value={input}
            onChange={setInput}
            modules={{ toolbar: false }}
            />
            <Button onClick={handleSubmit}>
            <Send className="h-4 w-4" />
            </Button>
            </div>
        </div>
    );
};



