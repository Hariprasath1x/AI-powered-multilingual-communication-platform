import React, { createContext, useContext, useState, useEffect } from 'react';
import { AUTH_TOKEN_KEY, AUTH_USER_KEY } from '../services/api';
import { getCurrentUser } from '../services/authService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem(AUTH_USER_KEY);
    if (!saved) return null;
    try {
      return JSON.parse(saved);
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(true);

  // Sync session with live backend on initial mount
  useEffect(() => {
    let isMounted = true;

    const verifySession = async () => {
      const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
      if (storedToken) {
        const result = await getCurrentUser();
        if (isMounted) {
          if (result.success && result.data.is_active) {
            setUser(result.data);
            localStorage.setItem(AUTH_USER_KEY, JSON.stringify(result.data));
          } else {
            // Token expired, malformed, or user deactivated
            logout();
          }
        }
      }
      if (isMounted) {
        setIsLoading(false);
      }
    };

    verifySession();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = (authToken, userData) => {
    setToken(authToken);
    setUser(userData);
    localStorage.setItem(AUTH_TOKEN_KEY, authToken);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(userData));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  };

  const value = {
    token,
    user,
    isLoading,
    login,
    logout,
    isAuthenticated: Boolean(token && user),
    isAdmin: user?.role_name === 'Admin',
    isCampaignManager: user?.role_name === 'Campaign Manager',
    isCommunicationTeam: user?.role_name === 'Communication Team',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

