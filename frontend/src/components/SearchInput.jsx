/**
 * Компонент поля поиска с автодополнением
 */

import React, { useState, useRef, useEffect } from 'react';
import './SearchInput.css';

export function SearchInput({ value, onChange, placeholder = 'Поиск...', suggestions = [] }) {
  const [isFocused, setIsFocused] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef(null);
  const suggestionsRef = useRef(null);

  const filteredSuggestions = suggestions.filter(suggestion =>
    suggestion.toLowerCase().includes(value.toLowerCase())
  ).slice(0, 5);

  const handleInputChange = (e) => {
    onChange(e.target.value);
    setHighlightedIndex(-1);
  };

  const handleSuggestionClick = (suggestion) => {
    onChange(suggestion);
    setIsFocused(false);
    inputRef.current?.blur();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(prev =>
        prev < filteredSuggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev > 0 ? prev - 1 : -1));
    } else if (e.key === 'Enter' && highlightedIndex >= 0) {
      e.preventDefault();
      handleSuggestionClick(filteredSuggestions[highlightedIndex]);
    } else if (e.key === 'Escape') {
      setIsFocused(false);
      inputRef.current?.blur();
    }
  };

  useEffect(() => {
    if (highlightedIndex >= 0 && suggestionsRef.current) {
      const highlightedElement = suggestionsRef.current.children[highlightedIndex];
      if (highlightedElement) {
        highlightedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex]);

  return (
    <div className="search-input-wrapper">
      <input
        ref={inputRef}
        type="text"
        className="search-input"
        value={value}
        onChange={handleInputChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setTimeout(() => setIsFocused(false), 200)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
      />
      {isFocused && filteredSuggestions.length > 0 && (
        <ul ref={suggestionsRef} className="search-suggestions">
          {filteredSuggestions.map((suggestion, index) => (
            <li
              key={index}
              className={index === highlightedIndex ? 'highlighted' : ''}
              onClick={() => handleSuggestionClick(suggestion)}
              onMouseEnter={() => setHighlightedIndex(index)}
            >
              {suggestion}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
