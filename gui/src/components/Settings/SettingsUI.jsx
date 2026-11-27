import { Check, Layers, Monitor, RotateCcw } from 'lucide-react';
import { ModernCheckbox } from './ModernCheckbox';

export function SettingsUI({ 
  theme, setTheme, accent, setAccent, uiScale, setUiScale,
  uiDensity, setUiDensity, fontFamily, setFontFamily,
  acrylicBlur, setAcrylicBlur, reduceMotion, setReduceMotion,
  handleResetUiDefaults
}) {
  const accentColors = [
    { id: 'purple', label: 'Roxo (Padrão)', color: '#8b5cf6' },
    { id: 'blue', label: 'Azul Elétrico', color: '#3b82f6' },
    { id: 'cyan', label: 'Ciano Cyber', color: '#06b6d4' },
    { id: 'green', label: 'Verde Esmeralda', color: '#10b981' },
    { id: 'orange', label: 'Laranja Solar', color: '#f59e0b' },
    { id: 'pink', label: 'Rosa Sakura', color: '#ec4899' },
    { id: 'red', label: 'Vermelho Carmim', color: '#ef4444' },
    { id: 'white', label: 'Branco Puro', color: '#ffffff' },
    { id: 'black', label: 'Preto Puro', color: '#000000' },
  ];

  return (
    <div className="settings-section ui-section">
      <div className="ui-settings-card">
        {document.documentElement.getAttribute('data-theme') === 'dev-matrix' && (
          <div className="dev-noir-notice">
            <span className="dev-noir-badge">MODO NOIR ATIVO</span>
            <span>Visual monocromático de alta fidelidade em execução. As preferências de tema e cor abaixo ficam salvas para o retorno ao modo padrão.</span>
          </div>
        )}

        <div className="ui-group-block">
          <div className="ui-group-header">
            <span className="ui-group-title">Arquitetura & Tema do Estúdio</span>
            <span className="ui-group-desc">Altera cores, geometria de cantos, sombras, textura dos painéis e padrão do canvas</span>
          </div>
          <div className="theme-specimen-grid">
            {[
              { id: 'Dark',      label: 'Pro Studio',      trait: 'Vidro & Pílula',     desc: 'Escuro profissional com acrílico sutil e cantos suaves', tone: 'dark' },
              { id: 'WarmPaper', label: 'Paperwhite',      trait: 'Papel & Nanquim',    desc: 'Off-white suave com nanquim profundo para leitura longa sem fadiga visual', tone: 'warm' },
              { id: 'OLED',      label: 'Cyber CAD',       trait: '0px & Blueprint',    desc: 'Preto absoluto OLED com cantos vivos e grade técnica CAD', tone: 'oled' },
              { id: 'EInk',      label: 'E-Ink Matte',     trait: '100% Fosco',         desc: 'Grafite fosco sem glow nem gradientes para leitura longa', tone: 'eink' },
              { id: 'NeoTokyo',  label: 'Neo-Tokyo',       trait: 'HUD Sci-Fi',         desc: 'Azul-abissal noturno com marcadores angulares e grade cyber', tone: 'neotokyo' },
              { id: 'Light',     label: 'Estúdio Neutro',  trait: 'Linear & Figma',     desc: 'Claro moderno e neutro de alto contraste inspirado no Figma e Linear', tone: 'light' },
            ].map(t => (
              <button
                key={t.id}
                className={`theme-specimen-btn ${theme === t.id ? 'active' : ''}`}
                onClick={() => setTheme(t.id)}
                title={t.desc}
              >
                <div className={`theme-viewport-mini tone-${t.tone}`}>
                  <div className="mini-sidebar" />
                  <div className="mini-content">
                    <div className="mini-bar-title" />
                    <div className="mini-bar-accent" />
                  </div>
                </div>
                <div className="theme-specimen-Captions">
                  <span className="theme-specimen-name">{t.label}</span>
                  <span className="theme-specimen-trait">{t.trait}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="ui-card-divider" />

        <div className="ui-group-block">
          <div className="ui-group-header">
            <span className="ui-group-title">Família Tipográfica</span>
            <span className="ui-group-desc">Tipografia dos menus, cabeçalhos, réguas e ferramentas</span>
          </div>
          <div className="font-specimen-grid">
            {[
              { id: 'modern', label: 'Inter Moderno', desc: 'Sans-serif geométrica de alta legibilidade', sample: 'Aa 123' },
              { id: 'system', label: 'Windows Segoe', desc: 'Tipografia nativa e fluida do sistema', sample: 'Aa 123' },
              { id: 'tech',   label: 'JetBrains Mono', desc: 'Monospaçada técnica de alta precisão', sample: '0x1F Aa' },
            ].map(f => (
              <button
                key={f.id}
                className={`font-specimen-btn ${fontFamily === f.id ? 'active' : ''}`}
                onClick={() => setFontFamily(f.id)}
                data-font-preview={f.id}
              >
                <div className="font-specimen-preview">{f.sample}</div>
                <div className="font-specimen-meta">
                  <span className="font-specimen-name">{f.label}</span>
                  <span className="font-specimen-desc">{f.desc}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="ui-card-divider" />

        <div className="ui-bottom-grid">
          <div className="ui-sub-col">
            <div className="ui-sub-header">
              <span className="ui-group-title">Ergonomia & Escala</span>
              <span className="ui-group-desc">Ajuste o zoom e a densidade para o seu monitor</span>
            </div>

            <div className="ui-control-row">
              <div className="ui-control-label">
                <strong>Zoom da Interface</strong>
                <span>Escala global de renderização</span>
              </div>
              <div className="scale-toggle-group">
                {['90%', '100%', '110%', '120%'].map(s => (
                  <button
                    key={s}
                    className={`scale-btn ${uiScale === s ? 'active' : ''}`}
                    onClick={() => setUiScale(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="ui-control-row">
              <div className="ui-control-label">
                <strong>Densidade de Menus</strong>
                <span>Espaçamento de linhas e listas</span>
              </div>
              <div className="density-toggle-group">
                <button 
                  className={`density-btn ${uiDensity === 'comfortable' ? 'active' : ''}`}
                  onClick={() => setUiDensity('comfortable')}
                >
                  <Monitor size={13} /> Confortável
                </button>
                <button 
                  className={`density-btn ${uiDensity === 'compact' ? 'active' : ''}`}
                  onClick={() => setUiDensity('compact')}
                >
                  <Layers size={13} /> Compacta
                </button>
              </div>
            </div>
          </div>

          <div className="ui-sub-col">
            <div className="ui-sub-header">
              <span className="ui-group-title">Cor de Destaque & Tokens</span>
              <span className="ui-group-desc">Cor ativa: {accent}</span>
            </div>

            <div className="accent-swatches">
              {accentColors.map(a => (
                <button
                  key={a.id}
                  className={`swatch ${accent === a.label || accent === a.color ? 'active' : ''}`}
                  style={{ background: a.color }}
                  title={a.label}
                  onClick={() => setAccent(a.label)}
                >
                  {(accent === a.label || accent === a.color) && <Check size={14} className="swatch-check" />}
                </button>
              ))}
              
              <label 
                className={`swatch custom-swatch ${accent.startsWith('#') && !accentColors.some(a => a.color === accent || a.label === accent) ? 'active' : ''}`}
                title="Cor Personalizada (RGB)"
              >
                <input
                  type="color"
                  className="color-input-hidden"
                  value={accent.startsWith('#') ? accent : '#ffffff'}
                  onChange={(e) => setAccent(e.target.value)}
                />
                {accent.startsWith('#') && !accentColors.some(a => a.color === accent || a.label === accent) && (
                  <Check size={14} className="swatch-check" style={{ pointerEvents: 'none' }} />
                )}
              </label>
            </div>

            <div className="ui-tokens-preview-bar">
              <button className="preview-btn-sample">
                <Check size={12} /> Ação Primária
              </button>
              <div className="preview-tab-sample">
                <span className="preview-dot-sample" />
                <span>Aba Ativa</span>
              </div>
              <span className="preview-badge-sample">Foco Ativo</span>
              <div className="preview-toggle-sample" title="Alternador de estado">
                <div className="preview-toggle-knob" />
              </div>
            </div>
          </div>
        </div>

        <div className="ui-card-divider" />

        <div className="ui-bottom-grid">
          <div className="ui-sub-col">
            <div className="ui-sub-header">
              <span className="ui-group-title">Renderização & Fluidez</span>
              <span className="ui-group-desc">Aceleração visual e responsividade das animações</span>
            </div>

            <div className="modern-checkboxes-stack">
              <ModernCheckbox
                checked={acrylicBlur}
                onChange={setAcrylicBlur}
                label="Efeito Vidro Acrílico"
                description="Desfoque translúcido nos painéis suspensos. Desative para fundo sólido."
                badge="Visual"
              />
              <ModernCheckbox
                checked={reduceMotion}
                onChange={setReduceMotion}
                label="Reduzir Animações (Interface Ágil)"
                description="Suprime microanimações para máxima rapidez e resposta."
                badge="Desempenho"
              />
            </div>
          </div>

          <div className="ui-sub-col">
            <div className="ui-sub-header">
              <span className="ui-group-title">Restauração de Preferências</span>
              <span className="ui-group-desc">Reverte aparência e notificações para os valores originais</span>
            </div>

            <div className="audio-reset-box">
              <div className="audio-reset-info">
                <span className="audio-reset-title">Padrões de Fábrica</span>
                <span className="audio-reset-desc">
                  Restaura tema, tipografia, escala, densidade, efeitos visuais, áudio e notificações.
                </span>
              </div>
              <button className="audio-btn-reset" onClick={handleResetUiDefaults} title="Restaurar padrões de fábrica">
                <RotateCcw size={13} />
                <span>Restaurar Padrões</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
