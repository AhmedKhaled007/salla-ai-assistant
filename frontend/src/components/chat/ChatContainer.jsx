import { useRef, useEffect } from 'react';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';

/**
 * Main chat container component
 */
export function ChatContainer({ messages, isLoading, onSendMessage }) {
    const messagesEndRef = useRef(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    return (
        <div className="flex-1 flex flex-col h-screen overflow-hidden">
            <div className="flex-1 overflow-y-auto p-8 pb-0 flex flex-col">
                {messages.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center text-text-muted p-12 max-w-[800px] w-full mx-auto">
                        <div className="text-6xl mb-6 opacity-60">💬</div>
                        <h3 className="text-xl font-semibold text-text-primary mb-2">Start a conversation</h3>
                        <p className="text-base text-text-secondary">Ask me anything about your Salla store</p>
                    </div>
                ) : (
                    <div className="flex flex-col min-h-full max-w-[800px] w-full mx-auto">
                        {messages.map((message) => (
                            <MessageBubble key={message.id} message={message} />
                        ))}
                        {isLoading && (
                            <div className="flex gap-1.5 px-6 py-4 bg-bg-primary border border-border rounded-2xl rounded-bl-sm w-fit mb-4 shadow-sm animate-fade-in">
                                <div className="w-2 h-2 bg-primary rounded-full animate-typing-bounce"></div>
                                <div className="w-2 h-2 bg-primary rounded-full animate-typing-bounce-delay-1"></div>
                                <div className="w-2 h-2 bg-primary rounded-full animate-typing-bounce-delay-2"></div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>
                )}
            </div>
            <ChatInput onSend={onSendMessage} isLoading={isLoading} />
        </div>
    );
}
