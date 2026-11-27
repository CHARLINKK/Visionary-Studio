/**
 * Contrato Canônico de Balão de Fala e Bloco de Texto OCR no Frontend.
 * Correspondência simétrica 1:1 com o modelo BubbleModel (Pydantic v2) do Backend.
 */

export interface Bubble {
  /** Identificador único do balão (número ou UUID string) */
  id: number | string;
  /** Ordem sequencial de leitura na página (1-based) */
  order: number;
  /** Coordenada X do canto superior esquerdo */
  x1: number;
  /** Coordenada Y do canto superior esquerdo */
  y1: number;
  /** Coordenada X do canto inferior direito */
  x2: number;
  /** Coordenada Y do canto inferior direito */
  y2: number;
  /** Vértices do contorno curvo do balão extraídos pela segmentação */
  polygon?: [number, number][];
  /** Coordenadas primordiais de detecção do balão [x1, y1, x2, y2] */
  initial_box?: [number, number, number, number];
  /** Contorno poligonal primordial de detecção */
  initial_polygon?: [number, number][];

  /** Texto OCR original da página */
  text: string;
  /** Alias legado para o texto original */
  original?: string;
  /** Tradução corrente aplicada ao balão */
  translated_text: string;
  /** Alias legado para a tradução */
  translated?: string;
  /** Tradução primordial gerada pela IA (usada para detectar edições manuais) */
  ai_translated_text?: string;
  /** Alias legado para tradução de IA */
  ai_translated?: string;
  /** Indica se o texto traduzido foi alterado manualmente pelo usuário */
  user_edited: boolean;

  /** Flag indicando se é efeito sonoro / onomatopeia */
  is_sfx: boolean;
  /** Alias camelCase para compatibilidade com componentes legado */
  isSfx?: boolean;
  /** Rótulo do detector YOLO (text_bubble, text_free) */
  label?: string;
  /** Tipo de fundo morfólogico (white, complex, sfx, unknown) */
  bg_type?: string;
  /** Grau de confiança da inferência YOLO (0.0 a 1.0) */
  confidence?: number;
  /** Área da caixa delimitadora em pixels */
  area?: number;
  /** ID de agrupamento de balões conectados em cascata */
  group_id?: number | string | null;
  /** Alias camelCase legado para ID de agrupamento */
  groupId?: number | string | null;
  /** ID do quadro (panel) em que este balão reside */
  panel_id?: number | null;
  /** Texto OCR bruto pré-higienização */
  ocr_raw?: string;
  /** Indica se é um balão de fala formal */
  is_bubble?: boolean;
  /** Dicionário contendo traduções geradas por múltiplos modelos */
  model_translations?: Record<string, string>;
}

export interface PanelBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  order?: number;
  polygon?: [number, number][];
  box?: [number, number, number, number];
  confidence?: number;
}

export interface PageData {
  boxes: Bubble[];
  panels?: PanelBox[];
  backup?: any;
}
