// Use environment variable with fallback for local development
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Send a query to the AI agent (non-streaming)
 * @param {string} query - The user's query
 * @param {string|null} sessionId - Optional session ID
 * @returns {Promise<{session_id: string, messages: Array}>} - The response
 */
export async function sendQuery(query, sessionId = null) {
    const response = await fetch(`${API_BASE_URL}/query`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, session_id: sessionId }),
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
 * @param {string|null} sessionId - Optional session ID
 * @param {object} callbacks - Event callbacks
 * @param {function} callbacks.onSession - Called with session_id
 * @param {function} callbacks.onToolCall - Called with {tool_name, tool_args}
 * @param {function} callbacks.onToolResult - Called with {tool_name, result}
 * @param {function} callbacks.onResponse - Called with response content
 * @param {function} callbacks.onError - Called with error message
 * @param {function} callbacks.onDone - Called when complete
 * @returns {Promise<void>}
 */
export async function sendQueryStream(query, sessionId = null, callbacks = {}) {
    const response = await fetch(`${API_BASE_URL}/query/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, session_id: sessionId }),
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
                        case 'session':
                            callbacks.onSession?.(event.session_id);
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
                        case 'response':
                            callbacks.onResponse?.(event.content);
                            break;
                        case 'error':
                            callbacks.onError?.(event.message);
                            break;
                        case 'done':
                            callbacks.onDone?.(event.session_id);
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
 * @returns {Promise<{tools: Array}>} - List of available tools
 */
export async function getTools() {
    const response = await fetch(`${API_BASE_URL}/tools`);

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

// ============ Session Management ============

/**
 * Create a new conversation session
 * @returns {Promise<{session_id: string}>}
 */
export async function createSession() {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
        method: 'POST',
    });

    if (!response.ok) {
        throw new Error('Failed to create session');
    }

    return response.json();
}

/**
 * Get all active sessions
 * @returns {Promise<{sessions: string[]}>}
 */
export async function getSessions() {
    const response = await fetch(`${API_BASE_URL}/sessions`);

    if (!response.ok) {
        throw new Error('Failed to fetch sessions');
    }

    return response.json();
}

/**
 * Get messages for a specific session
 * @param {string} sessionId - The session ID
 * @returns {Promise<{session_id: string, messages: Array}>}
 */
export async function getSession(sessionId) {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);

    if (!response.ok) {
        if (response.status === 404) {
            return null;
        }
        throw new Error('Failed to fetch session');
    }

    return response.json();
}

/**
 * Delete a conversation session
 * @param {string} sessionId - The session ID to delete
 * @returns {Promise<{message: string}>}
 */
export async function deleteSession(sessionId) {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'DELETE',
    });

    if (!response.ok) {
        throw new Error('Failed to delete session');
    }

    return response.json();
}


// ============ Authentication ============

/**
 * Get the Salla OAuth authorization URL
 * @returns {Promise<{auth_url: string}>}
 */
export async function getAuthUrl() {
    const response = await fetch(`${API_BASE_URL}/auth/salla/url`);

    if (!response.ok) {
        throw new Error('Failed to get auth URL');
    }

    return response.json();
}

/**
 * Exchange OAuth authorization code for tokens
 * @param {string} code - The authorization code from Salla
 * @returns {Promise<{success: boolean, merchant_info?: object, error?: string}>}
 */
export async function exchangeCode(code) {
    const response = await fetch(`${API_BASE_URL}/auth/salla/callback`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code }),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to exchange code');
    }

    return response.json();
}

/**
 * Check current authentication status
 * @returns {Promise<{authenticated: boolean, merchant_info?: object}>}
 */
export async function checkAuthStatus() {
    const response = await fetch(`${API_BASE_URL}/auth/status`, {
        credentials: 'include',
    });

    if (!response.ok) {
        throw new Error('Failed to check auth status');
    }

    return response.json();
}

/**
 * Logout and clear session
 * @returns {Promise<{success: boolean}>}
 */
export async function logout() {
    const response = await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
    });

    if (!response.ok) {
        throw new Error('Failed to logout');
    }

    return response.json();
}
