import { useState } from 'react';

/**
 * Chat input component with send button
 */
export function ChatInput({ onSend, isLoading, placeholder = "Ask about your Salla store..." }) {
    const [input, setInput] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (input.trim() && !isLoading) {
            onSend(input.trim());
            setInput('');
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="p-6 bg-gradient-to-t from-bg-primary to-transparent flex flex-col items-center">
            <div className="flex items-end gap-2 p-2 rounded-2xl bg-bg-primary border border-border shadow-sm transition-all max-w-[800px] w-full focus-within:border-primary focus-within:shadow-md">
                <textarea
                    className="flex-1 bg-transparent border-none text-text-primary text-base px-4 py-2 resize-none max-h-[120px] min-h-[44px] outline-none placeholder:text-text-muted disabled:opacity-60 disabled:cursor-not-allowed"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    rows={1}
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    className="w-11 h-11 rounded-lg bg-primary border-none text-text-inverse cursor-pointer flex items-center justify-center shrink-0 transition-all hover:bg-primary-dark hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                    disabled={!input.trim() || isLoading}
                >
                    {isLoading ? (
                        <span className="text-xl animate-spin">⟳</span>
                    ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
                        </svg>
                    )}
                </button>
            </div>
            <p className="text-center text-xs text-text-muted mt-2">Press Enter to send, Shift+Enter for new line</p>
        </form>
    );
}
