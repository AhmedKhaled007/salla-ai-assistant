import { useState, useCallback, useRef } from 'react';
import { sendQueryStream } from '../services/api';

/**
 * Custom hook for chat functionality with SSE streaming
 */
export function useChat() {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [sessionId, setSessionId] = useState(null);
    const [currentToolCall, setCurrentToolCall] = useState(null);
    const abortControllerRef = useRef(null);

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
        setCurrentToolCall(null);

        // Create placeholder for assistant response
        const assistantMessageId = Date.now() + 1;
        const toolCalls = [];

        try {
            await sendQueryStream(query, sessionId, {
                onSession: (newSessionId) => {
                    setSessionId(newSessionId);
                },
                onToolCall: ({ toolName, toolArgs }) => {
                    const toolCall = { name: toolName, args: toolArgs, status: 'running' };
                    toolCalls.push(toolCall);
                    setCurrentToolCall(toolCall);

                    // Add tool call as a message
                    setMessages(prev => [...prev, {
                        id: Date.now(),
                        role: 'tool_call',
                        toolName,
                        toolArgs,
                        timestamp: new Date().toISOString(),
                    }]);
                },
                onToolResult: ({ toolName, result }) => {
                    // Mark tool as complete
                    const tool = toolCalls.find(t => t.name === toolName && t.status === 'running');
                    if (tool) tool.status = 'complete';
                    setCurrentToolCall(null);

                    // Add tool result as a message
                    setMessages(prev => [...prev, {
                        id: Date.now(),
                        role: 'tool_result',
                        toolName,
                        result,
                        timestamp: new Date().toISOString(),
                    }]);
                },
                onResponse: (content) => {
                    // Add final assistant response
                    setMessages(prev => [...prev, {
                        id: assistantMessageId,
                        role: 'assistant',
                        content,
                        timestamp: new Date().toISOString(),
                    }]);
                },
                onError: (message) => {
                    setError(message);
                    setMessages(prev => [...prev, {
                        id: Date.now(),
                        role: 'assistant',
                        content: `Sorry, an error occurred: ${message}`,
                        isError: true,
                        timestamp: new Date().toISOString(),
                    }]);
                },
                onDone: () => {
                    setCurrentToolCall(null);
                },
            });
        } catch (err) {
            setError(err.message);
            setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'assistant',
                content: `Sorry, an error occurred: ${err.message}`,
                isError: true,
                timestamp: new Date().toISOString(),
            }]);
        } finally {
            setIsLoading(false);
            setCurrentToolCall(null);
        }
    }, [sessionId]);

    const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
        setSessionId(null);
        setCurrentToolCall(null);
    }, []);

    return {
        messages,
        isLoading,
        error,
        sessionId,
        currentToolCall,
        sendMessage,
        clearMessages,
    };
}

