"""
Modelo Canônico de Balão e Página (Pydantic v2).
Garante tipagem estrita, validação em tempo de ingestão e compatibilidade
bidirecional com arquivos _map.json legados e com o frontend React.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


def _safe_int_coord(val: Any, default: int = 0) -> int:
    """Higieniza e converte coordenadas para inteiros de forma segura."""
    if val is None:
        return default
    try:
        return int(round(float(val)))
    except (ValueError, TypeError):
        return default


def _extract_str(val: Any) -> str:
    """Extrai texto seguro de strings ou estruturas aninhadas legadas {'text': ...}."""
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("text", "") or "")
    return str(val or "")


class BubbleModel(BaseModel):
    """
    Representação tipada e canônica de um balão de fala ou bloco de texto OCR.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        validate_assignment=True
    )

    id: Union[int, str] = Field(default=0, description="Identificador único do balão")
    order: Optional[int] = Field(default=None, description="Ordem de leitura na página (1-based), ou None para SFX/ruído")
    x1: int = Field(default=0, description="Coordenada X inicial (topo-esquerda)")
    y1: int = Field(default=0, description="Coordenada Y inicial (topo-esquerda)")
    x2: int = Field(default=0, description="Coordenada X final (base-direita)")
    y2: int = Field(default=0, description="Coordenada Y final (base-direita)")
    polygon: List[List[int]] = Field(default_factory=list, description="Vértices do contorno curvo do balão")
    initial_box: Optional[List[int]] = Field(default=None, description="Coordenadas de detecção iniciais [x1, y1, x2, y2]")
    initial_polygon: Optional[List[List[int]]] = Field(default=None, description="Contorno poligonal inicial de detecção")

    # Textos e tradução
    text: str = Field(default="", description="Texto original detectado via OCR")
    translated_text: str = Field(default="", description="Tradução atual")
    ai_translated_text: str = Field(default="", description="Tradução original gerada pela IA")
    user_edited: bool = Field(default=False, description="Indica se o texto foi editado manualmente pelo usuário")

    # Metadados e classificações
    is_sfx: bool = Field(default=False, description="Flag indicando se é efeito sonoro / onomatopeia")
    is_bubble: bool = Field(default=True, description="Indica se é um balão de fala formal")
    label: str = Field(default="text_bubble", description="Rótulo do detector YOLO (ex: text_bubble, text_free)")
    bg_type: str = Field(default="unknown", description="Tipo de fundo: white, complex, sfx, unknown")
    confidence: Optional[float] = Field(default=1.0, description="Confiança da detecção YOLO (0.0 a 1.0)")
    area: Optional[int] = Field(default=None, description="Área em pixels da caixa delimitadora")
    group_id: Optional[Union[int, str]] = Field(default=None, description="Agrupamento de múltiplos balões interligados")
    panel_id: Optional[int] = Field(default=None, description="ID do quadro (panel) ao qual pertence")
    ocr_raw: str = Field(default="", description="Texto OCR bruto antes de qualquer higienização")
    model_translations: Dict[str, str] = Field(default_factory=dict, description="Histórico de traduções por modelo")

    @model_validator(mode="before")
    @classmethod
    def _normalize_incoming_dict(cls, data: Any) -> Any:
        """
        Normaliza chaves legadas e variações sintáticas (camelCase / snake_case)
        antes da validação estrita dos campos.
        """
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Resolução do texto original
        orig_text = _extract_str(
            d.get("original")
            or d.get("text")
            or d.get("ocr_raw")
            or ""
        )
        d["text"] = orig_text
        d["ocr_raw"] = d.get("ocr_raw") or orig_text

        # 2. Resolução da tradução
        trans_text = _extract_str(
            d.get("translated_text")
            or d.get("translated")
            or d.get("text_ptbr")
            or d.get("ptbr")
            or ""
        )
        d["translated_text"] = trans_text

        # 3. Resolução da tradução gerada pela IA
        ai_trans = _extract_str(
            d.get("ai_translated_text")
            or d.get("ai_translated")
            or ""
        )
        d["ai_translated_text"] = ai_trans

        # 4. Resolução da flag de edição do usuário
        if d.get("user_edited") is not None:
            d["user_edited"] = bool(d["user_edited"])
        elif ai_trans and trans_text and trans_text.strip() != ai_trans.strip():
            d["user_edited"] = True
        else:
            d["user_edited"] = False

        # 5. Resolução de SFX (aceita is_sfx, isSfx e text_free)
        label_val = str(d.get("label") or "text_bubble")
        d["is_sfx"] = bool(
            d.get("is_sfx")
            or d.get("isSfx")
            or (label_val == "text_free")
            or False
        )
        d["label"] = label_val

        # 6. Coordenadas seguras
        d["x1"] = _safe_int_coord(d.get("x1", d.get("xmin", 0)))
        d["y1"] = _safe_int_coord(d.get("y1", d.get("ymin", 0)))
        d["x2"] = _safe_int_coord(d.get("x2", d.get("xmax", 0)))
        d["y2"] = _safe_int_coord(d.get("y2", d.get("ymax", 0)))

        # 7. Ordem e ID
        order_val = d.get("order")
        if order_val is not None:
            try:
                d["order"] = int(order_val)
            except (ValueError, TypeError):
                d["order"] = None
        else:
            d["order"] = None if d.get("is_sfx") else 1

        if d.get("id") is None:
            d["id"] = d["order"] if d["order"] is not None else 0

        # 8. Polígono
        poly = d.get("polygon")
        if isinstance(poly, list):
            cleaned_poly = []
            for pt in poly:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    cleaned_poly.append([_safe_int_coord(pt[0]), _safe_int_coord(pt[1])])
            d["polygon"] = cleaned_poly
        else:
            d["polygon"] = []

        return d

    def to_gui_dict(self) -> Dict[str, Any]:
        """
        Gera o dicionário canônico e compatível com a interface React.
        Mantém os sinônimos ('original', 'translated', 'isSfx') para garantir que
        componentes antigos ou novos leiam suas propriedades sem falhas.
        """
        return {
            "id": self.id,
            "order": self.order,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "polygon": self.polygon,
            # Canônicos e aliases para o React
            "text": self.text,
            "original": self.text,
            "translated": self.translated_text,
            "translated_text": self.translated_text,
            "ai_translated": self.ai_translated_text,
            "ai_translated_text": self.ai_translated_text,
            "user_edited": self.user_edited,
            "is_sfx": self.is_sfx,
            "isSfx": self.is_sfx,
            "label": self.label,
            "is_bubble": self.is_bubble,
            "bg_type": self.bg_type,
            "confidence": self.confidence,
            "area": self.area or max(0, (self.x2 - self.x1) * (self.y2 - self.y1)),
            "group_id": self.group_id,
            "panel_id": self.panel_id,
            "ocr_raw": self.ocr_raw or self.text,
            "model_translations": dict(self.model_translations),
        }

    def to_storage_dict(self) -> Dict[str, Any]:
        """
        Gera o dicionário limpo e padronizado para salvar no _map.json.
        """
        data: Dict[str, Any] = {
            "id": self.id,
            "order": self.order,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "text": self.text,
            "translated": self.translated_text,
            "translated_text": self.translated_text,
            "ai_translated": self.ai_translated_text,
            "ai_translated_text": self.ai_translated_text,
            "user_edited": self.user_edited,
            "is_sfx": self.is_sfx,
            "label": self.label,
            "bg_type": self.bg_type,
            "confidence": self.confidence,
            "area": self.area or max(0, (self.x2 - self.x1) * (self.y2 - self.y1)),
        }
        if self.polygon:
            data["polygon"] = self.polygon
        if self.group_id is not None:
            data["group_id"] = self.group_id
        if self.panel_id is not None:
            data["panel_id"] = self.panel_id
        if self.model_translations:
            data["model_translations"] = dict(self.model_translations)
        return data


class PageDataModel(BaseModel):
    """
    Representação tipada do arquivo de mapeamento de página (_map.json).
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    boxes: List[BubbleModel] = Field(default_factory=list, description="Lista ordenada de balões e textos da página")
    panels: List[Dict[str, Any]] = Field(default_factory=list, description="Quadros detectados pelo YOLO de layout")
    backup: Optional[Dict[str, Any]] = Field(default=None, description="Ponto de restauração/checkpoint embutido")

    @classmethod
    def from_raw(cls, raw_data: Any) -> "PageDataModel":
        """Constrói uma instância PageDataModel a partir de dicionários brutos ou listas legadas."""
        if isinstance(raw_data, list):
            # Formato arcaico que salvava apenas array de caixas
            return cls(boxes=[BubbleModel.model_validate(b) for b in raw_data if isinstance(b, dict)])
        if isinstance(raw_data, dict):
            raw_boxes = raw_data.get("boxes", [])
            valid_boxes = [BubbleModel.model_validate(b) for b in raw_boxes if isinstance(b, dict)]
            return cls(
                boxes=valid_boxes,
                panels=raw_data.get("panels", []),
                backup=raw_data.get("backup"),
            )
        return cls()

    def to_gui_dict(self) -> Dict[str, Any]:
        """Formato consumível pela interface React."""
        return {
            "boxes": [b.to_gui_dict() for b in self.boxes],
            "panels": self.panels,
            "backup": self.backup,
        }

    def to_storage_dict(self) -> Dict[str, Any]:
        """Formato persistível em _map.json."""
        return {
            "boxes": [b.to_storage_dict() for b in self.boxes],
            "panels": self.panels,
            "backup": self.backup,
        }
