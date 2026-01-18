import { useRef, useEffect, useState, useCallback } from 'react';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';

/**
 * Main chat container component
 */
export function ChatContainer({ messages, isLoading, onSendMessage }) {
    const messagesEndRef = useRef(null);
    const scrollContainerRef = useRef(null);
    const [showScrollButton, setShowScrollButton] = useState(false);

    // Check if user is near bottom
    const checkScrollPosition = useCallback(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        setShowScrollButton(distanceFromBottom > 100);
    }, []);

    // Scroll to bottom smoothly
    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

        // Only auto-scroll if user is near bottom (within 150px)
        if (distanceFromBottom < 150) {
            scrollToBottom();
        }
    }, [messages, scrollToBottom]);

    // Listen for scroll events
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        container.addEventListener('scroll', checkScrollPosition);
        return () => container.removeEventListener('scroll', checkScrollPosition);
    }, [checkScrollPosition]);

    return (
        <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto p-8 pb-0 flex flex-col"
            >
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

            {/* Scroll to bottom button */}
            {showScrollButton && (
                <button
                    onClick={scrollToBottom}
                    className="absolute bottom-28 end-8 w-10 h-10 bg-primary text-text-inverse rounded-full shadow-lg flex items-center justify-center hover:bg-primary-dark transition-all animate-fade-in"
                    title="Scroll to bottom"
                >
                    <span className="text-lg">↓</span>
                </button>
            )}

            <ChatInput onSend={onSendMessage} isLoading={isLoading} />
        </div>
    );
}

