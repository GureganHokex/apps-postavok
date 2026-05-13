/**
 * Нижний таб-бар для мобильного представления.
 *
 * Контракт: принимает массив описаний вкладок и id активной вкладки.
 * Сам не знает о бизнес-логике приложения — это просто визуальный shell.
 *
 * Видимость регулируется CSS: на ширинах > 768px скрыт.
 */

import React, { useMemo, useState, useCallback } from 'react';
import './BottomTabBar.css';

const VISIBLE_LIMIT = 4;

export default function BottomTabBar({ items, activeId, onSelect }) {
  const [moreOpen, setMoreOpen] = useState(false);

  const { primary, overflow } = useMemo(() => {
    const safeItems = Array.isArray(items) ? items.filter(Boolean) : [];
    if (safeItems.length <= VISIBLE_LIMIT) {
      return { primary: safeItems, overflow: [] };
    }
    const primaryItems = safeItems.slice(0, VISIBLE_LIMIT - 1);
    const overflowItems = safeItems.slice(VISIBLE_LIMIT - 1);
    const activeInOverflow = overflowItems.some((item) => item.id === activeId);
    if (activeInOverflow) {
      const reordered = [...primaryItems];
      const swapIndex = reordered.length - 1;
      const movedToPrimary = overflowItems.find((item) => item.id === activeId);
      const movedToOverflow = reordered[swapIndex];
      reordered[swapIndex] = movedToPrimary;
      const newOverflow = overflowItems
        .filter((item) => item.id !== activeId)
        .concat(movedToOverflow);
      return { primary: reordered, overflow: newOverflow };
    }
    return { primary: primaryItems, overflow: overflowItems };
  }, [items, activeId]);

  const handleSelect = useCallback(
    (id) => {
      setMoreOpen(false);
      onSelect?.(id);
    },
    [onSelect],
  );

  if (!items || items.length === 0) return null;

  return (
    <>
      {moreOpen && (
        <div
          className="bottom-tabbar__backdrop"
          onClick={() => setMoreOpen(false)}
          role="presentation"
        />
      )}

      {moreOpen && overflow.length > 0 && (
        <div className="bottom-tabbar__sheet" role="dialog" aria-label="Ещё разделы">
          {overflow.map((item) => (
            <button
              type="button"
              key={item.id}
              className={
                'bottom-tabbar__sheet-item' +
                (item.id === activeId ? ' bottom-tabbar__sheet-item--active' : '')
              }
              onClick={() => handleSelect(item.id)}
            >
              {item.icon ? (
                <span className="bottom-tabbar__icon" aria-hidden="true">
                  {item.icon}
                </span>
              ) : null}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}

      <nav className="bottom-tabbar" aria-label="Главная навигация">
        {primary.map((item) => (
          <button
            type="button"
            key={item.id}
            className={
              'bottom-tabbar__item' +
              (item.id === activeId ? ' bottom-tabbar__item--active' : '')
            }
            aria-label={item.label}
            aria-current={item.id === activeId ? 'page' : undefined}
            onClick={() => handleSelect(item.id)}
          >
            {item.icon ? (
              <span className="bottom-tabbar__icon" aria-hidden="true">
                {item.icon}
              </span>
            ) : null}
            <span className="bottom-tabbar__label">{item.label}</span>
            {item.badge ? (
              <span className="bottom-tabbar__badge" aria-hidden="true">
                {item.badge}
              </span>
            ) : null}
          </button>
        ))}

        {overflow.length > 0 && (
          <button
            type="button"
            className={
              'bottom-tabbar__item bottom-tabbar__item--more' +
              (moreOpen ? ' bottom-tabbar__item--active' : '')
            }
            aria-label="Ещё разделы"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen((value) => !value)}
          >
            <span className="bottom-tabbar__label">Ещё</span>
          </button>
        )}
      </nav>
    </>
  );
}
