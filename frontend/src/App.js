import React, { useState, useRef } from 'react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import { Menubar, MenubarCheckboxItem, MenubarContent, MenubarItem, MenubarMenu, 
  MenubarSeparator, MenubarShortcut, MenubarSub, MenubarSubContent, 
  MenubarSubTrigger, MenubarTrigger } from './components/ui/menubar';
import { Button } from './components/ui/button';
import { Card } from './components/ui/card';
import { ChevronRight, ChevronLeft, Upload, Send } from 'lucide-react';

// Import CSS files
import './styles/App.css';
import './styles/components.css';
import './styles/globals.css'; 

const App = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editorContent, setEditorContent] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [structureTemplate, setStructureTemplate] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const quillRef = useRef(null);

  const handleStructureUpload = (event) => {
    const file = event.target.files[0];
    if (file) setStructureTemplate(file);
  };

  const handleContentUpload = (event) => {
    const files = Array.from(event.target.files);
    setUploadedFiles([...uploadedFiles, ...files]);
  };

  const handleEditorChange = (content) => {
    setEditorContent(content);
  };

  const handleChatSubmit = () => {
    if (chatInput.trim()) {
      setChatMessages([...chatMessages, { text: chatInput, sender: 'user' }]);
      setChatInput('');
    }
  };

  return (
    <div className="app-container">
      <div className="menubar-container">
        <div className="menubar-content">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="toggle-button"
          >
            {sidebarOpen ? <ChevronLeft /> : <ChevronRight />}
          </Button>
          <Menubar className="border-none">
            <MenubarMenu>
              <MenubarTrigger>File</MenubarTrigger>
              <MenubarContent>
                <MenubarItem>New Tab <MenubarShortcut>⌘T</MenubarShortcut></MenubarItem>
                <MenubarItem>Open <MenubarShortcut>⌘O</MenubarShortcut></MenubarItem>
                <MenubarItem>Save <MenubarShortcut>⌘S</MenubarShortcut></MenubarItem>
                <MenubarSeparator />
                <MenubarSub>
                  <MenubarSubTrigger>Share</MenubarSubTrigger>
                  <MenubarSubContent>
                    <MenubarItem>Email link</MenubarItem>
                    <MenubarItem>Messages</MenubarItem>
                    <MenubarItem>Notes</MenubarItem>
                  </MenubarSubContent>
                </MenubarSub>
                <MenubarSeparator />
                <MenubarItem>Print... <MenubarShortcut>⌘P</MenubarShortcut></MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>Edit</MenubarTrigger>
              <MenubarContent>
                <MenubarItem>Undo <MenubarShortcut>⌘Z</MenubarShortcut></MenubarItem>
                <MenubarItem>Redo <MenubarShortcut>⇧⌘Z</MenubarShortcut></MenubarItem>
                <MenubarSeparator />
                <MenubarSub>
                  <MenubarSubTrigger>Find</MenubarSubTrigger>
                  <MenubarSubContent>
                    <MenubarItem>Find... <MenubarShortcut>⌘F</MenubarShortcut></MenubarItem>
                    <MenubarItem>Find Next</MenubarItem>
                    <MenubarItem>Find Previous</MenubarItem>
                  </MenubarSubContent>
                </MenubarSub>
                <MenubarSeparator />
                <MenubarItem>Cut</MenubarItem>
                <MenubarItem>Copy</MenubarItem>
                <MenubarItem>Paste</MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>View</MenubarTrigger>
              <MenubarContent>
                <MenubarCheckboxItem onClick={() => setSidebarOpen(!sidebarOpen)}>
                  Show Sidebar
                </MenubarCheckboxItem>
                <MenubarSeparator />
                <MenubarItem>Toggle Fullscreen</MenubarItem>
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      </div>
       

      <div className="main-content">
        <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          <div className="sidebar-content">
            <div className="upload-section">
              <h2 className="font-medium mb-4">Structure Template</h2>
              <Card className="upload-card">
                <div className="upload-container">
                  <Upload className="upload-icon" />
                  <input
                    type="file"
                    onChange={handleStructureUpload}
                    className="hidden"
                    id="structure-upload"
                  />
                  <label
                    htmlFor="structure-upload"
                    className="upload-label"
                  >
                    Upload Template
                  </label>
                </div>
              </Card>
            </div>

            <div className="upload-section flex-1">
              <h2 className="font-medium mb-4">Content Files</h2>
              <Card className="upload-card">
                <div className="upload-container">
                  <Upload className="upload-icon" />
                  <input
                    type="file"
                    multiple
                    onChange={handleContentUpload}
                    className="hidden"
                    id="content-upload"
                  />
                  <label
                    htmlFor="content-upload"
                    className="upload-label"
                  >
                    Upload Files
                  </label>
                </div>
              </Card>
              <div className="file-list">
                {uploadedFiles.map((file, index) => (
                  <div key={index} className="file-item">
                    {file.name}
                  </div>
                ))}
              </div>
            </div>

            <div className="chat-section">
              <h2 className="font-medium mb-4">Chat</h2>
              <div className="chat-messages">
                {chatMessages.map((message, index) => (
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
                value={chatInput}
                onChange={setChatInput}
                modules={{ toolbar: false }}
              />
              <Button onClick={handleChatSubmit}>
                <Send className="h-4 w-4" />
              </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="editor-container">
          <ReactQuill
            ref={quillRef}
            value={editorContent}
            onChange={handleEditorChange}
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
      </div>
    </div>
  );
};

export default App;