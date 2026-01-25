import { useState, useCallback, useRef, useEffect } from 'react';
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
    const activeConversationIdRef = useRef(conversationId);

    useEffect(() => {
        activeConversationIdRef.current = conversationId;
    }, [conversationId]);



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



        // Track the conversation ID for this specific request
        let trackingId = conversationId;

        try {
            await sendQueryStream(query, conversationId, authSessionId, {
                onConversation: (newConversationId) => {
                    // Only update if we are still viewing the relevant conversation
                    if (activeConversationIdRef.current === trackingId) {
                        setConversationId(newConversationId);
                        // Update trackingId because the conversation ID has formally changed from null -> newId
                        trackingId = newConversationId;
                        // Manually sync ref to prevent race conditions during the render cycle
                        activeConversationIdRef.current = newConversationId;
                    }
                },
                onTitle: (newTitle) => {
                    if (activeConversationIdRef.current === trackingId) {
                        setTitle(newTitle);
                    }
                },
                onToolCall: ({ toolName, toolArgs }) => {
                    if (activeConversationIdRef.current !== trackingId) return;

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
                    if (activeConversationIdRef.current !== trackingId) return;

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
                    if (activeConversationIdRef.current !== trackingId) return;

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
                    if (activeConversationIdRef.current !== trackingId) return;

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
                    if (activeConversationIdRef.current !== trackingId) return;

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
                    if (activeConversationIdRef.current === trackingId) {
                        setCurrentToolCall(null);
                    }
                },
            });
        } catch (err) {
            if (activeConversationIdRef.current !== trackingId) return;

            setError(err.message);
            setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'assistant',
                content: `Sorry, an error occurred: ${err.message}`,
                isError: true,
                timestamp: new Date().toISOString(),
            }]);
        } finally {
            if (activeConversationIdRef.current === trackingId) {
                setIsLoading(false);
                setCurrentToolCall(null);
            }
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
        setTitle,

        setIsLoading,
        setCurrentToolCall,
    };
}

