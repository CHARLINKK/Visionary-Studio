import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';
import { ToastProvider } from './contexts/ToastContext.jsx';
import { ErrorBoundary } from './components/ErrorBoundary.jsx';
import { installUniversalBridge } from './api/bridge.js';

installUniversalBridge();

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(
    <StrictMode>
      <ToastProvider>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </ToastProvider>
    </StrictMode>
  );
}
