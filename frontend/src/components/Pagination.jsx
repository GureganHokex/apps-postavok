/**
 * Компонент пагинации
 */

import React from 'react';
import { motion } from 'framer-motion';
import './Pagination.css';

export function Pagination({ currentPage, totalPages, onPageChange, itemsPerPage, onItemsPerPageChange }) {
  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 7;
    
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 5; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 4; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        pages.push(1);
        pages.push('...');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i);
        }
        pages.push('...');
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="pagination">
      <div className="pagination-info">
        <span>Страница {currentPage} из {totalPages}</span>
        {onItemsPerPageChange && (
          <select
            value={itemsPerPage}
            onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
            className="items-per-page-select"
          >
            <option value={10}>10 на странице</option>
            <option value={25}>25 на странице</option>
            <option value={50}>50 на странице</option>
            <option value={100}>100 на странице</option>
          </select>
        )}
      </div>
      <div className="pagination-controls">
        <button
          onClick={handlePrevious}
          disabled={currentPage === 1}
          className="pagination-button"
          aria-label="Предыдущая страница"
        >
          ←
        </button>
        {getPageNumbers().map((page, index) => (
          <React.Fragment key={index}>
            {page === '...' ? (
              <span className="pagination-ellipsis">...</span>
            ) : (
              <motion.button
                onClick={() => onPageChange(page)}
                className={`pagination-button ${currentPage === page ? 'active' : ''}`}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                aria-label={`Страница ${page}`}
                aria-current={currentPage === page ? 'page' : undefined}
              >
                {page}
              </motion.button>
            )}
          </React.Fragment>
        ))}
        <button
          onClick={handleNext}
          disabled={currentPage === totalPages}
          className="pagination-button"
          aria-label="Следующая страница"
        >
          →
        </button>
      </div>
    </div>
  );
}

export default Pagination;

