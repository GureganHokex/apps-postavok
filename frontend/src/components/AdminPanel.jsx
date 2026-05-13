/**
 * Страница админ-панели: управление пользователями (добавление, роли, имена, удаление).
 * Доступна только администратору по маршруту /admin.
 */
import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getUsers, createUser, updateUser, deleteUser } from '../api';
import { useIsMobile } from '../hooks/useBreakpoint';
import './AdminPanel.css';

const ROLE_LABELS = { admin: 'Администратор', bartender: 'Бармен', user: 'Пользователь' };

export default function AdminPanel() {
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    username: '',
    password: '',
    role: 'user',
    first_name: '',
    last_name: '',
    email: '',
  });
  const [editForm, setEditForm] = useState({ role: '', first_name: '', last_name: '', email: '', password: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });
  const users = Array.isArray(data) ? data : (data?.results ?? []);

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Пользователь создан');
      setFormOpen(false);
      setForm({ username: '', password: '', role: 'user', first_name: '', last_name: '', email: '' });
    },
    onError: (err) => {
      const msg = err.response?.data?.username?.[0] || err.response?.data?.password?.[0] || err.response?.data?.detail || err.message;
      toast.error(msg || 'Ошибка создания');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Изменения сохранены');
      setEditingId(null);
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || err.message;
      toast.error(msg || 'Ошибка сохранения');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Пользователь удалён');
    },
    onError: (err) => {
      const msg = err.response?.data?.error || err.response?.data?.detail || err.message;
      toast.error(msg || 'Ошибка удаления');
    },
  });

  const handleCreateSubmit = (e) => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) {
      toast.error('Укажите логин и пароль');
      return;
    }
    createMutation.mutate({
      username: form.username.trim(),
      password: form.password,
      role: form.role,
      first_name: (form.first_name || '').trim(),
      last_name: (form.last_name || '').trim(),
      email: (form.email || '').trim(),
    });
  };

  const startEdit = useCallback((u) => {
    setEditingId(u.id);
    setEditForm({
      role: u.role || 'user',
      first_name: u.first_name || '',
      last_name: u.last_name || '',
      email: u.email || '',
      password: '',
    });
  }, []);

  const handleEditSubmit = (e) => {
    e.preventDefault();
    const payload = {
      role: editForm.role,
      first_name: editForm.first_name.trim(),
      last_name: editForm.last_name.trim(),
      email: editForm.email.trim(),
    };
    if (editForm.password) payload.password = editForm.password;
    updateMutation.mutate({ id: editingId, data: payload });
  };

  const handleDelete = (id, username) => {
    if (!window.confirm(`Удалить пользователя «${username}»?`)) return;
    deleteMutation.mutate(id);
  };

  if (isLoading) return <div className="admin-panel-loading">Загрузка пользователей…</div>;

  return (
    <div className="admin-panel">
      <div className="admin-panel-header">
        <h2>Управление пользователями</h2>
        <button type="button" className="admin-panel-btn-add" onClick={() => setFormOpen(true)}>
          + Добавить пользователя
        </button>
      </div>

      {formOpen && (
        <form className="admin-panel-form" onSubmit={handleCreateSubmit}>
          <h3>Новый пользователь</h3>
          <div className="admin-panel-form-grid">
            <label>
              Логин *
              <input
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                required
                autoComplete="off"
              />
            </label>
            <label>
              Пароль *
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                required
                autoComplete="new-password"
              />
            </label>
            <label>
              Роль
              <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                {Object.entries(ROLE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              Имя
              <input
                value={form.first_name}
                onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
                placeholder="Имя"
              />
            </label>
            <label>
              Фамилия
              <input
                value={form.last_name}
                onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
                placeholder="Фамилия"
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="email@example.com"
              />
            </label>
          </div>
          <div className="admin-panel-form-actions">
            <button type="submit" disabled={createMutation.isPending}>Создать</button>
            <button type="button" onClick={() => setFormOpen(false)}>Отмена</button>
          </div>
        </form>
      )}

      {/*
        * Адаптивный рендер списка:
        * - десктоп/планшет — обычная таблица;
        * - мобильный — карточки с label/value.
        * Форма редактирования вынесена в renderEditForm()
        * чтобы не дублировать JSX между двумя ветками.
        */}
      {(() => {
        const renderEditForm = () => (
          <form className="admin-panel-edit-form" onSubmit={handleEditSubmit}>
            <div className="admin-panel-form-grid">
              <label>
                Роль
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
                >
                  {Object.entries(ROLE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </label>
              <label>
                Имя
                <input
                  value={editForm.first_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
                />
              </label>
              <label>
                Фамилия
                <input
                  value={editForm.last_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
                />
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                />
              </label>
              <label>
                Новый пароль (оставьте пустым, чтобы не менять)
                <input
                  type="password"
                  value={editForm.password}
                  onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="Не менять"
                  autoComplete="new-password"
                />
              </label>
            </div>
            <div className="admin-panel-form-actions">
              <button type="submit" disabled={updateMutation.isPending}>Сохранить</button>
              <button type="button" onClick={() => setEditingId(null)}>Отмена</button>
            </div>
          </form>
        );

        if (isMobile) {
          return (
            <div className="admin-panel-cards">
              {users.map((u) => (
                <div key={u.id} className="admin-panel-card">
                  {editingId === u.id ? (
                    renderEditForm()
                  ) : (
                    <>
                      <div className="admin-panel-card-header">
                        <span className="admin-panel-card-title">{u.username}</span>
                        <span className={`admin-panel-role-badge admin-panel-role-badge--${u.role}`}>
                          {ROLE_LABELS[u.role] || u.role}
                        </span>
                      </div>
                      <dl className="admin-panel-card-fields">
                        <div>
                          <dt>Имя</dt>
                          <dd>{u.first_name || '—'}</dd>
                        </div>
                        <div>
                          <dt>Фамилия</dt>
                          <dd>{u.last_name || '—'}</dd>
                        </div>
                        <div className="admin-panel-card-fields__full">
                          <dt>Email</dt>
                          <dd>{u.email || '—'}</dd>
                        </div>
                      </dl>
                      <div className="admin-panel-card-actions">
                        <button type="button" className="admin-panel-btn-edit" onClick={() => startEdit(u)}>
                          Изменить
                        </button>
                        <button type="button" className="admin-panel-btn-delete" onClick={() => handleDelete(u.id, u.username)}>
                          Удалить
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {users.length === 0 && (
                <div className="admin-panel-empty">Пользователи не найдены</div>
              )}
            </div>
          );
        }

        return (
          <div className="admin-panel-table-wrap">
            <table className="admin-panel-table">
              <thead>
                <tr>
                  <th>Логин</th>
                  <th>Имя</th>
                  <th>Фамилия</th>
                  <th>Email</th>
                  <th>Роль</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    {editingId === u.id ? (
                      <td colSpan={6}>{renderEditForm()}</td>
                    ) : (
                      <>
                        <td>{u.username}</td>
                        <td>{u.first_name || '—'}</td>
                        <td>{u.last_name || '—'}</td>
                        <td>{u.email || '—'}</td>
                        <td>{ROLE_LABELS[u.role] || u.role}</td>
                        <td>
                          <button type="button" className="admin-panel-btn-edit" onClick={() => startEdit(u)}>Изменить</button>
                          <button type="button" className="admin-panel-btn-delete" onClick={() => handleDelete(u.id, u.username)}>Удалить</button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}
    </div>
  );
}
