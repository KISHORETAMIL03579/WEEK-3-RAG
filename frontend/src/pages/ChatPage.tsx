import React, { useState, useEffect, useRef, useCallback } from 'react';
import { DocumentInfo, StagedFile } from '../types/document';
import { ToastContainer, ToastItem } from '../components/common/ToastContainer';
import { Topbar } from '../components/common/Topbar';
import { Sidebar } from '../components/Sidebar/Sidebar';
import { ChatArea, ChatMessage } from '../components/Chat/ChatArea';
import { api } from '../services/api';
import { generateId } from '../utils/helpers';

export const ChatPage: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.innerWidth > 700 : true
  );
  const [backendMode, setBackendMode] = useState<string>('');
  const [backendStatus, setBackendStatus] = useState<'checking' | 'healthy' | 'error'>('checking');
  const [retrievalMode, setRetrievalMode] = useState<string>('hybrid');
  const [files, setFiles] = useState<DocumentInfo[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<StagedFile[]>([]);
  const [strategy, setStrategy] = useState<string>('structured');
  const [strategySelected, setStrategySelected] = useState<boolean>(false);
  const [topK, setTopK] = useState<number>(8);
  const [temperature, setTemperature] = useState<number>(0.0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const activeAbortControllerRef = useRef<AbortController | null>(null);
  const toastTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const selectedFilesRef = useRef<StagedFile[]>(selectedFiles);

  useEffect(() => {
    selectedFilesRef.current = selectedFiles;
  }, [selectedFiles]);

  const dismissToast = useCallback((id: string) => {
    if (toastTimersRef.current.has(id)) {
      clearTimeout(toastTimersRef.current.get(id));
      toastTimersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: 'info' | 'success' | 'error' = 'info', duration = 5000) => {
      const id = generateId('toast');
      setToasts((prev) => [...prev, { id, message, type }]);
      if (duration > 0) {
        const timer = setTimeout(() => {
          dismissToast(id);
        }, duration);
        toastTimersRef.current.set(id, timer);
      }
    },
    [dismissToast]
  );

  // Clean up all toast timers on component unmount
  useEffect(() => {
    return () => {
      toastTimersRef.current.forEach((timer) => clearTimeout(timer));
      toastTimersRef.current.clear();
    };
  }, []);

  // Display toast after browser hard refresh
  useEffect(() => {
    const HARD_REFRESH_TOAST_KEY = 'ask-my-docs-hard-refresh';
    try {
      if (sessionStorage.getItem(HARD_REFRESH_TOAST_KEY) === '1') {
        sessionStorage.removeItem(HARD_REFRESH_TOAST_KEY);
        const timer = setTimeout(() => {
          showToast('↻ Hard refresh completed. Latest resources loaded.', 'success', 3500);
        }, 300);
        return () => clearTimeout(timer);
      }
    } catch {
      // Gracefully handle restricted storage
    }
  }, [showToast]);

  // Global key listener to detect hard refresh
  useEffect(() => {
    const HARD_REFRESH_TOAST_KEY = 'ask-my-docs-hard-refresh';
    const handleKeyDown = (event: KeyboardEvent) => {
      const isHardRefresh =
        (event.shiftKey && (event.ctrlKey || event.metaKey) && event.key && event.key.toLowerCase() === 'r') ||
        ((event.ctrlKey || event.shiftKey) && (event.key === 'F5' || event.code === 'F5'));

      if (isHardRefresh) {
        try {
          sessionStorage.setItem(HARD_REFRESH_TOAST_KEY, '1');
        } catch {
          // Gracefully handle storage errors
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Staged files lifecycle management with preview URLs
  const handleAddSelectedFiles = useCallback((rawFiles: File[]) => {
    const newItems: StagedFile[] = rawFiles.map((file) => ({
      id: generateId('staged'),
      file,
      name: file.name,
      previewUrl:
        typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : null,
    }));
    setSelectedFiles((prev) => [...prev, ...newItems]);
  }, []);

  const handleRemoveSelectedFile = useCallback((idToRemove: string) => {
    setSelectedFiles((prev) => {
      const target = prev.find((item) => item.id === idToRemove);
      if (target && target.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((item) => item.id !== idToRemove);
    });
  }, []);

  const handleClearSelectedFiles = useCallback(() => {
    setSelectedFiles((prev) => {
      prev.forEach((item) => {
        if (item.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
      return [];
    });
  }, []);

  // Cleanup all staged URLs on component unmount
  useEffect(() => {
    return () => {
      selectedFilesRef.current.forEach((item) => {
        if (item.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
    };
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.getStatus();
      setFiles(status.documents || []);
      if (status.vector_backend) setBackendMode(status.vector_backend);
      if (status.mode) setRetrievalMode(status.mode);
      setBackendStatus('healthy');
    } catch (err: unknown) {
      const e = err as Error;
      console.error('Failed to fetch status:', e);
      setBackendStatus('error');
      showToast('Could not connect to backend server: ' + e.message, 'error', 6000);
    }
  }, [showToast]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Synchronize Sidebar with Viewport Resize
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 700px)');
    const handleMediaChange = (e: MediaQueryListEvent) => {
      if (e.matches) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    if (mql.addEventListener) {
      mql.addEventListener('change', handleMediaChange);
    } else {
      mql.addListener(handleMediaChange);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarOpen && window.innerWidth <= 700) {
        setSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      if (mql.removeEventListener) {
        mql.removeEventListener('change', handleMediaChange);
      } else {
        mql.removeListener(handleMediaChange);
      }
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [sidebarOpen]);

  const handleUpload = async (stagedList: StagedFile[]) => {
    if (!stagedList || stagedList.length === 0 || isThinking || isUploading) return;
    setIsUploading(true);
    const formData = new FormData();
    stagedList.forEach((item) => formData.append('files', item.file));
    formData.append('chunk_mode', strategy);

    try {
      const res = await api.uploadFiles(formData);
      handleClearSelectedFiles();
      await fetchStatus();
      const failed = (res.documents || []).filter((d) => d.error);
      const degraded = (res.documents || []).filter((d) => d.warning);
      if (failed.length > 0) {
        showToast(
          `${failed.length} file(s) failed: ${failed.map((d) => d.filename + ' (' + d.error + ')').join(', ')}`,
          'error',
          7000
        );
      } else if (degraded.length > 0) {
        showToast(
          `${degraded.length} file(s) indexed with warnings: ${degraded.map((d) => d.filename).join(', ')}`,
          'info',
          6000
        );
      } else {
        showToast('Documents uploaded and indexed successfully!', 'success', 4000);
      }
    } catch (err: unknown) {
      const e = err as Error;
      showToast('Upload failed: ' + e.message, 'error', 6000);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadUrl = async (url: string) => {
    if (isThinking || isUploading) return;
    try {
      await api.loadUrl(url, strategy);
      await fetchStatus();
      showToast('Web page fetched and indexed successfully!', 'success', 4000);
    } catch (err: unknown) {
      const e = err as Error;
      showToast('Failed to load URL: ' + e.message, 'error', 6000);
    }
  };

  const handleRemoveDoc = async (doc_id: string) => {
    if (isThinking || isUploading) return;
    try {
      await api.removeDoc(doc_id);
      await fetchStatus();
      showToast('Document removed from index.', 'info', 3000);
    } catch (err: unknown) {
      const e = err as Error;
      showToast('Failed to remove document: ' + e.message, 'error', 6000);
    }
  };

  const handleClear = async () => {
    if (isThinking || isUploading) return;
    try {
      await api.clearSession();
      setMessages([]);
      await fetchStatus();
      showToast('All documents and chat history cleared.', 'info', 3000);
    } catch (err: unknown) {
      const e = err as Error;
      showToast('Failed to clear documents: ' + e.message, 'error', 6000);
    }
  };

  const handleSend = async (query: string) => {
    if (isThinking || isUploading) return;
    const userMsg: ChatMessage = { id: generateId('user-msg'), role: 'user', text: query };
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    const controller = new AbortController();
    activeAbortControllerRef.current = controller;

    try {
      const res = await api.askQuestion(query, strategy, topK, temperature, controller.signal);
      const aiMsg: ChatMessage = {
        id: generateId('ai-msg'),
        role: 'ai',
        text: res.answer || "I don't know.",
        sources: res.sources || [],
        query,
        topK: res.top_k != null ? res.top_k : topK,
        temperature: res.temperature != null ? res.temperature : temperature,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: unknown) {
      const e = err as Error;
      if (e.name === 'AbortError') {
        return;
      }
      setMessages((prev) => [
        ...prev,
        {
          id: generateId('err-msg'),
          role: 'ai',
          text: 'Error executing query: ' + e.message,
          topK,
          temperature,
        },
      ]);
      showToast('Query error: ' + e.message, 'error', 6000);
    } finally {
      setIsThinking(false);
      activeAbortControllerRef.current = null;
    }
  };

  return (
    <div className={`layout ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <Topbar
        backendMode={backendMode}
        backendStatus={backendStatus}
        docsCount={files.length}
        retrievalMode={retrievalMode}
        topK={topK}
        temperature={temperature}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <div
        className="sidebar-backdrop"
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />
      <Sidebar
        strategy={strategy}
        setStrategy={setStrategy}
        setStrategySelected={setStrategySelected}
        topK={topK}
        setTopK={setTopK}
        temperature={temperature}
        setTemperature={setTemperature}
        files={files}
        onUpload={handleUpload}
        onLoadUrl={handleLoadUrl}
        onRemoveDoc={handleRemoveDoc}
        onClear={handleClear}
        isUploading={isUploading}
        isThinking={isThinking}
        selectedFiles={selectedFiles}
        onAddSelectedFiles={handleAddSelectedFiles}
        onRemoveSelectedFile={handleRemoveSelectedFile}
        onClearSelectedFiles={handleClearSelectedFiles}
      />
      <ChatArea
        messages={messages}
        onSend={handleSend}
        isThinking={isThinking}
        filesCount={files.length}
        selectedFilesCount={selectedFiles.length}
        strategy={strategy}
        strategySelected={strategySelected}
      />
    </div>
  );
};

