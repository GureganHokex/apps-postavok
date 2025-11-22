/**
 * Утилиты для сохранения настроек пользователя
 */

const SETTINGS_KEY = 'app_settings';

const defaultSettings = {
  tableColumns: {
    brewery: true,
    beer_name: true,
    style: true,
    abv: true,
    ibu: true,
    price: true,
    currency: true,
    volume: true,
    format_type: true,
    stock: true,
    description: true,
  },
  tableRowHeight: 50,
  filters: {
    brewery: '',
    beer_name: '',
    style: '',
  },
  theme: 'light',
};

export function getSettings() {
  try {
    const settings = localStorage.getItem(SETTINGS_KEY);
    return settings ? { ...defaultSettings, ...JSON.parse(settings) } : defaultSettings;
  } catch (error) {
    console.error('Ошибка чтения настроек:', error);
    return defaultSettings;
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (error) {
    console.error('Ошибка сохранения настроек:', error);
  }
}

export function updateSetting(key, value) {
  const settings = getSettings();
  settings[key] = value;
  saveSettings(settings);
  return settings;
}

