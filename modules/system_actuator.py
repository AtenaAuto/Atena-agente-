import platform
import subprocess
import logging
import shutil
import re
from typing import Optional, Dict, Any, Tuple
from .base import BaseActuator

logger = logging.getLogger("atena.actuator.system")

# Tentativas de import para funcionalidades extras
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

try:
    import glob
    HAS_GLOB = True
except ImportError:
    HAS_GLOB = False


class SystemActuator(BaseActuator):
    """
    Atuador para aes de sistema operacional:
      - Controle de volume (get/set)
      - Bloqueio de tela
      - Shutdown / restart / sleep / hibernate
      - Controle de brilho (experimental)
      - Execuo segura com confirmao e dry-run
    """

    def __init__(
        self,
        sysaware: Optional[Any] = None,
        enable_history: bool = False,
        dry_run: bool = False,
        confirm_destructive: bool = True,
    ):
        """
        Args:
            sysaware: Instncia de SysAware (fornece contexto adicional)
            enable_history: Se True, mantm histrico de aes
            dry_run: Se True, apenas simula aes (no executa comandos reais)
            confirm_destructive: Se True, pede confirmao antes de shutdown/restart
        """
        super().__init__(sysaware=sysaware, enable_history=enable_history)
        self.dry_run = dry_run
        self.confirm_destructive = confirm_destructive
        self._platform = platform.system()
        self._check_dependencies()
        self._volume_interface = None
        self._init_volume_interface()

    # ------------------------------------------------------------
    # Verificao de dependncias (com shutil.which)
    # ------------------------------------------------------------
    def _check_dependencies(self) -> None:
        """Verifica se as ferramentas necessrias esto disponveis."""
        self._has_pactl = False
        self._has_amixer = False
        self._has_nircmd = False

        if self._platform == "Linux":
            # Verifica pactl
            if shutil.which("pactl"):
                self._has_pactl = True
                logger.info("pactl disponvel para controle de volume")
            # Verifica amixer
            if shutil.which("amixer"):
                self._has_amixer = True
                logger.info("amixer disponvel como fallback para volume")

            if not (self._has_pactl or self._has_amixer):
                logger.warning(
                    "Nenhuma ferramenta de volume encontrada (pactl/amixer). "
                    "Instale pulseaudio-utils ou alsa-utils."
                )

        elif self._platform == "Windows":
            if HAS_PYCAW:
                logger.info("pycaw disponvel para controle avanado de volume")
            else:
                # Fallback: tentar nircmd
                if shutil.which("nircmd"):
                    self._has_nircmd = True
                    logger.info("nircmd disponvel como fallback para volume")
                else:
                    logger.warning(
                        "Nenhuma ferramenta de volume encontrada (pycaw ou nircmd). "
                        "Considere instalar pycaw ou nircmd."
                    )

    def _init_volume_interface(self) -> None:
        """Inicializa interface de volume especfica da plataforma."""
        if self._platform == "Windows" and HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._volume_interface = interface.QueryInterface(IAudioEndpointVolume)
            except Exception as e:
                logger.warning(f"Falha ao inicializar pycaw: {e}")

    # ------------------------------------------------------------
    # Utilitrios
    # ------------------------------------------------------------
    def _run_cmd(
        self, cmd: list, check: bool = True, capture: bool = False
    ) -> Optional[str]:
        """
        Executa comando shell com tratamento de erros e dry-run.

        Args:
            cmd: Lista de argumentos do comando
            check: Se True, levanta exceo em caso de erro
            capture: Se True, retorna a sada padro

        Returns:
            Sada padro (strip) se capture=True e comando bem-sucedido, seno None

        Raises:
            RuntimeError: Se o comando falhar e check=True
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Simulando comando: {' '.join(cmd)}")
            return None

        try:
            if capture:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=check
                )
                return result.stdout.strip()
            else:
                subprocess.run(cmd, check=check)
                return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Comando falhou: {' '.join(cmd)} - {e.stderr if capture else e}")
            if check:
                raise RuntimeError(f"Falha ao executar comando: {e}") from e
            return None
        except FileNotFoundError as e:
            logger.error(f"Comando no encontrado: {cmd[0]}")
            if check:
                raise RuntimeError(f"Comando no encontrado: {cmd[0]}") from e
            return None

    def _confirm_destructive(self, action: str) -> bool:
        """Pede confirmao do usurio para aes destrutivas."""
        if not self.confirm_destructive:
            return True
        resposta = input(f"  Confirmar {action} do sistema? (s/N): ").strip().lower()
        return resposta == "s"

    # ------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------
    def get_volume(self) -> Optional[int]:
        """
        Retorna o volume atual (0-100) ou None se no suportado.

        Para Windows, usa pycaw (se disponvel) ou nircmd.
        Para Linux, usa pactl ou amixer.
        Para macOS, usa osascript.
        """
        if self._platform == "Windows":
            if self._volume_interface:
                return int(self._volume_interface.GetMasterVolumeLevelScalar() * 100)
            elif self._has_nircmd:
                out = self._run_cmd(["nircmd", "changesysvolume"], capture=True)
                if out and "Current Volume:" in out:
                    val = int(out.split(":")[1].strip())
                    return int(val / 655.35)
            return None

        elif self._platform == "Linux":
            if self._has_pactl:
                out = self._run_cmd(
                    ["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture=True
                )
                match = re.search(r"(\d+)%", out)
                if match:
                    return int(match.group(1))
            elif self._has_amixer:
                out = self._run_cmd(["amixer", "sget", "Master"], capture=True)
                match = re.search(r"\[(\d+)%\]", out)
                if match:
                    return int(match.group(1))
            return None

        elif self._platform == "Darwin":
            out = self._run_cmd(
                ["osascript", "-e", "output volume of (get volume settings)"], capture=True
            )
            if out and out.isdigit():
                return int(out)
            return None

        return None

    def set_volume(self, level: int) -> None:
        """
        Ajusta volume (0-100). Lana exceo se no for possvel.
        """
        if not 0 <= level <= 100:
            raise ValueError("Volume deve estar entre 0 e 100")

        if self.dry_run:
            self.log_action("set_volume", {"level": level, "dry_run": True})
            return

        if self._platform == "Windows":
            if self._volume_interface:
                self._volume_interface.SetMasterVolumeLevelScalar(level / 100.0, None)
                self.log_action("set_volume", {"level": level, "method": "pycaw"})
                return
            elif self._has_nircmd:
                val = int(level * 655.35)
                self._run_cmd(["nircmd", "setsysvolume", str(val)])
                self.log_action("set_volume", {"level": level, "method": "nircmd"})
                return
            else:
                raise RuntimeError(
                    "Nenhum mtodo de controle de volume disponvel no Windows"
                )

        elif self._platform == "Linux":
            if self._has_pactl:
                self._run_cmd(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"]
                )
            elif self._has_amixer:
                self._run_cmd(["amixer", "sset", "Master", f"{level}%"])
            else:
                raise RuntimeError(
                    "Nenhuma ferramenta de volume encontrada (pactl/amixer)"
                )
            self.log_action("set_volume", {"level": level})

        elif self._platform == "Darwin":
            script = f"set volume output volume {level}"
            self._run_cmd(["osascript", "-e", script])
            self.log_action("set_volume", {"level": level})

        else:
            raise NotImplementedError(
                f"Controle de volume no suportado em {self._platform}"
            )

    # ------------------------------------------------------------
    # Aes do sistema
    # ------------------------------------------------------------
    def lock_screen(self) -> None:
        """Bloqueia a tela."""
        if self.dry_run:
            self.log_action("lock_screen", {"dry_run": True})
            return

        if self._platform == "Linux":
            for cmd in [
                ["xdg-screensaver", "lock"],
                ["gnome-screensaver-command", "--lock"],
                ["loginctl", "lock-session"],
            ]:
                if shutil.which(cmd[0]):
                    try:
                        self._run_cmd(cmd)
                        self.log_action("lock_screen", {"method": cmd[0]})
                        return
                    except RuntimeError:
                        continue
            raise RuntimeError("Nenhum comando de lock screen encontrado no Linux")

        elif self._platform == "Windows":
            self._run_cmd(["rundll32.exe", "user32.dll,LockWorkStation"])
            self.log_action("lock_screen")

        elif self._platform == "Darwin":
            self._run_cmd(["pmset", "displaysleepnow"])
            self.log_action("lock_screen")

        else:
            raise NotImplementedError(
                f"Lock screen no suportado em {self._platform}"
            )

    def shutdown(self, delay: int = 0) -> None:
        """Desliga o computador aps `delay` segundos."""
        if not self._confirm_destructive("shutdown"):
            self.log_action("shutdown_cancelled", {"delay": delay})
            return

        if self.dry_run:
            self.log_action("shutdown", {"delay": delay, "dry_run": True})
            return

        if self._platform == "Linux":
            cmd = ["shutdown", "-h", f"+{delay}" if delay else "now"]
        elif self._platform == "Windows":
            cmd = ["shutdown", "/s", "/t", str(delay)]
        elif self._platform == "Darwin":
            cmd = ["sudo", "shutdown", "-h", f"+{delay}" if delay else "now"]
        else:
            raise NotImplementedError(f"Shutdown no suportado em {self._platform}")

        self._run_cmd(cmd)
        self.log_action("shutdown", {"delay": delay})

    def restart(self, delay: int = 0) -> None:
        """Reinicia o computador aps `delay` segundos."""
        if not self._confirm_destructive("restart"):
            self.log_action("restart_cancelled", {"delay": delay})
            return

        if self.dry_run:
            self.log_action("restart", {"delay": delay, "dry_run": True})
            return

        if self._platform == "Linux":
            cmd = ["shutdown", "-r", f"+{delay}" if delay else "now"]
        elif self._platform == "Windows":
            cmd = ["shutdown", "/r", "/t", str(delay)]
        elif self._platform == "Darwin":
            cmd = ["sudo", "shutdown", "-r", f"+{delay}" if delay else "now"]
        else:
            raise NotImplementedError(f"Restart no suportado em {self._platform}")

        self._run_cmd(cmd)
        self.log_action("restart", {"delay": delay})

    def sleep(self) -> None:
        """Coloca o computador em modo de suspenso (sleep)."""
        if self.dry_run:
            self.log_action("sleep", {"dry_run": True})
            return

        if self._platform == "Linux":
            for cmd in [["systemctl", "suspend"], ["pm-suspend"]]:
                if shutil.which(cmd[0]):
                    try:
                        self._run_cmd(cmd)
                        self.log_action("sleep", {"method": cmd[0]})
                        return
                    except RuntimeError:
                        continue
            raise RuntimeError("Nenhum comando de suspenso encontrado no Linux")
        elif self._platform == "Windows":
            self._run_cmd(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"]
            )
            self.log_action("sleep")
        elif self._platform == "Darwin":
            self._run_cmd(["pmset", "sleepnow"])
            self.log_action("sleep")
        else:
            raise NotImplementedError(f"Sleep no suportado em {self._platform}")

    def hibernate(self) -> None:
        """Hiberna o computador."""
        if self.dry_run:
            self.log_action("hibernate", {"dry_run": True})
            return

        if self._platform == "Linux":
            if shutil.which("systemctl"):
                try:
                    self._run_cmd(["systemctl", "hibernate"])
                    self.log_action("hibernate")
                    return
                except RuntimeError:
                    pass
            raise RuntimeError(
                "Hibernao no suportada ou systemctl no disponvel"
            )
        elif self._platform == "Windows":
            self._run_cmd(["shutdown", "/h"])
            self.log_action("hibernate")
        elif self._platform == "Darwin":
            # macOS no tem hibernao direta, mas deep sleep
            self._run_cmd(["pmset", "sleepnow"])
            logger.warning(
                "Hibernate no suportado nativamente no macOS, usando sleep"
            )
        else:
            raise NotImplementedError(
                f"Hibernate no suportado em {self._platform}"
            )

    # ------------------------------------------------------------
    # Controle de brilho (experimental)
    # ------------------------------------------------------------
    def set_brightness(self, level: int) -> None:
        """
        Ajusta brilho da tela (0-100). Suporte limitado a Linux (brightnessctl) e Windows (WMI).
        """
        if not 0 <= level <= 100:
            raise ValueError("Brilho deve estar entre 0 e 100")

        if self.dry_run:
            self.log_action("set_brightness", {"level": level, "dry_run": True})
            return

        if self._platform == "Linux":
            # Tenta brightnessctl
            if shutil.which("brightnessctl"):
                try:
                    self._run_cmd(["brightnessctl", "set", f"{level}%"])
                    self.log_action(
                        "set_brightness",
                        {"level": level, "method": "brightnessctl"},
                    )
                    return
                except RuntimeError:
                    pass
            # Fallback via sysfs
            if HAS_GLOB:
                backlight = glob.glob("/sys/class/backlight/*/brightness")
                if backlight:
                    max_file = backlight[0].replace("brightness", "max_brightness")
                    try:
                        with open(max_file, "r") as f:
                            max_val = int(f.read().strip())
                        new_val = int(max_val * level / 100)
                        with open(backlight[0], "w") as f:
                            f.write(str(new_val))
                        self.log_action(
                            "set_brightness", {"level": level, "method": "sysfs"}
                        )
                        return
                    except (IOError, OSError) as e:
                        logger.error(f"Falha ao escrever brilho via sysfs: {e}")
            raise RuntimeError(
                "Nenhum mtodo para controlar brilho no Linux (brightnessctl ou sysfs)"
            )

        elif self._platform == "Windows":
            # Usa WMI via PowerShell
            script = f"""
            $brightness = {level}
            $obj = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods
            $obj.WmiSetBrightness(1, $brightness)
            """
            self._run_cmd(["powershell", "-Command", script])
            self.log_action("set_brightness", {"level": level, "method": "WMI"})

        else:
            raise NotImplementedError(
                f"Controle de brilho no suportado em {self._platform}"
            )

    def get_brightness(self) -> Optional[int]:
        """Retorna o brilho atual (0-100) ou None se no suportado."""
        if self._platform == "Linux":
            if HAS_GLOB:
                backlight = glob.glob("/sys/class/backlight/*/brightness")
                if backlight:
                    max_file = backlight[0].replace("brightness", "max_brightness")
                    try:
                        with open(backlight[0], "r") as f:
                            cur = int(f.read().strip())
                        with open(max_file, "r") as f:
                            maxv = int(f.read().strip())
                        return int(cur * 100 / maxv)
                    except:
                        pass
            # Fallback via brightnessctl
            if shutil.which("brightnessctl"):
                out = self._run_cmd(["brightnessctl", "g"], capture=True)
                if out and out.isdigit():
                    cur = int(out)
                    max_out = self._run_cmd(["brightnessctl", "m"], capture=True)
                    if max_out and max_out.isdigit():
                        maxv = int(max_out)
                        return int(cur * 100 / maxv)
            return None

        elif self._platform == "Windows":
            # via PowerShell
            out = self._run_cmd(
                [
                    "powershell",
                    "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness",
                ],
                capture=True,
            )
            if out and out.isdigit():
                return int(out)
            return None

        elif self._platform == "Darwin":
            # macOS: usar 'brightness' (se instalado) ou osascript?
            # Osascript no fornece leitura, ento retorna None por enquanto
            return None

        return None
