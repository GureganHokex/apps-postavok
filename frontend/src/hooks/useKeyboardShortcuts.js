/**
 * Хук для клавиатурных сокращений
 */

import { useEffect } from 'react';

export function useKeyboardShortcuts(shortcuts) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Проверяем, не находится ли фокус в input/textarea
      if (
        event.target.tagName === 'INPUT' ||
        event.target.tagName === 'TEXTAREA' ||
        event.target.isContentEditable
      ) {
        // Разрешаем только Ctrl+S для сохранения
        if (event.ctrlKey && event.key === 's') {
          event.preventDefault();
          const saveShortcut = shortcuts.find(s => s.keys === 'ctrl+s');
          if (saveShortcut) {
            saveShortcut.handler();
          }
        }
        return;
      }

      // Формируем строку комбинации клавиш
      const keyParts = [];
      if (event.ctrlKey || event.metaKey) keyParts.push('ctrl');
      if (event.shiftKey) keyParts.push('shift');
      if (event.altKey) keyParts.push('alt');
      keyParts.push(event.key.toLowerCase());

      const keyCombo = keyParts.join('+');

      // Ищем подходящий shortcut
      const shortcut = shortcuts.find(s => s.keys === keyCombo);
      if (shortcut) {
        event.preventDefault();
        shortcut.handler();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [shortcuts]);
}

