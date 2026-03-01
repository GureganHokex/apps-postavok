/**
 * Главный компонент приложения.
 * Режим страницы: data-page="admin" (или ?page=admin) — админ-панель; иначе — основное приложение (бармен/пользователь).
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Routes, Route, NavLink, Navigate, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuth } from './contexts/AuthContext';
import LoginForm from './components/LoginForm';
import AdminPanel from './components/AdminPanel';
import FileUpload from './components/FileUpload';
import ParsedTable from './components/ParsedTable';
import MetadataTab from './components/MetadataTab';
import OrderForm from './components/OrderForm';
import OrdersHistory from './components/OrdersHistory';
import ThemeToggle from './components/ThemeToggle';
import StatisticsDashboard from './components/StatisticsDashboard';
import TapsPage from './components/TapsPage';
import SupplierSettings from './components/SupplierSettings';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

function getPageType() {
  const root = document.getElementById('root');
  const fromRoot = root?.getAttribute('data-page');
  if (fromRoot) return fromRoot;
  const params = new URLSearchParams(window.location.search);
  return params.get('page') || '';
}

function AdminGate() {
  const { user, loading, login, logout, isAdmin } = useAuth();
  const [loginError, setLoginError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (username, password) => {
    setLoginError('');
    setSubmitting(true);
    try {
      const data = await login(username, password);
      if (!data?.is_admin) {
        await logout();
        setLoginError('Доступ только для администратора.');
      }
    } catch (err) {
      const msg = err.response?.data?.error ?? err.response?.data?.detail ?? (err.response ? `${err.response.status}: ${err.response.statusText}` : err.message);
      setLoginError(msg || 'Ошибка входа');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="app-gate-loading">Загрузка…</div>;
  if (!user) {
    return (
      <div className="app-gate">
        <LoginForm
          title="Админ-панель"
          onSubmit={handleLogin}
          error={loginError}
          loading={submitting}
        />
      </div>
    );
  }
  if (!isAdmin) {
    return (
      <div className="app-gate">
        <div className="app-gate-message">
          <p>Доступ только для администратора.</p>
          <button type="button" className="btn-logout" onClick={logout}>
            Выйти
          </button>
        </div>
      </div>
    );
  }
  return <LoggedInLayout fullAccess role={user?.user?.role} />;
}

function MainGate() {
  const { user, loading, login } = useAuth();
  const [loginError, setLoginError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleLogin = async (username, password) => {
    setLoginError('');
    setSubmitting(true);
    try {
      await login(username, password);
    } catch (err) {
      const msg = err.response?.data?.error ?? err.response?.data?.detail ?? (err.response ? `${err.response.status}: ${err.response.statusText}` : err.message);
      setLoginError(msg || 'Ошибка входа');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="app-gate-loading">Загрузка…</div>;
  if (!user) {
    return (
      <div className="app-gate">
        <LoginForm
          title="Вход"
          onSubmit={handleLogin}
          error={loginError}
          loading={submitting}
        />
      </div>
    );
  }
  return <LoggedInLayout fullAccess={false} role={user?.user?.role} />;
}

function LayoutHeader({ isAdmin }) {
  const { logout } = useAuth();
  return (
    <motion.header
      className="App-header"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="header-content">
        <div>
          <NavLink to="/" className="header-title-link">
            <motion.h1 initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2, duration: 0.5 }}>
              Пивной импортер
            </motion.h1>
          </NavLink>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 0.9 }} transition={{ delay: 0.4, duration: 0.5 }}>
            Парсинг прайсов для баров
          </motion.p>
        </div>
        <div className="header-actions">
          {isAdmin && (
            <NavLink to="/admin" className={({ isActive }) => 'btn-admin-header' + (isActive ? ' active' : '')} title="Админ-панель">
              Админ-панель
            </NavLink>
          )}
          <button type="button" className="btn-logout-header" onClick={logout} title="Выйти">
            Выйти
          </button>
          <ThemeToggle />
        </div>
      </div>
    </motion.header>
  );
}

function Layout({ isAdmin }) {
  return (
    <>
      <LayoutHeader isAdmin={isAdmin} />
      <Outlet />
    </>
  );
}

function LoggedInLayout({ fullAccess, role }) {
  const isAdmin = fullAccess || role === 'admin';
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            boxShadow: 'var(--shadow-lg)',
            borderRadius: 'var(--radius-md)',
          },
          success: { iconTheme: { primary: 'var(--success-color)', secondary: 'white' } },
          error: { iconTheme: { primary: 'var(--danger-color)', secondary: 'white' } },
        }}
      />
      <Routes>
        <Route element={<Layout isAdmin={isAdmin} />}>
          <Route path="/admin" element={isAdmin ? <AdminPanel /> : <Navigate to="/" replace />} />
          <Route path="/*" element={<AppContent fullAccess={fullAccess} role={role} />} />
        </Route>
      </Routes>
    </QueryClientProvider>
  );
}

// Настройка React Query с улучшенным кэшированием
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      retry: 2,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      staleTime: 10 * 60 * 1000, // 10 минут
      cacheTime: 30 * 60 * 1000, // 30 минут
      keepPreviousData: true, // Сохраняем предыдущие данные при загрузке новых
    },
    mutations: {
      retry: 1,
      retryDelay: 1000,
    },
  },
});

function AppContent({ fullAccess = false, role = 'user' }) {
  const [currentFile, setCurrentFile] = useState(null);
  const [items, setItems] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const isAdmin = fullAccess || role === 'admin';
  const defaultTab = isAdmin ? 'upload' : 'taps';
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [selectedItems, setSelectedItems] = useState([]);

  const allowedTabs = useMemo(() => {
    if (fullAccess || role === 'admin') return new Set(['upload', 'items', 'metadata', 'order', 'statistics', 'orders-history', 'taps', 'suppliers']);
    if (role === 'bartender') return new Set(['taps', 'orders-history']);
    return new Set(['taps']);
  }, [fullAccess, role]);

  useEffect(() => {
    if (!allowedTabs.has(activeTab)) setActiveTab(isAdmin ? 'upload' : 'taps');
  }, [allowedTabs, isAdmin]);

  const setActiveTabSafe = useCallback((tab) => {
    setActiveTab((prev) => (allowedTabs.has(tab) ? tab : prev));
  }, [allowedTabs]);

  const handleFileUploaded = (fileData) => {
    setCurrentFile(fileData);
    setActiveTab('parse');
  };

  const handleParseComplete = (parseResult, itemsData, metadataData) => {
    setItems(itemsData);
    setMetadata(metadataData);
    setActiveTab('items');
  };

  const handleItemSelect = useCallback((itemId, isSelected) => {
    setSelectedItems(prev => {
      if (isSelected) {
        return [...prev, itemId];
      } else {
        return prev.filter(id => id !== itemId);
      }
    });
  }, []);

  const handleSelectAll = useCallback((allItemIds) => {
    setSelectedItems(allItemIds);
  }, []);

  const handleDeselectAll = useCallback(() => {
    setSelectedItems([]);
  }, []);

  const selectedCount = useMemo(() => selectedItems.length, [selectedItems]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '5') {
        e.preventDefault();
        const tabIndex = parseInt(e.key) - 1;
        const tabs = ['upload', 'items', 'metadata', 'order', 'orders-history'];
        if (tabs[tabIndex] && (tabIndex === 0 || currentFile) && allowedTabs.has(tabs[tabIndex])) {
          setActiveTab(tabs[tabIndex]);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentFile, allowedTabs]);

  return (
    <ErrorBoundary>
      <div className="App">
        <nav className="App-nav">
          {allowedTabs.has('upload') && (
            <button
              className={activeTab === 'upload' ? 'active' : ''}
              onClick={() => setActiveTabSafe('upload')}
              aria-label="Загрузка файлов"
            >
              📤 Загрузка файлов
            </button>
          )}
          {allowedTabs.has('items') && currentFile && (
            <>
              <button
                className={activeTab === 'items' ? 'active' : ''}
                onClick={() => setActiveTabSafe('items')}
                aria-label="Позиции"
              >
                📋 Позиции {items.length > 0 && `(${items.length})`}
              </button>
              <button
                className={activeTab === 'metadata' ? 'active' : ''}
                onClick={() => setActiveTabSafe('metadata')}
                aria-label="Метаданные"
              >
                ℹ️ Метаданные
              </button>
              <button
                className={activeTab === 'order' ? 'active' : ''}
                onClick={() => setActiveTabSafe('order')}
                aria-label="Формирование заказа"
              >
                🛒 Заказ {selectedCount > 0 && `(${selectedCount})`}
              </button>
              <button
                className={activeTab === 'statistics' ? 'active' : ''}
                onClick={() => setActiveTabSafe('statistics')}
                aria-label="Статистика"
              >
                📊 Статистика
              </button>
            </>
          )}
          {allowedTabs.has('orders-history') && (
            <button
              className={activeTab === 'orders-history' ? 'active' : ''}
              onClick={() => setActiveTabSafe('orders-history')}
              aria-label="История заказов"
            >
              📜 История заказов
            </button>
          )}
          {allowedTabs.has('taps') && (
            <button
              className={activeTab === 'taps' ? 'active' : ''}
              onClick={() => setActiveTabSafe('taps')}
              aria-label="Краны"
            >
              🍺 Краны
            </button>
          )}
          {allowedTabs.has('suppliers') && (
            <button
              className={activeTab === 'suppliers' ? 'active' : ''}
              onClick={() => setActiveTabSafe('suppliers')}
              aria-label="Настройки поставщиков"
            >
              ⚙️ Настройки поставщиков
            </button>
          )}
        </nav>

      <main className="App-main">
        <AnimatePresence mode="wait">
          {(activeTab === 'upload' || activeTab === 'parse') && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <FileUpload
                onFileUploaded={handleFileUploaded}
                onParseComplete={handleParseComplete}
              />
            </motion.div>
          )}

          {activeTab === 'items' && currentFile && (
            <motion.div
              key="items"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
              className="items-full-width"
            >
              <ParsedTable
                fileId={currentFile.id}
                items={items}
                onItemsUpdate={setItems}
                onItemSelect={handleItemSelect}
                selectedItems={selectedItems}
                onSelectAll={handleSelectAll}
                onDeselectAll={handleDeselectAll}
              />
            </motion.div>
          )}

          {activeTab === 'metadata' && currentFile && metadata && (
            <motion.div
              key="metadata"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <MetadataTab metadata={metadata} />
            </motion.div>
          )}

          {activeTab === 'order' && currentFile && (
            <motion.div
              key="order"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <OrderForm
                fileId={currentFile.id}
                selectedItems={selectedItems}
                items={items}
              />
            </motion.div>
          )}

          {activeTab === 'orders-history' && (
            <motion.div
              key="orders-history"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <OrdersHistory />
            </motion.div>
          )}

          {activeTab === 'statistics' && currentFile && items.length > 0 && (
            <motion.div
              key="statistics"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <StatisticsDashboard items={items} />
            </motion.div>
          )}

          {activeTab === 'taps' && (
            <motion.div
              key="taps"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <TapsPage />
            </motion.div>
          )}

          {activeTab === 'suppliers' && (
            <motion.div
              key="suppliers"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <SupplierSettings />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
      </div>
    </ErrorBoundary>
  );
}

function App() {
  const isAdminPage = getPageType() === 'admin';
  return (
    <ErrorBoundary>
      {isAdminPage ? <AdminGate /> : <MainGate />}
    </ErrorBoundary>
  );
}

export default App;

