const API_BASE_URL = 'http://localhost:8000';

/**
 * Send a query to the AI agent
 * @param {string} query - The user's query
 * @returns {Promise<{messages: Array}>} - The response messages
 */
export async function sendQuery(query) {
    const response = await fetch(`${API_BASE_URL}/query`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to send query');
    }

    return response.json();
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
