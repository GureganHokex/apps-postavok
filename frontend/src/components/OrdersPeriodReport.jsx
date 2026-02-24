/**
 * Отчёт по заказам за период: сумма, рост цен, по форматам (банки/кеги).
 * Используется на вкладке «Статистика» и при необходимости в «Истории заказов».
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getOrderStatistics } from '../api';
import './OrdersPeriodReport.css';

function formatDateOnly(isoDate) {
  if (!isoDate) return '—';
  const [y, m, d] = String(isoDate).split('-');
  return [d, m, y].filter(Boolean).join('.') || '—';
}

function toISO(date) {
  return date.toISOString().slice(0, 10);
}

const PRESETS = [
  { id: 'all', label: 'Всё время', getRange: () => ({ from: '', to: '' }) },
  {
    id: '2weeks',
    label: '2 недели',
    getRange: () => {
      const end = new Date();
      const start = new Date(end);
      start.setDate(start.getDate() - 14);
      return { from: toISO(start), to: toISO(end) };
    },
  },
  {
    id: 'month',
    label: 'Месяц',
    getRange: () => {
      const end = new Date();
      const start = new Date(end);
      start.setMonth(start.getMonth() - 1);
      return { from: toISO(start), to: toISO(end) };
    },
  },
  {
    id: 'quarter',
    label: 'Квартал',
    getRange: () => {
      const end = new Date();
      const start = new Date(end);
      start.setMonth(start.getMonth() - 3);
      return { from: toISO(start), to: toISO(end) };
    },
  },
  {
    id: 'halfyear',
    label: 'Полгода',
    getRange: () => {
      const end = new Date();
      const start = new Date(end);
      start.setMonth(start.getMonth() - 6);
      return { from: toISO(start), to: toISO(end) };
    },
  },
];

function OrdersPeriodReport() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedFormat, setSelectedFormat] = useState(null);

  const setPeriod = (from, to) => {
    setDateFrom(from);
    setDateTo(to);
  };

  const { data: stats, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['order-statistics', dateFrom || undefined, dateTo || undefined],
    queryFn: () =>
      getOrderStatistics({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    staleTime: 60000,
    retry: false,
  });

  return (
    <div className="OrdersPeriodReport">
      <h3>Статистика по заказам за период</h3>
      <div className="OrdersPeriodReport-filters">
        <div className="OrdersPeriodReport-presets">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              className="OrdersPeriodReport-preset"
              onClick={() => {
                const { from, to } = p.getRange();
                setPeriod(from, to);
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="OrdersPeriodReport-dates">
          <label className="OrdersPeriodReport-date-label">
            <span>От</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="input"
              aria-label="Дата начала периода"
            />
          </label>
          <label className="OrdersPeriodReport-date-label">
            <span>До</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="input"
              aria-label="Дата окончания периода"
            />
          </label>
        </div>
        <div className="OrdersPeriodReport-period-hint">
          Период: {dateFrom ? formatDateOnly(dateFrom) : 'все время'}
          {dateTo ? ` — ${formatDateOnly(dateTo)}` : ''}
        </div>
      </div>

      {(isLoading || isFetching) && (
        <div className="OrdersPeriodReport-loading">
          {isFetching && !isLoading ? 'Обновление...' : 'Загрузка статистики...'}
        </div>
      )}
      {error && (
        <div className="OrdersPeriodReport-error">
          <p>
            {error.response?.data?.detail ||
              (typeof error.message === 'string' ? error.message : null) ||
              'Не удалось загрузить статистику.'}
          </p>
          {error.response?.status === 404 ? (
            <p className="OrdersPeriodReport-error-hint">
              Эндпоинт /api/orders/statistics/ не найден. Убедитесь, что используется актуальная версия бэкенда.
            </p>
          ) : (
            <p className="OrdersPeriodReport-error-hint">
              Убедитесь, что бэкенд запущен на порту 8000:{' '}
              <code>cd backend && python manage.py runserver</code>
            </p>
          )}
          <button
            type="button"
            className="button button-secondary"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            Повторить
          </button>
        </div>
      )}
      {!isLoading && !error && stats && (
        <>
          <div className="OrdersPeriodReport-summary">
            <div className="OrdersPeriodReport-summary-item">
              <span className="OrdersPeriodReport-label">Заказов</span>
              <strong>{stats.total_orders}</strong>
            </div>
            <div className="OrdersPeriodReport-summary-item">
              <span className="OrdersPeriodReport-label">Позиций (шт)</span>
              <strong>{stats.total_positions}</strong>
            </div>
            <div className="OrdersPeriodReport-summary-item">
              <span className="OrdersPeriodReport-label">Средний чек (руб)</span>
              <strong>
                {Number(stats.average_order_sum || 0).toLocaleString('ru-RU')}
              </strong>
            </div>
          </div>

          <div className="OrdersPeriodReport-total">
            <strong>Сумма за период:</strong>{' '}
            {Number(stats.total_sum).toLocaleString('ru-RU')} ₽
            {stats.price_increase_sum != null && stats.price_increase_sum !== 0 && (
              <span
                className={
                  stats.price_increase_sum > 0
                    ? 'OrdersPeriodReport-price-increase'
                    : 'OrdersPeriodReport-price-decrease'
                }
              >
                {' '}
                ({stats.price_increase_sum > 0 ? '+' : ''}
                {Number(stats.price_increase_sum).toLocaleString('ru-RU')} ₽ за
                счёт изменения цен за период)
              </span>
            )}
            {stats.sum_at_period_start != null &&
              stats.sum_at_period_start > 0 && (
                <div className="OrdersPeriodReport-hint">
                  В ценах на начало периода:{' '}
                  {Number(stats.sum_at_period_start).toLocaleString('ru-RU')} ₽
                </div>
              )}
          </div>

          {stats.by_format && stats.by_format.length > 0 && (
            <section className="OrdersPeriodReport-section">
              <h4>По форматам (банки, кеги)</h4>
              <p className="OrdersPeriodReport-format-hint">
                Нажмите на название формата, чтобы открыть детальную статистику по позициям и поставщикам.
              </p>
              <div className="OrdersPeriodReport-table-wrap">
                <table className="OrdersPeriodReport-table">
                  <thead>
                    <tr>
                      <th>Формат</th>
                      <th>Кол-во, шт</th>
                      <th>Позиций</th>
                      <th>Сумма, руб</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.by_format.map((row, idx) => {
                      const hasDetail = stats.format_detail && stats.format_detail[row.format]?.length > 0;
                      return (
                        <tr key={row.format || idx}>
                          <td>
                            {hasDetail ? (
                              <button
                                type="button"
                                className="OrdersPeriodReport-format-link"
                                onClick={() => setSelectedFormat(row.format)}
                              >
                                {row.format}
                              </button>
                            ) : (
                              row.format
                            )}
                          </td>
                          <td>{row.quantity}</td>
                          <td>{row.count}</td>
                          <td>
                            {Number(row.sum || 0).toLocaleString('ru-RU')}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {selectedFormat && stats?.format_detail?.[selectedFormat] && (
            <section className="OrdersPeriodReport-detail">
              <div className="OrdersPeriodReport-detail-header">
                <h4>Статистика по формату: {selectedFormat}</h4>
                <button
                  type="button"
                  className="OrdersPeriodReport-detail-close"
                  onClick={() => setSelectedFormat(null)}
                  aria-label="Закрыть"
                >
                  ✕
                </button>
              </div>
              <div className="OrdersPeriodReport-table-wrap">
                <table className="OrdersPeriodReport-table OrdersPeriodReport-detail-table">
                  <thead>
                    <tr>
                      <th>Название</th>
                      <th>Поставщик</th>
                      <th>Заказано, шт</th>
                      <th>Сумма, руб</th>
                      <th>Была цена</th>
                      <th>Стала цена</th>
                      <th>Изменение, %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.format_detail[selectedFormat].map((row, idx) => (
                      <tr key={row.item_id ?? idx}>
                        <td>{row.name}</td>
                        <td>{row.supplier_name}</td>
                        <td>{row.quantity}</td>
                        <td>{Number(row.total_sum || 0).toLocaleString('ru-RU')}</td>
                        <td>{row.first_price != null ? row.first_price : '—'}</td>
                        <td>{row.last_price != null ? row.last_price : '—'}</td>
                        <td
                          className={
                            row.change_percent == null
                              ? ''
                              : row.change_percent > 0
                                ? 'OrdersPeriodReport-price-up'
                                : row.change_percent < 0
                                  ? 'OrdersPeriodReport-price-down'
                                  : ''
                          }
                        >
                          {row.change_percent != null
                            ? `${row.change_percent > 0 ? '+' : ''}${row.change_percent}%`
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

export default OrdersPeriodReport;
