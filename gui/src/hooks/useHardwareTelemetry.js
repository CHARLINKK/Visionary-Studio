import { useState, useCallback, useRef } from "react";
import { clientApi } from "../api/bridge";

/**
 * Hook especializado na coleta e telemetria de hardware (GPU, CPU, RAM, VRAM e Temperatura).
 */
export function useHardwareTelemetry() {
  const isPollingHwRef = useRef(false);

  const [hardwareStats, setHardwareStats] = useState(() => {
    try {
      const cached = localStorage.getItem("visionary:cached_hardware_stats");
      return cached
        ? JSON.parse(cached)
        : {
            gpu_name: "Identificando...",
            vram_reserved_gb: 0,
            vram_allocated_gb: 0,
          };
    } catch {
      return {
        gpu_name: "Identificando...",
        vram_reserved_gb: 0,
        vram_allocated_gb: 0,
      };
    }
  });

  const applyHardwareStats = useCallback((hwStats) => {
    if (!hwStats) return;
    setHardwareStats((prev) => {
      if (
        prev.gpu_name === hwStats.gpu_name &&
        prev.vram_allocated_gb === hwStats.vram_allocated_gb &&
        prev.vram_reserved_gb === hwStats.vram_reserved_gb &&
        prev.cpu_percent === hwStats.cpu_percent &&
        prev.ram_used_gb === hwStats.ram_used_gb &&
        prev.gpu_temp === hwStats.gpu_temp
      ) {
        return prev;
      }
      return hwStats;
    });
    try {
      localStorage.setItem("visionary:cached_hardware_stats", JSON.stringify(hwStats));
    } catch {}
  }, []);

  const fetchHardwareTelemetry = useCallback(async () => {
    if (isPollingHwRef.current) return;
    isPollingHwRef.current = true;
    try {
      const hwStats = await clientApi.getHardwareStats();
      applyHardwareStats(hwStats);
    } catch (_) {
    } finally {
      isPollingHwRef.current = false;
    }
  }, [applyHardwareStats]);

  return {
    hardwareStats,
    setHardwareStats,
    applyHardwareStats,
    fetchHardwareTelemetry,
  };
}
