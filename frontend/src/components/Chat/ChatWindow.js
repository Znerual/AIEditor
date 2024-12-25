import { useCallback, useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { Button } from '../ui/button';
import { Send, X } from 'lucide-react';
import '../../styles/chatSection.css';

export const ChatWindow = ({ messages, setMessages, onSend }) => {
  const [inputText, setInputText] = useState('');
  const [isPoppedOut, setIsPoppedOut] = useState(false);
  const [popupWindow, setPopupWindow] = useState(null);
  const [containerDiv, setContainerDiv] = useState(null);

  const handleInputChange = (event) => {
    setInputText(event.target.value);
  };

  const handleSubmit = useCallback(() => {
    if (inputText.trim()) {
      onSend(inputText.trim());
      setInputText('');
    }
  }, [inputText, onSend]);

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleDeleteMessage = (indexToDelete) => {
    setMessages(prevMessages =>
      prevMessages.filter((_, index) => index !== indexToDelete)
    );
  };

  const handlePopOut = () => {
    if (!isPoppedOut) {
      const newWindow = window.open('', '', 'width=600,height=800');
      const container = document.createElement('div');
      newWindow.document.body.appendChild(container);
      newWindow.document.title = 'Chat Window';
      setPopupWindow(newWindow);
      setContainerDiv(container);
      setIsPoppedOut(true);
    }
  };

  const handlePopBackIn = () => {
    if (popupWindow) {
      popupWindow.close();
      setPopupWindow(null);
      setContainerDiv(null);
      setIsPoppedOut(false);
    }
  };

  // Clean up the popup window on unmount
  useEffect(() => {
    return () => {
      if (popupWindow) {
        popupWindow.close();
      }
    };
  }, [popupWindow]);

  const ChatContent = (
    <div className="chat-section">
        <div className="chat-header-container">
            <h2 className="chat-header-title">Chat</h2>
            {!isPoppedOut && (
                <Button onClick={handlePopOut} className="chat-header-button">
                Pop Out
                </Button>
            )}
            {isPoppedOut && popupWindow && (
                <Button onClick={handlePopBackIn} className="chat-header-button">
                Pop Back In
                </Button>
            )}
        </div>
        <div className="chat-messages">
            {messages.map((message, index) => (
            <div
                key={index}
                className={`message ${
                message.sender === 'user' ? 'message-user' : 'message-other'
                }`}
            >
                <div className="message-content">
                    {message.text}
                </div>
                <button
                    onClick={() => handleDeleteMessage(index)}
                    className="delete-button"
                >
                    <X className="h-3 w-3" />
                </button>
            </div>
            
            ))}
        </div>
        <div className="chat-input-container">
            <textarea
            value={inputText}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="w-full p-2 border rounded-md resize-y min-h-[100px]"
            />
            <Button onClick={handleSubmit}>
            <Send className="h-4 w-4" />
            </Button>
        </div>
        </div>
  );

  // Render in the popup or the main window
  if (isPoppedOut && containerDiv) {
    return ReactDOM.createPortal(ChatContent, containerDiv);
  }
  return ChatContent;
};