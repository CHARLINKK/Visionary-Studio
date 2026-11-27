import React from "react";
import { Cpu } from "lucide-react";

export const RECOMMENDED_MODELS = [
  {
    name: "amadeus:14b",
    pullTarget: "hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M",
    title: "Amadeus Verbo (14B)",
    paramSize: "14B",
    version: "PT-BR Instruct · Q4_K_M",
    tag: "Padrão Ouro",
    tagType: "featured",
    vramReq: "9.8 GB",
    vramNum: 10,
    speedEst: "~20 tok/s",
    qualityScore: 5,
    contextWindow: "32k",
    sizeEst: "9.0 GB",
    developer: "Amadeus AI (Qwen 2.5)",
    iconTheme: "amadeus",
    suitability: "Híbrido (GPU + RAM)",
    suitabilityType: "hybrid",
    desc: "O ápice de localização brasileira sobre Qwen 2.5. Compreensão absoluta de gírias, subtexto e ritmo da fala oral sem calques do inglês.",
  },
  {
    name: "amadeus:7b",
    pullTarget: "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M",
    title: "Amadeus Verbo (7B)",
    paramSize: "7B",
    version: "PT-BR Instruct · Q4_K_M",
    tag: "PT-BR Rápido",
    tagType: "fast",
    vramReq: "5.2 GB",
    vramNum: 6,
    speedEst: "~42 tok/s",
    qualityScore: 5,
    contextWindow: "32k",
    sizeEst: "4.7 GB",
    developer: "Amadeus AI (Qwen 2.5)",
    iconTheme: "amadeus",
    suitability: "100% VRAM (Ideal para 8GB)",
    suitabilityType: "optimal",
    desc: "Ajustado especificamente para linguagem oral brasileira e diálogos sem calques. Roda 100% na VRAM da RTX 2060S.",
  },
  {
    name: "amadeus:32b",
    pullTarget: "hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M",
    title: "Amadeus Verbo (32B)",
    paramSize: "32B",
    version: "PT-BR Instruct · Q4_K_M",
    tag: "Padrão Ouro Máximo",
    tagType: "heavy",
    vramReq: "20.5 GB",
    vramNum: 20,
    speedEst: "~7 tok/s",
    qualityScore: 5,
    contextWindow: "32k",
    sizeEst: "19.8 GB",
    developer: "Amadeus AI (Qwen 2.5)",
    iconTheme: "amadeus",
    suitability: "Requer 20 GB+ VRAM ou Offload de RAM",
    suitabilityType: "heavy",
    desc: "A expressão máxima de localização e inteligência em português brasileiro. Vocabulário refinado e nuances extremas de contexto.",
  },
];

export function ModelLogo({ theme }) {
  switch (theme) {
    case "qwen":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2L20.5 7V17L12 22L3.5 17V7L12 2Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          <path
            d="M12 22V12M12 12L20.5 7M12 12L3.5 7"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinejoin="round"
            opacity="0.8"
          />
          <circle cx="12" cy="12" r="2.5" fill="currentColor" />
        </svg>
      );
    case "deepseek":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path
            d="M2.5 13.5C2.5 13.5 5 8 11.5 8C18 8 21.5 12.5 21.5 15.5C21.5 18 19.5 20 16.5 20C13 20 10.5 17 8 17C5.5 17 3.5 18.5 2.5 18.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="15.5" cy="12" r="1.5" fill="currentColor" />
          <path
            d="M8 8C8 5.5 10 3.5 12 3.5C13.5 3.5 14 4.5 14 4.5"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      );
    case "amadeus":
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 3L21 12L12 21L3 12L12 3Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          <circle cx="12" cy="12" r="3.5" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      );
    default:
      return <Cpu size={16} />;
  }
}
