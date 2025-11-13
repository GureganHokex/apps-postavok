/**
 * Главный компонент приложения.
 */

import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import ParsedTable from './components/ParsedTable';
import MetadataTab from './components/MetadataTab';
import OrderForm from './components/OrderForm';
import './App.css';

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

  const handleItemSelect = (itemId, isSelected) => {
    if (isSelected) {
      setSelectedItems([...selectedItems, itemId]);
    } else {
      setSelectedItems(selectedItems.filter(id => id !== itemId));
    }
  };

  const handleSelectAll = (allItemIds) => {
    setSelectedItems(allItemIds);
  };

  const handleDeselectAll = () => {
    setSelectedItems([]);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Пивной импортер</h1>
        <p>Парсинг прайсов для баров</p>
      </header>

      <nav className="App-nav">
        <button
          className={activeTab === 'upload' ? 'active' : ''}
          onClick={() => setActiveTab('upload')}
        >
          Загрузка файлов
        </button>
        {currentFile && (
          <>
            <button
              className={activeTab === 'items' ? 'active' : ''}
              onClick={() => setActiveTab('items')}
            >
              Позиции ({items.length})
            </button>
            <button
              className={activeTab === 'metadata' ? 'active' : ''}
              onClick={() => setActiveTab('metadata')}
            >
              Метаданные
            </button>
            <button
              className={activeTab === 'order' ? 'active' : ''}
              onClick={() => setActiveTab('order')}
            >
              Формирование заказа
            </button>
          </>
        )}
      </nav>

      <main className="App-main">
        {activeTab === 'upload' && (
          <FileUpload
            onFileUploaded={handleFileUploaded}
            onParseComplete={handleParseComplete}
          />
        )}

        {activeTab === 'items' && currentFile && (
          <div className="items-full-width">
            <ParsedTable
              fileId={currentFile.id}
              items={items}
              onItemsUpdate={setItems}
              onItemSelect={handleItemSelect}
              selectedItems={selectedItems}
              onSelectAll={handleSelectAll}
              onDeselectAll={handleDeselectAll}
            />
          </div>
        )}

        {activeTab === 'metadata' && currentFile && metadata && (
          <MetadataTab metadata={metadata} />
        )}

        {activeTab === 'order' && currentFile && (
          <OrderForm
            fileId={currentFile.id}
            selectedItems={selectedItems}
            items={items}
          />
        )}
      </main>
    </div>
  );
}

export default App;

