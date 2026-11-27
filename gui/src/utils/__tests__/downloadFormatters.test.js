import { describe, it, expect } from "vitest";
import {
  formatBytes,
  formatSpeed,
  formatEta,
  formatDownloadTelemetry,
} from "../downloadFormatters";

describe("downloadFormatters", () => {
  describe("formatBytes", () => {
    it("returns empty string for zero or invalid inputs", () => {
      expect(formatBytes(0)).toBe("");
      expect(formatBytes(-100)).toBe("");
      expect(formatBytes(null)).toBe("");
      expect(formatBytes(undefined)).toBe("");
      expect(formatBytes("abc")).toBe("");
    });

    it("formats bytes, KB, MB, and GB accurately", () => {
      expect(formatBytes(500)).toBe("500 B");
      expect(formatBytes(2048)).toBe("2 KB");
      expect(formatBytes(15 * 1024 * 1024)).toBe("15.0 MB");
      expect(formatBytes(3.42 * 1024 * 1024 * 1024)).toBe("3.42 GB");
      expect(formatBytes(9.0 * 1024 * 1024 * 1024)).toBe("9.00 GB");
    });
  });

  describe("formatSpeed", () => {
    it("returns empty string for low or zero speeds", () => {
      expect(formatSpeed(0)).toBe("");
      expect(formatSpeed(0.04)).toBe("");
      expect(formatSpeed(-1)).toBe("");
    });

    it("formats speeds in KB/s and MB/s", () => {
      expect(formatSpeed(0.5)).toBe("512 KB/s");
      expect(formatSpeed(1.2)).toBe("1.2 MB/s");
      expect(formatSpeed(34.25)).toBe("34.3 MB/s");
    });
  });

  describe("formatEta", () => {
    it("returns empty string for non-positive eta", () => {
      expect(formatEta(0)).toBe("");
      expect(formatEta(-5)).toBe("");
    });

    it("formats seconds, minutes and hours", () => {
      expect(formatEta(15)).toBe("~15s rest.");
      expect(formatEta(59)).toBe("~59s rest.");
      expect(formatEta(160)).toBe("~2m 40s rest.");
      expect(formatEta(120)).toBe("~2m rest.");
      expect(formatEta(3665)).toBe("~1h 1m rest.");
    });
  });

  describe("formatDownloadTelemetry", () => {
    it("formats sober telemetry by default without erratic speed or eta", () => {
      const summary = formatDownloadTelemetry({
        progress: 38,
        speed_mbps: 34.2,
        eta_seconds: 160,
        downloaded_bytes: 3.42 * 1024 * 1024 * 1024,
        total_bytes: 9.0 * 1024 * 1024 * 1024,
      });
      expect(summary).toBe("3.42 GB / 9.00 GB");
    });

    it("formats combined telemetry when showSpeed and showEta are explicitly enabled", () => {
      const summary = formatDownloadTelemetry({
        progress: 38,
        speed_mbps: 34.2,
        eta_seconds: 160,
        downloaded_bytes: 3.42 * 1024 * 1024 * 1024,
        total_bytes: 9.0 * 1024 * 1024 * 1024,
        showSpeed: true,
        showEta: true,
      });
      expect(summary).toBe("34.2 MB/s · 3.42 GB / 9.00 GB · ~2m 40s rest.");
    });

    it("falls back to text or percentage with fallback size if bytes are missing", () => {
      expect(
        formatDownloadTelemetry({
          progress: 50,
          fallbackSize: "4.7 GB",
        })
      ).toBe("50% de 4.7 GB");

      expect(
        formatDownloadTelemetry({
          text: "Conectando ao Ollama...",
        })
      ).toBe("Conectando ao Ollama...");

      expect(formatDownloadTelemetry({})).toBe("Baixando...");
    });

    it("displays clean finalizing message without speed or eta when progress is 99% or finalizing", () => {
      const summaryAt99 = formatDownloadTelemetry({
        progress: 99,
        speed_mbps: 242.3,
        eta_seconds: 1,
        downloaded_bytes: 1.54 * 1024 * 1024 * 1024,
        total_bytes: 1.56 * 1024 * 1024 * 1024,
      });
      expect(summaryAt99).toBe("Finalizando instalação... · 1.56 GB");

      const summaryText = formatDownloadTelemetry({
        progress: 95,
        text: "Finalizando instalação...",
        fallbackSize: "~59 MB",
      });
      expect(summaryText).toBe("Finalizando instalação... · ~59 MB");
    });

    it("formats ultra-compact tabular progress and preserves explicit verification phases", () => {
      const compactTelemetry = formatDownloadTelemetry({
        progress: 42,
        speed_mbps: 38.4,
        eta_seconds: 135,
        downloaded_bytes: 0.6 * 1024 * 1024 * 1024,
        total_bytes: 1.43 * 1024 * 1024 * 1024,
        compact: true,
        showSpeed: true,
        showEta: true,
      });
      expect(compactTelemetry).toBe("38.4 MB/s · 0.60/1.43 GB · ~2m15s");
      expect(compactTelemetry.length).toBeLessThanOrEqual(36);

      const verifyingPhase = formatDownloadTelemetry({
        progress: 99.1,
        text: "Verificando pesos Safetensors...",
        compact: true,
      });
      expect(verifyingPhase).toBe("Verificando pesos Safetensors...");
    });
  });
});
