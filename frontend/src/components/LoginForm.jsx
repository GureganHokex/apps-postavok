/**
 * Форма входа: логин и пароль.
 */
import React, { useState } from 'react';
import './LoginForm.css';

export default function LoginForm({ onSubmit, error, loading, title = 'Вход' }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(username, password);
  };

  return (
    <div className="login-form-wrap">
      <form className="login-form" onSubmit={handleSubmit}>
        <h2>{title}</h2>
        {error && <div className="login-form-error">{error}</div>}
        <label>
          Логин
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            disabled={loading}
            autoFocus
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={loading}
          />
        </label>
        <button type="submit" disabled={loading || !username.trim() || !password}>
          {loading ? 'Вход…' : 'Войти'}
        </button>
      </form>
    </div>
  );
}
