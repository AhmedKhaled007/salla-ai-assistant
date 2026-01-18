import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { ChatContainer } from './components/chat/ChatContainer';
import { useChat } from './hooks/useChat';
import { useToast } from './components/ui/Toast';
import { getSessions, getSession, deleteSession, checkHealth } from './services/api';

function App() {
  const { messages, isLoading, sessionId, sendMessage, clearMessages, setMessages, setSessionId } = useChat();
  const [sessions, setSessions] = useState([]);
  const [healthStatus, setHealthStatus] = useState(null);
  const { showError, showSuccess, showWarning } = useToast();

  // Fetch sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const data = await getSessions();
        setSessions(data.sessions || []);
      } catch (err) {
        // Silent fail for session fetch - not critical
        console.error('Failed to fetch sessions:', err);
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

    fetchSessions();
    fetchHealth();
  }, [showError, showWarning]);

  // Refresh sessions when current session changes
  useEffect(() => {
    if (sessionId) {
      setSessions(prev => {
        if (!prev.includes(sessionId)) {
          return [sessionId, ...prev];
        }
        return prev;
      });
    }
  }, [sessionId]);

  // Load a previous session
  const handleLoadSession = useCallback(async (id) => {
    try {
      const data = await getSession(id);
      if (data) {
        setSessionId(id);
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
  }, [setMessages, setSessionId, showError]);

  // Delete a session
  const handleDeleteSession = useCallback(async (id) => {
    try {
      await deleteSession(id);
      setSessions(prev => prev.filter(s => s !== id));
      if (sessionId === id) {
        clearMessages();
      }
      showSuccess('Conversation deleted');
    } catch (err) {
      showError('Failed to delete conversation');
    }
  }, [sessionId, clearMessages, showError, showSuccess]);

  // Quick action handlers
  const handleQuickAction = useCallback((query) => {
    sendMessage(query);
  }, [sendMessage]);

  return (
    <div className="flex min-h-screen w-full bg-gradient-to-b from-accent to-bg-primary">
      <Sidebar
        onNewChat={clearMessages}
        sessions={sessions}
        currentSessionId={sessionId}
        onLoadSession={handleLoadSession}
        onDeleteSession={handleDeleteSession}
        onQuickAction={handleQuickAction}
        healthStatus={healthStatus}
      />
      <main className="flex-1 flex flex-col bg-gradient-to-br from-accent/30 via-transparent to-accent/10">
        <ChatContainer
          messages={messages}
          isLoading={isLoading}
          onSendMessage={sendMessage}
        />
      </main>
    </div>
  );
}

export default App;

