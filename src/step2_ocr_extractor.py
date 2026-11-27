"""
Fachada de retrocompatibilidade para `src.step2_ocr_extractor`.
A implementação canônica reside em `src.model_engines.florence_ocr_engine`.
"""

import sys
import src.model_engines.florence_ocr_engine as _florence_mod
from src.model_engines.florence_ocr_engine import (  # noqa: F401
    FlorenceReader,
    MODEL_ID,
    CACHE_DIR,
    _suppress_flash_attn_check,
    _resolve_hf_snapshot_path,
    resolve_hf_snapshot_path,
    is_valid_florence_dir,
    _cli_main,
)

if __name__ == "__main__":
    _cli_main()
else:
    sys.modules[__name__] = _florence_mod
