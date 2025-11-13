/**
 * Компонент для отображения метаданных файла.
 */

import React from 'react';
import './MetadataTab.css';

function MetadataTab({ metadata }) {
  if (!metadata) {
    return <div className="loading">Метаданные не загружены</div>;
  }

  const contacts = metadata.contacts || {};
  const extraText = metadata.extra_text || [];
  const summary = metadata.summary || {};

  return (
    <div className="MetadataTab">
      <div className="card">
        <h2>Метаданные файла</h2>

        <div className="metadata-section">
          <h3>Статистика парсинга</h3>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="label">Всего позиций:</span>
              <span className="value">{summary.total_items || 0}</span>
            </div>
            <div className="summary-item">
              <span className="label">Отброшено строк:</span>
              <span className="value">{summary.skipped_rows || 0}</span>
            </div>
            {summary.contacts_found && (
              <>
                <div className="summary-item">
                  <span className="label">Найдено телефонов:</span>
                  <span className="value">{summary.contacts_found.phones || 0}</span>
                </div>
                <div className="summary-item">
                  <span className="label">Найдено email:</span>
                  <span className="value">{summary.contacts_found.emails || 0}</span>
                </div>
                <div className="summary-item">
                  <span className="label">Найдено адресов:</span>
                  <span className="value">{summary.contacts_found.addresses || 0}</span>
                </div>
                <div className="summary-item">
                  <span className="label">Найдено ссылок:</span>
                  <span className="value">{summary.contacts_found.links || 0}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="metadata-section">
          <h3>Контакты</h3>
          
          {contacts.phones && contacts.phones.length > 0 && (
            <div className="contact-group">
              <h4>Телефоны:</h4>
              <ul>
                {contacts.phones.map((phone, idx) => (
                  <li key={idx}>{phone}</li>
                ))}
              </ul>
            </div>
          )}

          {contacts.emails && contacts.emails.length > 0 && (
            <div className="contact-group">
              <h4>Email:</h4>
              <ul>
                {contacts.emails.map((email, idx) => (
                  <li key={idx}>
                    <a href={`mailto:${email}`}>{email}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {contacts.addresses && contacts.addresses.length > 0 && (
            <div className="contact-group">
              <h4>Адреса:</h4>
              <ul>
                {contacts.addresses.map((address, idx) => (
                  <li key={idx}>{address}</li>
                ))}
              </ul>
            </div>
          )}

          {contacts.links && contacts.links.length > 0 && (
            <div className="contact-group">
              <h4>Ссылки:</h4>
              <ul>
                {contacts.links.map((link, idx) => (
                  <li key={idx}>
                    <a href={link} target="_blank" rel="noopener noreferrer">
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(!contacts.phones || contacts.phones.length === 0) &&
           (!contacts.emails || contacts.emails.length === 0) &&
           (!contacts.addresses || contacts.addresses.length === 0) &&
           (!contacts.links || contacts.links.length === 0) && (
            <p className="empty">Контакты не найдены</p>
          )}
        </div>

        <div className="metadata-section">
          <h3>Служебные тексты</h3>
          {extraText.length > 0 ? (
            <ul className="extra-text-list">
              {extraText.map((text, idx) => (
                <li key={idx}>{text}</li>
              ))}
            </ul>
          ) : (
            <p className="empty">Служебные тексты не найдены</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default MetadataTab;

