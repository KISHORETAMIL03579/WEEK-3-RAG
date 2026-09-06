import React, { useState, useEffect } from 'react';
import { ChatPage } from './pages/ChatPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { ViewerPage } from './pages/ViewerPage';

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>(() =>
    typeof window !== 'undefined' ? window.location.pathname : '/'
  );

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  if (currentPath === '/eval') {
    return <EvaluationPage />;
  }

  if (currentPath.startsWith('/file/')) {
    const segments = currentPath.split('/');
    const docId = segments[2] ? decodeURIComponent(segments[2]) : undefined;
    return <ViewerPage initialDocId={docId} />;
  }

  return <ChatPage />;
};

export default App;

