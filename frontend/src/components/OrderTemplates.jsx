/**
 * Компонент для работы с шаблонами заказов
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { useLocalStorage } from '../hooks/useLocalStorage';
import './OrderTemplates.css';

function OrderTemplates({ onApplyTemplate, currentItems, currentQuantities }) {
  const [templates, setTemplates] = useLocalStorage('order_templates', []);
  const [showModal, setShowModal] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [editingTemplate, setEditingTemplate] = useState(null);

  const handleSaveTemplate = () => {
    if (!templateName.trim()) {
      toast.error('Введите название шаблона');
      return;
    }

    if (!currentItems || currentItems.length === 0) {
      toast.error('Нет позиций для сохранения в шаблон');
      return;
    }

    const template = {
      id: Date.now(),
      name: templateName,
      items: currentItems.map(item => ({
        item_id: item.id,
        quantity: currentQuantities[item.id] || 0,
        brewery: item.brewery,
        beer_name: item.beer_name,
        price: item.price,
        style: item.style,
        format_type: item.format_type,
      })),
      created_at: new Date().toISOString(),
    };

    setTemplates(prev => [...prev, template]);
    setTemplateName('');
    setShowModal(false);
    toast.success('Шаблон сохранен');
  };

  const handleDeleteTemplate = (templateId) => {
    if (window.confirm('Удалить этот шаблон?')) {
      setTemplates(prev => prev.filter(t => t.id !== templateId));
      toast.success('Шаблон удален');
    }
  };

  const handleApplyTemplate = (template) => {
    if (onApplyTemplate) {
      onApplyTemplate(template);
      toast.success(`Шаблон "${template.name}" применен`);
    }
  };

  return (
    <div className="OrderTemplates">
      <div className="templates-header">
        <h3>Шаблоны заказов</h3>
        {currentItems && currentItems.length > 0 && (
          <button
            className="button button-primary"
            onClick={() => setShowModal(true)}
          >
            + Создать шаблон
          </button>
        )}
      </div>

      {templates.length === 0 ? (
        <div className="empty-templates">
          <p>Нет сохраненных шаблонов</p>
          <p className="hint">Создайте шаблон из текущего заказа для быстрого повторного использования</p>
        </div>
      ) : (
        <div className="templates-list">
          {templates.map((template) => (
            <motion.div
              key={template.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="template-card"
            >
              <div className="template-info">
                <h4>{template.name}</h4>
                <p className="template-meta">
                  Позиций: {template.items.length} | 
                  Создан: {new Date(template.created_at).toLocaleDateString('ru-RU')}
                </p>
              </div>
              <div className="template-actions">
                <button
                  className="button button-success"
                  onClick={() => handleApplyTemplate(template)}
                >
                  Применить
                </button>
                <button
                  className="button button-danger"
                  onClick={() => handleDeleteTemplate(template.id)}
                >
                  Удалить
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {showModal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="template-modal"
          onClick={() => setShowModal(false)}
        >
          <motion.div
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            className="template-modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Создать шаблон</h3>
            <input
              type="text"
              placeholder="Название шаблона"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="input"
              autoFocus
            />
            <div className="modal-actions">
              <button
                className="button button-primary"
                onClick={handleSaveTemplate}
                disabled={!templateName.trim()}
              >
                Сохранить
              </button>
              <button
                className="button button-secondary"
                onClick={() => {
                  setShowModal(false);
                  setTemplateName('');
                }}
              >
                Отмена
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

export default OrderTemplates;

