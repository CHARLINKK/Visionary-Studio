import { HELP_CATALOG } from '../data/helpInspectorCatalog';

/**
 * Fallback dinâmico detalhado para micro-elementos sem entrada estática.
 */
function buildDynamicElementEntry(el) {
  if (!el) return null;

  const tag = (el.tagName || '').toLowerCase();
  const titleAttr = (el.getAttribute('title') || el.getAttribute('aria-label') || '').trim();
  const placeholder = (el.getAttribute('placeholder') || '').trim();
  const rawText = (el.innerText || el.value || '').trim().split('\n')[0].slice(0, 70);

  let kindLabel = 'Controle de Interface';
  if (tag === 'button' || el.getAttribute('role') === 'button') kindLabel = 'Botão de Ação';
  else if (tag === 'input' && el.type === 'checkbox') kindLabel = 'Caixa de Marcação (Checkbox)';
  else if (tag === 'input' && el.type === 'number') kindLabel = 'Campo Numérico';
  else if (tag === 'input' && el.type === 'range') kindLabel = 'Controle Deslizante (Slider)';
  else if (tag === 'input') kindLabel = 'Campo de Entrada';
  else if (tag === 'select') kindLabel = 'Menu de Seleção (Dropdown)';
  else if (tag === 'textarea') kindLabel = 'Caixa de Texto';

  const displayTitle = rawText || titleAttr || placeholder || kindLabel;
  const summaryText = titleAttr && titleAttr !== rawText
    ? titleAttr
    : placeholder
      ? `Campo com valor sugerido: "${placeholder}".`
      : `${kindLabel} "${displayTitle}" da interface.`;

  return {
    id: `dynamic-${tag}-${displayTitle.slice(0, 20)}`,
    category: kindLabel,
    title: displayTitle,
    summary: summaryText,
    details: [
      'Clique fora do Modo Inspetor para acionar ou editar este campo normalmente.',
      'Use o seletor de camadas no topo para inspecionar o grupo ou painel onde este controle está inserido.'
    ],
    tip: 'Pressione Esc para fechar este pop-up ou sair do Modo Inspetor.'
  };
}

/**
 * Detecta se as coordenadas do cursor coincidem com um balão vetorial desenhado no Canvas Konva.
 * 
 * POR QUE ESTA RESOLUÇÃO É ESPECIAL:
 * O elemento <canvas> do HTML5 é uma superfície gráfica opaca para o DOM; APIs nativas do navegador
 * como 'document.elementFromPoint' enxergam apenas a tag <canvas>, sem saber o que está desenhado dentro.
 * Esta função quebra essa limitação do DOM:
 * 1. Consulta 'stage.getIntersection' para saber se o mouse intercepta uma forma vetorial do Konva.
 * 2. Fallback Geométrico: Caso a camada gráfica esteja sem listeners de evento, mapeia as coordenadas
 *    da tela para o espaço de zoom e pan da imagem (scaleX, stage.x/y) e calcula colisão matemática AABB
 *    contra os balões ativos ('__VISIONARY_ACTIVE_BOXES__').
 * Isso permite que o Inspetor de Ajuda exiba o guia contextual do balão mesmo dentro da arte do mangá.
 */
export function resolveKonvaCanvasBubble(coords) {
  if (typeof window === 'undefined' || !coords || typeof coords.x !== 'number') return null;
  const stage = window.__VISIONARY_KONVA_STAGE__;
  if (!stage || typeof stage.container !== 'function') return null;

  try {
    const stageContainer = stage.container();
    if (!stageContainer || typeof stageContainer.getBoundingClientRect !== 'function') return null;
    const stageBox = stageContainer.getBoundingClientRect();

    const pointerPos = {
      x: coords.x - stageBox.left,
      y: coords.y - stageBox.top,
    };

    if (
      pointerPos.x < 0 ||
      pointerPos.y < 0 ||
      pointerPos.x > stageBox.width ||
      pointerPos.y > stageBox.height
    ) {
      return null;
    }

    let boxId = null;
    if (typeof stage.getIntersection === 'function') {
      const shape = stage.getIntersection(pointerPos);
      if (shape) {
        let curr = shape;
        while (curr && curr !== stage) {
          const id = curr.id ? (typeof curr.id === 'function' ? curr.id() : curr.id) : null;
          if (id && typeof id === 'string' && id.startsWith('box-')) {
            boxId = id.replace('box-', '');
            break;
          }
          curr = curr.getParent ? curr.getParent() : null;
        }
      }
    }

    const boxes = window.__VISIONARY_ACTIVE_BOXES__ || [];
    let foundBox = null;
    let boxIndex = -1;

    if (boxId) {
      boxIndex = boxes.findIndex((b) => String(b.id) === String(boxId));
      if (boxIndex !== -1) foundBox = boxes[boxIndex];
    }

    // Fallback geométrico no espaço da imagem se o shape não tiver escuta ativa de eventos
    if (!foundBox && boxes.length > 0) {
      const scale = stage.scaleX ? stage.scaleX() : 1;
      const stageX = stage.x ? stage.x() : 0;
      const stageY = stage.y ? stage.y() : 0;

      const pageX = (pointerPos.x - stageX) / scale;
      const pageY = (pointerPos.y - stageY) / scale;

      let bestCandidate = null;
      let bestArea = Infinity;
      let bestIndex = -1;

      for (let i = boxes.length - 1; i >= 0; i--) {
        const b = boxes[i];
        const minX = Math.min(b.x1, b.x2);
        const maxX = Math.max(b.x1, b.x2);
        const minY = Math.min(b.y1, b.y2);
        const maxY = Math.max(b.y1, b.y2);

        if (pageX >= minX && pageX <= maxX && pageY >= minY && pageY <= maxY) {
          const area = Math.abs((maxX - minX) * (maxY - minY));
          if (area < bestArea) {
            bestArea = area;
            bestCandidate = b;
            bestIndex = i;
          }
        }
      }

      if (bestCandidate) {
        foundBox = bestCandidate;
        boxIndex = bestIndex;
      }
    }

    if (foundBox) {
      const isSfx = Boolean(foundBox.is_sfx || foundBox.isSfx);
      const orderNum = foundBox.order ?? (boxIndex + 1);
      const textPreview = foundBox.text ? `"${foundBox.text.slice(0, 45)}"` : '(Sem texto extraído)';
      const transPreview = foundBox.translated ? ` ➔ "${foundBox.translated.slice(0, 45)}"` : '';

      const scale = stage.scaleX ? stage.scaleX() : 1;
      const stageX = stage.x ? stage.x() : 0;
      const stageY = stage.y ? stage.y() : 0;
      const minX = Math.min(foundBox.x1, foundBox.x2) * scale + stageX + stageBox.left;
      const minY = Math.min(foundBox.y1, foundBox.y2) * scale + stageY + stageBox.top;
      const width = Math.abs(foundBox.x2 - foundBox.x1) * scale;
      const height = Math.abs(foundBox.y2 - foundBox.y1) * scale;

      const bubbleItem = {
        id: `canvas-bubble-${foundBox.id}`,
        bubbleId: foundBox.id,
        actionType: 'select-bubble',
        actionPayload: foundBox.id,
        actionLabel: 'Selecionar Balão no Estúdio',
        category: 'Canvas do Mangá • Balão Interativo',
        title: `Balão #${orderNum} (${isSfx ? 'Onomatopeia / SFX' : 'Balão de Diálogo'})`,
        shortcut: 'Duplo clique p/ vértices',
        summary: `Caixa delimitadora de texto: ${textPreview}${transPreview}. Dimensões: ${Math.round(Math.abs(foundBox.x2 - foundBox.x1))} × ${Math.round(Math.abs(foundBox.y2 - foundBox.y1))} px.`,
        details: [
          'Delimitação Geométrica: No Modo Layout, arraste ou redimensione os vértices para que o OCR englobe 100% dos caracteres em inglês sem cortar pontuações (... e ?!).',
          'Ordem Canônica (#): O crachá verde/azul indica a ordem de tradução do lote e a ordem de saída no arquivo de roteiro final.',
          'Classificação SFX: Se for um som desenhado na arte em vez de uma fala, marque com a ferramenta SFX (S) para exclusão do lote.'
        ],
        tip: 'Duplo clique no balão ativa o modo de edição de vértices orgânicos (Modo Polígono).'
      };

      return {
        item: bubbleItem,
        element: stageContainer,
        depth: 9999,
        priority: 150,
        customRect: {
          top: Math.round(minY),
          left: Math.round(minX),
          width: Math.round(Math.max(24, width)),
          height: Math.round(Math.max(24, height)),
          bottom: Math.round(minY + height),
          right: Math.round(minX + width),
        }
      };
    }
  } catch (_) {}

  return null;
}

/**
 * Recalcula as coordenadas de tela de um balão no Canvas Konva (útil durante resize ou scroll).
 */
export function computeKonvaBubbleRect(bubbleId) {
  if (typeof window === 'undefined' || !bubbleId) return null;
  const stage = window.__VISIONARY_KONVA_STAGE__;
  if (!stage || typeof stage.container !== 'function') return null;

  try {
    const stageContainer = stage.container();
    if (!stageContainer || typeof stageContainer.getBoundingClientRect !== 'function') return null;
    const stageBox = stageContainer.getBoundingClientRect();
    const boxes = window.__VISIONARY_ACTIVE_BOXES__ || [];
    const b = boxes.find((item) => String(item.id) === String(bubbleId));
    if (!b) return null;

    const scale = stage.scaleX ? stage.scaleX() : 1;
    const stageX = stage.x ? stage.x() : 0;
    const stageY = stage.y ? stage.y() : 0;
    const minX = Math.min(b.x1, b.x2) * scale + stageX + stageBox.left;
    const minY = Math.min(b.y1, b.y2) * scale + stageY + stageBox.top;
    const width = Math.abs(b.x2 - b.x1) * scale;
    const height = Math.abs(b.y2 - b.y1) * scale;

    return {
      top: Math.round(minY),
      left: Math.round(minX),
      width: Math.round(Math.max(24, width)),
      height: Math.round(Math.max(24, height)),
      bottom: Math.round(minY + height),
      right: Math.round(minX + width),
    };
  } catch (_) {
    return null;
  }
}

/**
 * Retorna toda a pilha hierárquica do elemento inspecionado, ordenada do mais interno (específico)
 * para o mais externo (painel amplo).
 */
export function resolveHelpStackForElement(targetEl, coords = null) {
  if (!targetEl || typeof targetEl.closest !== 'function') return [];

  if (
    targetEl.closest('.help-inspector-popover') ||
    targetEl.closest('.help-inspector-banner')
  ) {
    return [];
  }

  const getDomDepth = (node) => {
    let d = 0;
    let c = node;
    while (c && c.parentElement) {
      d++;
      c = c.parentElement;
    }
    return d;
  };

  const matchedLayers = [];
  const seenElements = new Set();

  // 1. Resolução cirúrgica de balões Konva dentro do Canvas
  if (coords && (targetEl.tagName === 'CANVAS' || targetEl.closest('.canvas-stage-wrapper') || targetEl.closest('.canvas-container'))) {
    const bubbleLayer = resolveKonvaCanvasBubble(coords);
    if (bubbleLayer) {
      matchedLayers.push(bubbleLayer);
    }
  }

  for (const item of HELP_CATALOG) {
    try {
      const matchedNode = targetEl.closest(item.selector);
      if (matchedNode) {
        const depth = getDomDepth(matchedNode);
        let layerItem = item;

        // Personalização dinâmica para cards de modelos LLM (exibe o nome real, proposta e dados técnicos do modelo)
        if (item.selector === '.native-model-card') {
          const titleEl = matchedNode.querySelector('.model-name-title');
          const descEl = matchedNode.querySelector('.model-desc-snippet');
          const versionEl = matchedNode.querySelector('.model-version-sub');
          const sizeEl = matchedNode.querySelector('.meta-size-chip');
          const vramEl = matchedNode.querySelector('.meta-vram-chip');
          const compatEl = matchedNode.querySelector('.meta-compat-tag');
          const isDownloaded = Boolean(matchedNode.classList.contains('installed-model'));
          const isActiveModel = Boolean(matchedNode.classList.contains('active-model'));

          const modelTitle = titleEl?.innerText?.trim();
          const modelDesc = descEl?.innerText?.trim();
          const version = versionEl?.innerText?.trim();
          const size = sizeEl?.innerText?.trim();
          const vram = vramEl?.innerText?.trim();
          const compat = compatEl?.innerText?.trim();

          if (modelTitle) {
            layerItem = {
              ...item,
              title: modelTitle,
              summary: modelDesc || 'Modelo neural executado localmente via Ollama para tradução adaptativa de mangás do inglês para o português.',
              details: [
                version ? `Arquitetura & Desenvolvedor: ${version}.` : 'Execução local via Ollama.',
                `Requisito de Memória: ${vram || 'VRAM'} · Compatibilidade com seu PC: ${compat || 'Detectado automaticamente'} (Tamanho no disco: ${size || 'Variável'}).`,
                isActiveModel
                  ? 'Status Ativo: Este é o modelo que está traduzindo os diálogos do Estúdio no momento.'
                  : isDownloaded
                    ? 'Status: Baixado no seu computador ("No HD"). Clique no botão "Usar" para defini-lo como tradutor ativo.'
                    : 'Status: Disponível no catálogo. Clique em "Baixar Modelo" para iniciar o download dos pesos em segundo plano.',
                'Privacidade Total: Executa 100% offline no seu computador sem enviar dados para a internet e sem custos de API.'
              ],
              tip: 'Modelos de 14B fornecem maior domínio de gírias e diálogos coloquiais naturais; modelos de 7B a 8B são mais ágeis para hardware modesto.'
            };
          }
        } else if (item.selector.includes('.pipeline-engine-card')) {
          const engineTitleEl = matchedNode.querySelector('.engine-title-text');
          const engineSubTypeEl = matchedNode.querySelector('.engine-sub-type');
          const engineDescEl = matchedNode.querySelector('.engine-description-text');
          const engineTitle = engineTitleEl?.innerText?.trim();
          const engineSub = engineSubTypeEl?.innerText?.trim();
          const engineDesc = engineDescEl?.innerText?.trim();

          if (engineTitle) {
            layerItem = {
              ...item,
              title: engineTitle,
              summary: engineDesc || item.summary,
              details: [
                engineSub ? `Especificação: ${engineSub}.` : 'Motor do pipeline neural.',
                ...item.details
              ]
            };
          }
        }

        matchedLayers.push({
          item: layerItem,
          element: matchedNode,
          depth,
          priority: item.priority || 50
        });
        seenElements.add(matchedNode);
      }
    } catch (_) {}
  }

  // Identifica micro-controles genuinamente interativos (botões, inputs, selects, links, sliders, abas)
  let microControl = targetEl.closest(
    'button, input, select, textarea, [role="button"], [role="tab"], [role="checkbox"], .modern-checkbox-card, a[href], .btn-icon-trash-subtle, .btn-model-action, .btn-utility-action, .btn-split-tool, .scale-btn, .density-btn, .font-specimen-btn, .swatch'
  );

  // Se não achou um controle explícito, verifica se há algum elemento com [title] interativo (botão, badge ou chip)
  if (!microControl) {
    const titled = targetEl.closest('[title], [aria-label]');
    if (titled) {
      const tTag = (titled.tagName || '').toLowerCase();
      const isPlainSnippetOrText =
        ['p', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code'].includes(tTag) &&
        !titled.classList.contains('btn') &&
        !titled.className.includes('btn') &&
        !titled.className.includes('action') &&
        !titled.className.includes('chip') &&
        !titled.className.includes('pill') &&
        !titled.className.includes('badge') &&
        !titled.getAttribute('onclick') &&
        !titled.getAttribute('role');

      // Se for apenas um parágrafo/snippet descritivo de texto com tooltip (ex: .model-desc-snippet),
      // IGNORA como micro-controle para que o clique selecione o card inteiro!
      if (!isPlainSnippetOrText) {
        microControl = titled;
      }
    }
  }

  if (microControl && !seenElements.has(microControl)) {
    const microDepth = getDomDepth(microControl);
    const deepestCatalogDepth = matchedLayers.length > 0
      ? Math.max(...matchedLayers.map((m) => m.depth))
      : -1;

    if (microDepth > deepestCatalogDepth) {
      const dynamicItem = buildDynamicElementEntry(microControl);
      if (dynamicItem) {
        matchedLayers.push({
          item: dynamicItem,
          element: microControl,
          depth: microDepth,
          priority: 97
        });
      }
    }
  }

  matchedLayers.sort((a, b) => {
    if (b.depth !== a.depth) return b.depth - a.depth;
    return b.priority - a.priority;
  });

  const uniqueByElement = [];
  const usedNodes = new Set();
  for (const layer of matchedLayers) {
    if (layer.customRect || !usedNodes.has(layer.element)) {
      if (!layer.customRect) usedNodes.add(layer.element);
      uniqueByElement.push(layer);
    }
  }

  return uniqueByElement;
}

export function resolveHelpItemForElement(targetEl) {
  const stack = resolveHelpStackForElement(targetEl);
  return stack.length > 0 ? stack[0] : null;
}
