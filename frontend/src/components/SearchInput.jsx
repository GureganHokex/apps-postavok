/**
 * Компонент поиска с автодополнением
 */

import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './SearchInput.css';

function SearchInput({ 
  placeholder = 'Поиск...', 
  onSearch, 
  suggestions = [],
  debounceDelay = 300 
}) {
  const [value, setValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const filteredSuggestions = useMemo(() => {
    if (!value || value.length < 2) return [];
    const lowerValue = value.toLowerCase();
    return suggestions
      .filter(suggestion => 
        typeof suggestion === 'string' 
          ? suggestion.toLowerCase().includes(lowerValue)
          : suggestion.label?.toLowerCase().includes(lowerValue)
      )
      .slice(0, 5);
  }, [value, suggestions]);

  const handleChange = useCallback((e) => {
    const newValue = e.target.value;
    setValue(newValue);
    setFocusedIndex(-1);
    
    if (onSearch) {
      const timeoutId = setTimeout(() => {
        onSearch(newValue);
      }, debounceDelay);
      return () => clearTimeout(timeoutId);
    }
  }, [onSearch, debounceDelay]);

  const handleSelect = useCallback((suggestion) => {
    const selectedValue = typeof suggestion === 'string' ? suggestion : suggestion.value;
    setValue(selectedValue);
    setShowSuggestions(false);
    if (onSearch) {
      onSearch(selectedValue);
    }
  }, [onSearch]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex(prev => 
        prev < filteredSuggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex(prev => prev > 0 ? prev - 1 : -1);
    } else if (e.key === 'Enter' && focusedIndex >= 0) {
      e.preventDefault();
      handleSelect(filteredSuggestions[focusedIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }, [filteredSuggestions, focusedIndex, handleSelect]);

  return (
    <div className="search-input-wrapper">
      <div className="search-input-container">
        <span className="search-icon">🔍</span>
        <input
          type="text"
          className="search-input"
          placeholder={placeholder}
          value={value}
          onChange={handleChange}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          onKeyDown={handleKeyDown}
        />
        {value && (
          <button
            className="search-clear"
            onClick={() => {
              setValue('');
              if (onSearch) onSearch('');
            }}
            aria-label="Очистить поиск"
          >
            ✕
          </button>
        )}
      </div>
      
      <AnimatePresence>
        {showSuggestions && filteredSuggestions.length > 0 && (
          <motion.ul
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="search-suggestions"
          >
            {filteredSuggestions.map((suggestion, index) => {
              const displayValue = typeof suggestion === 'string' 
                ? suggestion 
                : suggestion.label;
              
              return (
                <motion.li
                  key={index}
                  className={`suggestion-item ${index === focusedIndex ? 'focused' : ''}`}
                  onClick={() => handleSelect(suggestion)}
                  whileHover={{ backgroundColor: 'var(--bg-tertiary)' }}
                >
                  {displayValue}
                </motion.li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

export default SearchInput;

