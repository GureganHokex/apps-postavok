/**
 * Настройки поставщиков: маппинг колонок для точного парсинга.
 * Отдельная запись на каждого поставщика (Парадокс, CBD и т.д.).
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getSuppliers, createSupplier, updateSupplier, deleteSupplier } from '../api';
import './SupplierSettings.css';

const FIELD_LABELS = {
  brewery: 'Пивоварня',
  beer_name: 'Название пива',
  style: 'Стиль',
  abv: 'Крепость (ABV)',
  ibu: 'Горечь (IBU)',
  price: 'Цена',
  currency: 'Валюта',
  volume: 'Объём',
  format_type: 'Формат упаковки',
  stock: 'Остатки',
  supplier_name: 'Поставщик',
  description: 'Описание',
};

const FIELDS = Object.keys(FIELD_LABELS);

function SupplierSettings() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState(null);
  const [formName, setFormName] = useState('');
  const [formMapping, setFormMapping] = useState({});
  const [isCreating, setIsCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['suppliers'],
    queryFn: getSuppliers,
  });
  // API возвращает пагинированный ответ { results: [...] }
  const suppliers = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);

  const createMutation = useMutation({
    mutationFn: createSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success('Поставщик добавлен');
      setIsCreating(false);
      setFormName('');
      setFormMapping({});
    },
    onError: (err) => toast.error(err.response?.data?.name?.[0] || err.message || 'Ошибка создания'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateSupplier(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success('Настройки сохранены');
      setEditingId(null);
      setFormName('');
      setFormMapping({});
    },
    onError: (err) => toast.error(err.response?.data?.detail || err.message || 'Ошибка сохранения'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      toast.success('Поставщик удалён');
      setEditingId(null);
      setIsCreating(false);
    },
    onError: (err) => toast.error(err.message || 'Ошибка удаления'),
  });

  const startEdit = (supplier) => {
    setEditingId(supplier.id);
    setFormName(supplier.name);
    const mapping = {};
    FIELDS.forEach((f) => {
      const val = supplier.column_mapping?.[f];
      mapping[f] = Array.isArray(val) ? val.join(', ') : (val || '');
    });
    setFormMapping(mapping);
  };

  const startCreate = () => {
    setIsCreating(true);
    setEditingId(null);
    setFormName('');
    setFormMapping(FIELDS.reduce((acc, f) => ({ ...acc, [f]: '' }), {}));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setIsCreating(false);
    setFormName('');
    setFormMapping({});
  };

  const buildColumnMapping = () => {
    const out = {};
    FIELDS.forEach((f) => {
      const raw = (formMapping[f] || '').trim();
      if (!raw) return;
      const keywords = raw.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
      if (keywords.length) out[f] = keywords;
    });
    return out;
  };

  const handleSave = () => {
    const name = formName.trim();
    if (!name) {
      toast.error('Введите название поставщика');
      return;
    }
    const column_mapping = buildColumnMapping();
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: { name, column_mapping } });
    } else {
      createMutation.mutate({ name, column_mapping });
    }
  };

  const handleDelete = (id, name) => {
    if (!window.confirm(`Удалить поставщика «${name}»?`)) return;
    deleteMutation.mutate(id);
  };

  if (isLoading) {
    return <div className="supplier-settings-loading">Загрузка...</div>;
  }

  return (
    <div className="supplier-settings">
      <div className="supplier-settings-header">
        <h2>Настройки поставщиков</h2>
        <p className="supplier-settings-desc">
          Задайте ключевые слова для колонок — так парсер точнее сопоставит заголовки с полями. Например: для поля «Название пива» укажите «Имя» или «Название товара», если в прайсе колонка так называется.
        </p>
        {!isCreating && !editingId && (
          <button type="button" className="btn-add-supplier" onClick={startCreate}>
            + Добавить поставщика
          </button>
        )}
      </div>

      <div className="supplier-list">
        {suppliers.map((s) => (
          <div key={s.id} className="supplier-card">
            <div className="supplier-card-header">
              <span className="supplier-name">{s.name}</span>
              {editingId !== s.id && !isCreating && (
                <div className="supplier-card-actions">
                  <button type="button" className="btn-edit" onClick={() => startEdit(s)}>Редактировать</button>
                  <button type="button" className="btn-delete" onClick={() => handleDelete(s.id, s.name)}>Удалить</button>
                </div>
              )}
            </div>
            {(editingId === s.id || isCreating) && (
              <SupplierForm
                formName={formName}
                setFormName={setFormName}
                formMapping={formMapping}
                setFormMapping={setFormMapping}
                onSave={handleSave}
                onCancel={cancelEdit}
                saving={updateMutation.isPending || createMutation.isPending}
                isNew={isCreating}
              />
            )}
          </div>
        ))}
      </div>

      {isCreating && (
        <div className="supplier-card supplier-card-new">
          <SupplierForm
            formName={formName}
            setFormName={setFormName}
            formMapping={formMapping}
            setFormMapping={setFormMapping}
            onSave={handleSave}
            onCancel={cancelEdit}
            saving={createMutation.isPending}
            isNew
          />
        </div>
      )}
    </div>
  );
}

function SupplierForm({ formName, setFormName, formMapping, setFormMapping, onSave, onCancel, saving, isNew }) {
  return (
    <div className="supplier-form">
      <div className="form-row">
        <label>Название поставщика</label>
        <input
          type="text"
          value={formName}
          onChange={(e) => setFormName(e.target.value)}
          placeholder="Например: Парадокс, CBD"
        />
      </div>
      <div className="form-section">
        <p>Ключевые слова для колонок (через запятую — как в заголовках таблицы)</p>
        {FIELDS.map((field) => (
          <div key={field} className="form-row form-row-field">
            <label>{FIELD_LABELS[field]}</label>
            <input
              type="text"
              value={formMapping[field] || ''}
              onChange={(e) => setFormMapping((prev) => ({ ...prev, [field]: e.target.value }))}
              placeholder={`Например: ${field === 'beer_name' ? 'Имя, Название товара' : field === 'price' ? 'Цена за штуку, Стоимость' : ''}`}
            />
          </div>
        ))}
      </div>
      <div className="form-actions">
        <button type="button" className="btn-save" onClick={onSave} disabled={saving}>
          {saving ? 'Сохранение...' : isNew ? 'Создать' : 'Сохранить'}
        </button>
        <button type="button" className="btn-cancel" onClick={onCancel} disabled={saving}>
          Отмена
        </button>
      </div>
    </div>
  );
}

export default SupplierSettings;
