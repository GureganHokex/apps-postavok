/**
 * Страница управления кранами (как в Google Sheets).
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  getLocations,
  createLocation,
  deleteLocation,
  getLocation,
  addTap,
  updateTap,
  deleteTap,
  addAvailableBeer,
  deleteAvailableBeer,
  exportLocationTaps,
} from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useIsMobile } from '../hooks/useBreakpoint';
import './TapsPage.css';

function TapsPage() {
  const { role, isAdmin } = useAuth();
  const isMobile = useIsMobile();
  const canAddDeleteLocationsAndTaps = isAdmin;
  const canOnlyChangeVisibility = role === 'user';
  const [locations, setLocations] = useState([]);
  const [activeLocationId, setActiveLocationId] = useState(null);
  const [activeLocation, setActiveLocation] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAddingLocation, setIsAddingLocation] = useState(false);
  const [newLocationName, setNewLocationName] = useState('');
  const [editingCell, setEditingCell] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [newBeerInput, setNewBeerInput] = useState('');
  const [draggedBeer, setDraggedBeer] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  /*
   * Альтернатива drag-n-drop для тач-устройств:
   * - тап по доступной позиции — выбираем (selectedBeer).
   * - тап по слоту крана (current / next_beer_1 / next_beer_2) — назначаем.
   * На десктопе работает параллельно с drag-n-drop и не мешает редактированию
   * (если selectedBeer не выбран — тап по ячейке всё ещё начинает редактирование).
   */
  const [selectedBeer, setSelectedBeer] = useState(null);
  const [isBeersPanelOpen, setIsBeersPanelOpen] = useState(false);
  const [detailsTap, setDetailsTap] = useState(null);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState('');
  const [isSavingDescription, setIsSavingDescription] = useState(false);

  useEffect(() => {
    setIsEditingDescription(false);
    setDescriptionDraft('');
  }, [detailsTap?.id]);

  const startEditDescription = () => {
    if (!detailsTap) return;
    setDescriptionDraft(detailsTap.description || '');
    setIsEditingDescription(true);
  };

  const cancelEditDescription = () => {
    setIsEditingDescription(false);
    setDescriptionDraft('');
  };

  const saveDescription = async () => {
    if (!detailsTap) return;
    setIsSavingDescription(true);
    try {
      const nextDescription = descriptionDraft;
      await updateTap(detailsTap.id, { description: nextDescription });
      setDetailsTap((prev) => (prev ? { ...prev, description: nextDescription } : prev));
      setIsEditingDescription(false);
      setDescriptionDraft('');
      loadActiveLocation();
      toast.success('Описание сохранено');
    } catch (err) {
      toast.error('Не удалось сохранить описание');
    } finally {
      setIsSavingDescription(false);
    }
  };

  // Загрузка локаций
  const loadLocations = useCallback(async () => {
    try {
      const data = await getLocations();
      const locationsList = data.results || data;
      setLocations(locationsList);
      
      if (locationsList.length > 0 && !activeLocationId) {
        setActiveLocationId(locationsList[0].id);
      }
    } catch (err) {
      toast.error('Ошибка загрузки локаций');
    } finally {
      setIsLoading(false);
    }
  }, [activeLocationId]);

  // Загрузка активной локации с кранами
  const loadActiveLocation = useCallback(async () => {
    if (!activeLocationId) {
      setActiveLocation(null);
      return;
    }
    
    try {
      const data = await getLocation(activeLocationId);
      setActiveLocation(data);
    } catch (err) {
      toast.error('Ошибка загрузки кранов');
    }
  }, [activeLocationId]);

  useEffect(() => {
    loadLocations();
  }, [loadLocations]);

  useEffect(() => {
    loadActiveLocation();
  }, [activeLocationId, loadActiveLocation]);

  // Создание новой локации
  const handleCreateLocation = async () => {
    if (!newLocationName.trim()) {
      toast.error('Введите название локации');
      return;
    }
    
    try {
      const newLocation = await createLocation(newLocationName.trim());
      setLocations([...locations, newLocation]);
      setActiveLocationId(newLocation.id);
      setNewLocationName('');
      setIsAddingLocation(false);
      toast.success('Локация создана');
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        (typeof err.response?.data === 'string' ? err.response.data : null) ||
        err.response?.data?.error;
      const msg = Array.isArray(detail) ? detail.map((d) => d || '').join(' ') : detail;
      toast.error(msg ? `Ошибка создания локации: ${msg}` : 'Ошибка создания локации');
    }
  };

  // Удаление локации
  const handleDeleteLocation = async (locationId) => {
    if (!window.confirm('Удалить локацию и все её краны?')) return;
    
    try {
      await deleteLocation(locationId);
      const newLocations = locations.filter(l => l.id !== locationId);
      setLocations(newLocations);
      
      if (activeLocationId === locationId) {
        setActiveLocationId(newLocations[0]?.id || null);
      }
      toast.success('Локация удалена');
    } catch (err) {
      toast.error('Ошибка удаления локации');
    }
  };

  // Добавление крана
  const handleAddTap = async () => {
    if (!activeLocationId) return;
    
    try {
      await addTap(activeLocationId, { status: 'free' });
      loadActiveLocation();
      toast.success('Кран добавлен');
    } catch (err) {
      toast.error('Ошибка добавления крана');
    }
  };

  // Удаление крана
  const handleDeleteTap = async (tapId) => {
    try {
      await deleteTap(tapId);
      loadActiveLocation();
      toast.success('Кран удален');
    } catch (err) {
      toast.error('Ошибка удаления крана');
    }
  };

  // Начало редактирования ячейки
  const startEditing = (tapId, field, value) => {
    setEditingCell({ tapId, field });
    setEditValue(value || '');
  };

  // Сохранение редактирования
  const saveEdit = async () => {
    if (!editingCell) return;
    
    const { tapId, field } = editingCell;
    
    try {
      await updateTap(tapId, { [field]: editValue || '' });
      loadActiveLocation();
      setEditingCell(null);
      setEditValue('');
    } catch (err) {
      toast.error('Ошибка сохранения');
    }
  };

  // Отмена редактирования
  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue('');
  };

  // Обработка нажатия клавиш
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      saveEdit();
    } else if (e.key === 'Escape') {
      cancelEdit();
    }
  };

  // Добавление доступного пива
  const handleAddAvailableBeer = async () => {
    if (!newBeerInput.trim() || !activeLocationId) return;
    
    // Парсим формат "Пивоварня | Название(Цена)"
    const match = newBeerInput.match(/^(.+?)\s*\|\s*(.+?)(?:\((\d+)\))?$/);
    
    let brewery = '';
    let beerName = '';
    let price = null;
    
    if (match) {
      brewery = match[1].trim();
      beerName = match[2].trim();
      price = match[3] ? parseInt(match[3]) : null;
    } else {
      beerName = newBeerInput.trim();
    }
    
    try {
      await addAvailableBeer({
        location: activeLocationId,
        brewery,
        beer_name: beerName,
        price_per_liter: price,
      });
      loadActiveLocation();
      setNewBeerInput('');
      toast.success('Позиция добавлена');
    } catch (err) {
      toast.error('Ошибка добавления');
    }
  };

  // Удаление доступного пива
  const handleDeleteAvailableBeer = async (beerId) => {
    try {
      await deleteAvailableBeer(beerId);
      loadActiveLocation();
    } catch (err) {
      toast.error('Ошибка удаления');
    }
  };

  // Drag and Drop
  const handleDragStart = (beer) => {
    setDraggedBeer(beer);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  // Унифицированное назначение позиции на слот крана.
  // Используется как из drag-n-drop, так и из click-to-place.
  const assignBeerToTap = useCallback(
    async (beer, tapId, field) => {
      if (!beer) return;
      try {
        if (field === 'current') {
          await updateTap(tapId, {
            brewery: beer.brewery,
            beer_name: beer.beer_name,
            price_per_liter: beer.price_per_liter,
            description: beer.description || '',
            status: 'active',
          });
        } else {
          await updateTap(tapId, { [field]: beer.display_name });
        }
        loadActiveLocation();
        toast.success('Позиция назначена');
      } catch (err) {
        toast.error('Ошибка обновления');
      }
    },
    [loadActiveLocation],
  );

  const handleDropOnTap = async (tapId, field) => {
    if (!draggedBeer) return;
    await assignBeerToTap(draggedBeer, tapId, field);
    setDraggedBeer(null);
  };

  // Тап по слоту крана: если выбрана позиция — назначаем; иначе обычное редактирование.
  const handleCellTap = useCallback(
    (tap, field, currentValue) => {
      if (selectedBeer) {
        assignBeerToTap(selectedBeer, tap.id, field);
        setSelectedBeer(null);
        setIsBeersPanelOpen(false);
        return;
      }
      if (field === 'current' && (tap.current_beer || tap.brewery || tap.beer_name)) {
        setDetailsTap(tap);
        return;
      }
      startEditing(tap.id, field === 'current' ? 'current_beer' : field, currentValue);
    },
    [selectedBeer, assignBeerToTap],
  );

  // Тап по доступной позиции: переключаем выбор. Повторный тап — снимает.
  const toggleSelectBeer = useCallback((beer) => {
    setSelectedBeer((prev) => (prev?.id === beer.id ? null : beer));
  }, []);

  // Фильтрация кранов по поисковому запросу
  const filteredTaps = useMemo(() => {
    if (!activeLocation || !activeLocation.taps) return [];
    if (!searchQuery.trim()) return activeLocation.taps;
    
    const query = searchQuery.toLowerCase().trim();
    return activeLocation.taps.filter(tap => {
      const currentBeer = tap.current_beer || `${tap.brewery} ${tap.beer_name}`.toLowerCase();
      const next1 = (tap.next_beer_1 || '').toLowerCase();
      const next2 = (tap.next_beer_2 || '').toLowerCase();
      const brewery = (tap.brewery || '').toLowerCase();
      const beerName = (tap.beer_name || '').toLowerCase();
      
      return currentBeer.includes(query) || 
             next1.includes(query) || 
             next2.includes(query) ||
             brewery.includes(query) ||
             beerName.includes(query);
    });
  }, [activeLocation, searchQuery]);

  // Сдвиг очереди (текущее -> архив, след1 -> текущее, след2 -> след1)
  const handleShiftQueue = async (tap) => {
    try {
      // Парсим next_beer_1 для получения данных
      let newBrewery = '';
      let newBeerName = '';
      let newPrice = null;
      let newStatus = 'free';
      
      if (tap.next_beer_1) {
        const match = tap.next_beer_1.match(/^(.+?)\s*\|\s*(.+?)(?:\((\d+)\))?$/);
        if (match) {
          newBrewery = match[1].trim();
          newBeerName = match[2].trim();
          newPrice = match[3] ? parseInt(match[3]) : null;
          newStatus = 'active';
        }
      }
      
      await updateTap(tap.id, {
        brewery: newBrewery,
        beer_name: newBeerName,
        price_per_liter: newPrice,
        description: '',
        status: newStatus,
        next_beer_1: tap.next_beer_2 || '',
        next_beer_2: '',
      });
      loadActiveLocation();
      toast.success('Очередь сдвинута');
    } catch (err) {
      toast.error('Ошибка сдвига');
    }
  };

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner">
          <div className="spinner-ring"></div>
        </div>
        <p>Загрузка...</p>
      </div>
    );
  }

  return (
    <div className="TapsPage">
      <div className="taps-layout">
        {/* Основная таблица */}
        <div className="taps-main">
          <div className="card">
            <div className="taps-header">
              <h2>Управление кранами</h2>
              {canAddDeleteLocationsAndTaps && activeLocation && (
                <button
                  className="button button-secondary"
                  onClick={async () => {
                    try {
                      await exportLocationTaps(activeLocationId);
                      toast.success('Краны экспортированы');
                    } catch (err) {
                      toast.error('Ошибка экспорта');
                    }
                  }}
                  title="Экспортировать краны в Excel"
                >
                  Экспорт в Excel
                </button>
              )}
            </div>

            {/* Табы локаций */}
            <div className="locations-tabs">
              {locations.map(location => (
                <div
                  key={location.id}
                  className={`location-tab ${activeLocationId === location.id ? 'active' : ''}`}
                  onClick={() => setActiveLocationId(location.id)}
                >
                  <span className="location-name">{location.name}</span>
                  <span className="location-count">{location.taps_count || 0}</span>
                  {canAddDeleteLocationsAndTaps && (
                    <button
                      className="delete-location-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteLocation(location.id);
                      }}
                      title="Удалить локацию"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              
              {canAddDeleteLocationsAndTaps && (isAddingLocation ? (
                <div className="add-location-form">
                  <div className="add-location-form-row">
                    <input
                      type="text"
                      value={newLocationName}
                      onChange={(e) => setNewLocationName(e.target.value)}
                      placeholder="Название локации"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleCreateLocation();
                        if (e.key === 'Escape') setIsAddingLocation(false);
                      }}
                    />
                    <button type="button" onClick={handleCreateLocation} className="btn-confirm" title="Создать локацию">OK</button>
                    <button type="button" onClick={() => setIsAddingLocation(false)} className="btn-cancel" title="Отмена">×</button>
                  </div>
                  <p className="add-location-hint">Нажмите OK или Enter — пока только текст в поле, локация не создана.</p>
                </div>
              ) : (
                <button
                  className="add-location-btn"
                  onClick={() => setIsAddingLocation(true)}
                >
                  + Локация
                </button>
              )) }
            </div>

            {/* Легенда цветов — только для редактирования */}
            {!canOnlyChangeVisibility && (
            <div className="color-legend">
              <span className="legend-title">Цвета:</span>
              <div className="legend-item">
                <span className="legend-bar blue"></span>
                <span>След на кран</span>
              </div>
              <div className="legend-item">
                <span className="legend-bar green"></span>
                <span>Свежее / Новая поставка</span>
              </div>
              <span className="legend-hint">(клик по полоске меняет цвет)</span>
            </div>
            )}

            {/* Поиск по кранам */}
            {activeLocation && activeLocation.taps && activeLocation.taps.length > 0 && (
              <div className="taps-search">
                <input
                  type="text"
                  placeholder="Поиск по пиву или пивоварне..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="search-input"
                />
                {searchQuery && (
                  <button
                    className="clear-search-btn"
                    onClick={() => setSearchQuery('')}
                    title="Очистить поиск"
                  >
                    ×
                  </button>
                )}
              </div>
            )}

            {/* Таблица кранов */}
            {activeLocation ? (
              <div className="taps-table-container">
                <table className="taps-table sheets-style">
                  <thead>
                    <tr>
                      <th className="col-num">№</th>
                      <th className="col-current">Что сейчас</th>
                      {!canOnlyChangeVisibility && (
                        <>
                          <th className="col-next">След 1</th>
                          <th className="col-next">След 2</th>
                        </>
                      )}
                      <th className="col-actions">{canOnlyChangeVisibility ? 'Видимость' : ''}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <AnimatePresence>
                      {filteredTaps && filteredTaps.map(tap => (
                        <motion.tr
                          key={tap.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className={`tap-row status-${tap.status} ${tap.is_visible === false ? 'tap-hidden' : ''}`}
                        >
                          <td className="col-num">{tap.position}</td>
                          {canOnlyChangeVisibility ? (
                            <>
                              <td
                                className="col-current tap-details-trigger"
                                colSpan={2}
                                onClick={() => {
                                  if (tap.current_beer || tap.brewery || tap.beer_name) {
                                    setDetailsTap(tap);
                                  }
                                }}
                              >
                                <span>{tap.current_beer || '—'}</span>
                              </td>
                              <td className="col-actions">
                                <label className="tap-visibility-toggle" title={tap.is_visible !== false ? 'Скрыть' : 'Показать'}>
                                  <input
                                    type="checkbox"
                                    checked={tap.is_visible !== false}
                                    onChange={async () => {
                                      try {
                                        await updateTap(tap.id, { is_visible: !(tap.is_visible !== false) });
                                        loadActiveLocation();
                                        toast.success(tap.is_visible !== false ? 'Кран скрыт' : 'Кран показан');
                                      } catch (err) {
                                        toast.error('Ошибка');
                                      }
                                    }}
                                  />
                                  <span>{tap.is_visible !== false ? 'Показан' : 'Скрыт'}</span>
                                </label>
                              </td>
                            </>
                          ) : (
                            <>
                          {/* Текущее пиво */}
                          <td
                            className={`col-current${selectedBeer ? ' col-droppable' : ''}`}
                            onDragOver={handleDragOver}
                            onDrop={() => handleDropOnTap(tap.id, 'current')}
                          >
                            <div className={`cell-with-color color-${tap.color_current || 'none'}`}>
                              <div 
                                className="color-bar"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  const colors = ['', 'blue', 'green'];
                                  const idx = colors.indexOf(tap.color_current || '');
                                  const next = colors[(idx + 1) % colors.length];
                                  await updateTap(tap.id, { color_current: next });
                                  loadActiveLocation();
                                }}
                                title="Клик для смены цвета"
                              />
                              <div 
                                className="cell-content"
                                onClick={() => handleCellTap(tap, 'current', tap.current_beer)}
                              >
                                <span>{tap.current_beer || '—'}</span>
                              </div>
                            </div>
                          </td>
                          
                          {/* След 1 */}
                          <td
                            className={`col-next${selectedBeer ? ' col-droppable' : ''}`}
                            onDragOver={handleDragOver}
                            onDrop={() => handleDropOnTap(tap.id, 'next_beer_1')}
                          >
                            <div className={`cell-with-color color-${tap.color_next1 || 'none'}`}>
                              <div 
                                className="color-bar"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  const colors = ['', 'blue', 'green'];
                                  const idx = colors.indexOf(tap.color_next1 || '');
                                  const next = colors[(idx + 1) % colors.length];
                                  await updateTap(tap.id, { color_next1: next });
                                  loadActiveLocation();
                                }}
                                title="Клик для смены цвета"
                              />
                              {editingCell?.tapId === tap.id && editingCell?.field === 'next_beer_1' ? (
                                <input
                                  type="text"
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={saveEdit}
                                  onKeyDown={handleKeyDown}
                                  autoFocus
                                />
                              ) : (
                                <div 
                                  className="cell-content"
                                  onClick={() => handleCellTap(tap, 'next_beer_1', tap.next_beer_1)}
                                >
                                  <span>{tap.next_beer_1 || '—'}</span>
                                </div>
                              )}
                            </div>
                          </td>
                          
                          {/* След 2 */}
                          <td
                            className={`col-next${selectedBeer ? ' col-droppable' : ''}`}
                            onDragOver={handleDragOver}
                            onDrop={() => handleDropOnTap(tap.id, 'next_beer_2')}
                          >
                            <div className={`cell-with-color color-${tap.color_next2 || 'none'}`}>
                              <div 
                                className="color-bar"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  const colors = ['', 'blue', 'green'];
                                  const idx = colors.indexOf(tap.color_next2 || '');
                                  const next = colors[(idx + 1) % colors.length];
                                  await updateTap(tap.id, { color_next2: next });
                                  loadActiveLocation();
                                }}
                                title="Клик для смены цвета"
                              />
                              {editingCell?.tapId === tap.id && editingCell?.field === 'next_beer_2' ? (
                                <input
                                  type="text"
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onBlur={saveEdit}
                                  onKeyDown={handleKeyDown}
                                  autoFocus
                                />
                              ) : (
                                <div 
                                  className="cell-content"
                                  onClick={() => handleCellTap(tap, 'next_beer_2', tap.next_beer_2)}
                                >
                                  <span>{tap.next_beer_2 || '—'}</span>
                                </div>
                              )}
                            </div>
                          </td>
                          
                          {/* Действия */}
                          <td className="col-actions">
                            <button
                              className="btn-shift"
                              onClick={() => handleShiftQueue(tap)}
                              title="Сдвинуть очередь"
                              disabled={!tap.next_beer_1}
                            >
                              ⟳
                            </button>
                            {canAddDeleteLocationsAndTaps && (
                              <button
                                className="btn-delete-tap"
                                onClick={() => handleDeleteTap(tap.id)}
                                title="Удалить кран"
                              >
                                Удалить
                              </button>
                            )}
                          </td>
                            </>
                          )}
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  </tbody>
                </table>
                
                {canAddDeleteLocationsAndTaps && (
                  <button className="add-tap-btn" onClick={handleAddTap}>
                    + Добавить кран
                  </button>
                )}
              </div>
            ) : (
              <div className="no-location">
                <p>Выберите или создайте локацию</p>
              </div>
            )}
          </div>
        </div>

        {/* Боковая панель с доступным пивом — только для тех, кто может редактировать краны */}
        {activeLocation && !canOnlyChangeVisibility && (
          <div className={`taps-sidebar${isMobile && !isBeersPanelOpen ? ' taps-sidebar--hidden' : ''}${isMobile ? ' taps-sidebar--mobile' : ''}`}>
            <div className="card">
              <div className="sidebar-head">
                <h3>Доступные позиции</h3>
                {isMobile && (
                  <button
                    type="button"
                    className="sidebar-close"
                    onClick={() => setIsBeersPanelOpen(false)}
                    aria-label="Закрыть"
                  >
                    Закрыть
                  </button>
                )}
              </div>
              <p className="sidebar-hint">
                {selectedBeer
                  ? 'Тапните по нужному слоту крана'
                  : isMobile
                    ? 'Тапните по позиции, затем по слоту крана'
                    : 'Перетащите на кран — или тапните и выберите слот'}
              </p>

              <div className="add-beer-form">
                <input
                  type="text"
                  value={newBeerInput}
                  onChange={(e) => setNewBeerInput(e.target.value)}
                  placeholder="Пивоварня | Название(Цена)"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddAvailableBeer();
                  }}
                />
                <button onClick={handleAddAvailableBeer}>+</button>
              </div>

              <div className="available-beers-list">
                {activeLocation.available_beers && activeLocation.available_beers.map(beer => {
                  const isSelected = selectedBeer?.id === beer.id;
                  return (
                    <div
                      key={beer.id}
                      className={`available-beer-item${isSelected ? ' available-beer-item--selected' : ''}`}
                      draggable
                      onDragStart={() => handleDragStart(beer)}
                      onClick={() => toggleSelectBeer(beer)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          toggleSelectBeer(beer);
                        }
                      }}
                    >
                      <span className="drag-handle">⋮⋮</span>
                      <span className="beer-display">{beer.display_name}</span>
                      <button
                        className="delete-beer-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteAvailableBeer(beer.id);
                        }}
                      >
                        ×
                      </button>
                    </div>
                  );
                })}

                {(!activeLocation.available_beers || activeLocation.available_beers.length === 0) && (
                  <p className="empty-list">Нет доступных позиций</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Floating-кнопка открытия панели доступных позиций — только на мобильном. */}
        {isMobile && activeLocation && !canOnlyChangeVisibility && !isBeersPanelOpen && (
          <button
            type="button"
            className="taps-fab"
            onClick={() => setIsBeersPanelOpen(true)}
            aria-label="Открыть доступные позиции"
          >
            Позиции
            {activeLocation.available_beers?.length ? (
              <span className="taps-fab-badge">{activeLocation.available_beers.length}</span>
            ) : null}
          </button>
        )}

        {/* Плашка с выбранной позицией — подсказка пользователю что делать дальше. */}
        {selectedBeer && (
          <div className="taps-selected-banner" role="status" aria-live="polite">
            <span className="taps-selected-banner__label">Назначить:</span>
            <span className="taps-selected-banner__beer">{selectedBeer.display_name}</span>
            <button
              type="button"
              className="taps-selected-banner__cancel"
              onClick={() => setSelectedBeer(null)}
            >
              Отмена
            </button>
          </div>
        )}

        {detailsTap && (
          <div className="tap-details-modal" onClick={() => setDetailsTap(null)}>
            <div className="tap-details-card" onClick={(e) => e.stopPropagation()}>
              <div className="tap-details-header">
                <div>
                  <h3>Описание кеги</h3>
                  <p>Кран №{detailsTap.position}</p>
                </div>
                <button
                  type="button"
                  className="tap-details-close"
                  onClick={() => setDetailsTap(null)}
                >
                  Закрыть
                </button>
              </div>

              <dl className="tap-details-list">
                <div>
                  <dt>Пивоварня</dt>
                  <dd>{detailsTap.brewery || 'Не указана'}</dd>
                </div>
                <div>
                  <dt>Название</dt>
                  <dd>{detailsTap.beer_name || detailsTap.current_beer || 'Не указано'}</dd>
                </div>
                <div>
                  <dt>Цена</dt>
                  <dd>{detailsTap.price_per_liter ? `${Math.round(detailsTap.price_per_liter)} ₽` : 'Не указана'}</dd>
                </div>
                <div>
                  <dt>Описание</dt>
                  {isEditingDescription ? (
                    <dd className="tap-details-description-edit">
                      <textarea
                        className="tap-details-textarea"
                        value={descriptionDraft}
                        onChange={(e) => setDescriptionDraft(e.target.value)}
                        placeholder="Например: стиль, ABV, IBU, особенности, рекомендации по подаче"
                        rows={5}
                        autoFocus
                        disabled={isSavingDescription}
                      />
                      <div className="tap-details-edit-actions">
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={saveDescription}
                          disabled={isSavingDescription}
                        >
                          {isSavingDescription ? 'Сохранение…' : 'Сохранить'}
                        </button>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={cancelEditDescription}
                          disabled={isSavingDescription}
                        >
                          Отмена
                        </button>
                      </div>
                    </dd>
                  ) : (
                    <dd>
                      {detailsTap.description
                        ? detailsTap.description
                        : 'Описание для этой кеги не указано.'}
                    </dd>
                  )}
                </div>
              </dl>

              {!canOnlyChangeVisibility && !isEditingDescription && (
                <div className="tap-details-actions">
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={startEditDescription}
                  >
                    {detailsTap.description ? 'Изменить описание' : 'Добавить описание'}
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => {
                      setDetailsTap(null);
                      startEditing(detailsTap.id, 'current_beer', detailsTap.current_beer);
                    }}
                  >
                    Редактировать название
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default TapsPage;
