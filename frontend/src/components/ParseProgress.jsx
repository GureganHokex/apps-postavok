/**
 * Компонент прогресс-бара для парсинга файлов
 */

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './ParseProgress.css';

export function ParseProgress({ isVisible, progress, message }) {
  const [displayProgress, setDisplayProgress] = useState(0);

  useEffect(() => {
    if (isVisible && progress !== undefined) {
      // Плавная анимация прогресса
      const timer = setTimeout(() => {
        setDisplayProgress(progress);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [progress, isVisible]);

  if (!isVisible) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="parse-progress-overlay"
      >
        <div className="parse-progress-container">
          <div className="parse-progress-header">
            <h3>Парсинг файла</h3>
            <div className="parse-progress-percent">{Math.round(displayProgress)}%</div>
          </div>
          
          <div className="parse-progress-bar-wrapper">
            <div className="parse-progress-bar">
              <motion.div
                className="parse-progress-fill"
                initial={{ width: 0 }}
                animate={{ width: `${displayProgress}%` }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              />
            </div>
          </div>
          
          {message && (
            <div className="parse-progress-message">
              {message}
            </div>
          )}
          
          <div className="parse-progress-steps">
            <div className={`step ${displayProgress >= 20 ? 'completed' : displayProgress >= 10 ? 'active' : ''}`}>
              <span className="step-icon">{displayProgress >= 20 ? 'OK' : '1'}</span>
              <span className="step-label">Загрузка файла</span>
            </div>
            <div className={`step ${displayProgress >= 50 ? 'completed' : displayProgress >= 30 ? 'active' : ''}`}>
              <span className="step-icon">{displayProgress >= 50 ? 'OK' : '2'}</span>
              <span className="step-label">Чтение данных</span>
            </div>
            <div className={`step ${displayProgress >= 80 ? 'completed' : displayProgress >= 60 ? 'active' : ''}`}>
              <span className="step-icon">{displayProgress >= 80 ? 'OK' : '3'}</span>
              <span className="step-label">Обработка</span>
            </div>
            <div className={`step ${displayProgress >= 100 ? 'completed' : displayProgress >= 90 ? 'active' : ''}`}>
              <span className="step-icon">{displayProgress >= 100 ? 'OK' : '4'}</span>
              <span className="step-label">Завершение</span>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export default ParseProgress;

