import os
import re
import unittest
import importlib
from src.api_bridge import ApiBridge

class TestRpcContract(unittest.TestCase):
    def test_rpc_contract(self):
        gui_src_dir = os.path.join(os.path.dirname(__file__), '..', 'gui', 'src')
        self.assertTrue(os.path.exists(gui_src_dir), "O diretório gui/src não foi encontrado")
        
        methods_called_by_frontend = set()
        pattern = re.compile(r'(?:window\.pywebview(?:\?)?\.api(?:\?)?|clientApi(?:\?)?)\.(\w+)')
        
        for root, _, files in os.walk(gui_src_dir):
            for file in files:
                if file.endswith(('.js', '.jsx')):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Remove blocos de comentário /* ... */ para evitar falsos positivos
                            content = re.sub(r'/\*[\s\S]*?\*/', '', content)
                            # Remove comentários de linha // ...
                            content = re.sub(r'//.*', '', content)
                            
                            matches = pattern.findall(content)
                            for match in matches:
                                methods_called_by_frontend.add(match)
                    except Exception:
                        pass
        
        # Métodos gerenciados pelo bridge/Electron ou handlers de interface
        electron_handled = {
            "minimize", "toggle_maximize", "get_is_maximized", "close", 
            "selectFolder", "select_folder", "openPath", "showItemInFolder",
            "getServerUrl", "on"
        }
        
        missing_in_backend = []
        api_bridge_instance = ApiBridge()
        
        for method in methods_called_by_frontend:
            if method in electron_handled:
                continue
            
            if method not in ApiBridge.__dict__:
                missing_in_backend.append(f"{method} (not explicitly registered in ApiBridge.__dict__)")
            elif not callable(getattr(api_bridge_instance, method)):
                missing_in_backend.append(f"{method} (not callable)")
                
        self.assertEqual(len(missing_in_backend), 0, f"Os seguintes métodos chamados no frontend não existem no ApiBridge: {missing_in_backend}")

    def test_open_external_protocol_validation(self):
        bridge = ApiBridge()
        invalid_res = bridge.openExternal("file:///C:/Windows/notepad.exe")
        self.assertFalse(invalid_res.get("success"))
        self.assertEqual(invalid_res.get("error"), "Protocolo inválido")

    def test_open_folder_delegates_to_library_service(self):
        from unittest.mock import patch
        bridge = ApiBridge()
        with patch.object(bridge._library_service, "openFileInExplorer", return_value={"success": True}) as mock_open:
            res = bridge.open_folder("C:/test_folder")
            self.assertTrue(res.get("success"))
            mock_open.assert_called_once_with("C:/test_folder")
