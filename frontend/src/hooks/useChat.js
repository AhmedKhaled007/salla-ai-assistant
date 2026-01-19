import { useState, useCallback, useRef } from 'react';
import { sendQueryStream } from '../services/api';

/**
 * Custom hook for chat functionality with SSE streaming
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 */
export function useChat(authSessionId = null) {
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [conversationId, setConversationId] = useState(null);
    const [title, setTitle] = useState(null);
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
            await sendQueryStream(query, conversationId, authSessionId, {
                onConversation: (newConversationId) => {
                    setConversationId(newConversationId);
                },
                onTitle: (newTitle) => {
                    setTitle(newTitle);
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
                onResponseChunk: (chunk) => {
                    setMessages(prev => {
                        const existingMsgIndex = prev.findIndex(m => m.id === assistantMessageId);
                        if (existingMsgIndex !== -1) {
                            const newMessages = [...prev];
                            newMessages[existingMsgIndex] = {
                                ...newMessages[existingMsgIndex],
                                content: (newMessages[existingMsgIndex].content || '') + chunk
                            };
                            return newMessages;
                        } else {
                            return [...prev, {
                                id: assistantMessageId,
                                role: 'assistant',
                                content: chunk,
                                timestamp: new Date().toISOString(),
                            }];
                        }
                    });
                },
                onResponse: (content) => {
                    // Final update to ensure consistency
                    setMessages(prev => {
                        const existingMsgIndex = prev.findIndex(m => m.id === assistantMessageId);
                        if (existingMsgIndex !== -1) {
                            const newMessages = [...prev];
                            newMessages[existingMsgIndex] = {
                                ...newMessages[existingMsgIndex],
                                content: content
                            };
                            return newMessages;
                        } else {
                            return [...prev, {
                                id: assistantMessageId,
                                role: 'assistant',
                                content,
                                timestamp: new Date().toISOString(),
                            }];
                        }
                    });
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
    }, [conversationId, authSessionId]);

    const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
        setConversationId(null);
        setTitle(null);
        setCurrentToolCall(null);
    }, []);

    return {
        messages,
        isLoading,
        error,
        conversationId,
        title,
        currentToolCall,
        sendMessage,
        clearMessages,
        setMessages,
        setConversationId,
    };
}

