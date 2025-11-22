/**
 * Компонент перетаскиваемого элемента заказа
 */

import React from 'react';
import { useDrag } from 'react-dnd';
import { motion } from 'framer-motion';

const ItemType = 'ORDER_ITEM';

function DraggableOrderItem({ item, index, onQuantityChange, quantity, quantityErrors }) {
  const [{ isDragging }, drag] = useDrag({
    type: ItemType,
    item: { id: item.id, index },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  return (
    <motion.tr
      ref={drag}
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: isDragging ? 0.5 : 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className={isDragging ? 'dragging' : ''}
    >
      <td>{item.brewery || '-'}</td>
      <td>{item.beer_name || '-'}</td>
      <td>{item.style || '-'}</td>
      <td>{item.price || '-'}</td>
      <td>{item.currency || '-'}</td>
      <td>{item.volume || '-'}</td>
      <td>{item.format_type || '-'}</td>
      <td>
        <div className="quantity-input-wrapper">
          <input
            type="number"
            min="0"
            max="10000"
            value={quantity}
            onChange={(e) => onQuantityChange(item.id, e.target.value)}
            className={`input input-small ${quantityErrors[item.id] ? 'input-error' : ''}`}
            aria-label={`Количество для ${item.beer_name || item.id}`}
          />
          {quantityErrors[item.id] && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="input-error-message"
            >
              {quantityErrors[item.id]}
            </motion.div>
          )}
        </div>
      </td>
      <td className="sum">{(quantity * (parseFloat(item.price) || 0)).toFixed(2)}</td>
    </motion.tr>
  );
}

export default DraggableOrderItem;

