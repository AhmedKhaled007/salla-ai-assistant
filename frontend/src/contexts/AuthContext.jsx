import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getAuthUrl, exchangeCode, checkAuthStatus, logout as apiLogout } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [merchantInfo, setMerchantInfo] = useState(null);
    const [authSessionId, setAuthSessionId] = useState(null);  // OAuth session ID for API calls
    const [error, setError] = useState(null);

    // Check authentication status on mount
    useEffect(() => {
        const checkAuth = async () => {
            try {
                // First check localStorage for cached auth state
                const cachedAuth = localStorage.getItem('salla_auth');
                let currentSessionId = null;

                if (cachedAuth) {
                    const parsed = JSON.parse(cachedAuth);
                    setIsAuthenticated(true);
                    setMerchantInfo(parsed.merchantInfo);
                    setAuthSessionId(parsed.authSessionId);
                    currentSessionId = parsed.authSessionId;
                }

                // Then verify with backend
                // If we have a cached session ID, check that specific session
                if (currentSessionId) {
                    const status = await checkAuthStatus(currentSessionId);
                    if (status.authenticated) {
                        setIsAuthenticated(true);
                        setMerchantInfo(status.merchant_info);
                        // Refresh storage with latest info
                        localStorage.setItem('salla_auth', JSON.stringify({
                            merchantInfo: status.merchant_info,
                            authSessionId: currentSessionId
                        }));
                    } else {
                        // Backend says not authenticated (expired/invalid), clear local state
                        console.log('Session expired or invalid according to backend');
                        setIsAuthenticated(false);
                        setMerchantInfo(null);
                        setAuthSessionId(null);
                        localStorage.removeItem('salla_auth');
                    }
                }
            } catch (err) {
                // If backend is unreachable, keep cached state if we have it
                console.error('Auth check failed:', err);
                if (err.message && err.message.includes('Failed to fetch')) {
                    // Network error, maybe keep offline state?
                    // For now, doing nothing satisfies "keep cached state"
                }
            } finally {
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    // Initiate OAuth login flow
    const login = useCallback(async () => {
        try {
            setError(null);
            const { url } = await getAuthUrl();
            // Redirect to Salla OAuth
            window.location.href = url;
        } catch (err) {
            setError('Failed to initiate login. Please try again.');
            console.error('Login failed:', err);
        }
    }, []);

    // Handle OAuth callback
    const handleCallback = useCallback(async (code, state) => {
        try {
            setIsLoading(true);
            setError(null);
            const result = await exchangeCode(code, state);

            if (result.status === "success") {
                setIsAuthenticated(true);
                setMerchantInfo(result.merchant);
                setAuthSessionId(result.auth_session_id);  // Store auth session ID
                localStorage.setItem('salla_auth', JSON.stringify({
                    merchantInfo: result.merchant,
                    authSessionId: result.auth_session_id,
                }));
                return true;
            } else {
                setError(result.error || 'Authentication failed');
                return false;
            }
        } catch (err) {
            setError('Failed to complete authentication. Please try again.');
            console.error('Callback failed:', err);
            return false;
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Logout
    const logout = useCallback(async () => {
        try {
            if (authSessionId) {
                await apiLogout(authSessionId);
            }
        } catch (err) {
            console.error('Logout API call failed:', err);
        } finally {
            setIsAuthenticated(false);
            setMerchantInfo(null);
            setAuthSessionId(null);
            localStorage.removeItem('salla_auth');
        }
    }, [authSessionId]);

    const value = {
        isAuthenticated,
        isLoading,
        merchantInfo,
        authSessionId,
        error,
        login,
        logout,
        handleCallback,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
