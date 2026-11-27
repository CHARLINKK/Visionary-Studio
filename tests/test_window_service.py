import unittest
from unittest.mock import patch, MagicMock
from src.api_services.window_service import WindowService

class TestWindowService(unittest.TestCase):
    def setUp(self):
        self.ws = WindowService()
        self.mock_window = MagicMock()
        self.mock_window.title = "Test Window"
        self.ws.set_window(self.mock_window)

    def test_setup_native_frame(self):
        # Deve ser no-op
        self.ws.setup_native_frame()

    @patch("src.api_services.window_service.user32")
    def test_get_hwnd(self, mock_user32):
        mock_user32.FindWindowW.return_value = 12345
        hwnd = self.ws._get_hwnd()
        self.assertEqual(hwnd, 12345)
        
        # Test sem título
        self.ws._window_title = None
        self.assertIsNone(self.ws._get_hwnd())

    @patch("src.api_services.window_service.user32")
    def test_get_hwnd_exception(self, mock_user32):
        mock_user32.FindWindowW.side_effect = Exception("Erro")
        self.assertIsNone(self.ws._get_hwnd())

    def test_get_window(self):
        self.assertEqual(self.ws._get_window(), self.mock_window)
        
        self.ws._window = None
        self.assertIsNone(self.ws._get_window())

    def test_minimize(self):
        res = self.ws.minimize()
        self.assertTrue(res)
        self.mock_window.minimize.assert_called_once()
        
    def test_minimize_error(self):
        self.mock_window.minimize.side_effect = Exception("Erro")
        res = self.ws.minimize()
        self.assertFalse(res)

    @patch("src.api_services.window_service.user32")
    def test_toggle_maximize_from_zoomed(self, mock_user32):
        mock_user32.FindWindowW.return_value = 123
        mock_user32.IsZoomed.return_value = True # Já está maximizado
        
        res = self.ws.toggle_maximize()
        self.assertFalse(res) # False significa que não está mais maximizado
        self.mock_window.restore.assert_called_once()
        
    @patch("src.api_services.window_service.user32")
    def test_toggle_maximize_from_restored(self, mock_user32):
        mock_user32.FindWindowW.return_value = 123
        mock_user32.IsZoomed.return_value = False # Não está maximizado
        
        res = self.ws.toggle_maximize()
        self.assertTrue(res) # True significa que agora está maximizado
        self.mock_window.maximize.assert_called_once()

    def test_toggle_maximize_no_window(self):
        self.ws._window = None
        res = self.ws.toggle_maximize()
        self.assertFalse(res)
            
    def test_toggle_maximize_error(self):
        self.ws._get_hwnd = MagicMock(side_effect=Exception("Erro"))
        res = self.ws.toggle_maximize()
        self.assertFalse(res)

    @patch("src.api_services.window_service.user32")
    def test_get_is_maximized(self, mock_user32):
        mock_user32.FindWindowW.return_value = 123
        mock_user32.IsZoomed.return_value = True
        self.assertTrue(self.ws.get_is_maximized())
        
        mock_user32.FindWindowW.return_value = None
        self.ws._is_maximized = False
        self.assertFalse(self.ws.get_is_maximized())

    @patch("src.api_services.window_service.user32")
    def test_start_tear_off_drag(self, mock_user32):
        mock_user32.FindWindowW.return_value = 123
        res = self.ws.start_tear_off_drag(0, 0, 0)
        self.assertTrue(res)

    @patch("src.api_services.window_service.user32")
    def test_show_system_menu(self, mock_user32):
        mock_user32.FindWindowW.return_value = 123
        res = self.ws.show_system_menu(0, 0)
        self.assertTrue(res)

    def test_close(self):
        res = self.ws.close()
        self.assertTrue(res)
        self.mock_window.destroy.assert_called_once()
        
    def test_close_error(self):
        self.mock_window.destroy.side_effect = Exception("Erro")
        res = self.ws.close()
        self.assertFalse(res)
