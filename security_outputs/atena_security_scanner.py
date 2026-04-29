#!/usr/bin/env python3
# atena_security_scanner.py

import os
import stat
import pwd
import spwd
import socket
import threading
import json
import logging
from queue import Queue
from typing import List, Dict, Any

# Configuração do logger
logger = logging.getLogger('SecurityScanner')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(threadName)s - %(message)s'
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class SecurityScanner:
    def __init__(self):
        self.open_ports: Dict[int, bool] = {}
        self.dangerous_files: List[str] = []
        self.users_info: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def scan_open_ports(self, host: str = '127.0.0.1',
                        ports: List[int] = [80, 443, 22, 8080, 3306]) -> None:
        """
        Verifica portas abertas no host especificado usando threading para performance.
        Atualiza self.open_ports com {porta: True/False}.
        """
        logger.info(f"Iniciando scan de portas em {host} para portas: {ports}")
        self.open_ports = {}
        port_queue = Queue()

        for port in ports:
            port_queue.put(port)

        def worker():
            while not port_queue.empty():
                port = port_queue.get()
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.settimeout(1.0)
                        result = sock.connect_ex((host, port))
                        is_open = (result == 0)
                        with self._lock:
                            self.open_ports[port] = is_open
                        logger.debug(f"Porta {port} {'ABERTA' if is_open else 'FECHADA'}")
                except Exception as e:
                    logger.error(f"Erro ao escanear porta {port}: {e}")
                    with self._lock:
                        self.open_ports[port] = False
                finally:
                    port_queue.task_done()

        thread_count = min(10, len(ports))
        threads = []
        for _ in range(thread_count):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        port_queue.join()
        logger.info("Scan de portas finalizado.")

    def check_file_permissions(self, directory: str = '.') -> None:
        """
        Identifica arquivos com permissões perigosas (ex: 777) no diretório especificado.
        Atualiza self.dangerous_files com caminhos dos arquivos.
        """
        logger.info(f"Iniciando verificação de permissões perigosas em: {directory}")
        self.dangerous_files = []

        for root, dirs, files in os.walk(directory):
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    st_mode = os.stat(filepath).st_mode
                    permissions = stat.S_IMODE(st_mode)
                    # Permissão 0o777 = leitura, escrita e execução para todos
                    if permissions & 0o777 == 0o777:
                        self.dangerous_files.append(filepath)
                        logger.debug(f"Arquivo com permissão 777 detectado: {filepath}")
                except Exception as e:
                    logger.warning(f"Não foi possível verificar arquivo {filepath}: {e}")

        logger.info(f"Verificação de permissões finalizada. "
                    f"Arquivos perigosos encontrados: {len(self.dangerous_files)}")

    def audit_system_users(self) -> None:
        """
        Lista usuários do sistema e verifica hashes de senha vazios (simulado/seguro).
        Atualiza self.users_info com lista de dicts contendo 'username' e 'password_empty' (bool).
        """
        logger.info("Iniciando auditoria de usuários do sistema (simulada).")
        self.users_info = []

        try:
            all_users = pwd.getpwall()
        except Exception as e:
            logger.error(f"Erro ao obter usuários do sistema: {e}")
            return

        # Simulação segura: não acessa hashes reais, apenas simula a checagem
        for user in all_users:
            username = user.pw_name
            # Simula que usuários com UID < 1000 são do sistema e não têm senha vazia
            # Usuários >= 1000 tem 5% chance de senha vazia (simulação)
            password_empty = False
            try:
                if user.pw_uid >= 1000:
                    # Simulação pseudoaleatória baseada no hash do nome
                    password_empty = (hash(username) % 20 == 0)
                self.users_info.append({
                    'username': username,
                    'uid': user.pw_uid,
                    'password_empty': password_empty
                })
                logger.debug(f"Usuário: {username}, senha vazia: {password_empty}")
            except Exception as e:
                logger.warning(f"Erro ao processar usuário {username}: {e}")

        logger.info(f"Auditoria de usuários finalizada. Usuários auditados: {len(self.users_info)}")

    def generate_security_report(self) -> None:
        """
        Consolida os achados em um arquivo JSON no caminho
        'atena_evolution/security_audit_results.json'.
        """
        logger.info("Gerando relatório de segurança.")
        report = {
            'open_ports': self.open_ports,
            'dangerous_files': self.dangerous_files,
            'users_info': self.users_info
        }

        output_dir = os.path.join('atena_evolution')
        output_file = os.path.join(output_dir, 'security_audit_results.json')

        try:
            os.makedirs(output_dir, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            logger.info(f"Relatório salvo em: {output_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar relatório: {e}")


def main():
    scanner = SecurityScanner()
    try:
        scanner.scan_open_ports()
    except Exception as e:
        logger.error(f"Falha no scan de portas: {e}")

    try:
        scanner.check_file_permissions()
    except Exception as e:
        logger.error(f"Falha na verificação de permissões: {e}")

    try:
        scanner.audit_system_users()
    except Exception as e:
        logger.error(f"Falha na auditoria de usuários: {e}")

    try:
        scanner.generate_security_report()
    except Exception as e:
        logger.error(f"Falha na geração do relatório: {e}")


if __name__ == '__main__':
    main()