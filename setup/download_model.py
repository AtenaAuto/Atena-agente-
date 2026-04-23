import os
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] ATENA Setup — %(message)s")
logger = logging.getLogger("ModelDownloader")

MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
SAVE_PATH = "/home/ubuntu/atena_repo/models/deepseek-r1-1.5b"

def download_model():
    logger.info(f"🚀 Iniciando download do modelo: {MODEL_NAME}")
    logger.info(f"📂 Destino: {SAVE_PATH}")
    
    try:
        # Baixar Tokenizer
        logger.info("📥 Baixando Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        tokenizer.save_pretrained(SAVE_PATH)
        logger.info("✅ Tokenizer salvo com sucesso.")
        
        # Baixar Modelo (usando float16 para economizar espaço e memória)
        logger.info("📥 Baixando Modelo (isso pode levar alguns minutos)...")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="cpu", # Forçamos CPU para o download inicial
            low_cpu_mem_usage=True
        )
        model.save_pretrained(SAVE_PATH)
        logger.info("✅ Modelo salvo com sucesso.")
        
        logger.info(f"✨ Download concluído! O modelo está pronto em: {SAVE_PATH}")
        
    except Exception as e:
        logger.error(f"❌ Erro durante o download: {e}")
        raise

if __name__ == "__main__":
    download_model()
