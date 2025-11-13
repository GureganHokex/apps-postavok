/**
 * Компонент для загрузки файлов через drag&drop.
 */

import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadFile, parseFile, getFileItems, getFileMetadata } from '../api';
import './FileUpload.css';

function FileUpload({ onFileUploaded, onParseComplete }) {
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);

  const onDrop = async (acceptedFiles) => {
    setError(null);
    setSuccess(null);

    for (const file of acceptedFiles) {
      try {
        setUploading(true);
        
        // Загружаем файл
        const fileData = await uploadFile(file);
        
        // Если файл загружен как массив (ZIP), обрабатываем каждый
        const filesToProcess = Array.isArray(fileData) ? fileData : [fileData];
        setUploadedFiles(filesToProcess);
        
        setSuccess(`Файл ${file.name} успешно загружен`);
        
        // Автоматически запускаем парсинг для первого файла
        if (filesToProcess.length > 0) {
          await handleParse(filesToProcess[0]);
        }
      } catch (err) {
        setError(`Ошибка загрузки файла ${file.name}: ${err.message}`);
      } finally {
        setUploading(false);
      }
    }
  };

  const handleParse = async (fileData) => {
    try {
      setParsing(true);
      setError(null);
      
      // Запускаем парсинг
      const parseResult = await parseFile(fileData.id);
      
      // Получаем распарсенные позиции
      const itemsData = await getFileItems(fileData.id);
      
      // Получаем метаданные
      let metadataData = null;
      try {
        metadataData = await getFileMetadata(fileData.id);
      } catch (err) {
        // Метаданные могут отсутствовать, если парсинг не завершился
      }
      
      setSuccess(`Парсинг завершен. Найдено позиций: ${parseResult.items_created}`);
      
      // Уведомляем родительский компонент
      if (onFileUploaded) {
        onFileUploaded(fileData);
      }
      if (onParseComplete) {
        onParseComplete(parseResult, itemsData, metadataData);
      }
    } catch (err) {
      setError(`Ошибка парсинга: ${err.message}`);
    } finally {
      setParsing(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/zip': ['.zip'],
    },
    multiple: true,
  });

  return (
    <div className="FileUpload">
      <div className="card">
        <h2>Загрузка файлов</h2>
        <p>Поддерживаемые форматы: PDF, Excel (.xls, .xlsx), ZIP архивы</p>
        
        <div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? 'active' : ''} ${uploading || parsing ? 'disabled' : ''}`}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <p>Загрузка файла...</p>
          ) : parsing ? (
            <p>Парсинг файла...</p>
          ) : isDragActive ? (
            <p>Отпустите файл для загрузки</p>
          ) : (
            <p>Перетащите файлы сюда или нажмите для выбора</p>
          )}
        </div>

        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}

        {uploadedFiles.length > 0 && (
          <div className="uploaded-files">
            <h3>Загруженные файлы:</h3>
            {uploadedFiles.map((file) => (
              <div key={file.id} className="file-item">
                <span>{file.original_filename}</span>
                <span className="file-type">{file.file_type}</span>
                <button
                  className="button button-primary"
                  onClick={() => handleParse(file)}
                  disabled={parsing}
                >
                  {parsing ? 'Парсинг...' : 'Парсить'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default FileUpload;

