/**
 * Компонент переключения темы
 */

import React from 'react';
import { motion } from 'framer-motion';
import { useTheme } from '../hooks/useTheme';
import './ThemeToggle.css';

function ThemeToggle() {
  const [theme, toggleTheme] = useTheme();

  return (
    <motion.button
      className="theme-toggle"
      onClick={toggleTheme}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      aria-label={`Переключить на ${theme === 'light' ? 'темную' : 'светлую'} тему`}
    >
      {theme === 'light' ? 'Темная тема' : 'Светлая тема'}
    </motion.button>
  );
}

export default ThemeToggle;

