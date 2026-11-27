import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, BookOpen, Play, Sparkles, CornerDownRight, Layers } from 'lucide-react';
import { resolveHelpStackForElement, computeKonvaBubbleRect } from '../../data/helpInspectorCatalog';
import './HelpInspectorOverlay.css';

export function HelpInspectorOverlay({
  isActive,
  onClose,
  onOpenFullDocs,
  onSwitchTab,
}) {
  const [hoverInfo, setHoverInfo] = useState(null);
  const [selectedStack, setSelectedStack] = useState([]);
  const [selectedLayerIdx, setSelectedLayerIdx] = useState(0);
  const [clickCoords, setClickCoords] = useState({ x: 0, y: 0 });
  const popoverRef = useRef(null);

  const selectedInfo = selectedStack[selectedLayerIdx] || null;

  // Limpa estados ao ativar/desativar
  useEffect(() => {
    if (!isActive) {
      setHoverInfo(null);
      setSelectedStack([]);
      setSelectedLayerIdx(0);
      document.body.classList.remove('help-inspector-active');
      return;
    }
    document.body.classList.add('help-inspector-active');
    return () => {
      document.body.classList.remove('help-inspector-active');
    };
  }, [isActive]);

  const computeRect = useCallback((el) => {
    if (!el || typeof el.getBoundingClientRect !== 'function') return null;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return null;
    return {
      top: r.top,
      left: r.left,
      width: r.width,
      height: r.height,
      bottom: r.bottom,
      right: r.right,
    };
  }, []);

  useEffect(() => {
    if (!isActive) return;

    let rafId = null;

    const handleMouseMove = (e) => {
      const target = e.target;
      if (!target || typeof target.closest !== 'function') return;

      if (target.closest('.help-inspector-popover')) {
        setHoverInfo(null);
        return;
      }

      const coords = { x: e.clientX, y: e.clientY };

      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const stack = resolveHelpStackForElement(target, coords);
        if (stack.length > 0 && (stack[0].customRect || stack[0].element)) {
          const rect = stack[0].customRect || computeRect(stack[0].element);
          if (rect) {
            setHoverInfo({
              item: stack[0].item,
              rect,
              layersCount: stack.length,
            });
            return;
          }
        }
        setHoverInfo(null);
      });
    };

    const handleInterceptorClick = (e) => {
      const target = e.target;
      if (!target || typeof target.closest !== 'function') return;

      // Permite cliques normais dentro do pop-up
      if (target.closest('.help-inspector-popover')) {
        return;
      }

      // Se clicou no próprio botão '?' do topo para desligar o modo, deixa passar
      if (target.closest('[data-help-id="help-inspector-toggle"]')) {
        return;
      }

      // SHIFT + CLIQUE PASSTHROUGH:
      // Permite que o usuário segure Shift ao clicar para abrir menus suspensos,
      // selecionar opções ou alternar estados sem fechar nem ser interceptado pelo Modo Inspetor!
      if (e.shiftKey) {
        return;
      }

      // Bloqueia a execução real do botão/painel para apenas explicar
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') {
        e.stopImmediatePropagation();
      }

      const coords = { x: e.clientX, y: e.clientY };
      const stack = resolveHelpStackForElement(target, coords);
      if (stack.length > 0) {
        const enrichedStack = stack
          .map((layer) => ({
            ...layer,
            rect: layer.customRect || computeRect(layer.element),
          }))
          .filter((layer) => Boolean(layer.rect));

        if (enrichedStack.length > 0) {
          setClickCoords(coords);
          setSelectedStack(enrichedStack);
          setSelectedLayerIdx(0);
        }
      }
    };

    const blockSecondaryMouseEvents = (e) => {
      const target = e.target;
      if (!target || typeof target.closest !== 'function') return;
      if (
        e.shiftKey ||
        target.closest('.help-inspector-popover') ||
        target.closest('[data-help-id="help-inspector-toggle"]')
      ) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      if (typeof e.stopImmediatePropagation === 'function') {
        e.stopImmediatePropagation();
      }
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        if (selectedStack.length > 0) {
          setSelectedStack([]);
          setSelectedLayerIdx(0);
        } else {
          onClose();
        }
        return;
      }
      if (e.key !== 'F1' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        e.stopPropagation();
      }
    };

    const handleScrollOrResize = () => {
      if (selectedStack.length > 0) {
        setSelectedStack((prev) =>
          prev
            .map((layer) => {
              const freshKonvaRect = layer.item?.bubbleId
                ? computeKonvaBubbleRect(layer.item.bubbleId)
                : null;
              return {
                ...layer,
                rect: freshKonvaRect || layer.customRect || computeRect(layer.element),
              };
            })
            .filter((layer) => Boolean(layer.rect))
        );
      }
    };

    window.addEventListener('mousemove', handleMouseMove, true);
    window.addEventListener('click', handleInterceptorClick, true);
    window.addEventListener('mousedown', blockSecondaryMouseEvents, true);
    window.addEventListener('mouseup', blockSecondaryMouseEvents, true);
    window.addEventListener('dblclick', blockSecondaryMouseEvents, true);
    window.addEventListener('contextmenu', blockSecondaryMouseEvents, true);
    window.addEventListener('dragstart', blockSecondaryMouseEvents, true);
    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('resize', handleScrollOrResize, true);
    window.addEventListener('scroll', handleScrollOrResize, true);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener('mousemove', handleMouseMove, true);
      window.removeEventListener('click', handleInterceptorClick, true);
      window.removeEventListener('mousedown', blockSecondaryMouseEvents, true);
      window.removeEventListener('mouseup', blockSecondaryMouseEvents, true);
      window.removeEventListener('dblclick', blockSecondaryMouseEvents, true);
      window.removeEventListener('contextmenu', blockSecondaryMouseEvents, true);
      window.removeEventListener('dragstart', blockSecondaryMouseEvents, true);
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('resize', handleScrollOrResize, true);
      window.removeEventListener('scroll', handleScrollOrResize, true);
    };
  }, [isActive, selectedStack.length, computeRect, onClose]);

  if (!isActive) return null;

  // Calcula posição inteligente do Pop-up para nunca cortar fora da janela
  const getPopoverStyle = () => {
    if (!selectedInfo?.rect) return {};
    const r = selectedInfo.rect;
    const popW = 400;
    const popEstimatedH = selectedStack.length > 1 ? 360 : 310;
    const margin = 12;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let top = r.bottom + margin;
    let left = r.left;

    // Se o elemento selecionado for muito grande (ex: Card largo, Canvas ou Sidebar), ancora perto do clique
    if (r.width > 420 || r.height > 320) {
      left = (clickCoords.x || r.left + 40) + 16;
      top = (clickCoords.y || r.top + 40) - 20;
    }

    // Se estourar embaixo, abre acima do elemento ou do ponto de clique
    if (top + popEstimatedH > vh - 16) {
      if (r.height > 320 && clickCoords.y) {
        top = Math.max(54, clickCoords.y - popEstimatedH - margin);
      } else {
        top = Math.max(54, r.top - popEstimatedH - margin);
      }
    }

    // Se estourar na direita, recua para a esquerda
    if (left + popW > vw - 16) {
      left = Math.max(16, vw - popW - 16);
    }

    if (left < 16) left = 16;
    if (top < 54) top = 54;

    return {
      top: `${Math.round(top)}px`,
      left: `${Math.round(left)}px`,
      width: `${popW}px`,
    };
  };

  const handleExecuteRealAction = () => {
    if (!selectedInfo) return;
    const { item, element } = selectedInfo;

    // Se for uma aba de navegação principal, permite ir para a aba mantendo o Modo Inspetor ligado!
    if (item.actionType === 'switch-tab' && item.actionPayload && onSwitchTab) {
      onSwitchTab(item.actionPayload);
      setSelectedStack([]);
      setSelectedLayerIdx(0);
      return;
    }

    // Se for seleção de balão no Canvas Konva, aciona a seleção nativa no Estúdio
    if (item.actionType === 'select-bubble' && item.bubbleId) {
      if (typeof window.__VISIONARY_SELECT_BUBBLE__ === 'function') {
        window.__VISIONARY_SELECT_BUBBLE__(item.bubbleId);
      }
      onClose();
      return;
    }

    // Caso contrário, desativa o inspetor e clica no elemento real se desejar
    onClose();
    setTimeout(() => {
      if (element && typeof element.click === 'function') {
        element.click();
      }
    }, 30);
  };

  const isDropdownOrMenuTrigger = Boolean(
    selectedInfo?.element?.closest?.(
      '.dropdown-wrapper, .select-wrapper, .stitch-select-wrapper, .view-mode-selector, .active-model-pill-trigger, .theme-specimen-grid, .font-specimen-grid, .scale-toggle-group, .density-toggle-group, .quick-symbol-bar'
    ) ||
    selectedInfo?.item?.id?.includes('dropdown') ||
    selectedInfo?.item?.id?.includes('selector') ||
    selectedInfo?.item?.id?.includes('stitch-direction') ||
    selectedInfo?.item?.title?.toLowerCase().includes('seletor') ||
    selectedInfo?.item?.title?.toLowerCase().includes('menu') ||
    selectedInfo?.item?.title?.toLowerCase().includes('regras de formatação')
  );

  const handleOpenDropdownForInspection = () => {
    if (!selectedInfo?.element) return;
    const el = selectedInfo.element;
    const targetTrigger = el.querySelector('button, select, [role="button"]') || el;
    setSelectedStack([]);
    setSelectedLayerIdx(0);
    setTimeout(() => {
      if (targetTrigger && typeof targetTrigger.click === 'function') {
        targetTrigger.click();
      }
    }, 40);
  };

  const activeHighlight = selectedInfo?.rect || hoverInfo?.rect;
  const activeLabel = selectedInfo?.item?.title || hoverInfo?.item?.title;

  return (
    <div className="help-inspector-layer" aria-live="polite">
      {/* Moldura de Destaque no Elemento Apontado ou Clicado */}
      {activeHighlight && (
        <div
          className={`help-inspector-highlight ${selectedInfo ? 'is-locked' : 'is-hover'}`}
          style={{
            top: `${activeHighlight.top - 3}px`,
            left: `${activeHighlight.left - 3}px`,
            width: `${activeHighlight.width + 6}px`,
            height: `${activeHighlight.height + 6}px`,
          }}
        >
          {activeLabel && !selectedInfo && (
            <div
              className={`help-highlight-tag ${activeHighlight.top < 42 ? 'place-below' : ''} ${activeHighlight.left + 260 > window.innerWidth ? 'align-right' : ''}`}
            >
              <span>{activeLabel}</span>
              <span className="help-highlight-click-cta">
                {hoverInfo?.layersCount > 1
                  ? `Clique (${hoverInfo.layersCount} camadas)`
                  : 'Clique'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Pop-up Explicativo Contextual ao Clicar */}
      {selectedInfo && (
        <div
          ref={popoverRef}
          className="help-inspector-popover"
          style={getPopoverStyle()}
          role="dialog"
          aria-label={selectedInfo.item.title}
        >
          {/* Seletor de Camadas (Raio-X Hierárquico: Micro-elemento -> Card -> Painel) */}
          {selectedStack.length > 1 && (
            <div className="help-pop-layers-bar">
              <div className="help-pop-layers-label">
                <Layers size={11} />
                <span>Camadas neste ponto:</span>
              </div>
              <div className="help-pop-layers-pills">
                {selectedStack.slice(0, 4).map((layer, idx) => (
                  <button
                    key={layer.item.id + '-' + idx}
                    type="button"
                    className={`help-layer-pill ${idx === selectedLayerIdx ? 'active' : ''}`}
                    onClick={() => setSelectedLayerIdx(idx)}
                    title={`Inspecionar camada: ${layer.item.title}`}
                  >
                    <span className="layer-pill-num">{idx + 1}</span>
                    <span className="layer-pill-text">
                      {idx === 0 ? 'Item Exato' : idx === selectedStack.length - 1 ? 'Painel' : 'Container'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="help-pop-header">
            <div className="help-pop-meta">
              <span className="help-pop-category">{selectedInfo.item.category}</span>
              {selectedInfo.item.shortcut && (
                <kbd className="help-pop-kbd">{selectedInfo.item.shortcut}</kbd>
              )}
            </div>
            <button
              type="button"
              className="help-pop-close"
              onClick={() => {
                setSelectedStack([]);
                setSelectedLayerIdx(0);
              }}
              title="Fechar explicação (Esc)"
            >
              <X size={14} />
            </button>
          </div>

          <h3 className="help-pop-title">{selectedInfo.item.title}</h3>
          <p className="help-pop-summary">{selectedInfo.item.summary}</p>

          {Array.isArray(selectedInfo.item.details) && selectedInfo.item.details.length > 0 && (
            <ul className="help-pop-details">
              {selectedInfo.item.details.map((line, idx) => (
                <li key={idx}>
                  <CornerDownRight size={12} className="help-pop-bullet" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          )}

          {selectedInfo.item.tip && (
            <div className="help-pop-tip">
              <Sparkles size={13} className="help-pop-tip-icon" />
              <span>{selectedInfo.item.tip}</span>
            </div>
          )}

          <div className="help-pop-footer">
            {selectedInfo.item.actionType === 'switch-tab' ? (
              <button
                type="button"
                className="help-pop-btn primary"
                onClick={handleExecuteRealAction}
              >
                <Play size={11} fill="currentColor" />
                <span>{selectedInfo.item.actionLabel || 'Ir para esta Aba'} (Manter Inspetor)</span>
              </button>
            ) : selectedInfo.item.actionType === 'select-bubble' ? (
              <button
                type="button"
                className="help-pop-btn primary"
                onClick={handleExecuteRealAction}
                title="Seleciona este balão no Estúdio e foca suas propriedades"
              >
                <Play size={11} fill="currentColor" />
                <span>Selecionar Balão no Estúdio</span>
              </button>
            ) : isDropdownOrMenuTrigger ? (
              <button
                type="button"
                className="help-pop-btn primary"
                onClick={handleOpenDropdownForInspection}
                title="Abre as opções deste menu mantendo o Modo Inspetor ativo para você inspecionar os itens internos"
              >
                <Layers size={11} />
                <span>Abrir Menu (Inspecionar Opções)</span>
              </button>
            ) : (
              <button
                type="button"
                className="help-pop-btn secondary"
                onClick={handleExecuteRealAction}
                title="Sai do Modo Inspetor e aciona este controle"
              >
                <Play size={11} />
                <span>Sair e Acionar Controle</span>
              </button>
            )}

            {Boolean(onOpenFullDocs) && (
              <button
                type="button"
                className="help-pop-btn ghost"
                onClick={() => {
                  onClose();
                  if (onOpenFullDocs) onOpenFullDocs();
                }}
              >
                <BookOpen size={12} />
                <span>Ver Índice Completo</span>
              </button>
            )}
          </div>

          <div className="help-pop-shortcut-hint">
            <span>💡 Segure <strong>Shift</strong> ao clicar para interagir normalmente com menus sem fechar o Inspetor.</span>
          </div>
        </div>
      )}
    </div>
  );
}
export default HelpInspectorOverlay;
