import os
import json
from unittest.mock import patch, MagicMock
from src.run_batch import run_batch_pipeline, backup_file, execute_rollback, request_cancel

def setup_function():
    # Setup run_batch state
    import src.run_batch
    src.run_batch._cancel_event.clear()
    src.run_batch._rollback_flag = False
    src.run_batch._session_backups = {}
    src.run_batch._session_outputs = []

def test_request_cancel():
    request_cancel(rollback=True)
    import src.run_batch
    assert src.run_batch._cancel_event.is_set()
    assert src.run_batch._rollback_flag

def test_backup_and_rollback(tmp_path):
    import src.run_batch
    test_file = tmp_path / "test.txt"
    test_file.write_text("orig")
    
    backup_file(str(test_file))
    assert src.run_batch._session_backups[str(test_file)] == "orig"
    
    test_file.write_text("modificado")
    src.run_batch._rollback_flag = True
    execute_rollback()
    
    assert test_file.read_text() == "orig"
    
    # Test file that didn't exist
    new_file = tmp_path / "new.txt"
    backup_file(str(new_file))
    new_file.write_text("new")
    src.run_batch._rollback_flag = True
    execute_rollback()
    
    assert not new_file.exists()

@patch("src.step1_layout_detector.YoloMapeador")
@patch("src.step2_ocr_extractor.FlorenceReader")
@patch("src.step4_translator.OllamaTranslator")
@patch("src.api_services.dev_service.DevService")
@patch("src.utils.txt_sync.sync_chapter_txt")
def test_run_batch_pipeline_full(mock_sync, mock_dev, mock_trans, mock_flo, mock_yolo, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    
    img1 = in_dir / "01.jpg"
    img1.write_bytes(b"dummy")
    
    # Mocks
    mock_y_inst = MagicMock()
    mock_yolo.return_value = mock_y_inst
    mock_y_inst.detect_bubbles.return_value = [{"x1":10, "y1":10, "x2":50, "y2":50, "text": ""}]
    mock_y_inst.detect_panels_and_sort.return_value = ([], [{"x1":10, "y1":10, "x2":50, "y2":50, "text": ""}])
    mock_y_inst.add_polygons.return_value = [{"x1":10, "y1":10, "x2":50, "y2":50, "text": ""}]
    
    mock_f_inst = MagicMock()
    mock_flo.return_value = mock_f_inst
    mock_f_inst.read_text_batch.return_value = [{"text": "Hello World", "regions": []}]
    
    mock_t_inst = MagicMock()
    mock_trans.return_value = mock_t_inst
    
    from PIL import Image
    
    with patch("PIL.Image.open") as mock_img_open:
        real_img = Image.new("RGB", (100, 100))
        mock_img_open.return_value = real_img
        
        res = run_batch_pipeline(
            str(in_dir), str(out_dir),
            model="fake_model",
            skip_ocr=False,
            skip_translate=False,
            only_layout=False
        )
        
        assert res is True
        mock_y_inst.detect_bubbles.assert_called()
        mock_f_inst.read_text_batch.assert_called()
        mock_t_inst.process_directory.assert_called()
        mock_sync.assert_called()

@patch("src.step4_translator.OllamaTranslator")
def test_run_batch_pipeline_only_translate(mock_trans, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    
    img1 = in_dir / "01.jpg"
    img1.write_bytes(b"dummy")
    
    res = run_batch_pipeline(
        str(in_dir), str(out_dir),
        model="fake_model",
        skip_ocr=True,
        skip_translate=False,
        only_layout=False
    )
    assert res is True
    mock_trans.return_value.process_directory.assert_called_once()

@patch("src.step1_layout_detector.YoloMapeador")
def test_run_batch_pipeline_only_layout(mock_yolo, tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    
    img1 = in_dir / "01.jpg"
    img1.write_bytes(b"dummy")
    
    mock_y_inst = MagicMock()
    mock_yolo.return_value = mock_y_inst
    mock_y_inst.detect_bubbles.return_value = []
    mock_y_inst.detect_panels_and_sort.return_value = ([], [])
    mock_y_inst.add_polygons.return_value = []
    
    with patch("PIL.Image.open"):
        res = run_batch_pipeline(
            str(in_dir), str(out_dir),
            model=None,
            skip_ocr=False,
            skip_translate=False,
            only_layout=True
        )
        assert res is True
        mock_y_inst.detect_bubbles.assert_called_once()

def test_run_batch_pipeline_no_images(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    res = run_batch_pipeline(
        str(in_dir), str(tmp_path / "out"),
        model="fake_model"
    )
    assert res is None


@patch("src.step4_translator.OllamaTranslator")
@patch("src.utils.txt_sync.sync_chapter_txt")
def test_run_batch_cached_ocr_preserves_target_bases_for_translation(mock_sync, mock_trans, tmp_path):
    """Garante que páginas já com OCR cacheado (filtradas na Fase 1) permanecem em target_bases na Fase 2."""
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Página 01 já possui OCR mas ainda não possui tradução
    (in_dir / "01.jpg").write_bytes(b"dummy")
    (out_dir / "01_map.json").write_text(
        json.dumps([{"id": 1, "x1": 0, "y1": 0, "x2": 10, "y2": 10, "text": "Hello", "translated_text": ""}]),
        encoding="utf-8",
    )

    res = run_batch_pipeline(
        str(in_dir),
        str(out_dir),
        model="qwen2.5:14b",
        overwrite=False,
        skip_ocr=False,
        skip_translate=False,
    )
    assert res is True
    mock_trans.return_value.process_directory.assert_called_once()
    _, kwargs = mock_trans.return_value.process_directory.call_args
    assert kwargs["target_bases"] == ["01"]


@patch("src.step1_layout_detector.YoloMapeador")
def test_run_batch_fatal_phase1_error_and_oom_propagation(mock_yolo, tmp_path):
    """Garante que falha fatal na Fase 1 retorna False e que CUDA OOM é relançado para o PipelineService."""
    import pytest

    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"
    (in_dir / "01.jpg").write_bytes(b"dummy")

    # 1. Erro fatal genérico na carga do modelo -> retorna False (não True!)
    mock_yolo.side_effect = RuntimeError("Pesos corrompidos")
    res = run_batch_pipeline(str(in_dir), str(out_dir), model="qwen2.5:14b")
    assert res is False

    # 2. CUDA out of memory -> relança para que PipelineService acione o protocolo OOM
    mock_yolo.side_effect = RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        run_batch_pipeline(str(in_dir), str(out_dir), model="qwen2.5:14b")


def test_run_batch_scoped_stdout_no_double_logging(tmp_path):
    """Garante que quando scoped_job_stdout estiver ativo, logs não são emitidos em duplicidade."""
    from src.utils.pipeline_emitter import PipelineEmitter, scoped_job_stdout
    emitter = PipelineEmitter(job_id="test_no_dup")
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"

    with patch.object(emitter, "emit_log") as mock_emit:
        with scoped_job_stdout(emitter):
            run_batch_pipeline(str(in_dir), str(out_dir), progress_emitter=emitter)

        calls = [c[0][0] for c in mock_emit.call_args_list]
        for msg in calls:
            assert calls.count(msg) == 1, f"Mensagem duplicada encontrada: {msg}"

