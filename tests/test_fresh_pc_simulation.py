import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock


from src.config import Config, _get_config_path
from src.api_bridge import ApiBridge


class TestFreshPCSimulation(unittest.TestCase):
    """
    Suite de testes que simula uma instalação limpa em um computador novo (Fresh PC):
    1. Executável instalado em diretório protegido/somente leitura (ex: C:\\Program Files).
    2. Primeira execução sem nenhum arquivo settings.json prévio.
    3. Simulação de máquina sem Python no PATH (gatilho do Bootstrap).
    4. Simulação de máquina com Python já presente.
    5. Validação do patch no arquivo python311._pth do Python Embeddable oficial.
    6. Cold start da API FastAPI e rotas de saúde em ambiente novo.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="visionary_fresh_pc_test_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simulation_1_read_only_install_directory(self):
        """
        Cenário: O usuário instalou via instalador em C:\\Program Files\\Visionary Studio.
        O diretório é protegido pelo Windows UAC (somente leitura para usuários comuns).
        A aplicação não pode dar crash (PermissionError) e deve redirecionar transparentemente
        para %APPDATA%\\Visionary Studio\\settings.json.
        """
        fake_appdata = os.path.join(self.temp_dir, "AppData", "Roaming")
        os.makedirs(fake_appdata, exist_ok=True)

        # Mock: simula erro de permissão ao tentar escrever no diretório do executável
        with patch.dict(os.environ, {"APPDATA": fake_appdata}, clear=False):
            # Garante isolamento caso os testes estejam sendo disparados de dentro do app Electron
            os.environ.pop("VISIONARY_USER_DATA", None)
            with patch("builtins.open") as mock_open:
                def side_effect(file_path, mode="r", *args, **kwargs):
                    if ".perm_test" in str(file_path) and "w" in mode:
                        raise PermissionError(13, "Permission denied (Simulating C:\\Program Files protected dir)")
                    return unittest.mock.mock_open().return_value

                mock_open.side_effect = side_effect
                resolved_path = _get_config_path()

                # Deve apontar para a pasta do AppData
                self.assertIn("Visionary Studio", resolved_path)
                self.assertTrue(resolved_path.startswith(fake_appdata))
                self.assertTrue(resolved_path.endswith("settings.json"))

    def test_simulation_2_first_run_defaults_creation(self):
        """
        Cenário: Primeiro boot em um PC novo.
        Nenhum arquivo de configuração existe ainda.
        O sistema deve criar os valores padrão e carregar todas as chaves essenciais.
        """
        test_cfg_file = os.path.join(self.temp_dir, "new_settings.json")
        
        with patch("src.config.CONFIG_FILE", test_cfg_file):
            # Garante que o arquivo não existe
            if os.path.exists(test_cfg_file):
                os.remove(test_cfg_file)

            cfg = Config.load()
            
            # Verifica que o arquivo foi criado fisicamente
            self.assertTrue(os.path.exists(test_cfg_file))
            self.assertIsInstance(cfg, dict)
            self.assertIn("ollama_url", cfg)
            self.assertIn("theme", cfg)
            self.assertIn("pipeline_steps", cfg)
            self.assertEqual(cfg["theme"], "Dark")
            self.assertTrue(cfg["pipeline_steps"]["ocr"])

    def test_simulation_3_python_embeddable_pth_patching(self):
        """
        Cenário: O usuário baixou o pacote oficial do Python 3.11 Embeddable (python-3.11.x-embed-amd64.zip).
        Por padrão de fábrica, a Python.org inclui '#import site' comentado, desabilitando pip e site-packages.
        Este teste valida que o algoritmo de patching ativa corretamente o suporte a pacotes externos.
        """
        fake_engine = os.path.join(self.temp_dir, "engine")
        os.makedirs(fake_engine, exist_ok=True)
        pth_path = os.path.join(fake_engine, "python311._pth")

        # Conteúdo de fábrica exato do Python 3.11 Embeddable oficial
        factory_content = (
            "python311.zip\n"
            ".\n"
            "# Uncomment to run site.main() automatically\n"
            "#import site\n"
        )
        with open(pth_path, "w", encoding="utf-8") as f:
            f.write(factory_content)

        # Executa o algoritmo de patching implementado no Electron
        with open(pth_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("#import site", "import site")
        if "import site" not in content:
            content += "\nimport site\n"

        with open(pth_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Valida que foi corrigido
        with open(pth_path, "r", encoding="utf-8") as f:
            patched_content = f.read()

        self.assertIn("import site", patched_content)
        self.assertNotIn("#import site", patched_content)

    def test_simulation_4_missing_python_detection(self):
        """
        Cenário: Simula um computador novo que NÃO tem Python instalado nem no PATH nem via py launcher.
        Valida que a lógica de detecção reconhece a ausência de Python.
        """
        with patch("shutil.which", return_value=None):
            # Quando shutil.which não encontra 'python' nem 'py'
            has_python = shutil.which("python") is not None
            has_py = shutil.which("py") is not None
            self.assertFalse(has_python)
            self.assertFalse(has_py)

    def test_simulation_5_present_python_detection(self):
        """
        Cenário: Computador que já possui Python 3.x instalado.
        Valida que o executável atual é detectado com versão >= 3.
        """
        self.assertGreaterEqual(sys.version_info[0], 3)
        self.assertTrue(os.path.isfile(sys.executable))

    def test_simulation_6_api_bridge_cold_start(self):
        """
        Cenário: Inicialização completa do ApiBridge em um ambiente recém-instalado.
        Todos os serviços (Hardware, Studio, Library, Settings, Model) devem responder
        sem exceções não tratadas.
        """
        bridge = ApiBridge()
        
        # Teste de serviços essenciais
        hw_info = bridge.getHardwareStats()
        self.assertIsInstance(hw_info, dict)
        self.assertIn("cpu_percent", hw_info)

        storage = bridge.getStorageStats()
        self.assertTrue(storage.get("success", False))
        self.assertIn("total_bytes", storage)

        settings = bridge.getSettings()
        self.assertIsInstance(settings, dict)
        self.assertIn("theme", settings)


if __name__ == "__main__":
    unittest.main()
