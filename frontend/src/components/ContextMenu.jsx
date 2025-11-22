/**
 * Компонент контекстного меню
 */

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './ContextMenu.css';

function ContextMenu({ x, y, items, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        onClose();
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  if (!items || items.length === 0) return null;

  return (
    <AnimatePresence>
      <motion.div
        ref={menuRef}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
        className="context-menu"
        style={{
          position: 'fixed',
          left: `${x}px`,
          top: `${y}px`,
        }}
      >
        {items.map((item, index) => (
          <motion.button
            key={index}
            className={`context-menu-item ${item.danger ? 'danger' : ''} ${item.disabled ? 'disabled' : ''}`}
            onClick={() => {
              if (!item.disabled && item.onClick) {
                item.onClick();
                onClose();
              }
            }}
            disabled={item.disabled}
            whileHover={!item.disabled ? { backgroundColor: 'var(--bg-tertiary)' } : {}}
          >
            {item.icon && <span className="menu-icon">{item.icon}</span>}
            <span>{item.label}</span>
            {item.shortcut && <span className="menu-shortcut">{item.shortcut}</span>}
          </motion.button>
        ))}
      </motion.div>
    </AnimatePresence>
  );
}

export default ContextMenu;

