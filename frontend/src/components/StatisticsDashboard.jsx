/**
 * Компонент дашборда со статистикой
 */

import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import ExportButton from './ExportButton';
import './StatisticsDashboard.css';

const COLORS = ['#3498db', '#27ae60', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c'];

function StatisticsDashboard({ items }) {
  // Статистика по пивоварням
  const breweryStats = useMemo(() => {
    const breweryCounts = {};
    items.forEach(item => {
      const brewery = item.brewery || 'Не указано';
      breweryCounts[brewery] = (breweryCounts[brewery] || 0) + 1;
    });

    return Object.entries(breweryCounts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [items]);

  // Статистика по стилям
  const styleStats = useMemo(() => {
    const styleCounts = {};
    items.forEach(item => {
      const style = item.style || 'Не указано';
      styleCounts[style] = (styleCounts[style] || 0) + 1;
    });

    return Object.entries(styleCounts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [items]);

  // Статистика по форматам
  const formatStats = useMemo(() => {
    const formatCounts = {};
    items.forEach(item => {
      const format = item.format_type || 'Не указано';
      formatCounts[format] = (formatCounts[format] || 0) + 1;
    });

    return Object.entries(formatCounts)
      .map(([name, value]) => ({ name, value }))
      .slice(0, 6);
  }, [items]);

  // Средняя цена
  const averagePrice = useMemo(() => {
    const prices = items
      .map(item => parseFloat(item.price))
      .filter(price => !isNaN(price) && price > 0);
    
    if (prices.length === 0) return 0;
    return prices.reduce((sum, price) => sum + price, 0) / prices.length;
  }, [items]);

  // Общая статистика
  const totalStats = useMemo(() => {
    const withPrice = items.filter(item => item.price && parseFloat(item.price) > 0).length;
    const withStock = items.filter(item => item.stock && item.stock !== '-').length;
    const withDescription = items.filter(item => item.description && item.description.trim()).length;

    return {
      total: items.length,
      withPrice,
      withStock,
      withDescription,
    };
  }, [items]);

  const exportData = useMemo(() => {
    return {
      summary: totalStats,
      averagePrice,
      breweryStats,
      styleStats,
      formatStats,
      generatedAt: new Date().toISOString(),
    };
  }, [totalStats, averagePrice, breweryStats, styleStats, formatStats]);

  const handleExportStats = () => {
    const dataStr = JSON.stringify(exportData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `statistics_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast.success('Статистика экспортирована');
  };

  return (
    <div className="StatisticsDashboard">
      <div className="card">
        <div className="statistics-header">
          <h2>Статистика</h2>
          <div className="statistics-actions">
            <button
              className="button button-secondary"
              onClick={handleExportStats}
            >
              Экспорт JSON
            </button>
            <ExportButton
              data={[
                { type: 'summary', ...totalStats, averagePrice },
                ...breweryStats.map(s => ({ type: 'brewery', ...s })),
                ...styleStats.map(s => ({ type: 'style', ...s })),
                ...formatStats.map(s => ({ type: 'format', ...s })),
              ]}
              filename={`statistics_${new Date().toISOString().split('T')[0]}`}
              formats={['csv', 'json']}
            />
          </div>
        </div>

        <div className="stats-grid">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="stat-card"
          >
            <div className="stat-icon">Σ</div>
            <div className="stat-content">
              <div className="stat-label">Всего позиций</div>
              <div className="stat-value">{totalStats.total}</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="stat-card"
          >
            <div className="stat-icon">₽</div>
            <div className="stat-content">
              <div className="stat-label">Средняя цена</div>
              <div className="stat-value">{averagePrice.toFixed(2)} ₽</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="stat-card"
          >
            <div className="stat-icon">Q</div>
            <div className="stat-content">
              <div className="stat-label">С остатками</div>
              <div className="stat-value">{totalStats.withStock}</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
            className="stat-card"
          >
            <div className="stat-icon">N</div>
            <div className="stat-content">
              <div className="stat-label">С описанием</div>
              <div className="stat-value">{totalStats.withDescription}</div>
            </div>
          </motion.div>
        </div>

        <div className="charts-grid">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="chart-card"
          >
            <h3>Топ пивоварен</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={breweryStats}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="name" 
                  angle={-45} 
                  textAnchor="end" 
                  height={100}
                  interval={0}
                  tick={{ fontSize: 12 }}
                />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill={COLORS[0]} />
              </BarChart>
            </ResponsiveContainer>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="chart-card"
          >
            <h3>Распределение по стилям</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={styleStats}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {styleStats.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="chart-card"
          >
            <h3>Распределение по форматам</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={formatStats} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={100} />
                <Tooltip />
                <Bar dataKey="value" fill={COLORS[2]} />
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

export default StatisticsDashboard;

