import os
import sys
import unittest
from PIL import Image


from src.step1_layout_detector import (
    _iou,
    _merge_bubbles,
    _merge_panels,
    _refine_bubble_box,
    _bubble_xy_cut,
    recursive_xy_cut
)

class TestLayoutDetector(unittest.TestCase):
    def test_iou_calculation(self):
        """Valida o cálculo de IoU entre duas caixas."""
        boxA = [0, 0, 10, 10]
        boxB = [0, 0, 10, 10]
        self.assertAlmostEqual(_iou(boxA, boxB), 1.0)

        boxC = [20, 20, 30, 30]
        self.assertEqual(_iou(boxA, boxC), 0.0)

        boxD = [0, 0, 10, 5]  # metade da área
        self.assertAlmostEqual(_iou(boxA, boxD), 0.5)

    def test_merge_overlapping_bubbles(self):
        """Valida que balões sobrepostos ou contidos são fundidos na união."""
        boxes = [
            {"x1": 10, "y1": 10, "x2": 50, "y2": 50, "confidence": 0.9, "label": "text_bubble"},
            {"x1": 15, "y1": 15, "x2": 45, "y2": 45, "confidence": 0.8, "label": "text_bubble"}, # Totalmente contido
            {"x1": 200, "y1": 200, "x2": 250, "y2": 250, "confidence": 0.95, "label": "text_bubble"} # Isolado
        ]
        merged = _merge_bubbles(boxes, iou_threshold=0.10, containment_threshold=0.40)
        self.assertEqual(len(merged), 2)
        # O primeiro balão unificado deve englobar [10, 10, 50, 50]
        b1 = [b for b in merged if b["x1"] == 10][0]
        self.assertEqual(b1["x2"], 50)
        self.assertEqual(b1["y2"], 50)

    def test_merge_panels(self):
        """Valida a fusão de quadros/painéis que colidem."""
        panels = [
            {"box": [0, 0, 100, 100], "area": 10000, "conf": 0.9},
            {"box": [10, 10, 95, 95], "area": 7225, "conf": 0.8},
            {"box": [0, 150, 100, 250], "area": 10000, "conf": 0.95}
        ]
        merged = _merge_panels(panels, iou_threshold=0.15, containment_threshold=0.50)
        self.assertEqual(len(merged), 2)

    def test_xy_cut_manga_order(self):
        """Valida que o algoritmo XY-Cut ordena da Direita para a Esquerda e de Cima para Baixo."""
        bubbles = [
            {"x1": 10, "y1": 10, "x2": 50, "y2": 50},    # Esquerda superior
            {"x1": 300, "y1": 10, "x2": 350, "y2": 50},  # Direita superior (Deve ser 1º)
            {"x1": 300, "y1": 200, "x2": 350, "y2": 250} # Direita inferior (Deve ser 2º)
        ]
        sorted_b = _bubble_xy_cut(bubbles)
        self.assertEqual(sorted_b[0]["x1"], 300)
        self.assertEqual(sorted_b[0]["y1"], 10)
        self.assertEqual(sorted_b[1]["x1"], 300)
        self.assertEqual(sorted_b[1]["y1"], 200)
        self.assertEqual(sorted_b[2]["x1"], 10)

    def test_refine_box_padding(self):
        """Valida que a caixa respeita os limites da imagem original."""
        img = Image.new("RGB", (1000, 1500), color="white")
        x1, y1, x2, y2 = _refine_bubble_box(img, -10, -5, 1010, 1520, "text_bubble", pad=10)
        self.assertGreaterEqual(x1, 0)
        self.assertGreaterEqual(y1, 0)
        self.assertLessEqual(x2, 1000)
        self.assertLessEqual(y2, 1500)

    def test_is_clean_white_bubble(self):
        """Valida a classificação estrita de balões de fundo branco."""
        import numpy as np
        from src.step1_layout_detector import is_clean_white_bubble
        
        # 1. Balão branco clássico: fundo 250, com texto preto no centro
        classic_bubble = np.full((100, 100), 250, dtype=np.uint8)
        classic_bubble[40:60, 30:70] = 10 # letras pretas
        self.assertTrue(is_clean_white_bubble(classic_bubble))
        
        # 2. Imagem escura ou com retícula cinza (ex: média 140)
        dark_crop = np.full((100, 100), 140, dtype=np.uint8)
        self.assertFalse(is_clean_white_bubble(dark_crop))
        
        # 3. Retângulo 100% branco sem nenhum texto (falso positivo de cenário/sarjeta)
        empty_white = np.full((100, 100), 255, dtype=np.uint8)
        self.assertFalse(is_clean_white_bubble(empty_white))

        # 4. Balão com hachuras/retícula/cinza NÃO deve ser classificado como balão branco limpo
        screentone_bubble = np.full((100, 100), 185, dtype=np.uint8)
        screentone_bubble[:55, :] = 205
        screentone_bubble[40:60, 30:70] = 10
        self.assertFalse(is_clean_white_bubble(screentone_bubble))

    def test_detect_panels_blind_master_cuda_fallback(self):
        """Valida que falhas de CUDA/OOM acionam fallback para CPU e limpeza de memória."""
        from unittest.mock import MagicMock, patch
        from src.step1_layout_detector import _detect_panels_blind_master

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.boxes = []
        # Primeira chamada lança CUDA error, segunda chamada no fallback CPU tem sucesso
        mock_model.predict.side_effect = [
            RuntimeError("CUDA error: out of memory"),
            [mock_result]
        ]

        img = Image.new("RGB", (200, 200), color="white")
        with patch("src.step1_layout_detector.cleanup_gpu_memory") as mock_cleanup:
            res = _detect_panels_blind_master(mock_model, img)
            self.assertEqual(res, [])
            mock_cleanup.assert_called_with(force_ipc=True)
            mock_model.to.assert_called_with("cpu")
            self.assertEqual(mock_model.predict.call_count, 2)

    def test_detect_panels_and_sort_auto_loads_panel_detector(self):
        """Valida que detect_panels_and_sort carrega automaticamente o modelo de quadros se _panel_model for None."""
        from unittest.mock import MagicMock
        from src.step1_layout_detector import YoloMapeador

        mapeador = YoloMapeador()
        mapeador.load_panel_detector = MagicMock()
        mapeador._panel_model = None

        img = Image.new("RGB", (100, 100), color="white")
        bubbles = [{"x1": 10, "y1": 10, "x2": 50, "y2": 50}]
        panels, sorted_b = mapeador.detect_panels_and_sort(img, bubbles)
        mapeador.load_panel_detector.assert_called_once()
        self.assertEqual(len(sorted_b), 1)

if __name__ == "__main__":
    unittest.main()
