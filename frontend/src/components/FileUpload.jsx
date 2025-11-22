/**
 * Компонент для загрузки файлов через drag&drop.
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
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
        
        toast.success(`Файл ${file.name} успешно загружен`);
        setSuccess(`Файл ${file.name} успешно загружен`);
        
        // Автоматически запускаем парсинг для первого файла
        if (filesToProcess.length > 0) {
          await handleParse(filesToProcess[0]);
        }
      } catch (err) {
        const errorMsg = `Ошибка загрузки файла ${file.name}: ${err.message}`;
        toast.error(errorMsg);
        setError(errorMsg);
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
      
      const successMsg = `Парсинг завершен. Найдено позиций: ${parseResult.items_created}`;
      toast.success(successMsg);
      setSuccess(successMsg);
      
      // Уведомляем родительский компонент
      if (onFileUploaded) {
        onFileUploaded(fileData);
      }
      if (onParseComplete) {
        onParseComplete(parseResult, itemsData, metadataData);
      }
    } catch (err) {
      const errorMsg = `Ошибка парсинга: ${err.message}`;
      toast.error(errorMsg);
      setError(errorMsg);
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
        
        <motion.div
          {...getRootProps()}
          className={`dropzone ${isDragActive ? 'active' : ''} ${uploading || parsing ? 'disabled' : ''}`}
          whileHover={!uploading && !parsing ? { scale: 1.02 } : {}}
          whileTap={!uploading && !parsing ? { scale: 0.98 } : {}}
          animate={isDragActive ? { 
            scale: 1.05,
            boxShadow: '0 0 0 4px rgba(52, 152, 219, 0.2)'
          } : {}}
        >
          <input {...getInputProps()} />
          <motion.p
            key={uploading ? 'uploading' : parsing ? 'parsing' : isDragActive ? 'active' : 'default'}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            {uploading ? 'Загрузка файла...' : 
             parsing ? 'Парсинг файла...' : 
             isDragActive ? 'Отпустите файл для загрузки' : 
             'Перетащите файлы сюда или нажмите для выбора'}
          </motion.p>
        </motion.div>

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

