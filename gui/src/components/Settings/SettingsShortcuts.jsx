export function SettingsShortcuts() {
  return (
    <div className="settings-section shortcuts-section">
      <div className="shortcuts-settings-card">
        <div className="shortcuts-grid-quad">
          {/* 1. Estúdio & Canvas */}
          <div className="shortcuts-col">
            <div className="shortcuts-col-header">
              <span className="shortcuts-col-title">Estúdio & Canvas</span>
              <span className="shortcuts-col-desc">Ferramentas de delimitação, modos e manipulação de balões.</span>
            </div>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <span className="shortcut-desc">Ferramentas (V: Mover, P: Caneta, B: Caixa)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">V</kbd><kbd className="keycap">P</kbd><kbd className="keycap">B</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Alternar Fala ⇄ SFX (ou Ferramenta SFX)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">S</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Vincular balões (Link) ou Reordenar</span>
                <div className="keycap-combo">
                  <kbd className="keycap">L</kbd><span className="keycap-sep">ou</span><kbd className="keycap">R</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Alternar modos (1: Layout, 2: OCR, 3: Tradução)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">1</kbd><kbd className="keycap">2</kbd><kbd className="keycap">3</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Navegar entre balões</span>
                <div className="keycap-combo">
                  <kbd className="keycap">A</kbd><kbd className="keycap">D</kbd><span className="keycap-sep">ou</span><kbd className="keycap">←</kbd><kbd className="keycap">→</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Navegar entre páginas</span>
                <div className="keycap-combo">
                  <kbd className="keycap">↑</kbd><kbd className="keycap">↓</kbd><span className="keycap-sep">ou</span><kbd className="keycap">[</kbd><kbd className="keycap">]</kbd><span className="keycap-sep">ou</span><kbd className="keycap">PgUp</kbd><kbd className="keycap">PgDn</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Excluir balão selecionado</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Del</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Bksp</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Editar vértices do polígono / Concluir</span>
                <div className="keycap-combo">
                  <kbd className="keycap">2x Clique</kbd><span className="keycap-sep">/</span><kbd className="keycap">Esc</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Enquadrar tela / Alternar Auto-Zoom</span>
                <div className="keycap-combo">
                  <kbd className="keycap">F</kbd><span className="keycap-sep">ou</span><kbd className="keycap">0</kbd><span className="keycap-sep">/</span><kbd className="keycap">Z</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Salvar / Desfazer / Refazer alterações</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">S</kbd>
                  <span className="keycap-sep">/</span>
                  <kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">Z</kbd>
                  <span className="keycap-sep">/</span>
                  <kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">Y</kbd>
                </div>
              </div>
            </div>
          </div>

          {/* 2. Biblioteca & Letreiramento */}
          <div className="shortcuts-col">
            <div className="shortcuts-col-header">
              <span className="shortcuts-col-title">Biblioteca & Letreiramento</span>
              <span className="shortcuts-col-desc">Cópia contínua de falas, conferência e diagramação.</span>
            </div>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <span className="shortcut-desc">Copiar próximo balão</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Espaço</kbd><span className="keycap-sep">ou</span><kbd className="keycap">↓</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Recopiar balão atual</span>
                <div className="keycap-combo">
                  <kbd className="keycap">C</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">C</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Voltar ao balão anterior</span>
                <div className="keycap-combo">
                  <kbd className="keycap">↑</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Desfazer status de colado</span>
                <div className="keycap-combo">
                  <kbd className="keycap">U</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Bksp</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Navegar entre páginas</span>
                <div className="keycap-combo">
                  <kbd className="keycap">←</kbd><kbd className="keycap">→</kbd><span className="keycap-sep">ou</span><kbd className="keycap">[</kbd><kbd className="keycap">]</kbd><span className="keycap-sep">ou</span><kbd className="keycap">PgUp</kbd><kbd className="keycap">PgDn</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Localizar texto no roteiro</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">F</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Próxima / Anterior ocorrência (na busca)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Enter</kbd><span className="keycap-sep">/</span><kbd className="keycap">Shift</kbd><span className="keycap-plus">+</span><kbd className="keycap">Enter</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Editar tradução inline (Salvar / Cancelar)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">2x Clique</kbd><span className="keycap-sep">/</span><kbd className="keycap">Enter</kbd><span className="keycap-sep">/</span><kbd className="keycap">Esc</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Alternar Auto-Zoom no balão focado</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Z</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Zoom e Pan no painel da imagem</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Scroll</kbd><span className="keycap-sep">/</span><kbd className="keycap">Arrastar</kbd>
                </div>
              </div>
            </div>
          </div>

          {/* 3. Lightbox (Mesa de Luz) */}
          <div className="shortcuts-col">
            <div className="shortcuts-col-header">
              <span className="shortcuts-col-title">Mesa de Luz (Lightbox)</span>
              <span className="shortcuts-col-desc">Organização de spreads, seleção e conferência de páginas.</span>
            </div>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <span className="shortcut-desc">Pré-visualização rápida (Quick Look)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Espaço</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Navegar páginas no Quick Look</span>
                <div className="keycap-combo">
                  <kbd className="keycap">←</kbd><kbd className="keycap">→</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Abrir página selecionada no Estúdio</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Enter</kbd><span className="keycap-sep">ou</span><kbd className="keycap">2x Clique</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Selecionar todas as páginas</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">A</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Selecionar intervalo contínuo</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Shift</kbd><span className="keycap-plus">+</span><kbd className="keycap">Clique</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Excluir página(s) selecionada(s)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Del</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Ajustar tamanho da grade (Miniaturas)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">+</kbd><kbd className="keycap">-</kbd><span className="keycap-sep">ou</span><kbd className="keycap">Ctrl</kbd><span className="keycap-plus">+</span><kbd className="keycap">Scroll</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Fechar Quick Look / Limpar seleção</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Esc</kbd>
                </div>
              </div>
            </div>
          </div>

          {/* 4. Global & Sistema */}
          <div className="shortcuts-col">
            <div className="shortcuts-col-header">
              <span className="shortcuts-col-title">Global & Sistema</span>
              <span className="shortcuts-col-desc">Ajuda interativa, navegação geral e fechamento de janelas.</span>
            </div>
            <div className="shortcuts-list">
              <div className="shortcut-item">
                <span className="shortcut-desc">Inspetor Interativo de Ajuda</span>
                <div className="keycap-combo">
                  <kbd className="keycap">F1</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Interagir através do Inspetor de Ajuda</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Shift</kbd><span className="keycap-plus">+</span><kbd className="keycap">Clique</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Fechar modal, terminal ou desselecionar</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Esc</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Zoom suave no Canvas (Estúdio)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Scroll</kbd>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Pan livre no Canvas (modo Seleção)</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Arrastar</kbd><span className="keycap-sep">(fundo vazio)</span>
                </div>
              </div>
              <div className="shortcut-item">
                <span className="shortcut-desc">Confirmar ação em modais</span>
                <div className="keycap-combo">
                  <kbd className="keycap">Enter</kbd>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
