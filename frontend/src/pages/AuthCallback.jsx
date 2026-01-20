import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function AuthCallback() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { handleCallback } = useAuth();
    const [status, setStatus] = useState('processing');
    const [errorMessage, setErrorMessage] = useState('');
    const processedRef = useRef(false);

    useEffect(() => {
        const processCallback = async () => {
            // Prevent duplicate calls (React StrictMode, dependency changes, etc.)
            if (processedRef.current) {
                return;
            }
            processedRef.current = true;

            const code = searchParams.get('code');
            const state = searchParams.get('state');
            const error = searchParams.get('error');
            const errorDescription = searchParams.get('error_description');

            // Handle OAuth error from Salla
            if (error) {
                setStatus('error');
                setErrorMessage(errorDescription || 'Authorization was denied');
                return;
            }

            // No code or state provided
            if (!code || !state) {
                setStatus('error');
                setErrorMessage(!code ? 'No authorization code received' : 'Missing security state parameter');
                return;
            }

            // Exchange code for tokens
            try {
                const success = await handleCallback(code, state);
                if (success) {
                    setStatus('success');
                    // Redirect to main app after short delay
                    setTimeout(() => {
                        navigate('/', { replace: true });
                    }, 1500);
                } else {
                    setStatus('error');
                    setErrorMessage('Failed to authenticate with Salla');
                }
            } catch (err) {
                setStatus('error');
                setErrorMessage(err.message || 'An unexpected error occurred');
            }
        };

        processCallback();
    }, [searchParams, handleCallback, navigate]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-accent via-bg-secondary to-accent-light p-4">
            <div className="bg-bg-primary rounded-2xl shadow-lg p-8 text-center max-w-md w-full">
                {status === 'processing' && (
                    <>
                        <div className="w-16 h-16 mx-auto mb-6 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
                        <h1 className="text-xl font-semibold text-text-primary mb-2">
                            Connecting to Salla...
                        </h1>
                        <p className="text-text-muted">
                            Please wait while we complete the authentication
                        </p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <div className="w-16 h-16 mx-auto mb-6 bg-success/10 rounded-full flex items-center justify-center">
                            <span className="text-4xl">✓</span>
                        </div>
                        <h1 className="text-xl font-semibold text-text-primary mb-2">
                            Connected Successfully!
                        </h1>
                        <p className="text-text-muted">
                            Redirecting to your dashboard...
                        </p>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div className="w-16 h-16 mx-auto mb-6 bg-error/10 rounded-full flex items-center justify-center">
                            <span className="text-4xl">✕</span>
                        </div>
                        <h1 className="text-xl font-semibold text-text-primary mb-2">
                            Connection Failed
                        </h1>
                        <p className="text-error mb-6">
                            {errorMessage}
                        </p>
                        <button
                            onClick={() => navigate('/login', { replace: true })}
                            className="px-6 py-3 bg-primary hover:bg-primary-dark text-white font-medium rounded-xl transition-colors"
                        >
                            Try Again
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}
