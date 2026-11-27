import { Volume1, Volume2, Bell } from 'lucide-react';
import { ModernCheckbox } from './ModernCheckbox';
import { playChime } from '../../utils/sound';
import { sendNativeNotification } from '../../utils/notification';

export function SettingsAudio({
  soundFeedback, setSoundFeedback,
  soundStyle, setSoundStyleState,
  soundVolume, setSoundVolumeState,
  systemNotifications, setSystemNotifications,
  notifyOnlyInBackgroundState, setNotifyOnlyInBackgroundState,
  closeAction, handleSetCloseAction
}) {
  return (
    <div className="settings-section audio-section">
      <div className="audio-settings-card">
        <div className="audio-grid-split">
          <div className="audio-col">
            <div className="audio-col-header">
              <span className="audio-col-title">Acústica & Feedback Sonoro</span>
              <span className="audio-col-desc">Sinais auditivos ao concluir tarefas e processamentos.</span>
            </div>

            <div className="audio-controls-stack">
              <div className="audio-group-item">
                <ModernCheckbox
                  checked={soundFeedback}
                  onChange={setSoundFeedback}
                  label="Feedback Sonoro"
                  description="Aviso acústico sutil ao concluir tarefas e processamento em lote."
                  badge="Áudio"
                >
                  <button
                    className="audio-btn-test"
                    onClick={(e) => { e.stopPropagation(); playChime(true); }}
                    title="Testar timbre acústico atual"
                  >
                    <Volume2 size={12} /> Testar
                  </button>
                </ModernCheckbox>

                {soundFeedback && (
                  <div className="audio-sub-block fade-in">
                    <div className="audio-sub-row">
                      <span className="audio-sub-label">Timbre do Som</span>
                      <div className="audio-style-pills">
                        {[
                          { id: 'harmonic', label: 'Harmônico', desc: 'Acorde tríade suave C5–E5–G5' },
                          { id: 'pop',      label: 'Pop Sutil', desc: 'Microestalinho duplo suave' },
                          { id: 'tech',     label: 'Tech Bip',  desc: 'Pulsos eletrônicos modernos' }
                        ].map(st => (
                          <button
                            key={st.id}
                            className={`audio-style-btn ${soundStyle === st.id ? 'active' : ''}`}
                            onClick={() => {
                              setSoundStyleState(st.id);
                              playChime(true, st.id);
                            }}
                            title={st.desc}
                          >
                            {st.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="audio-sub-row">
                      <div className="audio-sub-label-wrap">
                        <span className="audio-sub-label">Volume Acústico</span>
                        <span className="audio-volume-val">{soundVolume}%</span>
                      </div>
                      <div className="audio-slider-wrap">
                        <Volume1 size={13} className="audio-slider-icon" />
                        <input
                          type="range"
                          min="10"
                          max="100"
                          step="5"
                          value={soundVolume}
                          onChange={(e) => setSoundVolumeState(parseInt(e.target.value, 10))}
                          onMouseUp={() => playChime(true)}
                          className="audio-volume-slider"
                        />
                        <Volume2 size={13} className="audio-slider-icon" />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="audio-col">
            <div className="audio-col-header">
              <span className="audio-col-title">Sistema & Comportamento da Janela</span>
              <span className="audio-col-desc">Notificações do Windows e ciclo de vida ao fechar o app.</span>
            </div>

            <div className="audio-controls-stack">
              <div className="audio-group-item">
                <ModernCheckbox
                  checked={systemNotifications}
                  onChange={setSystemNotifications}
                  label="Notificações do Windows"
                  description="Avisos nativos no Action Center ao concluir exportações ou OCR."
                  badge="Sistema"
                >
                  <button
                    className="audio-btn-test"
                    onClick={(e) => {
                      e.stopPropagation();
                      sendNativeNotification('Visionary Studio', 'Notificações do Windows configuradas com sucesso!', { force: true });
                    }}
                    title="Enviar notificação de teste para o Windows"
                  >
                    <Bell size={12} /> Testar
                  </button>
                </ModernCheckbox>

                {systemNotifications && (
                  <div className="audio-sub-block fade-in">
                    <ModernCheckbox
                      checked={notifyOnlyInBackgroundState}
                      onChange={setNotifyOnlyInBackgroundState}
                      label="Silenciar quando em primeiro plano"
                      description="Só emite notificações se a janela estiver minimizada ou em segundo plano."
                      badge="Inteligente"
                    />
                  </div>
                )}
              </div>

              <div className="audio-group-item">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 14px', background: 'var(--bg-surface-elevated, rgba(255,255,255,0.03))', borderRadius: 'var(--radius, 8px)', border: '1px solid var(--border-subtle, rgba(255,255,255,0.06))' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>Ao Fechar a Janela (Botão X)</span>
                    <span className="modern-checkbox-badge">Janela</span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                    Define se o fechamento encerra o processo ou mantém o trabalho em segundo plano na bandeja (Tray).
                  </span>
                  <select
                    className="settings-select"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={closeAction || 'smart'}
                    onChange={(e) => handleSetCloseAction?.(e.target.value)}
                  >
                    <option value="smart">Inteligente (minimiza se houver tarefa; caso contrário, encerra)</option>
                    <option value="tray">Minimizar sempre para a Bandeja do Sistema (Tray)</option>
                    <option value="quit">Encerrar a aplicação completamente</option>
                  </select>
                  {closeAction === 'tray' && (
                    <div className="settings-tray-tip fade-in" style={{ fontSize: '11px', color: '#f59e0b', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '6px', padding: '8px 10px', marginTop: '4px', lineHeight: 1.4 }}>
                      ⚠️ <strong>Atenção:</strong> A aplicação continuará ativa na Bandeja do Sistema (ao lado do relógio do Windows) e manterá os modelos em RAM/VRAM até ser finalizada pelo menu da bandeja ou Gerenciador de Tarefas.
                    </div>
                  )}
                  {closeAction === 'smart' && (
                    <div className="settings-tray-tip fade-in" style={{ fontSize: '11px', color: '#38bdf8', background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '6px', padding: '8px 10px', marginTop: '4px', lineHeight: 1.4 }}>
                      ℹ️ <strong>Modo Inteligente:</strong> Se houver OCR, download ou tradução em execução, o app minimiza para a bandeja para não interromper a fila. Se estiver ocioso, fechar a janela encerrará o programa.
                    </div>
                  )}
                  {closeAction === 'quit' && (
                    <div className="settings-tray-tip fade-in" style={{ fontSize: '11px', color: '#10b981', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '6px', padding: '8px 10px', marginTop: '4px', lineHeight: 1.4 }}>
                      ✓ <strong>Encerramento Imediato:</strong> Ao clicar no botão X, a janela e todos os processos (backend e LLM) serão finalizados imediatamente, liberando 100% da RAM e VRAM.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
