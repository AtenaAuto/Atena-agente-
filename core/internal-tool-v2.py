import paramiko
import os

def implantar_atena(hostname, username, password, diretorio_local, diretorio_remoto):
    """
    Realiza a transferência e execução da Atena em um servidor remoto.
    """
    try:
        # 1. Configuração da conexão SSH
        print(f"[*] Conectando ao servidor {hostname}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)

        # 2. Criação do diretório remoto
        ssh.exec_command(f"mkdir -p {diretorio_remoto}")

        # 3. Transferência de arquivos via SFTP
        print("[*] Transferindo arquivos...")
        sftp = ssh.open_sftp()
        
        for arquivo in os.listdir(diretorio_local):
            caminho_local = os.path.join(diretorio_local, arquivo)
            caminho_remoto = os.path.join(diretorio_remoto, arquivo)
            if os.path.isfile(caminho_local):
                sftp.put(caminho_local, caminho_remoto)
        
        sftp.close()

        # 4. Execução da Atena em segundo plano (Background)
        # O comando 'nohup' garante que ela continue rodando após o logout
        print("[*] Iniciando a execução da Atena...")
        comando_execucao = f"cd {diretorio_remoto} && nohup python3 main.py > atena.log 2>&1 &"
        ssh.exec_command(comando_execucao)

        print(f"[+] Atena implantada com sucesso em {hostname}!")
        ssh.close()

    except Exception as e:
        print(f"[!] Erro na implantação: {e}")

# Configurações de exemplo
if __name__ == "__main__":
    # Substitua pelos dados reais do servidor alvo
    config = {
        "hostname": "192.168.1.100",
        "username": "root",
        "password": "sua_senha_segura",
        "diretorio_local": "./atena_source",
        "diretorio_remoto": "/opt/atena"
    }

    implantar_atena(**config)
