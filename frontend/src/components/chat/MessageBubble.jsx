/**
 * Renders a single message bubble
 */
export function MessageBubble({ message }) {
    const isUser = message.role === 'user';
    const isAssistant = message.role === 'assistant';
    const isTool = message.role === 'tool';

    // Parse tool call content if it's a string
    const getToolContent = () => {
        if (typeof message.content === 'string') {
            try {
                if (message.content.includes('TextContent')) {
                    const match = message.content.match(/text='([^']+)'/);
                    return match ? match[1] : message.content;
                }
                return message.content;
            } catch {
                return message.content;
            }
        }
        return JSON.stringify(message.content, null, 2);
    };

    if (isTool) {
        return (
            <div className="flex flex-col max-w-[90%] mr-auto mb-4 animate-fade-in">
                <div className="flex items-center gap-2 px-4 py-2 bg-bg-tertiary border border-border border-b-0 rounded-t-lg">
                    <span className="text-sm">🔧</span>
                    <span className="text-sm font-medium text-text-secondary">Tool Result</span>
                </div>
                <div className="bg-bg-secondary border border-border rounded-b-lg p-4 overflow-x-auto">
                    <pre className="font-mono text-sm text-text-secondary whitespace-pre-wrap break-words m-0">
                        {getToolContent()}
                    </pre>
                </div>
            </div>
        );
    }

    return (
        <div className={`flex gap-4 max-w-[85%] mb-4 animate-fade-in ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}>
            {isAssistant && (
                <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center shrink-0">
                    <span className="text-lg">✨</span>
                </div>
            )}
            <div className={`px-6 py-4 rounded-2xl ${isUser
                    ? 'bg-primary text-text-inverse rounded-br-sm'
                    : 'bg-bg-primary border border-border rounded-bl-sm shadow-sm'
                }`}>
                {message.toolCalls && message.toolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                        {message.toolCalls.map((call, index) => (
                            <div key={index} className="inline-flex items-center gap-2 px-2 py-1 bg-accent rounded-lg text-sm">
                                <span className="font-medium text-primary">{call.function?.name || 'Tool'}</span>
                                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary/10 text-primary">Executed</span>
                            </div>
                        ))}
                    </div>
                )}
                {message.content && (
                    <p className="text-base leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
                )}
                {message.isError && (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-error/15 text-error">Error</span>
                )}
            </div>
        </div>
    );
}
