import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.api_services.fs_service import FileSystemService

@pytest.fixture
def fs():
    return FileSystemService()

def test_get_drives_windows(fs):
    with patch("src.api_services.fs_service.sys.platform", "win32"):
        # Mock ctypes
        mock_windll = MagicMock()
        mock_windll.kernel32.GetLogicalDrives.return_value = 5 # Binary 101 -> A and C
        with patch.dict("sys.modules", {"ctypes": MagicMock(windll=mock_windll)}):
            drives = fs.get_drives()
            assert len(drives) == 2
            assert drives[0]["name"] == "A:\\"
            assert drives[1]["name"] == "C:\\"

def test_get_drives_linux(fs):
    with patch("src.api_services.fs_service.sys.platform", "linux"):
        drives = fs.get_drives()
        assert len(drives) == 1
        assert drives[0]["name"] == "/"

def test_list_directory_drives(fs):
    res = fs.list_directory("MEU COMPUTADOR")
    assert res["success"] is True
    assert "items" in res

def test_list_directory_not_found(fs):
    res = fs.list_directory("/fake/dir/nao/existe")
    assert res["success"] is False

def test_list_directory_with_data(fs, tmp_path):
    root = tmp_path / "chapter1"
    root.mkdir()
    
    # Create an image
    (root / "01.jpg").touch()
    (root / "02.jpg").touch()
    
    # Create output dir with a translated json
    out_dir = root / "output"
    out_dir.mkdir()
    
    # Translated mock
    translated_json = out_dir / "01_map.json"
    translated_json.write_text(json.dumps([{"translated_text": "hello"}]), encoding="utf-8")
    
    # Mock progress on 02 but not output
    (root / "02_map.json").write_text(json.dumps([{"text": "hi"}]), encoding="utf-8")
    
    res = fs.list_directory(str(root))
    assert res["success"] is True
    
    items = res["items"]
    # items[0] is Back
    # items[1] is 01.jpg, items[2] is 02.jpg (if it doesn't count dirs first)
    
    file_items = [i for i in items if i.get("isImage")]
    assert len(file_items) == 2
    
    # 01.jpg has output
    f1 = next(i for i in file_items if i["name"] == "01.jpg")
    assert f1["status"] == "ready"
    assert f1["pageData"]["translation"] is True
    
    # 02.jpg has ocr but not translation
    f2 = next(i for i in file_items if i["name"] == "02.jpg")
    assert f2["status"] == "ready"
    assert f2["pageData"]["ocr"] is True
    assert f2["pageData"]["translation"] is False

def test_delete_page(fs, tmp_path):
    root = tmp_path / "chapter"
    root.mkdir()
    
    img = root / "page.jpg"
    img.touch()
    
    map_json = root / "page_map.json"
    map_json.touch()
    
    out_dir = root / "output"
    out_dir.mkdir()
    (out_dir / "page_map.json").touch()
    
    res = fs.delete_page(str(img))
    
    assert res["success"] is True
    assert not img.exists()
    assert not map_json.exists()
    assert not (out_dir / "page_map.json").exists()

def test_reorder_pages(fs, tmp_path):
    root = tmp_path / "reorder"
    root.mkdir()
    
    (root / "10.jpg").touch()
    (root / "20.jpg").touch()
    (root / "10_map.json").touch() # json for 10
    
    files = [
        {"name": "20.jpg", "path": str(root / "20.jpg")}, # make 20 become 001
        {"name": "10.jpg", "path": str(root / "10.jpg")}  # make 10 become 002
    ]
    
    res = fs.reorder_pages(str(root), files)
    assert res["success"] is True
    
    assert (root / "001.jpg").exists()
    assert (root / "002.jpg").exists()
    assert (root / "002_map.json").exists() # The json moved with 10.jpg

@patch("PIL.Image")
def test_merge_pages(mock_image, fs, tmp_path):
    # Mock Pillow images
    mock_img1 = MagicMock()
    mock_img1.width = 100
    mock_img1.height = 200
    
    mock_img2 = MagicMock()
    mock_img2.width = 100
    mock_img2.height = 200
    
    mock_image.open.side_effect = [mock_img1, mock_img2]
    
    mock_new = MagicMock()
    def fake_save(path, *args, **kwargs):
        with open(path, "wb") as f:
            f.write(b"dummy_merged_content")
    mock_new.save.side_effect = fake_save
    mock_image.new.return_value = mock_new
    
    root = tmp_path / "merge"
    root.mkdir()
    f1 = str(root / "01.jpg")
    f2 = str(root / "02.jpg")
    open(f1, 'w').close()
    open(f2, 'w').close()
    
    with patch.dict("sys.modules", {"PIL": MagicMock(Image=mock_image), "PIL.Image": mock_image}):
        res = fs.merge_pages(str(root), [f1, f2], direction="rtl")
    assert res["success"] is True
    mock_new.save.assert_called_once()
    assert "01_spread" in res["newPath"]

@patch("PIL.Image")
def test_split_page(mock_image, fs, tmp_path):
    mock_img = MagicMock()
    mock_img.size = (200, 200)
    mock_crop = MagicMock()
    def fake_crop_save(path, *args, **kwargs):
        with open(path, "wb") as f:
            f.write(b"dummy_crop_content")
    mock_crop.save.side_effect = fake_crop_save
    mock_img.crop.return_value = mock_crop
    mock_image.open.return_value = mock_img
    
    root = tmp_path / "split"
    root.mkdir()
    f1 = str(root / "01_spread.jpg")
    open(f1, 'w').close()
    
    with patch.dict("sys.modules", {"PIL": MagicMock(Image=mock_image), "PIL.Image": mock_image}):
        res = fs.split_page(f1)
    assert res["success"] is True
    # check that two crops were created
    assert mock_img.crop.call_count == 2
    
def test_select_folder_directs_to_electron_ipc():
    # Diálogo de pasta no backend direciona para Electron IPC (window.electronAPI.selectFolder)
    fs = FileSystemService()
    res = fs.select_folder()
    assert res["success"] is False
    assert "electronAPI.selectFolder" in res["error"]



def test_merge_pages_insufficient_files(fs):
    res_none = fs.merge_pages("/fake", [])
    assert res_none["success"] is False
    assert "pelo menos 2" in res_none["error"]

    res_single = fs.merge_pages("/fake", ["/fake/01.jpg"])
    assert res_single["success"] is False
    assert "pelo menos 2" in res_single["error"]


def test_split_page_invalid_path_and_dimensions(fs, tmp_path):
    res_missing = fs.split_page("/fake/non_existent.jpg")
    assert res_missing["success"] is False
    assert "não encontrado" in res_missing["error"]

    res_none = fs.split_page(None)
    assert res_none["success"] is False

    # Mock image with width < 10
    narrow = tmp_path / "narrow.png"
    from PIL import Image
    Image.new("RGB", (4, 100), color="white").save(str(narrow))
    res_narrow = fs.split_page(str(narrow))
    assert res_narrow["success"] is False
    assert "muito estreita" in res_narrow["error"]


def test_delete_page_invalid_inputs(fs):
    for invalid in [None, "", 1234]:
        res = fs.delete_page(invalid)
        assert res["success"] is False
        assert "inválido" in res["error"]


def test_natural_sort_key_order():
    from src.api_services.fs_service import natural_sort_key
    raw_files = ["p10.png", "p2.png", "p1.png", "p20.png"]
    sorted_files = sorted(raw_files, key=natural_sort_key)
    assert sorted_files == ["p1.png", "p2.png", "p10.png", "p20.png"]


def test_detect_folder_output_progress(tmp_path):
    from src.api_services.fs_service import _detect_folder_output_progress

    # Empty folder
    has_out, has_prog = _detect_folder_output_progress(str(tmp_path), [])
    assert has_out is False
    assert has_prog is False

    # Only backup or ignored files
    ignored = ["01.bak.json", "02_backup.json", "03_panels.json", "04_strokes.json"]
    has_out, has_prog = _detect_folder_output_progress(str(tmp_path), ignored)
    assert has_out is False
    assert has_prog is False

    # Translated suffix directly flags output
    files_with_trans = ["01_translated.json", "02.json"]
    has_out, has_prog = _detect_folder_output_progress(str(tmp_path), files_with_trans)
    assert has_out is True
    assert has_prog is True

    # Filter by valid basenames
    files = ["01_map.json", "99_map.json"]
    has_out, has_prog = _detect_folder_output_progress(str(tmp_path), files, valid_basenames={"01"})
    assert has_out is False
    assert has_prog is True

    # Filter with non-matching basenames
    has_out, has_prog = _detect_folder_output_progress(str(tmp_path), files, valid_basenames={"02", "03"})
    assert has_out is False
    assert has_prog is False

