// Use environment variable with fallback for local development
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Send a query to the AI agent (non-streaming)
 * @param {string} query - The user's query
 * @param {string|null} sessionId - Optional conversation session ID
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{session_id: string, messages: Array}>} - The response
 */
/**
 * Send a query to the AI agent (non-streaming)
 * @param {string} query - The user's query
 * @param {string|null} conversationId - Optional conversation ID
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{conversation_id: string, messages: Array}>} - The response
 */
export async function sendQuery(query, conversationId = null, authSessionId = null) {
    const headers = {
        'Content-Type': 'application/json',
    };

    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            query,
            conversation_id: conversationId,
        }),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to send query');
    }

    return response.json();
}

/**
 * Send a query with SSE streaming
 * @param {string} query - The user's query
 * @param {string|null} conversationId - Optional conversation ID
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @param {object} callbacks - Event callbacks
 * @param {function} callbacks.onConversation - Called with conversation_id
 * @param {function} callbacks.onToolCall - Called with {tool_name, tool_args}
 * @param {function} callbacks.onToolResult - Called with {tool_name, result}
 * @param {function} callbacks.onResponse - Called with response content
 * @param {function} callbacks.onError - Called with error message
 * @param {function} callbacks.onDone - Called when complete
 * @returns {Promise<void>}
 */
export async function sendQueryStream(query, conversationId = null, authSessionId = null, callbacks = {}) {
    const headers = {
        'Content-Type': 'application/json',
    };

    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/query/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            query,
            conversation_id: conversationId,
        }),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to send query');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    const event = JSON.parse(line.slice(6));

                    switch (event.type) {
                        case 'conversation':
                            callbacks.onConversation?.(event.conversation_id);
                            break;
                        case 'title':
                            callbacks.onTitle?.(event.title);
                            break;
                        case 'tool_call':
                            callbacks.onToolCall?.({
                                toolName: event.tool_name,
                                toolArgs: event.tool_args,
                            });
                            break;
                        case 'tool_result':
                            callbacks.onToolResult?.({
                                toolName: event.tool_name,
                                result: event.result,
                            });
                            break;
                        case 'response_chunk':
                            callbacks.onResponseChunk?.(event.chunk);
                            break;
                        case 'response':
                            callbacks.onResponse?.(event.content);
                            break;
                        case 'error':
                            callbacks.onError?.(event.message);
                            break;
                        case 'done':
                            callbacks.onDone?.(event.conversation_id);
                            break;
                    }
                } catch (e) {
                    console.error('Failed to parse SSE event:', e);
                }
            }
        }
    }
}

/**
 * Get available tools from the agent
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{tools: Array}>} - List of available tools
 */
export async function getTools(authSessionId = null) {
    const headers = {};
    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }

    const response = await fetch(`${API_BASE_URL}/tools`, { headers });

    if (!response.ok) {
        throw new Error('Failed to fetch tools');
    }

    return response.json();
}

/**
 * Check backend health status
 * @returns {Promise<{status: string, mcp_connected: boolean, mcp_responsive: boolean}>}
 */
export async function checkHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);

    if (!response.ok) {
        throw new Error('Health check failed');
    }

    return response.json();
}

// ============ Conversation Management ============

/**
 * Create a new conversation
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{conversation_id: string}>}
 */
export async function createConversation(authSessionId = null) {
    const headers = {};
    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }
    const response = await fetch(`${API_BASE_URL}/api/conversations`, {
        method: 'POST',
        headers,
    });

    if (!response.ok) {
        throw new Error('Failed to create conversation');
    }

    return response.json();
}

/**
 * Get all active conversations
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{conversations: string[]}>}
 */
export async function getConversations(authSessionId = null) {
    const headers = {};
    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }
    const response = await fetch(`${API_BASE_URL}/api/conversations`, { headers });

    if (!response.ok) {
        throw new Error('Failed to fetch conversations');
    }

    return response.json();
}

/**
 * Get messages for a specific conversation
 * @param {string} conversationId - The conversation ID
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{conversation_id: string, messages: Array}>}
 */
export async function getConversation(conversationId, authSessionId = null) {
    const headers = {};
    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }
    const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`, { headers });

    if (!response.ok) {
        if (response.status === 404) {
            return null;
        }
        throw new Error('Failed to fetch conversation');
    }

    return response.json();
}

/**
 * Delete a conversation
 * @param {string} conversationId - The conversation ID to delete
 * @param {string|null} authSessionId - Optional OAuth session ID for authentication
 * @returns {Promise<{message: string}>}
 */
export async function deleteConversation(conversationId, authSessionId = null) {
    const headers = {};
    if (authSessionId) {
        headers['X-Auth-Session-Id'] = authSessionId;
    }
    const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`, {
        method: 'DELETE',
        headers,
    });

    if (!response.ok) {
        throw new Error('Failed to delete conversation');
    }

    return response.json();
}


// ============ Authentication ============

/**
 * Get the Salla OAuth authorization URL
 * @returns {Promise<{url: string}>}
 */
export async function getAuthUrl() {
    const response = await fetch(`${API_BASE_URL}/auth/url`);

    if (!response.ok) {
        throw new Error('Failed to get auth URL');
    }

    return response.json();
}

/**
 * Exchange OAuth authorization code for tokens
 * @param {string} code - The authorization code from Salla
 * @param {string} state - The CSRF state parameter from Salla
 * @returns {Promise<{success: boolean, merchant_info?: object, error?: string}>}
 */
export async function exchangeCode(code, state) {
    const response = await fetch(`${API_BASE_URL}/auth/callback`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code, state }),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to exchange code');
    }

    return response.json();
}

/**
 * Check current authentication status
 * @param {string} authSessionId - The auth session ID to check
 * @returns {Promise<{authenticated: boolean, merchant_info?: object}>}
 */
export async function checkAuthStatus(authSessionId) {
    if (!authSessionId) return { authenticated: false };

    const response = await fetch(`${API_BASE_URL}/auth/status`, {
        headers: {
            'X-Auth-Session-Id': authSessionId
        }
    });

    if (!response.ok) {
        throw new Error('Failed to check auth status');
    }

    return response.json();
}

/**
 * Logout and clear session
 * @param {string} authSessionId - The auth session ID to logout
 * @returns {Promise<{success: boolean}>}
 */
export async function logout(authSessionId) {
    if (!authSessionId) return { success: true };

    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        headers: {
            'X-Auth-Session-Id': authSessionId
        }
    });

    if (!response.ok) {
        throw new Error('Failed to logout');
    }

    return response.json();
}
