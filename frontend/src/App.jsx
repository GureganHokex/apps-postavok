/**
 * Главный компонент приложения.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import FileUpload from './components/FileUpload';
import ParsedTable from './components/ParsedTable';
import MetadataTab from './components/MetadataTab';
import OrderForm from './components/OrderForm';
import OrdersHistory from './components/OrdersHistory';
import ThemeToggle from './components/ThemeToggle';
import StatisticsDashboard from './components/StatisticsDashboard';
import './App.css';

// Настройка React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 минут
    },
  },
});

function App() {
  const [currentFile, setCurrentFile] = useState(null);
  const [items, setItems] = useState([]);
  const [metadata, setMetadata] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const [selectedItems, setSelectedItems] = useState([]);

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

  // Клавиатурные сокращения для навигации
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl+1-5 для переключения вкладок
      if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '5') {
        e.preventDefault();
        const tabIndex = parseInt(e.key) - 1;
        const tabs = ['upload', 'items', 'metadata', 'order', 'orders-history'];
        if (tabs[tabIndex] && (tabIndex === 0 || currentFile)) {
          setActiveTab(tabs[tabIndex]);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentFile]);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="App">
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
            success: {
              iconTheme: {
                primary: 'var(--success-color)',
                secondary: 'white',
              },
            },
            error: {
              iconTheme: {
                primary: 'var(--danger-color)',
                secondary: 'white',
              },
            },
          }}
        />
        
      <motion.header
        className="App-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <motion.h1
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
        >
          Пивной импортер
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.9 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          Парсинг прайсов для баров
        </motion.p>
      </motion.header>

        <nav className="App-nav">
          <button
            className={activeTab === 'upload' ? 'active' : ''}
            onClick={() => setActiveTab('upload')}
            aria-label="Загрузка файлов"
          >
            📤 Загрузка файлов
          </button>
          {currentFile && (
            <>
              <button
                className={activeTab === 'items' ? 'active' : ''}
                onClick={() => setActiveTab('items')}
                aria-label="Позиции"
              >
                📋 Позиции {items.length > 0 && `(${items.length})`}
              </button>
              <button
                className={activeTab === 'metadata' ? 'active' : ''}
                onClick={() => setActiveTab('metadata')}
                aria-label="Метаданные"
              >
                ℹ️ Метаданные
              </button>
            <button
              className={activeTab === 'order' ? 'active' : ''}
              onClick={() => setActiveTab('order')}
              aria-label="Формирование заказа"
            >
              🛒 Заказ {selectedCount > 0 && `(${selectedCount})`}
            </button>
            <button
              className={activeTab === 'orders-history' ? 'active' : ''}
              onClick={() => setActiveTab('orders-history')}
              aria-label="История заказов"
            >
              📜 История заказов
            </button>
            <button
              className={activeTab === 'statistics' ? 'active' : ''}
              onClick={() => setActiveTab('statistics')}
              aria-label="Статистика"
            >
              📊 Статистика
            </button>
          </>
        )}
      </nav>

      <main className="App-main">
        <AnimatePresence mode="wait">
          {activeTab === 'upload' && (
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
        </AnimatePresence>
      </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;

