/**
 * Модальное окно для выбора типа поставщика и профиля маппинга
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { getSuppliers } from '../api';
import './SupplierTypeModal.css';

function SupplierTypeModal({ isOpen, fileName, onConfirm, onCancel }) {
  const [supplierType, setSupplierType] = useState('distributor'); // 'distributor' или 'brewery'
  const [breweryName, setBreweryName] = useState('');
  const [autoDetectedBrewery, setAutoDetectedBrewery] = useState('');
  const [supplierId, setSupplierId] = useState('');

  const { data: suppliersData } = useQuery({
    queryKey: ['suppliers'],
    queryFn: getSuppliers,
    enabled: isOpen,
  });
  const suppliers = Array.isArray(suppliersData?.results) ? suppliersData.results : (Array.isArray(suppliersData) ? suppliersData : []);

  // Автоопределение пивоварни из имени файла
  useEffect(() => {
    if (fileName && supplierType === 'brewery') {
      // Извлекаем возможные названия пивоварен из имени файла
      const commonBreweries = ['Dieta', 'Paradox', 'Red Rocket', 'Zero Point', 'Yaki-Da', 'Red Rocket Brewery'];
      const fileNameLower = fileName.toLowerCase();
      
      for (const brewery of commonBreweries) {
        if (fileNameLower.includes(brewery.toLowerCase())) {
          setAutoDetectedBrewery(brewery);
          setBreweryName(brewery);
          break;
        }
      }
      
      // Если не найдено известное название, пробуем извлечь из имени файла
      if (!autoDetectedBrewery) {
        // Убираем расширение файла
        const nameWithoutExt = fileName.replace(/\.[^/.]+$/, '');
        // Пробуем найти слова с заглавной буквы
        const words = nameWithoutExt.split(/[\s_-]+/);
        const possibleBrewery = words.find(word => 
          word.length > 2 && 
          word[0] === word[0].toUpperCase() && 
          /^[A-Za-zА-Яа-я]+$/.test(word)
        );
        if (possibleBrewery) {
          setAutoDetectedBrewery(possibleBrewery);
          setBreweryName(possibleBrewery);
        }
      }
    } else {
      setAutoDetectedBrewery('');
      setBreweryName('');
    }
  }, [fileName, supplierType]);

  // Сброс при открытии модального окна
  useEffect(() => {
    if (isOpen) {
      setSupplierType('distributor');
      setBreweryName('');
      setAutoDetectedBrewery('');
      setSupplierId('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (supplierType === 'brewery' && !breweryName.trim()) {
      return; // Не позволяем продолжить без названия пивоварни
    }
    const payload = {
      supplier_type: supplierType,
      brewery_name: supplierType === 'brewery' ? breweryName.trim() : null,
    };
    if (supplierId) payload.supplier_id = parseInt(supplierId, 10);
    onConfirm(payload);
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="modal-overlay"
        onClick={onCancel}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="modal-content"
          onClick={(e) => e.stopPropagation()}
        >
          <h2>Тип поставщика</h2>
          <p className="modal-description">
            Выберите тип поставщика для файла: <strong>{fileName}</strong>
          </p>

          <div className="supplier-type-options">
            <label className={`option-card ${supplierType === 'distributor' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="supplierType"
                value="distributor"
                checked={supplierType === 'distributor'}
                onChange={(e) => setSupplierType(e.target.value)}
              />
              <div className="option-content">
                <div className="option-icon">🏢</div>
                <div className="option-text">
                  <div className="option-title">Дистрибьютор</div>
                  <div className="option-description">
                    Файл содержит товары от разных пивоварен
                  </div>
                </div>
              </div>
            </label>

            <label className={`option-card ${supplierType === 'brewery' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="supplierType"
                value="brewery"
                checked={supplierType === 'brewery'}
                onChange={(e) => setSupplierType(e.target.value)}
              />
              <div className="option-content">
                <div className="option-icon">🍺</div>
                <div className="option-text">
                  <div className="option-title">Частный поставщик</div>
                  <div className="option-description">
                    Файл содержит товары от одной пивоварни
                  </div>
                </div>
              </div>
            </label>
          </div>

          {suppliers.length > 0 && (
            <div className="supplier-profile-section">
              <label className="input-label">Профиль поставщика (маппинг колонок)</label>
              <select
                className="input select"
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value)}
              >
                <option value="">Не использовать</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              <div className="input-hint">Выберите, если настраивали ключевые слова в «Настройки поставщиков»</div>
            </div>
          )}

          {supplierType === 'brewery' && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="brewery-input-section"
            >
              <label className="input-label">
                Название пивоварни
                {autoDetectedBrewery && (
                  <span className="auto-detected">
                    (автоопределено: {autoDetectedBrewery})
                  </span>
                )}
              </label>
              <input
                type="text"
                className="input"
                value={breweryName}
                onChange={(e) => setBreweryName(e.target.value)}
                placeholder="Например: Dieta, Paradox..."
                autoFocus
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && breweryName.trim()) {
                    handleConfirm();
                  }
                }}
              />
              {!breweryName && (
                <div className="input-hint">
                  Введите название пивоварни или оставьте пустым для автоопределения
                </div>
              )}
            </motion.div>
          )}

          <div className="modal-actions">
            <button
              className="button button-secondary"
              onClick={onCancel}
            >
              Отмена
            </button>
            <button
              className="button button-primary"
              onClick={handleConfirm}
              disabled={supplierType === 'brewery' && !breweryName.trim()}
            >
              Продолжить
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export default SupplierTypeModal;

