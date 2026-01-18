import { Sidebar } from './components/layout/Sidebar';
import { ChatContainer } from './components/chat/ChatContainer';
import { useChat } from './hooks/useChat';

function App() {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();

  return (
    <div className="flex min-h-screen w-full bg-gradient-to-b from-accent to-bg-primary">
      <Sidebar onNewChat={clearMessages} />
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
