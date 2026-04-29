import logging
import subprocess
import platform
from .base import BaseActuator

logger = logging.getLogger("atena.notification")

class NotificationActuator(BaseActuator):
    """Envia notificaes para o sistema operacional."""
    def _check_dependencies(self):
        # Tenta importar bibliotecas especficas de cada SO
        self._notifier = None
        system = platform.system()
        if system == "Linux":
            try:
                from plyer import notification
                self._notifier = notification
            except ImportError:
                # Fallback para notify-send via subprocess
                import subprocess
                self._notifier = "notify-send"
        elif system == "Windows":
            try:
                from win10toast import ToastNotifier
                self._notifier = ToastNotifier()
            except ImportError:
                self._notifier = None
        elif system == "Darwin":  # macOS
            try:
                from pync import Notifier
                self._notifier = Notifier
            except ImportError:
                self._notifier = None

    def send_notification(self, title: str, message: str, timeout=5):
        """Envia notificao."""
        system = platform.system()
        try:
            if system == "Linux":
                if self._notifier == "notify-send":
                    subprocess.run(["notify-send", title, message, f"-t", str(timeout*1000)])
                elif self._notifier:
                    self._notifier.notify(title=title, message=message, timeout=timeout)
            elif system == "Windows" and self._notifier:
                self._notifier.show_toast(title, message, duration=timeout)
            elif system == "Darwin" and self._notifier:
                self._notifier.notify(message, title=title)
            else:
                print(f"[Notification] {title}: {message}")
            self.log_action("send_notification", {"title": title, "message": message})
        except Exception as e:
            logger.error(f"Falha ao enviar notificao: {e}")
