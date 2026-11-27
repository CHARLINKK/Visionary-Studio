import React, { useState, useEffect, useCallback } from 'react';
import {
  ChevronLeft, ChevronRight, X, Compass
} from 'lucide-react';

export const TOUR_STEPS = [
  {
    id: 'sidebar',
    tab: 'processamento',
    selector: '.app-sidebar',
    badge: 'Passo 1 de 8 • Navegação',
    title: 'Barra Lateral: Explorador e Capítulos',
    description:
      'Aqui você navega pelas pastas do seu PC. Quando uma pasta tem imagens de mangá, ela ganha ícone de livro aberto, etiqueta com total de páginas (ex: 24 págs) e uma bolinha de status:',
    bullets: [
      '🟢 Verde: Capítulo já traduzido e pronto.',
      '🟡 Amarelo: Capítulo em andamento (parcial).',
      '🔵 Azul: Pasta comum organizadora.',
      '💡 Dica: Quando você entra na aba Biblioteca, esta barra vira automaticamente a lista dos seus arquivos .txt!'
    ]
  },
  {
    id: 'tabs',
    tab: 'processamento',
    selector: '.top-tabs',
    badge: 'Passo 2 de 8 • Fluxo de Trabalho',
    title: 'As Abas Principais do Visionary Studio',
    description:
      'Toda a sua rotina segue a ordem natural destas abas no topo da janela:',
    bullets: [
      '1. Lightbox: Para unir páginas duplas cortadas ou reordenar arquivos antes de começar.',
      '2. Estúdio: Onde a IA detecta balões, lê o inglês (OCR) e traduz para português.',
      '3. Biblioteca: Mesa de letreiramento para copiar cada fala com 1 clique pro Photoshop/Clip Studio.',
      '4. Módulos & Configurações: Para gerenciar modelos de IA (7B/14B/32B), limpar VRAM e ajustar temas.'
    ]
  },
  {
    id: 'studio-main',
    tab: 'processamento',
    selector: '.studio-main',
    badge: 'Passo 3 de 8 • Aba Estúdio (Centro)',
    title: 'Canvas da Página e os 4 Modos do Editor',
    description:
      'No centro do Estúdio você visualiza a página do mangá e alterna entre os 4 modos na barra superior (ou pelas teclas 1, 2 e 3):',
    bullets: [
      '• Visualizar: Mostra o resumo da página, métricas e o botão "Ver Roteiro da Página (.txt)".',
      '• Layout (Tecla 1): Para ajustar o tamanho dos balões (+6px Margem), desenhar caixas novas (B ou Caneta P), vincular balões duplos (L), marcar SFX (S) e ajustar a Ordem de Leitura.',
      '• OCR (Tecla 2) e Tradução (Tecla 3): Para revisar o inglês extraído e editar a tradução em português (com botão "↺ Restaurar IA").'
    ]
  },
  {
    id: 'studio-batch',
    tab: 'processamento',
    selector: '.studio-batch-sidebar, .batch-sidebar',
    badge: 'Passo 4 de 8 • Aba Estúdio (Direita)',
    title: 'Processamento em Lote, Fila e Console (> _)',
    description:
      'Na coluna direita do Estúdio você automatiza o capítulo inteiro ou roda etapas separadas:',
    bullets: [
      '• Trilho de 3 Pontos: Ao lado de cada página, mostra se Layout (1º), OCR (2º) e Tradução (3º) estão prontos.',
      '• 3 Lixeiras (🗑 Tradução, 🗑 OCR, 🗑 Tudo): Apagam apenas a etapa escolhida nas páginas marcadas.',
      '• Botões ▶ Individuais: Permitem rodar só o Layout (com Filtro SFX), só o OCR ou só a Tradução.',
      '• Console de Execução (>_): Clique no ícone de terminal na Fila para ver o progresso, erros e o uso de VRAM ao vivo.'
    ]
  },
  {
    id: 'lightbox',
    tab: 'lightbox',
    selector: '.lightbox-unified-toolbar',
    badge: 'Passo 5 de 8 • Aba Lightbox',
    title: 'Lightbox: Costura de Páginas Duplas e Ordem',
    description:
      'Tem páginas duplas (spreads) que vieram divididas em dois arquivos? Prepare-as aqui antes de rodar a IA:',
    bullets: [
      '• Costura Mangá (Dir ➔ Esq) vs. Ocidental: Define de que lado cada página fica ao unir ou dividir.',
      '• Unir Páginas: Selecione 2 ou mais páginas e junte-as em uma única imagem horizontal.',
      '• Dividir: Selecione 1 página dupla para cortá-la exatamente ao meio na vertical.',
      '• Arrastar + Salvar Ordem: Arraste os cartões para reordenar e clique em "Salvar Ordem" para renomear os arquivos.'
    ]
  },
  {
    id: 'library',
    tab: 'biblioteca',
    selector: '.content-header, .library-container',
    badge: 'Passo 6 de 8 • Aba Biblioteca',
    title: 'Biblioteca: Hora de Letreirar com 1 Clique',
    description:
      'Com o capítulo traduzido, use a Biblioteca para copiar fala por fala para o seu editor de imagem:',
    bullets: [
      '• Menu Tipografia: Adiciona automaticamente Travessão (—), Reticências (…) ou CAIXA ALTA no momento da cópia.',
      '• Modo Lado a Lado: Mostra a imagem da página ao lado das falas — clique direto no balão da imagem para copiar!',
      '• Controle de Colados: Cada fala copiada (clique ou tecla Espaço) ganha o selo "✓ Colado". Use "Próxima Pendente" para nunca se perder.',
      '• Edição Rápida: Dê duplo clique em qualquer frase em português para corrigi-la ali mesmo!'
    ]
  },
  {
    id: 'modules',
    tab: 'modulos',
    selector: '.modules-container, .tab-content',
    badge: 'Passo 7 de 8 • Aba Módulos & IA',
    title: 'Central de Módulos, Modelos (7B/14B/32B) e VRAM',
    description:
      'Aqui você monitora sua Placa de Vídeo (GPU), processador e escolhe qual modelo de tradução usar:',
    bullets: [
      '• Motores Visuais: PyTorch Core (CUDA), Comic-YOLO (acha balões) e Florence-2 (lê o inglês).',
      '• Botão "Liberar VRAM": Descarrega a IA da placa de vídeo na hora — perfeito antes de abrir o Photoshop!',
      '• Amadeus Verbo 7B, 14B e 32B: Escolha o 7B para velocidade máxima em placas de 6–8 GB, 14B para equilíbrio ou 32B para fidelidade máxima.'
    ]
  },
  {
    id: 'settings',
    tab: 'configuracoes',
    selector: '.settings-top-nav-bar, .settings-container',
    badge: 'Passo 8 de 8 • Aba Configurações',
    title: 'Temas Visuais, Pasta Padrão e Bandeja do Sistema',
    description:
      'Personalize o Visionary Studio em 5 sub-abas:',
    bullets: [
      '• Interface (UX): 6 temas (incluindo Paperwhite claro para leitura longa e Cyber CAD OLED), fontes e cores.',
      '• Workflow & Pastas: Trave sua pasta raiz de mangás e ative o "Auto-Avanço de Página" na Biblioteca.',
      '• Áudio & Sistema: Configure o som de conclusão de lote e o comportamento do botão X (Bandeja do Sistema).'
    ]
  }
];

export function GuidedTourOverlay({
  isOpen,
  stepIndex,
  setStepIndex,
  onClose,
  setActiveTab,
  isSidebarOpen,
  setIsSidebarOpen
}) {
  const [targetRect, setTargetRect] = useState(null);
  const currentStep = TOUR_STEPS[stepIndex] || TOUR_STEPS[0];

  const updateHighlightRect = useCallback(() => {
    if (!isOpen || !currentStep) return;
    const selectors = currentStep.selector.split(',').map((s) => s.trim());
    let el = null;
    for (const sel of selectors) {
      const candidate = document.querySelector(sel);
      if (candidate && candidate.offsetWidth > 0 && candidate.offsetHeight > 0) {
        el = candidate;
        break;
      }
    }
    if (el) {
      const rect = el.getBoundingClientRect();
      setTargetRect({
        top: Math.max(4, rect.top - 4),
        left: Math.max(4, rect.left - 4),
        width: Math.min(window.innerWidth - 8, rect.width + 8),
        height: Math.min(window.innerHeight - 8, rect.height + 8)
      });
    } else {
      setTargetRect(null);
    }
  }, [isOpen, currentStep]);

  useEffect(() => {
    if (!isOpen || !currentStep) return;
    if (currentStep.id === 'sidebar' && !isSidebarOpen && setIsSidebarOpen) {
      setIsSidebarOpen(true);
    }
    if (currentStep.tab && setActiveTab) {
      setActiveTab(currentStep.tab);
    }
    const t1 = setTimeout(updateHighlightRect, 120);
    const t2 = setTimeout(updateHighlightRect, 350);
    window.addEventListener('resize', updateHighlightRect);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener('resize', updateHighlightRect);
    };
  }, [isOpen, stepIndex, currentStep, setActiveTab, isSidebarOpen, setIsSidebarOpen, updateHighlightRect]);

  if (!isOpen) return null;

  // Calcula posição inteligente do card explicativo para não cobrir a área destacada
  let cardStyle = {
    position: 'fixed',
    zIndex: 10002,
    width: '420px',
    maxWidth: 'calc(100vw - 32px)'
  };

  if (targetRect) {
    const spaceRight = window.innerWidth - (targetRect.left + targetRect.width);
    const spaceBottom = window.innerHeight - (targetRect.top + targetRect.height);

    if (spaceRight > 440) {
      cardStyle.left = `${targetRect.left + targetRect.width + 18}px`;
      cardStyle.top = `${Math.max(60, Math.min(window.innerHeight - 360, targetRect.top + 12))}px`;
    } else if (targetRect.left > 440) {
      cardStyle.left = `${targetRect.left - 438}px`;
      cardStyle.top = `${Math.max(60, Math.min(window.innerHeight - 360, targetRect.top + 12))}px`;
    } else if (spaceBottom > 290) {
      cardStyle.left = `${Math.max(20, Math.min(window.innerWidth - 440, targetRect.left + 20))}px`;
      cardStyle.top = `${targetRect.top + targetRect.height + 16}px`;
    } else {
      cardStyle.right = '28px';
      cardStyle.bottom = '28px';
    }
  } else {
    cardStyle.right = '28px';
    cardStyle.bottom = '28px';
  }

  return (
    <div className="guided-tour-root" style={{ position: 'fixed', inset: 0, zIndex: 10000, pointerEvents: 'none' }}>
      {/* Moldura Luminosa de Holofote ao redor do componente real */}
      {targetRect && (
        <div
          style={{
            position: 'fixed',
            top: `${targetRect.top}px`,
            left: `${targetRect.left}px`,
            width: `${targetRect.width}px`,
            height: `${targetRect.height}px`,
            borderRadius: '14px',
            border: '2px solid var(--brand-primary, #6366f1)',
            boxShadow: '0 0 0 9999px rgba(5, 7, 12, 0.68), 0 0 28px rgba(99, 102, 241, 0.65)',
            transition: 'all 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
            pointerEvents: 'none',
            zIndex: 10001
          }}
        />
      )}

      {/* Cartão Flutuante Didático */}
      <div
        style={{
          ...cardStyle,
          pointerEvents: 'auto',
          background: 'var(--bg-panel, #12141d)',
          border: '1px solid var(--brand-primary, #6366f1)',
          borderRadius: '16px',
          padding: '18px 20px',
          color: 'var(--text-main, #f8fafc)',
          boxShadow: '0 24px 48px rgba(0, 0, 0, 0.75)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: 800,
              background: 'rgba(99, 102, 241, 0.18)',
              color: 'var(--brand-primary, #818cf8)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em'
            }}
          >
            <Compass size={13} /> {currentStep.badge}
          </span>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted, #94a3b8)',
              cursor: 'pointer',
              padding: '4px'
            }}
            title="Encerrar Tour Guiado"
          >
            <X size={16} />
          </button>
        </div>

        <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '8px', color: 'var(--text-main, #fff)' }}>
          {currentStep.title}
        </h3>

        <p style={{ fontSize: '13px', lineHeight: 1.5, color: 'var(--text-secondary, #cbd5e1)', marginBottom: '12px' }}>
          {currentStep.description}
        </p>

        <div
          style={{
            background: 'var(--bg-surface, rgba(255,255,255,0.03))',
            border: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
            borderRadius: '10px',
            padding: '10px 12px',
            marginBottom: '14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px'
          }}
        >
          {currentStep.bullets.map((b, idx) => (
            <div key={idx} style={{ fontSize: '12px', lineHeight: 1.45, color: 'var(--text-main, #e2e8f0)' }}>
              {b}
            </div>
          ))}
        </div>

        {/* Barra de Progresso e Botões de Navegação do Tour */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
          <div style={{ display: 'flex', gap: '4px' }}>
            {TOUR_STEPS.map((st, idx) => (
              <button
                key={st.id}
                type="button"
                onClick={() => setStepIndex(idx)}
                title={st.title}
                style={{
                  width: idx === stepIndex ? '20px' : '8px',
                  height: '8px',
                  borderRadius: '999px',
                  border: 'none',
                  cursor: 'pointer',
                  background: idx === stepIndex ? 'var(--brand-primary, #6366f1)' : 'rgba(148, 163, 184, 0.3)',
                  transition: 'all 0.2s ease'
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setStepIndex(Math.max(0, stepIndex - 1))}
              disabled={stepIndex === 0}
              style={{ padding: '6px 10px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px', opacity: stepIndex === 0 ? 0.4 : 1 }}
            >
              <ChevronLeft size={14} /> Anterior
            </button>

            {stepIndex < TOUR_STEPS.length - 1 ? (
              <button
                type="button"
                className="btn-primary"
                onClick={() => setStepIndex(stepIndex + 1)}
                style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                Próximo <ChevronRight size={14} />
              </button>
            ) : (
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  onClose();
                  if (setActiveTab) setActiveTab('processamento');
                }}
                style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                Concluir Tour
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
export default GuidedTourOverlay;
