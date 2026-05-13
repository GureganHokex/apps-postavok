/**
 * Страница управления кранами (как в Google Sheets).
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  getAvailableBeers,
  reorderAvailableBeers,
} from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useIsMobile } from '../hooks/useBreakpoint';
import './TapsPage.css';

/** Разбор строки «Пивоварня | Название(цена)» для экранной доски */
function splitBeerDisplay(line) {
  if (!line || line === '—') return { brewery: '', beer: '—' };
  const parts = line.split(/\s*\|\s*/);
  if (parts.length >= 2) {
    return { brewery: parts[0].trim(), beer: parts.slice(1).join(' | ').trim() };
  }
  return { brewery: '', beer: line.trim() };
}

function stripTrailingPriceFromBeerLabel(beer) {
  return (beer || '').replace(/\s*\(\d+\)\s*$/, '').trim();
}

function shortDescriptionForMeta(desc) {
  const t = (desc || '').trim();
  if (!t || t.length > 96 || t.includes('\n')) return '';
  return t;
}

function formatAbvPresentation(text) {
  const t = (text || '').trim();
  if (!t) return '';
  if (/\babv\b/i.test(t)) return t;
  if (/%/.test(t)) return `${t.replace(/\s+$/, '')} ABV`;
  return `${t}% ABV`;
}

function formatIbuPresentation(text) {
  const t = (text || '').trim();
  if (!t) return '';
  if (/\bibu\b/i.test(t)) return t;
  if (/^\d+(\.\d+)?$/.test(t)) return `${t} IBU`;
  return t;
}

/** Стиль • ABV • IBU: при коротком описании считаем его стилем; пивоварню не дублируем (она над заголовком). */
function presentationMetaSegments(tap, descShort) {
  const parts = [];
  if (descShort) parts.push(descShort);
  const abv = formatAbvPresentation(tap.abv_text);
  const ibu = formatIbuPresentation(tap.bitterness_ibu);
  if (abv) parts.push(abv);
  if (ibu) parts.push(ibu);
  return parts;
}

function presentationPriceLine(tap) {
  const raw = (tap.volume_price_text || '').trim();
  if (raw) {
    const segments = raw.split(/\s*\|\s*/).filter(Boolean);
    const v = segments.length > 1 ? (segments[0] || '').trim() : raw;
    return v || raw;
  }
  if (tap.price_per_liter != null && tap.price_per_liter !== '') {
    const p = Math.round(Number(tap.price_per_liter));
    if (!Number.isNaN(p)) return `${p} ₽`;
  }
  return '';
}

/** Краткий текст ошибки DRF для toast */
function formatApiError(err, fallback) {
  const data = err?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) return data.detail.filter(Boolean).join(' ') || fallback;
  if (typeof data === 'object') {
    const parts = [];
    for (const [k, v] of Object.entries(data)) {
      if (k === 'detail') continue;
      const val = Array.isArray(v) ? v.filter(Boolean).join(' ') : String(v);
      if (val) parts.push(`${k}: ${val}`);
    }
    if (parts.length) return parts.join(' · ');
  }
  return fallback;
}

/** Колонки полноэкранной доски (фиксированно три). */
const PRESENTATION_COLUMN_COUNT = 3;

/** Колонки как при column-flow: сверху вниз, слева направо; без пустых «ячеек» внизу короткой колонки. */
function buildPresentationColumns(taps, colCount) {
  const n = taps.length;
  if (n === 0) return [];
  const c = Math.max(1, Math.min(colCount, n));
  const rows = Math.ceil(n / c);
  const columns = [];
  for (let col = 0; col < c; col += 1) {
    const colTaps = [];
    for (let row = 0; row < rows; row += 1) {
      const idx = row + col * rows;
      if (idx < n) colTaps.push(taps[idx]);
    }
    columns.push(colTaps);
  }
  return columns;
}

function TapsPage() {
  const { role, isAdmin } = useAuth();
  const isMobile = useIsMobile();
  const canAddDeleteLocationsAndTaps = isAdmin;
  /** Роль user: только просмотр кранов, без правок (видимость настраивает персонал). */
  const isReadOnlyTapsUser = role === 'user';
  const canEditTapsContent = !isReadOnlyTapsUser;
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
  const [untappdVolumePrice, setUntappdVolumePrice] = useState('');
  const [untappdIbu, setUntappdIbu] = useState('');
  const [untappdAbv, setUntappdAbv] = useState('');
  const [isSavingUntappd, setIsSavingUntappd] = useState(false);
  const [isPresentationOpen, setIsPresentationOpen] = useState(false);
  const presentationRef = useRef(null);

  const mergeTapIntoActiveLocation = useCallback((updatedTap) => {
    if (!updatedTap || updatedTap.id == null) return;
    setActiveLocation((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        taps: (prev.taps || []).map((t) => (t.id === updatedTap.id ? { ...t, ...updatedTap } : t)),
      };
    });
  }, []);

  const refreshAvailableBeers = useCallback(async () => {
    if (!activeLocationId) return;
    try {
      const data = await getAvailableBeers(activeLocationId);
      const beers = Array.isArray(data) ? data : data.results || [];
      setActiveLocation((prev) => {
        if (!prev || String(prev.id) !== String(activeLocationId)) return prev;
        return { ...prev, available_beers: beers };
      });
    } catch (err) {
      toast.error('Не удалось обновить список позиций');
    }
  }, [activeLocationId]);

  useEffect(() => {
    setIsEditingDescription(false);
    setDescriptionDraft('');
    if (!detailsTap) {
      setUntappdVolumePrice('');
      setUntappdIbu('');
      setUntappdAbv('');
      return;
    }
    setUntappdVolumePrice(detailsTap.volume_price_text || '');
    setUntappdIbu(detailsTap.bitterness_ibu || '');
    setUntappdAbv(detailsTap.abv_text || '');
  }, [detailsTap]);

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
      const updated = await updateTap(detailsTap.id, { description: nextDescription });
      mergeTapIntoActiveLocation(updated);
      setDetailsTap((prev) => (prev ? { ...prev, ...updated } : prev));
      setIsEditingDescription(false);
      setDescriptionDraft('');
      toast.success('Описание сохранено');
    } catch (err) {
      toast.error('Не удалось сохранить описание');
    } finally {
      setIsSavingDescription(false);
    }
  };

  const saveUntappdFields = async () => {
    if (!detailsTap || !canEditTapsContent) return;
    setIsSavingUntappd(true);
    const volume_price_text = (untappdVolumePrice || '').trim().slice(0, 200);
    const bitterness_ibu = (untappdIbu || '').trim().slice(0, 64);
    const abv_text = (untappdAbv || '').trim().slice(0, 32);
    try {
      const updated = await updateTap(detailsTap.id, {
        volume_price_text,
        bitterness_ibu,
        abv_text,
      });
      mergeTapIntoActiveLocation(updated);
      setDetailsTap((prev) => (prev ? { ...prev, ...updated } : prev));
      setUntappdVolumePrice(updated.volume_price_text || '');
      setUntappdIbu(updated.bitterness_ibu || '');
      setUntappdAbv(updated.abv_text || '');
      toast.success('Характеристики сохранены');
    } catch (err) {
      toast.error(formatApiError(err, 'Не удалось сохранить'));
    } finally {
      setIsSavingUntappd(false);
    }
  };

  // Загрузка локаций (только при монтировании; не привязываем к activeLocationId — иначе при каждом переключении локации лишний запрос к API)
  const loadLocations = useCallback(async () => {
    try {
      const data = await getLocations();
      const locationsList = data.results || data;
      setLocations(locationsList);

      setActiveLocationId((prev) => {
        if (locationsList.length > 0 && !prev) {
          return locationsList[0].id;
        }
        return prev;
      });
    } catch (err) {
      toast.error('Ошибка загрузки локаций');
    } finally {
      setIsLoading(false);
    }
  }, []);

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

  useEffect(() => {
    if (!isPresentationOpen) return undefined;
    const el = presentationRef.current;
    if (!el) return undefined;
    const req = el.requestFullscreen?.() || el.webkitRequestFullscreen?.();
    if (req && typeof req.then === 'function') {
      req.catch(() => {});
    }
    const onFsChange = () => {
      const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
      if (!fsEl) setIsPresentationOpen(false);
    };
    document.addEventListener('fullscreenchange', onFsChange);
    document.addEventListener('webkitfullscreenchange', onFsChange);
    return () => {
      document.removeEventListener('fullscreenchange', onFsChange);
      document.removeEventListener('webkitfullscreenchange', onFsChange);
    };
  }, [isPresentationOpen]);

  useEffect(() => {
    if (!isPresentationOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
        if (fsEl) {
          (document.exitFullscreen || document.webkitExitFullscreen)?.call(document);
        } else {
          setIsPresentationOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isPresentationOpen]);

  const exitPresentation = useCallback(() => {
    const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
    if (fsEl) {
      (document.exitFullscreen || document.webkitExitFullscreen)?.call(document).catch(() => {});
    }
    setIsPresentationOpen(false);
  }, []);

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
      const updated = await updateTap(tapId, { [field]: editValue || '' });
      mergeTapIntoActiveLocation(updated);
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
      const created = await addAvailableBeer({
        location: activeLocationId,
        brewery,
        beer_name: beerName,
        price_per_liter: price,
      });
      setActiveLocation((p) =>
        p ? { ...p, available_beers: [...(p.available_beers || []), created] } : p,
      );
      setNewBeerInput('');
      toast.success('Позиция добавлена');
    } catch (err) {
      toast.error('Ошибка добавления');
    }
  };

  // Удаление доступного пива
  const handleDeleteAvailableBeer = async (beerId) => {
    const prevBeers = activeLocation?.available_beers;
    setActiveLocation((p) =>
      p ? { ...p, available_beers: (p.available_beers || []).filter((b) => b.id !== beerId) } : p,
    );
    try {
      await deleteAvailableBeer(beerId);
    } catch (err) {
      setActiveLocation((p) => (p ? { ...p, available_beers: prevBeers || [] } : p));
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

  const handleBeerListDragOver = (e) => {
    e.preventDefault();
    try {
      e.dataTransfer.dropEffect = 'move';
    } catch (_) {
      /* старые браузеры */
    }
  };

  const applyBeerSort = useCallback(
    async (mode) => {
      if (!activeLocationId || !activeLocation?.available_beers?.length) return;
      const beers = [...activeLocation.available_beers];
      const cmpRu = (a, b) =>
        String(a || '').localeCompare(String(b || ''), 'ru', { sensitivity: 'base' });
      let sorted;
      switch (mode) {
        case 'brewery':
          sorted = beers.sort(
            (a, b) => cmpRu(a.brewery, b.brewery) || cmpRu(a.beer_name, b.beer_name),
          );
          break;
        case 'beer':
          sorted = beers.sort(
            (a, b) => cmpRu(a.beer_name, b.beer_name) || cmpRu(a.brewery, b.brewery),
          );
          break;
        case 'price_asc':
          sorted = beers.sort(
            (a, b) => (Number(a.price_per_liter) || 0) - (Number(b.price_per_liter) || 0),
          );
          break;
        case 'price_desc':
          sorted = beers.sort(
            (a, b) => (Number(b.price_per_liter) || 0) - (Number(a.price_per_liter) || 0),
          );
          break;
        case 'recent':
          sorted = beers.sort(
            (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0),
          );
          break;
        default:
          return;
      }
      const ids = sorted.map((b) => b.id);
      try {
        await reorderAvailableBeers(activeLocationId, ids);
        setActiveLocation((prev) => (prev ? { ...prev, available_beers: sorted } : prev));
        toast.success('Порядок обновлён');
      } catch (err) {
        toast.error('Не удалось сохранить порядок');
        await refreshAvailableBeers();
      }
    },
    [activeLocationId, activeLocation, refreshAvailableBeers],
  );

  const handleBeerReorderDrop = useCallback(
    async (e, targetBeer) => {
      e.preventDefault();
      e.stopPropagation();
      if (!activeLocationId) return;
      if (!draggedBeer || draggedBeer.id === targetBeer.id) return;
      const list = [...(activeLocation?.available_beers || [])];
      const from = list.findIndex((b) => b.id === draggedBeer.id);
      const to = list.findIndex((b) => b.id === targetBeer.id);
      if (from === -1 || to === -1) return;
      const nextList = [...list];
      const [moved] = nextList.splice(from, 1);
      nextList.splice(to, 0, moved);
      const ids = nextList.map((b) => b.id);
      try {
        await reorderAvailableBeers(activeLocationId, ids);
        setActiveLocation((prev) => (prev ? { ...prev, available_beers: nextList } : prev));
        toast.success('Порядок сохранён');
      } catch (err) {
        toast.error('Не удалось сохранить порядок');
        await refreshAvailableBeers();
      } finally {
        setDraggedBeer(null);
      }
    },
    [draggedBeer, activeLocation, activeLocationId, refreshAvailableBeers],
  );

  // Унифицированное назначение позиции на слот крана.
  // Используется как из drag-n-drop, так и из click-to-place.
  const assignBeerToTap = useCallback(
    async (beer, tapId, field) => {
      if (!beer) return;
      try {
        let updated;
        if (field === 'current') {
          updated = await updateTap(tapId, {
            brewery: beer.brewery,
            beer_name: beer.beer_name,
            price_per_liter: beer.price_per_liter,
            description: beer.description || '',
            volume_price_text: beer.volume_price_text || '',
            bitterness_ibu: beer.bitterness_ibu || '',
            abv_text: beer.abv_text || '',
            status: 'active',
          });
        } else {
          updated = await updateTap(tapId, { [field]: beer.display_name });
        }
        mergeTapIntoActiveLocation(updated);
        toast.success('Позиция назначена');
      } catch (err) {
        toast.error('Ошибка обновления');
      }
    },
    [mergeTapIntoActiveLocation],
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
      const currentBeer = (tap.current_beer || `${tap.brewery} ${tap.beer_name}`).toLowerCase();
      const next1 = (tap.next_beer_1 || '').toLowerCase();
      const next2 = (tap.next_beer_2 || '').toLowerCase();
      const brewery = (tap.brewery || '').toLowerCase();
      const beerName = (tap.beer_name || '').toLowerCase();
      
      const vp = (tap.volume_price_text || '').toLowerCase();
      const ibu = (tap.bitterness_ibu || '').toLowerCase();
      const abv = (tap.abv_text || '').toLowerCase();
      
      return currentBeer.includes(query) || 
             next1.includes(query) || 
             next2.includes(query) ||
             brewery.includes(query) ||
             beerName.includes(query) ||
             vp.includes(query) ||
             ibu.includes(query) ||
             abv.includes(query);
    });
  }, [activeLocation, searchQuery]);

  const presentationTaps = useMemo(() => {
    if (!filteredTaps.length) return [];
    return filteredTaps.filter((t) => t.is_visible !== false);
  }, [filteredTaps]);

  // Ровно 3 колонки на доске: см. PRESENTATION_COLUMN_COUNT (без usePresentationColumnCount)
  const presentationColumns = useMemo(
    () => buildPresentationColumns(presentationTaps, PRESENTATION_COLUMN_COUNT),
    [presentationTaps],
  );

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
      
      const updated = await updateTap(tap.id, {
        brewery: newBrewery,
        beer_name: newBeerName,
        price_per_liter: newPrice,
        description: '',
        volume_price_text: '',
        bitterness_ibu: '',
        abv_text: '',
        status: newStatus,
        next_beer_1: tap.next_beer_2 || '',
        next_beer_2: '',
      });
      mergeTapIntoActiveLocation(updated);
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
              <div className="taps-header-actions">
                {activeLocation && activeLocation.taps?.length > 0 && (
                  <button
                    type="button"
                    className="button button-secondary taps-presentation-btn"
                    onClick={() => setIsPresentationOpen(true)}
                    title="Полноэкранная доска для монитора или ТВ"
                  >
                    На экран
                  </button>
                )}
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
            {canEditTapsContent && (
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
                      {!isReadOnlyTapsUser && (
                        <>
                          <th className="col-next">След 1</th>
                          <th className="col-next">След 2</th>
                          {canEditTapsContent && <th className="col-actions" aria-label="Действия" />}
                        </>
                      )}
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
                          {isReadOnlyTapsUser ? (
                            <>
                              <td
                                className="col-current tap-details-trigger taps-readonly-cell"
                                onClick={() => {
                                  if (tap.current_beer || tap.brewery || tap.beer_name) {
                                    setDetailsTap(tap);
                                  }
                                }}
                              >
                                <span>{tap.current_beer || '—'}</span>
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
                                  const updated = await updateTap(tap.id, { color_current: next });
                                  mergeTapIntoActiveLocation(updated);
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
                                  const updated = await updateTap(tap.id, { color_next1: next });
                                  mergeTapIntoActiveLocation(updated);
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
                                  const updated = await updateTap(tap.id, { color_next2: next });
                                  mergeTapIntoActiveLocation(updated);
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
                            <label className="tap-screen-toggle" title="Показывать на полноэкранной доске">
                              <input
                                type="checkbox"
                                checked={tap.is_visible !== false}
                                onChange={async (e) => {
                                  try {
                                    const updated = await updateTap(tap.id, { is_visible: e.target.checked });
                                    mergeTapIntoActiveLocation(updated);
                                  } catch (err) {
                                    toast.error('Не удалось обновить видимость');
                                  }
                                }}
                              />
                              <span>Экран</span>
                            </label>
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
        {activeLocation && canEditTapsContent && (
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

              <div className="available-beers-toolbar">
                <label className="available-beers-sort-label">
                  <span>Порядок</span>
                  <select
                    key={`beer-sort-${activeLocationId}`}
                    className="available-beers-sort-select"
                    aria-label="Сортировка списка"
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value;
                      e.target.value = '';
                      if (v) applyBeerSort(v);
                    }}
                  >
                    <option value="" disabled>
                      Сортировать…
                    </option>
                    <option value="brewery">Пивоварня А→Я</option>
                    <option value="beer">Название А→Я</option>
                    <option value="price_asc">Цена ↑</option>
                    <option value="price_desc">Цена ↓</option>
                    <option value="recent">Сначала новые</option>
                  </select>
                </label>
              </div>

              <div className="available-beers-list">
                {activeLocation.available_beers && activeLocation.available_beers.map(beer => {
                  const isSelected = selectedBeer?.id === beer.id;
                  return (
                    <div
                      key={beer.id}
                      className={`available-beer-item${isSelected ? ' available-beer-item--selected' : ''}`}
                      onDragOver={handleBeerListDragOver}
                      onDrop={(e) => handleBeerReorderDrop(e, beer)}
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
                      <span
                        className="drag-handle"
                        draggable
                        onClick={(e) => e.stopPropagation()}
                        onDragStart={(e) => {
                          e.stopPropagation();
                          handleDragStart(beer);
                        }}
                        onDragEnd={() => setDraggedBeer(null)}
                        title="Перетащить на кран или на другую строку для порядка"
                      >
                        ⋮⋮
                      </span>
                      <span className="beer-display">{beer.display_name}</span>
                      <button
                        type="button"
                        className="delete-beer-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteAvailableBeer(beer.id);
                        }}
                        title="Удалить позицию"
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
        {isMobile && activeLocation && canEditTapsContent && !isBeersPanelOpen && (
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
                  <dt>Объём / цена (ТВ и меню)</dt>
                  <dd>
                    {canEditTapsContent ? (
                      <input
                        type="text"
                        className="tap-details-inline-input"
                        value={untappdVolumePrice}
                        onChange={(e) => setUntappdVolumePrice(e.target.value)}
                        placeholder="Например: 400 мл / 350 ₽ · 250 мл / 250 ₽"
                        disabled={isSavingUntappd}
                        maxLength={200}
                      />
                    ) : (
                      detailsTap.volume_price_text || '—'
                    )}
                  </dd>
                </div>
                {isAdmin && (detailsTap.price_per_liter != null && detailsTap.price_per_liter !== '') ? (
                  <div className="tap-details-price-internal">
                    <dt>Справочно (за литр)</dt>
                    <dd>{`${Math.round(detailsTap.price_per_liter)} ₽/л`}</dd>
                  </div>
                ) : null}
                <div>
                  <dt>Горечь (IBU)</dt>
                  <dd>
                    {canEditTapsContent ? (
                      <input
                        type="text"
                        className="tap-details-inline-input"
                        value={untappdIbu}
                        onChange={(e) => setUntappdIbu(e.target.value)}
                        placeholder="IBU"
                        disabled={isSavingUntappd}
                        maxLength={64}
                      />
                    ) : (
                      detailsTap.bitterness_ibu || '—'
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Алкоголь (ABV)</dt>
                  <dd>
                    {canEditTapsContent ? (
                      <input
                        type="text"
                        className="tap-details-inline-input"
                        value={untappdAbv}
                        onChange={(e) => setUntappdAbv(e.target.value)}
                        placeholder="Например: 5.2 %"
                        disabled={isSavingUntappd}
                        maxLength={32}
                      />
                    ) : (
                      detailsTap.abv_text || '—'
                    )}
                  </dd>
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

              {canEditTapsContent && (
                <div className="tap-details-untappd-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={saveUntappdFields}
                    disabled={isSavingUntappd}
                  >
                    {isSavingUntappd ? 'Сохранение…' : 'Сохранить для экрана'}
                  </button>
                </div>
              )}

              {canEditTapsContent && !isEditingDescription && (
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

      {isPresentationOpen && (
        <div
          ref={presentationRef}
          className="taps-presentation-root"
          role="dialog"
          aria-modal="true"
          aria-label="Доска кранов"
        >
          <button
            type="button"
            className="taps-presentation-exit taps-presentation-exit--floating"
            onClick={exitPresentation}
            title="Выйти (Esc)"
            aria-label="Выйти из полноэкранного режима"
          >
            Выйти
          </button>
          <div className="taps-presentation-body">
            {presentationTaps.length === 0 ? (
              <p className="taps-presentation-empty">
                Нет позиций для доски: включите «Экран» у кранов в таблице или снимите поиск.
              </p>
            ) : (
              <div className="taps-presentation-list">
                {presentationColumns.map((colTaps, colIdx) => (
                  <div
                    key={`presentation-col-${colIdx}`}
                    className="taps-presentation-column"
                    role="presentation"
                  >
                    {colTaps.map((tap) => {
                      const line = tap.current_beer || '—';
                      const split = splitBeerDisplay(line);
                      const brewery = (tap.brewery || '').trim() || split.brewery;
                      const beerNameRaw =
                        (tap.beer_name || '').trim() ||
                        stripTrailingPriceFromBeerLabel(split.beer) ||
                        split.beer;
                      const beerTitle = beerNameRaw === '' ? '—' : beerNameRaw;
                      const descShort = shortDescriptionForMeta(tap.description);
                      const metaParts = presentationMetaSegments(tap, descShort);
                      const priceLine = presentationPriceLine(tap);
                      return (
                        <article key={tap.id} className="taps-presentation-row">
                          <div className="taps-presentation-row__body">
                            {brewery ? (
                              <div className="taps-presentation-row__brewery">{brewery}</div>
                            ) : null}
                            <h2 className="taps-presentation-row__title">
                              <span className="taps-presentation-row__num">{tap.position}.</span>{' '}
                              {beerTitle}
                            </h2>
                            {metaParts.length > 0 ? (
                              <div className="taps-presentation-row__meta">
                                {metaParts.map((text, idx) => (
                                  <span
                                    key={`${tap.id}-m-${idx}`}
                                    className="taps-presentation-row__meta-item"
                                  >
                                    {text}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            {priceLine ? (
                              <div className="taps-presentation-row__prices">{priceLine}</div>
                            ) : null}
                          </div>
                        </article>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default TapsPage;
