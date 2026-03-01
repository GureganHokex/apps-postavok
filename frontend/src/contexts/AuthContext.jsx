/**
 * Контекст авторизации: текущий пользователь, роль, вход/выход.
 */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { authMe, authLogin, authLogout } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const data = await authMe();
      setUser(data);
      return data;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener('api:unauthorized', onUnauthorized);
    return () => window.removeEventListener('api:unauthorized', onUnauthorized);
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await authLogin(username, password);
    setUser(data);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authLogout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = {
    user,
    loading,
    login,
    logout,
    refreshUser: loadUser,
    isAdmin: user?.is_admin === true,
    role: user?.user?.role || null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
