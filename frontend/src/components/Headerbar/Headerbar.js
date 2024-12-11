import { Menubar, MenubarCheckboxItem, MenubarContent, MenubarItem, MenubarMenu, 
    MenubarSeparator, MenubarShortcut, MenubarSub, MenubarSubContent, 
    MenubarSubTrigger, MenubarTrigger } from '../ui/menubar';
import { Button, buttonVariants } from '../ui/button';
import { ChevronRight, ChevronLeft } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { Link } from 'react-router-dom';

export const Headerbar = ({ onToggleSidebar, sidebarOpen }) => {
  const { user, logout } = useAuth();
    return (
        <div className="menubar-container">
            <div className="menubar-toggle">
                <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={onToggleSidebar}
                    className="toggle-button"
                >
                    {sidebarOpen ? <ChevronLeft /> : <ChevronRight />}
                </Button>
            </div>
            <Menubar className="menubar-content">
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
                        <MenubarCheckboxItem onClick={onToggleSidebar}>
                            Show Sidebar
                        </MenubarCheckboxItem>
                        <MenubarSeparator />
                        <MenubarItem>Toggle Fullscreen</MenubarItem>
                    </MenubarContent>
                </MenubarMenu>
            </Menubar>
            <div className="menubar-actions">
                {user?.isAdmin && (
                    <Link to="/admin" className={buttonVariants({ variant: "default", className: 'mr-2' })}>
                        Admin
                    </Link>
                )}
                <Button variant="outline" onClick={logout}>Logout</Button>
            </div>
      </div>
    );
};