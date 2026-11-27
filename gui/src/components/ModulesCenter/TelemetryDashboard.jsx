import React from "react";
import { Monitor, Cpu, MemoryStick, HardDrive } from "lucide-react";

const TelemetryDashboard = React.memo(function TelemetryDashboard({
  hardwareStats,
  storageStats,
  ollamaModelsCount,
  formatGpuDisplayName,
  formatCpuDisplayName,
}) {
  return (
    <div className={`telemetry-dashboard-hero`}>
      {/* 1. GPU Card */}
      <div className={`telemetry-stat-card`}>
        <div className={`telemetry-card-header`}>
          <div className={`telemetry-title-group`}>
            <Monitor size={14} className={`telemetry-header-icon`} />
            <span className={`telemetry-device-title`} title={hardwareStats.gpu_name}>
              {formatGpuDisplayName(hardwareStats.gpu_name)}
            </span>
            {hardwareStats.cuda_version ? (
              <span className={`telemetry-meta-text`} style={{ opacity: 0.7, fontSize: 10.5 }}>
                · CUDA {hardwareStats.cuda_version}
              </span>
            ) : null}
          </div>
          <span className={`telemetry-meta-text`}>
            {hardwareStats.gpu_temp ? `${hardwareStats.gpu_temp}ºC` : hardwareStats.cuda_version ? '' : 'GPU'}
          </span>
        </div>
        <div className={`telemetry-card-data`}>
          <div className={`telemetry-primary-value`}>
            {(hardwareStats.vram_allocated_gb || 0).toFixed(1)} / {hardwareStats.vram_reserved_gb > 0 ? hardwareStats.vram_reserved_gb.toFixed(1) : '?'} GB
            <span className={`telemetry-unit-label`}>VRAM</span>
          </div>
          <span className={`telemetry-pct-badge`}>
            {hardwareStats.vram_reserved_gb > 0 ? Math.min(100, Math.round(((hardwareStats.vram_allocated_gb || 0) / hardwareStats.vram_reserved_gb) * 100)) : 0}%
          </span>
        </div>
        <div className={`telemetry-progress-track`}>
          <div
            className={`telemetry-progress-fill`}
            style={{
              width: hardwareStats.vram_reserved_gb > 0
                ? `${Math.min(100, ((hardwareStats.vram_allocated_gb || 0) / hardwareStats.vram_reserved_gb) * 100)}%`
                : '0%'
            }}
          />
        </div>
      </div>

      {/* 2. CPU Card */}
      <div className={`telemetry-stat-card`}>
        <div className={`telemetry-card-header`}>
          <div className={`telemetry-title-group`}>
            <Cpu size={14} className={`telemetry-header-icon`} />
            <span className={`telemetry-device-title`} title={hardwareStats.cpu_name}>
              {formatCpuDisplayName(hardwareStats.cpu_name)}
            </span>
          </div>
          <span className={`telemetry-meta-text`}>
            {hardwareStats.cpu_cores ? `${hardwareStats.cpu_cores}C · ${hardwareStats.cpu_threads || hardwareStats.cpu_cores}T` : 'CPU'}
          </span>
        </div>
        <div className={`telemetry-card-data`}>
          <div className={`telemetry-primary-value`}>
            {(hardwareStats.cpu_percent || 0).toFixed(0)}%
            <span className={`telemetry-unit-label`}>em uso</span>
          </div>
        </div>
        <div className={`telemetry-progress-track`}>
          <div
            className={`telemetry-progress-fill`}
            style={{
              width: `${Math.min(100, Math.round(hardwareStats.cpu_percent || 0))}%`
            }}
          />
        </div>
      </div>

      {/* 3. RAM Card */}
      <div className={`telemetry-stat-card`}>
        <div className={`telemetry-card-header`}>
          <div className={`telemetry-title-group`}>
            <MemoryStick size={14} className={`telemetry-header-icon`} />
            <span className={`telemetry-device-title`}>
              RAM
            </span>
          </div>
          <span className={`telemetry-meta-text`}>
            {hardwareStats.ram_total_gb ? `${(hardwareStats.ram_total_gb - (hardwareStats.ram_used_gb || 0)).toFixed(1)} GB livre` : 'RAM'}
          </span>
        </div>
        <div className={`telemetry-card-data`}>
          <div className={`telemetry-primary-value`}>
            {(hardwareStats.ram_used_gb || 0).toFixed(1)} / {hardwareStats.ram_total_gb ? hardwareStats.ram_total_gb.toFixed(1) : '?'} GB
          </div>
          <span className={`telemetry-pct-badge`}>
            {hardwareStats.ram_total_gb > 0 ? Math.min(100, Math.round(((hardwareStats.ram_used_gb || 0) / hardwareStats.ram_total_gb) * 100)) : 0}%
          </span>
        </div>
        <div className={`telemetry-progress-track`}>
          <div
            className={`telemetry-progress-fill`}
            style={{
              width: hardwareStats.ram_total_gb > 0
                ? `${Math.min(100, ((hardwareStats.ram_used_gb || 0) / hardwareStats.ram_total_gb) * 100)}%`
                : '0%'
            }}
          />
        </div>
      </div>

      {/* 4. Storage Card */}
      <div className={`telemetry-stat-card`}>
        <div className={`telemetry-card-header`}>
          <div className={`telemetry-title-group`}>
            <HardDrive size={14} className={`telemetry-header-icon`} />
            <span className={`telemetry-device-title`}>
              Armazenamento
            </span>
          </div>
          <span className={`telemetry-meta-text`}>
            {ollamaModelsCount} no HD
          </span>
        </div>
        <div className={`telemetry-card-data`}>
          <div className={`telemetry-primary-value`}>
            {storageStats ? storageStats.total_formatted : '0.0 GB'}
            <span className={`telemetry-unit-label`}>em modelos</span>
          </div>
        </div>
        <div className={`telemetry-progress-track`}>
          <div
            className={`telemetry-progress-fill`}
            style={{ width: storageStats?.total_gb > 0 ? '100%' : '0%' }}
          />
        </div>
      </div>
    </div>
  );
});

export default TelemetryDashboard;
