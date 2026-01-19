import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { AuthCallback } from './pages/AuthCallback';
import { Sidebar } from './components/layout/Sidebar';
import { ChatContainer } from './components/chat/ChatContainer';
import { useChat } from './hooks/useChat';
import { useToast, ToastProvider } from './components/ui/Toast';
import { useMediaQuery } from './hooks/useMediaQuery';
import { getConversations, getConversation, deleteConversation, checkHealth } from './services/api';

// Protected route wrapper
function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-accent via-bg-secondary to-accent-light">
        <div className="text-center">
          <div className="w-12 h-12 mx-auto border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
          <p className="mt-4 text-text-muted">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

// Main chat application content
function ChatApp() {
  const { logout, merchantInfo, authSessionId } = useAuth();
  const { messages, isLoading, conversationId, sendMessage, clearMessages, setMessages, setConversationId } = useChat(authSessionId);
  const [conversations, setConversations] = useState([]);
  const [healthStatus, setHealthStatus] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { showError, showSuccess, showWarning } = useToast();
  const isDesktop = useMediaQuery('(min-width: 1024px)');

  // Auto-close sidebar on desktop transition
  useEffect(() => {
    if (isDesktop) {
      setIsSidebarOpen(false);
    }
  }, [isDesktop]);

  // Fetch sessions on mount
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const data = await getConversations();
        setConversations(data.conversations || []);
      } catch (err) {
        // Silent fail for session fetch - not critical
        console.error('Failed to fetch conversations:', err);
      }
    };

    const fetchHealth = async () => {
      try {
        const health = await checkHealth();
        setHealthStatus(health);
        if (health.status === 'degraded') {
          showWarning('Backend connection is degraded');
        }
      } catch (err) {
        setHealthStatus({ status: 'error', mcp_connected: false });
        showError('Cannot connect to backend server');
      }
    };

    fetchConversations();
    fetchHealth();
  }, [showError, showWarning]);

  // Refresh conversations when current conversation changes
  useEffect(() => {
    if (conversationId) {
      setConversations(prev => {
        if (!prev.includes(conversationId)) {
          return [conversationId, ...prev];
        }
        return prev;
      });
    }
  }, [conversationId]);

  // Load a previous conversation
  const handleLoadConversation = useCallback(async (id) => {
    try {
      const data = await getConversation(id);
      if (data) {
        setConversationId(id);
        // Convert messages to frontend format
        const formattedMessages = data.messages
          .filter(msg => msg.role !== 'system')
          .map((msg, index) => ({
            id: Date.now() + index,
            role: msg.role,
            content: msg.content,
            timestamp: new Date().toISOString(),
          }));
        setMessages(formattedMessages);
      }
    } catch (err) {
      showError('Failed to load conversation');
    }
  }, [setMessages, setConversationId, showError]);

  // Delete a conversation
  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id);
      setConversations(prev => prev.filter(s => s !== id));
      if (conversationId === id) {
        clearMessages();
      }
      showSuccess('Conversation deleted');
    } catch (err) {
      showError('Failed to delete conversation');
    }
  }, [conversationId, clearMessages, showError, showSuccess]);

  // Quick action handlers
  const handleQuickAction = useCallback((query) => {
    sendMessage(query);
  }, [sendMessage]);

  // Handle logout
  const handleLogout = useCallback(async () => {
    await logout();
    showSuccess('Logged out successfully');
  }, [logout, showSuccess]);

  return (
    <div className="flex min-h-screen w-full bg-gradient-to-b from-accent to-bg-primary overflow-hidden">
      <Sidebar
        onNewChat={clearMessages}
        conversations={conversations}
        currentConversationId={conversationId}
        onLoadConversation={handleLoadConversation}
        onDeleteConversation={handleDeleteConversation}
        onQuickAction={handleQuickAction}
        onLogout={handleLogout}
        healthStatus={healthStatus}
        merchantInfo={merchantInfo}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <main className="flex-1 flex flex-col bg-gradient-to-br from-accent/30 via-transparent to-accent/10 relative w-full h-full overflow-hidden">
        {/* Mobile Header */}
        <div className="lg:hidden flex items-center p-4 border-b border-border bg-bg-primary/80 backdrop-blur-sm z-30 absolute top-0 left-0 right-0 h-16">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="p-2 -ml-2 text-text-primary hover:bg-accent rounded-lg"
          >
            <span className="text-xl">☰</span>
          </button>
          <div className="ml-4 font-semibold text-text-primary">Salla Agent</div>
        </div>

        <div className="flex-1 lg:pt-0 pt-16 h-full flex flex-col">
          <ChatContainer
            messages={messages}
            isLoading={isLoading}
            onSendMessage={sendMessage}
          />
        </div>
      </main>
    </div>
  );
}

// App wrapper with providers and routing
function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <ChatApp />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}

export default App;
