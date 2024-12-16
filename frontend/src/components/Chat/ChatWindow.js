// src/components/Chat/ChatWindow.js
import { useCallback, useState } from 'react';
import ReactQuill from 'react-quill';
import { Button } from '../ui/button';
import { Send } from 'lucide-react';

import '../../styles/chatSection.css';

export const ChatWindow = ({ messages, onSend }) => {
    const [htmlContent, setHtmlContent] = useState('');
    const [plainText, setPlainText] = useState('');

    // Custom handler to extract plain text
    const handleInputChange = (html, delta, source, editor) => {
        setHtmlContent(html);
        setPlainText(editor.getText().trim());
    };

    const handleSubmit = useCallback(() => {
        if (plainText) {
          onSend(plainText);
          setHtmlContent('');
          setPlainText('');
        }
      }, [plainText, onSend]);

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
            value={htmlContent}
            onChange={handleInputChange}
            modules={{ toolbar: false }}
            />
            <Button onClick={handleSubmit}>
            <Send className="h-4 w-4" />
            </Button>
            </div>
        </div>
    );
};



