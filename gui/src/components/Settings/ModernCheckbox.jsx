export function ModernCheckbox({ checked, onChange, label, description, badge, children }) {
  return (
    <div 
      className={`modern-checkbox-row ${checked ? 'is-active' : ''}`} 
      onClick={() => onChange(!checked)} 
      role="switch" 
      aria-checked={checked} 
      tabIndex={0} 
      onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); onChange(!checked); } }}
    >
      <div className="modern-checkbox-text">
        <div className="modern-checkbox-header">
          <span className="modern-checkbox-label">{label}</span>
          {badge && <span className="modern-checkbox-badge">{badge}</span>}
        </div>
        {description && <span className="modern-checkbox-desc">{description}</span>}
      </div>
      <div className="modern-checkbox-actions" onClick={e => e.stopPropagation()}>
        {children}
        <div className={`modern-toggle-track ${checked ? 'on' : 'off'}`} onClick={() => onChange(!checked)}>
          <div className="modern-toggle-knob" />
        </div>
      </div>
    </div>
  );
}
