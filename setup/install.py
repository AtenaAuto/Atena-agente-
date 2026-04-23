#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install.py — Instalador de dependências da ATENA Ω
Instala os pacotes essenciais para o funcionamento do sistema.
"""

import subprocess
import sys
import os

def run(cmd, check=True):
    print(f"[install] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if check and result.returncode != 0:
        print(f"[install] AVISO: comando retornou código {result.returncode}")
    return result.returncode

def main():
    pip = [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet"]

    # Pacotes essenciais (obrigatórios para main.py importar sem erro)
    essential = [
        "pip",
        "wheel",
        "setuptools",
        "astor",
        "requests",
        "numpy",
        "scipy",
        "pandas",
        "psutil",
        "tqdm",
        "joblib",
        "networkx",
        "matplotlib",
        "seaborn",
        "scikit-learn",
        "Pillow",
        "pydantic",
        "fastapi",
        "uvicorn",
        "python-multipart",
    ]

    # Pacotes opcionais (falha não bloqueia)
    optional = [
        "radon",
        "sentence-transformers",
        "transformers",
        "pytesseract",
        "streamlit",
        "altair<5",
    ]

    print("=" * 60)
    print("ATENA Ω — Instalando dependências essenciais")
    print("=" * 60)

    # Upgrade pip primeiro
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])

    # Instalar essenciais
    for pkg in essential:
        code = run(pip + [pkg], check=False)
        status = "✅" if code == 0 else "⚠️"
        print(f"  {status} {pkg}")

    print("\nInstalando pacotes opcionais (erros não são fatais)...")
    for pkg in optional:
        code = run(pip + [pkg], check=False)
        status = "✅" if code == 0 else "⚠️ (opcional)"
        print(f"  {status} {pkg}")

    # Torch: instala versão CPU para economizar tempo no CI
    print("\nInstalando PyTorch (CPU)...")
    torch_code = run(
        pip + ["torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cpu"],
        check=False
    )
    if torch_code == 0:
        print("  ✅ torch (CPU)")
    else:
        print("  ⚠️ torch não instalado — sistema usará fallback n-grama")

    print("\n✅ Instalação concluída!")

if __name__ == "__main__":
    main()
