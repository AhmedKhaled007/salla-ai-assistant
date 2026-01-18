import { useState, useCallback } from 'react';
import { sendQuery } from '../services/api';

/**
 * Custom hook for chat functionality
 */
export function useChat() {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const sendMessage = useCallback(async (query) => {
        if (!query.trim()) return;

        // Add user message immediately
        const userMessage = {
            id: Date.now(),
            role: 'user',
            content: query,
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, userMessage]);
        setIsLoading(true);
        setError(null);

        try {
            const response = await sendQuery(query);

            // Process response messages
            const newMessages = response.messages
                .filter(msg => msg.role !== 'system') // Skip system messages
                .map((msg, index) => ({
                    id: Date.now() + index + 1,
                    role: msg.role,
                    content: msg.content,
                    toolCalls: msg.tool_calls || null,
                    toolCallId: msg.tool_call_id || null,
                    timestamp: new Date().toISOString(),
                }));

            // Replace user message and add all response messages
            setMessages(prev => {
                const withoutLastUser = prev.slice(0, -1);
                return [...withoutLastUser, ...newMessages];
            });
        } catch (err) {
            setError(err.message);
            // Add error as assistant message
            setMessages(prev => [
                ...prev,
                {
                    id: Date.now() + 1,
                    role: 'assistant',
                    content: `Sorry, an error occurred: ${err.message}`,
                    isError: true,
                    timestamp: new Date().toISOString(),
                },
            ]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
    }, []);

    return {
        messages,
        isLoading,
        error,
        sendMessage,
        clearMessages,
    };
}
