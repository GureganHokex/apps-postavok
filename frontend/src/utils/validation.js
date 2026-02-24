/**
 * Схемы валидации с использованием Zod
 */

import { z } from 'zod';

// Схема валидации для позиции пива
export const beerItemSchema = z.object({
  brewery: z.string().min(1, 'Пивоварня обязательна').max(100, 'Слишком длинное название'),
  beer_name: z.string().min(1, 'Название пива обязательно').max(200, 'Слишком длинное название'),
  style: z.string().max(100, 'Слишком длинный стиль').optional(),
  abv: z.string().regex(/^\d+([.,]\d+)?$/, 'Некорректное значение крепости').optional(),
  ibu: z.string().max(10).optional(),
  price: z.string().regex(/^\d+([.,]\d+)?$/, 'Некорректная цена').optional(),
  currency: z.string().length(3, 'Валюта должна быть 3 символа').optional(),
  volume: z.string().regex(/^\d+([.,]\d+)?$/, 'Некорректный объем').optional(),
  format_type: z.string().max(50).optional(),
  stock: z.string().max(50).optional(),
  description: z.string().max(1000, 'Описание слишком длинное').optional(),
});

// Схема валидации для количества в заказе
export const quantitySchema = z.object({
  quantity: z.number().int().min(1, 'Количество должно быть больше 0').max(10000, 'Слишком большое количество'),
});

// Схема валидации для фильтров
export const filterSchema = z.object({
  brewery: z.string().max(100).optional(),
  beer_name: z.string().max(200).optional(),
  style: z.string().max(100).optional(),
});

