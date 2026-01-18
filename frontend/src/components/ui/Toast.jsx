import { useState, useCallback, createContext, useContext } from 'react';

// Toast context
const ToastContext = createContext(null);

/**
 * Toast component
 */
function Toast({ message, type = 'info', onClose }) {
    const bgColor = {
        success: 'bg-success',
        error: 'bg-error',
        warning: 'bg-warning',
        info: 'bg-primary',
    }[type] || 'bg-primary';

    const icon = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ',
    }[type] || 'ℹ';

    return (
        <div className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg ${bgColor} text-white animate-fade-in`}>
            <span className="text-lg">{icon}</span>
            <span className="flex-1 text-sm">{message}</span>
            <button
                onClick={onClose}
                className="text-white/80 hover:text-white ms-2"
            >
                ✕
            </button>
        </div>
    );
}

/**
 * Toast container that renders all active toasts
 */
function ToastContainer({ toasts, removeToast }) {
    if (toasts.length === 0) return null;

    return (
        <div className="fixed bottom-6 end-6 z-50 flex flex-col gap-2">
            {toasts.map((toast) => (
                <Toast
                    key={toast.id}
                    message={toast.message}
                    type={toast.type}
                    onClose={() => removeToast(toast.id)}
                />
            ))}
        </div>
    );
}

/**
 * Toast provider component
 */
export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'info', duration = 5000) => {
        const id = Date.now();
        setToasts(prev => [...prev, { id, message, type }]);

        if (duration > 0) {
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, duration);
        }

        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const showSuccess = useCallback((message) => addToast(message, 'success'), [addToast]);
    const showError = useCallback((message) => addToast(message, 'error'), [addToast]);
    const showWarning = useCallback((message) => addToast(message, 'warning'), [addToast]);
    const showInfo = useCallback((message) => addToast(message, 'info'), [addToast]);

    return (
        <ToastContext.Provider value={{ addToast, removeToast, showSuccess, showError, showWarning, showInfo }}>
            {children}
            <ToastContainer toasts={toasts} removeToast={removeToast} />
        </ToastContext.Provider>
    );
}

/**
 * Hook to use toast notifications
 */
export function useToast() {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}
