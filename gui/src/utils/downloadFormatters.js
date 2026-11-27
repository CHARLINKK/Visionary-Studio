/**
 * Utilitários de formatação de telemetria de downloads e transferências do Visionary Studio.
 * Formatação sóbria, compacta e tabular (Linear / Raycast style).
 */

export function formatBytes(bytes, decimals = 2) {
  if (typeof bytes !== "number" || isNaN(bytes) || bytes <= 0) return "";
  const gb = bytes / 1073741824; // 1024^3
  if (gb >= 1.0) {
    return `${gb.toFixed(decimals)} GB`;
  }
  const mb = bytes / 1048576; // 1024^2
  if (mb >= 1.0) {
    return `${mb.toFixed(decimals > 1 ? 1 : 0)} MB`;
  }
  const kb = bytes / 1024;
  if (kb >= 1.0) {
    return `${kb.toFixed(0)} KB`;
  }
  return `${bytes.toFixed(0)} B`;
}

export function formatSpeed(mbps) {
  if (typeof mbps !== "number" || isNaN(mbps) || mbps <= 0.05) return "";
  if (mbps >= 1.0) {
    return `${mbps.toFixed(1)} MB/s`;
  }
  const kbps = mbps * 1024;
  return `${kbps.toFixed(0)} KB/s`;
}

export function formatEta(seconds, { compact = false } = {}) {
  if (typeof seconds !== "number" || isNaN(seconds) || seconds <= 0) return "";
  const sec = Math.round(seconds);
  const suffix = compact ? "" : " rest.";
  if (sec < 60) {
    return `~${sec}s${suffix}`;
  }
  if (sec < 3600) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    if (compact) {
      return s > 0 ? `~${m}m${s}s` : `~${m}m`;
    }
    return `~${m}m ${s > 0 ? `${s}s ` : ""}${suffix}`.replace("  ", " ").trim();
  }
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (compact) {
    return m > 0 ? `~${h}h${m}m` : `~${h}h`;
  }
  return `~${h}h ${m > 0 ? `${m}m ` : ""}${suffix}`.replace("  ", " ").trim();
}

export function formatByteProgress(downloaded, total, { compact = false } = {}) {
  if (typeof downloaded !== "number" || typeof total !== "number" || total <= 0 || downloaded <= 0) return "";
  if (!compact) {
    return `${formatBytes(downloaded)} / ${formatBytes(total)}`;
  }
  const dlGb = downloaded / 1073741824;
  const totGb = total / 1073741824;
  if (totGb >= 1.0) {
    return `${dlGb.toFixed(2)}/${totGb.toFixed(2)} GB`;
  }
  const dlMb = downloaded / 1048576;
  const totMb = total / 1048576;
  if (totMb >= 1.0) {
    return `${dlMb.toFixed(1)}/${totMb.toFixed(1)} MB`;
  }
  const dlKb = downloaded / 1024;
  const totKb = total / 1024;
  return `${dlKb.toFixed(0)}/${totKb.toFixed(0)} KB`;
}

export function formatDownloadTelemetry({
  progress = 0,
  speed_mbps = 0,
  eta_seconds = 0,
  downloaded_bytes = 0,
  total_bytes = 0,
  text = "",
  fallbackSize = "",
  compact = false,
  showSpeed = false,
  showEta = false,
} = {}) {
  const isExplicitDiskPhase =
    typeof text === "string" &&
    (text.includes("Descompactando") ||
      text.includes("Extraindo") ||
      text.includes("Validando") ||
      text.includes("Registrando") ||
      text.includes("Carregando") ||
      text.includes("Compilando") ||
      text.includes("Preparando") ||
      text.includes("Instalando pacotes") ||
      text.includes("Limpando") ||
      text.includes("Removendo") ||
      text.includes("Desinstalando") ||
      text.includes("Liberando") ||
      text.includes("Sincronizando") ||
      text.includes("Resolvendo") ||
      text.includes("Verificando") ||
      text.includes("Otimizando") ||
      text.includes("Dependência já presente"));

  if (isExplicitDiskPhase) {
    return text.trim();
  }

  const isFinalizing =
    progress >= 99 ||
    (typeof text === "string" && text.includes("Finalizando"));

  if (isFinalizing) {
    const size = total_bytes > 0 ? formatBytes(total_bytes) : fallbackSize;
    if (compact) {
      return size ? `Finalizando · ${size}` : "Finalizando...";
    }
    return size ? `Finalizando instalação... · ${size}` : "Finalizando instalação...";
  }

  const parts = [];

  if (showSpeed) {
    const speedStr = formatSpeed(speed_mbps);
    if (speedStr) parts.push(speedStr);
  }

  if (total_bytes > 0 && downloaded_bytes > 0) {
    parts.push(formatByteProgress(downloaded_bytes, total_bytes, { compact }));
  } else if (fallbackSize && progress > 0) {
    parts.push(`${progress.toFixed(0)}% de ${fallbackSize}`);
  }

  if (showEta && eta_seconds > 0) {
    // Escudo contra anomalias transitórias durante handshakes de rede
    if (eta_seconds > 3600 && speed_mbps < 0.3) {
      parts.push("Calculando...");
    } else {
      const etaStr = formatEta(eta_seconds, { compact });
      if (etaStr) parts.push(etaStr);
    }
  }

  if (parts.length > 0) {
    return parts.join(" · ");
  }

  if (text && typeof text === "string" && text.trim().length > 0) {
    return text.trim();
  }

  return "Baixando...";
}
