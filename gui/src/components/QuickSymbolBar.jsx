import React from 'react';
import { Keyboard, ChevronDown, ChevronUp } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';

const SYMBOLS = ['…', '—', '♪', '!?', '?!', '“', '”', '♡', '★'];

/**
 * QuickSymbolBar Component
 * 
 * Barra flutuante de atalhos para símbolos matemáticos e caracteres especiais japoneses.
 * Fica ancorada na base da tela para facilitar transcrições em OCR.
 */
export default function QuickSymbolBar() {
  const quickSymbols = useWorkspaceStore((state) => state.quickSymbolsEnabled);
  const isOpen = useWorkspaceStore((state) => state.isQuickSymbolsOpen);
  const toggleQuickSymbols = useWorkspaceStore((state) => state.toggleQuickSymbols);

  if (!quickSymbols) return null;

  const handleSymbolClick = (e, sym) => {
    e.preventDefault();
    e.stopPropagation();
    
    try { navigator.clipboard.writeText(sym); } catch {}
    
    const active = document.activeElement;
    if (active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT')) {
      const start = active.selectionStart || 0;
      const end = active.selectionEnd || 0;
      const text = active.value || '';
      
      const newText = text.substring(0, start) + sym + text.substring(end);
      
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set
        || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
      
      if (nativeInputValueSetter) {
        nativeInputValueSetter.call(active, newText);
        active.dispatchEvent(new Event('input', { bubbles: true }));
        setTimeout(() => {
          active.focus();
          active.setSelectionRange(start + sym.length, start + sym.length);
        }, 0);
      }
    } else if (active && active.isContentEditable) {
      document.execCommand('insertText', false, sym);
    }
  };

  return (
    <div 
      className="quick-symbol-bar"
      style={{
        position: 'fixed',
        bottom: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 99999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        transformOrigin: 'bottom center'
      }}
    >
      <button 
        className="quick-symbol-toggle-btn"
        onClick={() => toggleQuickSymbols()}
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderBottom: 'none',
          borderRadius: '8px 8px 0 0',
          padding: '4px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          color: 'var(--text-dim)',
          cursor: 'pointer',
          boxShadow: '0 -2px 10px rgba(0,0,0,0.2)'
        }}
        title="Teclado Virtual de Símbolos"
      >
        <Keyboard size={14} />
        <span style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Símbolos</span>
        {isOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      <div 
        className="quick-symbol-drawer"
        style={{
          background: 'var(--bg-surface)',
          border: isOpen ? '1px solid var(--border-subtle)' : 'none',
          borderBottom: 'none',
          borderRadius: '12px 12px 0 0',
          padding: isOpen ? '12px 20px' : '0px 20px',
          display: 'flex',
          gap: '8px',
          boxShadow: isOpen ? '0 -10px 30px rgba(0,0,0,0.4)' : 'none',
          height: isOpen ? 'auto' : '0px',
          overflow: 'hidden',
          visibility: isOpen ? 'visible' : 'hidden',
          opacity: isOpen ? 1 : 0,
          transition: 'all 0.2s ease-in-out'
        }}
      >
        {SYMBOLS.map((sym) => (
          <button
            key={sym}
            type="button"
            className="quick-symbol-key"
            onMouseDown={(e) => handleSymbolClick(e, sym)}
            title={`Inserir caractere "${sym}"`}
            style={{
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-panel)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              color: 'var(--text-bright)',
              fontSize: '18px',
              fontWeight: '600',
              cursor: 'pointer',
              userSelect: 'none',
              transition: 'all 0.1s'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'var(--primary-color)';
              e.currentTarget.style.borderColor = 'var(--primary-color)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'var(--bg-panel)';
              e.currentTarget.style.borderColor = 'var(--border-subtle)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            {sym}
          </button>
        ))}
      </div>
    </div>
  );
}
