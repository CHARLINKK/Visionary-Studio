import unittest
from unittest.mock import patch, MagicMock
from src.api_services.library_service import LibraryService
import os

class TestLibraryService(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.ls = LibraryService(self.api)

    @patch("src.config.Config.get")
    def test_listLibraryFiles(self, mock_cfg):
        mock_cfg.side_effect = lambda k, d="": "/mock/base" if k == "baseFolder" else ""
        self.api.current_path = "/mock/chapter"
        
        with patch("os.path.exists", side_effect=lambda p: True), \
             patch("os.path.isdir", side_effect=lambda p: True), \
             patch("os.listdir", side_effect=lambda p: ["file1.txt", "ignore.jpg", "_tmp.txt"]), \
             patch("os.path.isfile", side_effect=lambda p: True), \
             patch("os.stat") as mock_stat, \
             patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="[1]\nOlá\n\n[PT] Algum texto\n[PENDENTE]"), \
             patch("os.scandir") as mock_scandir:
             
            # Scandir mock
            mock_entry = MagicMock()
            mock_entry.is_file.return_value = True
            mock_entry.name = "subfile.txt"
            mock_entry.path = "/mock/base/subfile.txt"
            
            mock_scandir.return_value.__enter__.return_value = [mock_entry]
            
            mock_stat_res = MagicMock()
            mock_stat_res.st_size = 100
            mock_stat_res.st_mtime = 1000
            mock_stat.return_value = mock_stat_res
            
            res = self.ls.listLibraryFiles()
            
            self.assertTrue(res["success"])
            self.assertIn("files", res)
            self.assertGreaterEqual(len(res["files"]), 1)

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_deleteLibraryFile(self, mock_remove, mock_exists):
        res = self.ls.deleteLibraryFile({"name": "test.txt", "path": "/fake/test.txt"})
        self.assertTrue(res["success"])
        mock_remove.assert_called_once()
        
    @patch("subprocess.Popen")
    def test_openFileInExplorer(self, mock_popen):
        res = self.ls.openFileInExplorer({"path": "/fake/test.txt"})
        self.assertTrue(res["success"])
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    @patch("os.path.exists", return_value=True)
    def test_openLibraryFolder(self, mock_exists, mock_popen):
        res = self.ls.openLibraryFolder()
        self.assertTrue(res["success"])
        mock_popen.assert_called_once()

    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_syncChapterTxt(self, mock_sync):
        mock_sync.return_value = {"success": True}
        res = self.ls.syncChapterTxt({"path": "/fake/dir"})
        self.assertTrue(res["success"])

    @patch("os.makedirs")
    @patch("os.stat")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_saveLibraryFile(self, mock_open, mock_exists, mock_stat, mock_makedirs):
        mock_stat_res = MagicMock()
        mock_stat_res.st_size = 100
        mock_stat_res.st_mtime = 1000
        mock_stat.return_value = mock_stat_res
        
        res = self.ls.saveLibraryFile("/fake/test.txt", "123")
        print(f"SAVE LIBRARY RES: {res}")
        self.assertTrue(res["success"])
        mock_open().write.assert_called_with("123")

    @patch("src.api_services.library_service.LibraryService._update_page_map_balloon")
    @patch("src.utils.txt_sync.sync_chapter_txt")
    @patch("os.path.exists", return_value=True)
    def test_updateBalloonText(self, mock_exists, mock_sync, mock_update):
        mock_update.return_value = {"success": True, "map_path": "/fake/map.json", "new_text": "text"}
        mock_sync.return_value = {"success": True}
        res = self.ls.updateBalloonText(
            "/fake/test.txt",
            "01.jpg", 
            1, 
            "text"
        )
        self.assertTrue(res["success"])
