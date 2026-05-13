/**
 * Хук текущего брейкпоинта.
 *
 * Источник истины — синхронизирован с CSS-переменными в src/index.css
 * (--bp-sm / --bp-md / --bp-lg / --bp-xl).
 *
 * Используется только там, где CSS-only решение невозможно: например,
 * условный рендер другого компонента (таблица ↔ карточки, верхняя
 * навигация ↔ нижний таб-бар).
 *
 * Для обычного скрытия/изменения стилей предпочтительнее CSS @media.
 */

import { useEffect, useState } from 'react';

export const BREAKPOINTS = Object.freeze({
  sm: 480,
  md: 768,
  lg: 1024,
  xl: 1280,
});

function getMatch(query) {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia(query).matches;
}

/**
 * Возвращает true, если viewport <= указанной ширины (включительно).
 * @param {number} maxWidth
 */
export function useMaxWidth(maxWidth) {
  const query = `(max-width: ${maxWidth}px)`;
  const [matches, setMatches] = useState(() => getMatch(query));

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mql = window.matchMedia(query);
    const handler = (event) => setMatches(event.matches);
    setMatches(mql.matches);
    if (mql.addEventListener) {
      mql.addEventListener('change', handler);
      return () => mql.removeEventListener('change', handler);
    }
    mql.addListener(handler);
    return () => mql.removeListener(handler);
  }, [query]);

  return matches;
}

/**
 * Хелперы для самых частых случаев.
 * Если нужен какой-то нестандартный порог — используйте useMaxWidth(N).
 */
export function useIsMobile() {
  return useMaxWidth(BREAKPOINTS.md);
}

export function useIsTabletOrLess() {
  return useMaxWidth(BREAKPOINTS.lg);
}

/**
 * Возвращает символьное имя текущего брейкпоинта: 'mobile' | 'tablet' | 'desktop'.
 * Удобно, когда нужно ветвить логику по нескольким состояниям сразу.
 */
export function useBreakpoint() {
  const isMobile = useMaxWidth(BREAKPOINTS.md);
  const isTablet = useMaxWidth(BREAKPOINTS.lg);
  if (isMobile) return 'mobile';
  if (isTablet) return 'tablet';
  return 'desktop';
}
