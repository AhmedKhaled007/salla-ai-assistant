import { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Code block with copy button
 */
function CodeBlock({ children, className }) {
    const [copied, setCopied] = useState(false);
    const language = className?.replace('language-', '') || '';
    const code = String(children).replace(/\n$/, '');

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group my-3">
            <div className="absolute end-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                    onClick={handleCopy}
                    className="px-2 py-1 text-xs rounded bg-bg-tertiary hover:bg-border text-text-secondary"
                >
                    {copied ? '✓ Copied' : 'Copy'}
                </button>
            </div>
            {language && (
                <div className="text-xs text-text-muted px-3 py-1 bg-bg-tertiary rounded-t border-b border-border">
                    {language}
                </div>
            )}
            <pre className={`bg-bg-secondary p-4 overflow-x-auto ${language ? 'rounded-b' : 'rounded'} border border-border`}>
                <code className={`font-mono text-sm text-text-primary ${className || ''}`}>
                    {code}
                </code>
            </pre>
        </div>
    );
}

/**
 * Renders a single message bubble
 */
export function MessageBubble({ message }) {
    const isUser = message.role === 'user';
    const isAssistant = message.role === 'assistant';
    const isTool = message.role === 'tool';
    const isToolCall = message.role === 'tool_call';
    const isToolResult = message.role === 'tool_result';

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

    // Custom markdown components
    const markdownComponents = {
        code({ inline, className, children, ...props }) {
            if (inline) {
                return (
                    <code className="px-1.5 py-0.5 bg-bg-tertiary rounded text-sm font-mono" {...props}>
                        {children}
                    </code>
                );
            }
            return <CodeBlock className={className}>{children}</CodeBlock>;
        },
        p({ children }) {
            return <p className="mb-3 last:mb-0">{children}</p>;
        },
        ul({ children }) {
            return <ul className="list-disc list-inside mb-3 space-y-1">{children}</ul>;
        },
        ol({ children }) {
            return <ol className="list-decimal list-inside mb-3 space-y-1">{children}</ol>;
        },
        li({ children }) {
            return <li className="text-text-primary">{children}</li>;
        },
        a({ href, children }) {
            return (
                <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                    {children}
                </a>
            );
        },
        strong({ children }) {
            return <strong className="font-semibold">{children}</strong>;
        },
        h1({ children }) {
            return <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0">{children}</h1>;
        },
        h2({ children }) {
            return <h2 className="text-lg font-bold mb-2 mt-3 first:mt-0">{children}</h2>;
        },
        h3({ children }) {
            return <h3 className="text-base font-bold mb-2 mt-3 first:mt-0">{children}</h3>;
        },
        blockquote({ children }) {
            return (
                <blockquote className="border-s-4 border-primary/50 ps-4 my-3 italic text-text-secondary">
                    {children}
                </blockquote>
            );
        },
        table({ children }) {
            return (
                <div className="overflow-x-auto my-3">
                    <table className="min-w-full border border-border rounded">{children}</table>
                </div>
            );
        },
        th({ children }) {
            return <th className="px-3 py-2 bg-bg-tertiary border-b border-border text-start font-semibold">{children}</th>;
        },

        td({ children }) {
            return <td className="px-3 py-2 border-b border-border">{children}</td>;
        },
    };

    // Render tool call (streaming - when tool is being called)
    if (isToolCall) {
        return (
            <div className="flex flex-col max-w-[90%] me-auto mb-3 animate-fade-in">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-accent/30 border border-primary/20 rounded-lg">
                    <span className="animate-spin text-primary">⚙️</span>
                    <span className="text-sm font-medium text-primary">Calling: {message.toolName}</span>
                </div>
                {message.toolArgs && Object.keys(message.toolArgs).length > 0 && (
                    <div className="mt-1 ms-4 px-3 py-2 bg-bg-tertiary rounded text-xs font-mono text-text-secondary">
                        {JSON.stringify(message.toolArgs, null, 2)}
                    </div>
                )}
            </div>
        );
    }

    // Render tool result (streaming - when tool returns)
    if (isToolResult) {
        const result = message.result;
        const isError = typeof result === 'string' && result.toLowerCase().includes('error');

        return (
            <div className="flex flex-col max-w-[90%] me-auto mb-3 animate-fade-in">
                <div className={`flex items-center gap-2 px-4 py-2 border border-b-0 rounded-t-lg ${isError ? 'bg-error/10 border-error/30' : 'bg-success/10 border-success/30'
                    }`}>
                    <span>{isError ? '❌' : '✅'}</span>
                    <span className={`text-sm font-medium ${isError ? 'text-error' : 'text-success'}`}>
                        {message.toolName}
                    </span>
                </div>
                <div className={`border rounded-b-lg p-3 overflow-x-auto ${isError ? 'border-error/30 bg-error/5' : 'border-success/30 bg-bg-secondary'
                    }`}>
                    <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap break-words m-0">
                        {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                    </pre>
                </div>
            </div>
        );
    }

    // Render legacy tool result
    if (isTool) {
        return (
            <div className="flex flex-col max-w-[90%] me-auto mb-4 animate-fade-in">
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
        <div className={`flex gap-4 max-w-[85%] mb-4 animate-fade-in ${isUser ? 'ms-auto flex-row-reverse' : 'me-auto'}`}>
            {isAssistant && (
                <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center shrink-0">
                    <span className="text-lg">✨</span>
                </div>
            )}
            <div className={`px-6 py-4 rounded-2xl ${isUser
                ? 'bg-primary text-text-inverse rounded-br-sm rtl:rounded-bl-sm rtl:rounded-br-2xl'
                : 'bg-bg-primary border border-border rounded-bl-sm shadow-sm rtl:rounded-br-sm rtl:rounded-bl-2xl'
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
                    isUser ? (
                        <p className="text-base leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
                    ) : (
                        <div className="prose prose-sm max-w-none text-text-primary leading-relaxed text-start">
                            <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                                {message.content}
                            </Markdown>
                        </div>
                    )
                )}
                {message.isError && (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-error/15 text-error">Error</span>
                )}
            </div>
        </div>
    );
}


