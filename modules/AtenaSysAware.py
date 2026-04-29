import os
import sys
import platform
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger("atena.sysaware")

class AtenaSysAware:
    """
    Fornece consciência do sistema e recursos de hardware para a ATENA.
    """
    def __init__(self):
        self.start_time = psutil.boot_time()

    def get_profile(self) -> Dict[str, Any]:
        """
        Coleta um perfil detalhado do sistema atual.
        """
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            profile = {
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "cpu_count": psutil.cpu_count(logical=True),
                "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
                "memory_total_gb": round(mem.total / (1024**3), 2),
                "memory_available_gb": round(mem.available / (1024**3), 2),
                "memory_percent": mem.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_percent": disk.percent,
                "python_version": sys.version.split()[0],
                "pid": os.getpid(),
                "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else "N/A"
            }
            return profile
        except Exception as e:
            logger.error(f"Erro ao coletar perfil do sistema: {e}")
            return {"error": str(e)}

    def get_resource_usage(self) -> Dict[str, float]:
        """
        Retorna o uso atual de recursos pelo processo.
        """
        process = psutil.Process(os.getpid())
        return {
            "cpu_percent": process.cpu_percent(interval=0.1),
            "memory_mb": process.memory_info().rss / (1024 * 1024)
        }
