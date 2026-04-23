#!/usr/bin/env python3
import subprocess
import time
import sys
import os
import signal
import logging
from pathlib import Path

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [DAEMON] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("atena_daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("atena.daemon")

class AtenaDaemon:
    """
    Gerenciador de persistência para a ATENA Ω.
    Monitora o processo principal e o reinicia em caso de falha.
    """
    def __init__(self, script_path="main.py"):
        self.script_path = script_path
        self.process = None
        self.running = True
        
        # Registrar sinais de encerramento
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def start(self):
        logger.info("🚀 Iniciando ATENA Ω em modo persistente...")
        while self.running:
            try:
                # Comando para rodar a ATENA em modo não interativo
                # Redireciona stdout/stderr para logs para não travar o terminal
                with open("atena_execution.log", "a") as log_file:
                    self.process = subprocess.Popen(
                        [sys.executable, self.script_path],
                        stdout=log_file,
                        stderr=log_file,
                        preexec_fn=os.setsid # Cria um novo grupo de processos
                    )
                
                logger.info(f"✅ Processo ATENA iniciado (PID: {self.process.pid})")
                
                # Monitora o processo
                while self.process.poll() is None:
                    if not self.running:
                        break
                    time.sleep(5)
                
                if self.running:
                    exit_code = self.process.returncode
                    logger.warning(f"⚠️ ATENA encerrou inesperadamente (Código: {exit_code}). Reiniciando em 10s...")
                    time.sleep(10)
                    
            except Exception as e:
                logger.error(f"❌ Erro crítico no Daemon: {e}")
                time.sleep(30)

    def stop(self, signum, frame):
        logger.info("🛑 Encerrando Daemon e ATENA...")
        self.running = False
        if self.process:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        sys.exit(0)

if __name__ == "__main__":
    # Garante que estamos no diretório correto
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    daemon = AtenaDaemon()
    daemon.start()
