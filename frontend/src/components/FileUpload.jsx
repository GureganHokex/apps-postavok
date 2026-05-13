/**
 * Компонент для загрузки файлов через drag&drop.
 */

import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  uploadFile,
  parseFile,
  getFileItems,
  getFileMetadata,
  getParseProgress,
  getApiErrorMessage,
} from '../api';
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
  const progressPollTimerRef = useRef(null);
  /** Подряд 502/503/504 от прокси Vercel→Render — для backoff и одного предупреждения пользователю. */
  const gatewayErrorStreakRef = useRef(0);
  const gatewayUserWarnedRef = useRef(false);
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
        const errorMsg = `Ошибка загрузки файла ${file.name}: ${getApiErrorMessage(err)}`;
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
    if (progressPollTimerRef.current) {
      clearTimeout(progressPollTimerRef.current);
      progressPollTimerRef.current = null;
    }
    gatewayErrorStreakRef.current = 0;
    gatewayUserWarnedRef.current = false;

    const stopProgressPolling = () => {
      if (progressPollTimerRef.current) {
        clearTimeout(progressPollTimerRef.current);
        progressPollTimerRef.current = null;
      }
    };

    /** Объявление выше assign — иначе scheduleProgressPoll ссылается на функцию до const (eslint no-undef). */
    let runProgressPoll;

    const scheduleProgressPoll = (delayMs) => {
      if (parseDoneRef.current) return;
      if (progressPollTimerRef.current) {
        clearTimeout(progressPollTimerRef.current);
      }
      progressPollTimerRef.current = setTimeout(() => {
        progressPollTimerRef.current = null;
        runProgressPoll();
      }, delayMs);
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

      // POST /parse/ — 202 «принято», итог по GET parse_progress/ (прогресс-бар) + finalize при completed.
      // 200 — только если backend когда-либо вернёт синхронный успех (локальная совместимость).
      parseFile(fileData.id, supplierInfo)
        .then(async (result) => {
          if (result?.accepted || result?.status === 'accepted') {
            return;
          }
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

      // Polling прогресса: setTimeout-цепочка (интервал меняется при 502/503/504 с прокси).
      let notStartedCount = 0;

      runProgressPoll = async () => {
        if (parseDoneRef.current) return;
        try {
          const progress = await getParseProgress(fileData.id);
          gatewayErrorStreakRef.current = 0;

          if (progress.status === 'not_started') {
            if (progress.is_running === false) {
              await finalizeParseSuccess(progress.total_items);
              return;
            }
            notStartedCount++;
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
            scheduleProgressPoll(550);
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
            return;
          }

          scheduleProgressPoll(550);
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

          const isGateway = status === 502 || status === 503 || status === 504;
          if (isGateway) {
            gatewayErrorStreakRef.current += 1;
            const streak = gatewayErrorStreakRef.current;
            const delayMs = Math.min(8000, Math.round(550 * 2 ** Math.min(streak - 1, 4)));
            if (streak === 1 || streak % 6 === 0) {
              console.warn('Progress polling (продолжаем ждать):', err.message || status || err);
            }
            if (streak >= 5 && !gatewayUserWarnedRef.current) {
              gatewayUserWarnedRef.current = true;
              setParseMessage(
                'Нестабильная связь с сервером (ошибка шлюза). Парсинг на backend может продолжаться — ' +
                  'обновите страницу и вкладку «Позиции». При частых сбоях: в Vercel задайте REACT_APP_FORCE_API_URL=1 и REACT_APP_API_URL на URL API Render (см. README).'
              );
              toast.error(
                'Шлюз Vercel→Render не отвечает на опрос прогресса. Подождите или обновите страницу; для стабильности — прямой REACT_APP_API_URL на Render.',
                { duration: 8000 }
              );
            }
            scheduleProgressPoll(delayMs);
            return;
          }

          gatewayErrorStreakRef.current = 0;
          console.warn('Progress polling (продолжаем ждать):', err.message || status || err);
          scheduleProgressPoll(550);
        }
      };

      scheduleProgressPoll(300);

      // Отключаем poll через 20 мин — снижаем нагрузку, если вкладка оставлена в подвешенном состоянии.
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

