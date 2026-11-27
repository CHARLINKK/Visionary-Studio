import subprocess
import threading
import sys
import os
from src.config import is_test_environment

def send_system_notification(title: str, message: str) -> dict:
    """
    Emite uma notificação nativa do Windows usando o Windows Runtime Toast Notification.
    Executa de forma assíncrona em background thread sem bloquear a aplicação.
    """
    if sys.platform != "win32":
        return {"success": False, "error": "Not supported on non-Windows"}

    # Suprime popups nativos e avisos sonoros do Windows durante a execução de testes automatizados
    if "pytest" in sys.modules or is_test_environment() or os.environ.get("VISIONARY_SILENT_TESTS") == "1":
        return {"success": True, "suppressed": True}

    def _worker():
        try:
            # Escapa aspas para injeção segura no script PowerShell
            safe_title = title.replace('"', '`"').replace("'", "''")
            safe_msg = message.replace('"', '`"').replace("'", "''")

            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastGeneric">
                        <text>{safe_title}</text>
                        <text>{safe_msg}</text>
                    </binding>
                </visual>
            </toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Visionary Studio")
            $notifier.Show($toast)
            '''
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
        except Exception as err:
            pass

    threading.Thread(target=_worker, daemon=True).start()
    return {"success": True}
