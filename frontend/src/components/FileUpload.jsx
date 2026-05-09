/**
 * Компонент для загрузки файлов через drag&drop.
 */

import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { uploadFile, parseFile, getFileItems, getFileMetadata, getParseProgress } from '../api';
import { ParseProgress } from './ParseProgress';
import SupplierTypeModal from './SupplierTypeModal';
import './FileUpload.css';

function FileUpload({ onFileUploaded, onParseComplete }) {
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parseMessage, setParseMessage] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [showSupplierModal, setShowSupplierModal] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const progressIntervalRef = useRef(null);
  /** Защита от двойного завершения: и по polling, и по ответу POST /parse/. */
  const parseDoneRef = useRef(false);

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
        
        // Показываем модальное окно для выбора типа поставщика
        if (filesToProcess.length > 0) {
          setPendingFile(filesToProcess[0]);
          setShowSupplierModal(true);
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

  const handleSupplierConfirm = (info) => {
    setShowSupplierModal(false);
    if (pendingFile) {
      handleParse(pendingFile, info);
    }
  };

  const handleParse = async (fileData, supplierInfo = null) => {
    parseDoneRef.current = false;
    // Очищаем предыдущий interval если есть
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }

    const stopProgressPolling = () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };

    const finalizeParseSuccess = async (totalItemsHint) => {
      if (parseDoneRef.current) return;
      parseDoneRef.current = true;
      stopProgressPolling();
      try {
        setParseProgress(90);
        setParseMessage('Загрузка позиций...');

        const itemsResponse = await getFileItems(fileData.id);
        const itemsData = Array.isArray(itemsResponse)
          ? itemsResponse
          : (itemsResponse.results || itemsResponse.items || []);
        setParseProgress(95);
        setParseMessage('Загрузка метаданных...');

        let metadataData = null;
        try {
          metadataData = await getFileMetadata(fileData.id);
        } catch {
          // метаданные опциональны
        }

        setParseProgress(100);
        setParseMessage('Завершено!');

        const count = totalItemsHint ?? itemsData.length;
        const successMsg = `Парсинг завершен. Найдено позиций: ${count}`;
        toast.success(successMsg);
        setSuccess(successMsg);

        if (onFileUploaded) {
          onFileUploaded(fileData);
        }
        if (onParseComplete) {
          onParseComplete({ items_created: count }, itemsData, metadataData);
        }

        setTimeout(() => {
          setParsing(false);
          setParseProgress(0);
          setParseMessage('');
        }, 1000);
      } catch (e) {
        parseDoneRef.current = true;
        stopProgressPolling();
        setParsing(false);
        const msg = e?.message || 'Ошибка после парсинга';
        setError(msg);
        toast.error(msg);
      }
    };

    try {
      setParsing(true);
      setError(null);
      setParseProgress(0);
      setParseMessage('Запуск парсинга...');

      window.parseStartTime = Date.now();

      // Главный сценарий: успешный POST /parse/ уже значит «парсинг на сервере завершён» (см. backend views).
      // Polling только для прогресс-бара; при сбоях GET UI всё равно дойдёт до конца по этому promise.
      parseFile(fileData.id, supplierInfo)
        .then(async (result) => {
          await finalizeParseSuccess(result?.items_created);
        })
        .catch((err) => {
          stopProgressPolling();
          if (parseDoneRef.current) return;
          parseDoneRef.current = true;
          setParsing(false);
          const msg =
            err.response?.data?.error ||
            err.response?.data?.detail ||
            err.message ||
            'Ошибка парсинга';
          setError(msg);
          toast.error(msg);
        });

      // Polling для получения прогресса
      let notStartedCount = 0;
      progressIntervalRef.current = setInterval(async () => {
        if (parseDoneRef.current) return;
        try {
          const progress = await getParseProgress(fileData.id);

          if (progress.status === 'not_started') {
            notStartedCount++;
            // Долгий POST на одном воркере: not_started может держаться минуты — не обрываем через 3 с.
            if (notStartedCount > 600) {
              stopProgressPolling();
              if (!parseDoneRef.current) {
                parseDoneRef.current = true;
                setParsing(false);
                setError('Парсинг не запустился. Проверьте консоль браузера на наличие ошибок.');
                toast.error('Парсинг не запустился');
              }
              return;
            }
            return;
          }

          notStartedCount = 0;

          setParseProgress(progress.progress || 0);
          setParseMessage(progress.message || 'Обработка...');

          if (progress.status === 'completed' || progress.status === 'error') {
            if (progress.status === 'completed') {
              await finalizeParseSuccess(progress.total_items);
            } else if (progress.status === 'error') {
              if (parseDoneRef.current) return;
              parseDoneRef.current = true;
              stopProgressPolling();
              setParsing(false);
              setError(progress.message || 'Ошибка парсинга');
              toast.error(progress.message || 'Ошибка парсинга');
            }
          }
        } catch (err) {
          const status = err.response?.status;
          if (status === 404) {
            stopProgressPolling();
            if (!parseDoneRef.current) {
              parseDoneRef.current = true;
              setParsing(false);
              setError('Файл не найден');
              toast.error('Файл не найден');
            }
            return;
          }
          console.warn('Progress polling (продолжаем ждать):', err.message || status || err);
        }
      }, 500);

      // Только отключаем poll через 20 мин — итог всё равно придёт по POST /parse/ (таймаут в api.js).
      setTimeout(() => {
        if (parseDoneRef.current) return;
        stopProgressPolling();
      }, 1200000);
    } catch (err) {
      const errorMsg = `Ошибка парсинга: ${err.message}`;
      toast.error(errorMsg);
      setError(errorMsg);
      setParsing(false);
      setParseProgress(0);
      setParseMessage('');
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
      <SupplierTypeModal
        isOpen={showSupplierModal}
        fileName={pendingFile?.original_filename}
        onConfirm={handleSupplierConfirm}
        onCancel={() => {
          setShowSupplierModal(false);
          setPendingFile(null);
        }}
      />
      <ParseProgress
        isVisible={parsing}
        progress={parseProgress}
        message={parseMessage}
      />
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

