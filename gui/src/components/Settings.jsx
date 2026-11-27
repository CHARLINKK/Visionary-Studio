import { useState } from 'react';
import './Settings.css';
import { useToast } from '../contexts/ToastContext';
import { Palette, FolderOpen, Volume2, Keyboard, Info } from 'lucide-react';

import { useSettingsManager } from './Settings/useSettingsManager';
import { SettingsUI } from './Settings/SettingsUI';
import { SettingsWorkflow } from './Settings/SettingsWorkflow';
import { SettingsAudio } from './Settings/SettingsAudio';
import { SettingsShortcuts } from './Settings/SettingsShortcuts';
import { SettingsAbout } from './Settings/SettingsAbout';

export default function Settings({ onBaseFolderChange }) {
  const { addToast } = useToast();
  const [activeCategory, setActiveCategory] = useState('ui');
  
  const manager = useSettingsManager(addToast, onBaseFolderChange);
  const safeCategory = activeCategory === 'docs' ? 'ui' : activeCategory;

  return (
    <div className="settings-container fade-in">
      <div className="settings-layout">
        <div className="settings-page-header">
          <div className="settings-page-header-inner">
            <h1>Configurações</h1>
            <p>Suas preferências de interface e conveniência são salvas automaticamente.</p>
          </div>
        </div>

        <div className="settings-top-nav-bar">
          <div className="settings-top-nav">
            <button className={`settings-nav-item ${safeCategory === 'ui' ? 'active' : ''}`} onClick={() => setActiveCategory('ui')}>
              <Palette size={16} className="nav-icon" />
              <span>Interface (UX)</span>
            </button>
            <button className={`settings-nav-item ${safeCategory === 'nav' ? 'active' : ''}`} onClick={() => setActiveCategory('nav')}>
              <FolderOpen size={16} className="nav-icon" />
              <span>Workflow & Pastas</span>
            </button>
            <button className={`settings-nav-item ${safeCategory === 'audio' ? 'active' : ''}`} onClick={() => setActiveCategory('audio')}>
              <Volume2 size={16} className="nav-icon" />
              <span>Áudio & Sistema</span>
            </button>
            <button className={`settings-nav-item ${safeCategory === 'shortcuts' ? 'active' : ''}`} onClick={() => setActiveCategory('shortcuts')}>
              <Keyboard size={16} className="nav-icon" />
              <span>Atalhos de Teclado</span>
            </button>
            {/* Menu de Documentação mantido no código, mas inacessível pela interface */}
            {/*
            <button className={`settings-nav-item ${safeCategory === 'docs' ? 'active' : ''}`} onClick={() => setActiveCategory('docs')}>
              <BookOpen size={16} className="nav-icon" />
              <span>Documentação</span>
            </button>
            */}
            <button className={`settings-nav-item ${safeCategory === 'about' ? 'active' : ''}`} onClick={() => setActiveCategory('about')}>
              <Info size={16} className="nav-icon" />
              <span>Sobre o App</span>
            </button>
          </div>
        </div>

        <div className="settings-content-area">
          {safeCategory === 'ui' && <SettingsUI {...manager} />}
          {safeCategory === 'nav' && <SettingsWorkflow {...manager} />}
          {safeCategory === 'audio' && <SettingsAudio {...manager} />}
          {safeCategory === 'shortcuts' && <SettingsShortcuts />}
          {/* safeCategory === 'docs' && <InteractiveTutorial embedded /> */}
          {safeCategory === 'about' && <SettingsAbout />}

          {safeCategory !== 'about' && (
            <p className="settings-footer">
              As configurações visuais e preferências são salvas automaticamente no seu perfil.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
