"""
Serviço da Biblioteca de Roteiros.

Coordena a varredura de capítulos (`LibraryScanner`), a edição e sincronização
bidirecional entre `.txt` e `_map.json` (`LibraryScriptManager`) e a abertura
segura de pastas no Windows Explorer.
"""

import os
import subprocess
from src.api_services.library_scanner import LibraryScanner
from src.api_services.library_script_manager import LibraryScriptManager


class LibraryService:
    """Fachada da Biblioteca exposta ao frontend via `ApiBridge`."""

    def __init__(self, workspace_context=None, api_bridge=None, scanner=None, script_manager=None):
        from src.utils.workspace_context import WorkspaceContext
        self.context, self.api = WorkspaceContext.resolve_service_binding(
            workspace_context, api_bridge, "MEU COMPUTADOR"
        )

        self.scanner = scanner or LibraryScanner()
        self.script_manager = script_manager or LibraryScriptManager(scanner=self.scanner)

    @property
    def current_path(self):
        return self.context.current_path if self.context else getattr(self.api, "current_path", None)

    def listLibraryFiles(self) -> dict:
        """Lista todos os roteiros encontrados nos workspaces ativos e na biblioteca."""
        return self.scanner.list_library_files(current_path=self.current_path)

    def _resolve_chapter_dir(self, script_path) -> str:
        return self.scanner.resolve_chapter_dir(script_path, current_path=self.current_path)

    def readLibraryFile(self, path) -> dict:
        """Lê o roteiro do capítulo preenchendo páginas silenciosas quando aplicável."""
        file_path = path.get("path") if isinstance(path, dict) else str(path)
        return self.script_manager.read_library_file(
            file_path,
            resolve_chapter_dir_fn=self._resolve_chapter_dir
        )

    def deleteLibraryFile(self, path) -> dict:
        return self.script_manager.delete_library_file(path)

    def _update_page_map_balloon(self, chapter_dir, page_name, balloon_index, new_text, original_text=None, balloon_id=None) -> dict:
        return self.script_manager.update_page_map_balloon(
            chapter_dir, page_name, balloon_index, new_text, original_text, balloon_id=balloon_id
        )

    def updateBalloonText(self, script_path, page_name, balloon_index, new_text, original_text=None, balloon_id=None) -> dict:
        """Atualiza a tradução de um balão no `_map.json` e ressincroniza o `.txt`."""
        file_path = script_path.get("path") if isinstance(script_path, dict) else str(script_path)
        return self.script_manager.update_balloon_text(
            file_path,
            page_name,
            balloon_index,
            new_text,
            original_text=original_text,
            resolve_chapter_dir_fn=self._resolve_chapter_dir,
            update_map_fn=self._update_page_map_balloon,
            balloon_id=balloon_id
        )

    def _sync_json_from_script(self, script_path, content, resolve_chapter_dir_fn=None):
        resolver = resolve_chapter_dir_fn or self._resolve_chapter_dir
        return self.script_manager.sync_json_from_script(
            script_path, content, resolve_chapter_dir_fn=resolver
        )

    def saveLibraryFile(self, path, content) -> dict:
        """Salva o `.txt` atomicamente e propaga edições de volta aos mapas JSON."""
        file_path = path.get("path") if isinstance(path, dict) else str(path)
        return self.script_manager.save_library_file(
            file_path,
            content,
            resolve_chapter_dir_fn=self._resolve_chapter_dir,
            sync_json_fn=self._sync_json_from_script
        )

    def syncChapterTxt(self, chapter_dir, chapter_name=None):
        target_dir = chapter_dir.get("path") if isinstance(chapter_dir, dict) else str(chapter_dir)
        from src.utils.txt_sync import sync_chapter_txt
        return sync_chapter_txt(target_dir, chapter_name)

    def exportScript(self, path, export_format="clean_txt") -> dict:
        """Exporta o roteiro em texto limpo ou RTF compatível com Microsoft Word."""
        file_path = path.get("path") if isinstance(path, dict) else str(path)
        return self.script_manager.export_script(file_path, export_format=export_format)

    def openFileInExplorer(self, path) -> dict:
        """
        Abre a pasta pai no Windows Explorer sem usar a flag `/select`.
        No Windows, `/select` interpreta vírgulas no nome da pasta/arquivo como
        delimitadores de argumento e falha silenciosamente em capítulos com `,` no título.
        """
        try:
            target = path.get("path") if isinstance(path, dict) else str(path) if path else ""
            if not target:
                return self.openLibraryFolder()

            clean_path = os.path.normpath(target).replace('/', '\\')

            if os.path.isdir(clean_path):
                subprocess.Popen(['explorer', clean_path])
                return {"success": True, "path": clean_path}

            parent = os.path.dirname(clean_path)
            if parent and os.path.exists(parent):
                subprocess.Popen(['explorer', parent])
                return {"success": True, "path": parent}

            return self.openLibraryFolder()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def openLibraryFolder(self) -> dict:
        """Abre a pasta do capítulo ativo ou a `baseFolder` configurada no Explorer."""
        try:
            from src.config import Config

            target_dir = None
            current_path = getattr(self.api, "current_path", None)
            if not current_path:
                current_path = Config.get("last_opened_folder", "")

            if current_path and os.path.exists(current_path):
                if os.path.isdir(current_path):
                    parent = os.path.dirname(os.path.normpath(current_path))
                    target_dir = parent if os.path.exists(parent) and os.path.isdir(parent) else current_path
                else:
                    target_dir = os.path.dirname(os.path.normpath(current_path))

            if not target_dir or not os.path.exists(target_dir):
                base_folder = Config.get("baseFolder", "")
                if base_folder and os.path.exists(base_folder):
                    target_dir = base_folder

            if not target_dir or not os.path.exists(target_dir):
                target_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'library'))
                os.makedirs(target_dir, exist_ok=True)

            clean_dir = os.path.normpath(target_dir).replace('/', '\\')
            subprocess.Popen(['explorer', clean_dir])
            return {"success": True, "path": clean_dir}
        except Exception as e:
            return {"success": False, "error": str(e)}
