# modules/voice_enhanced.py
"""

         ATENA VOICE ENHANCED v2.0                                   
  Sntese de fala, reconhecimento de voz, interpretao de comandos   
                                                                     
  Features:                                                          
    Mltiplas engines TTS (pyttsx3, gTTS, fallback)                 
    Reconhecimento de voz com fallback para texto                   
    NLU simples para interpretao de inteno                      
    Comandos inteligentes da Atena                                  
    Cache de vozes e preferncias                                   
    Mtricas e logging estruturado                                  
    Persistncia de estado                                          
    Integrao com AtenaCore                                        

"""

import os
import re
import json
import queue
import threading
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Callable
from collections import deque, Counter
from dataclasses import dataclass
import hashlib

logger = logging.getLogger("atena.voice")

#  Deteco de backends 

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

try:
    import google.cloud.texttospeech as tts_google
    HAS_GOOGLE_CLOUD_TTS = True
except ImportError:
    HAS_GOOGLE_CLOUD_TTS = False


# 
# CONFIGURAO
# 

@dataclass
class VoiceConfig:
    """Configuraes do mdulo de voz"""
    
    # Diretrio
    base_dir: Path = Path("./atena_evolution/voice")
    
    # TTS (Text-to-Speech)
    tts_engine: str = "auto"  # "pyttsx3", "gtts", "google_cloud", "espeak"
    tts_language: str = "pt-BR"
    tts_rate: int = 150  # palavras por minuto
    tts_volume: float = 0.9
    tts_voice_id: int = 0  # qual voz usar
    
    # ASR (Automatic Speech Recognition)
    asr_engine: str = "google"  # "google", "whisper" (local)
    asr_language: str = "pt-BR"
    asr_timeout: int = 5  # segundos
    asr_ambient_duration: float = 1.0
    
    # NLU (Natural Language Understanding)
    nlu_enabled: bool = True
    nlu_confidence_threshold: float = 0.5
    
    # Comportamento
    auto_speak: bool = True  # fala respostas automaticamente
    voice_feedback: bool = True  # feedback de aes via voz
    verbose: bool = False  # logs detalhados
    
    # Cache
    cache_tts: bool = True
    cache_dir: Path = Path("./atena_evolution/voice/cache")
    
    def setup(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# 
# ENGINE TTS (Text-to-Speech) COM FALLBACKS
# 

class TTSEngine:
    """Gerencia sntese de fala com mltiplos backends"""
    
    def __init__(self, cfg: VoiceConfig):
        self.cfg = cfg
        self._engine = None
        self._engine_type = None
        self._voices_cache: Dict[str, str] = {}
        self._init_engine()
    
    def _init_engine(self):
        """Inicializa a melhor engine disponvel"""
        strategies = self._get_strategies()
        
        for engine_type, init_fn in strategies:
            try:
                engine = init_fn()
                if engine:
                    self._engine = engine
                    self._engine_type = engine_type
                    logger.info(f"[Voice TTS] Engine: {engine_type}")
                    return
            except Exception as e:
                logger.debug(f"[Voice TTS] {engine_type} falhou: {e}")
        
        logger.warning("[Voice TTS] Nenhuma engine TTS disponvel  usando fallback texto")
        self._engine_type = "text_only"
    
    def _get_strategies(self) -> List[Tuple[str, Callable]]:
        """Retorna estratgias de TTS em ordem de preferncia"""
        if self.cfg.tts_engine == "auto":
            return [
                ("pyttsx3", self._init_pyttsx3),
                ("gtts", self._init_gtts),
                ("google_cloud", self._init_google_cloud),
                ("espeak", self._init_espeak),
            ]
        else:
            # Usa engine especfica
            strategies = {
                "pyttsx3": self._init_pyttsx3,
                "gtts": self._init_gtts,
                "google_cloud": self._init_google_cloud,
                "espeak": self._init_espeak,
            }
            fn = strategies.get(self.cfg.tts_engine)
            return [(self.cfg.tts_engine, fn)] if fn else []
    
    def _init_pyttsx3(self):
        """Inicializa pyttsx3 (offline, leve)"""
        if not HAS_PYTTSX3:
            return None
        engine = pyttsx3.init()
        engine.setProperty('rate', self.cfg.tts_rate)
        engine.setProperty('volume', self.cfg.tts_volume)
        # Tenta usar voz portuguesa se disponvel
        voices = engine.getProperty('voices')
        for voice in voices:
            if 'portuguese' in voice.languages or 'pt' in voice.id.lower():
                engine.setProperty('voice', voice.id)
                break
        return engine
    
    def _init_gtts(self):
        """Inicializa gTTS (online, qualidade alta)"""
        if not HAS_GTTS:
            return None
        # gTTS  chamado por demanda, no precisa init
        return "gtts"
    
    def _init_google_cloud(self):
        """Inicializa Google Cloud TTS (online, melhor qualidade)"""
        if not HAS_GOOGLE_CLOUD_TTS:
            return None
        try:
            return tts_google.TextToSpeechClient()
        except Exception:
            return None
    
    def _init_espeak(self):
        """Inicializa eSpeak (offline, fallback leve)"""
        import shutil
        if shutil.which("espeak"):
            return "espeak"
        return None
    
    def speak(self, text: str, wait: bool = False,
              cache_key: Optional[str] = None) -> bool:
        """
        Sintetiza e reproduz fala.
        Returns: True se sucesso, False se falhou
        """
        if not text or len(text.strip()) < 1:
            return False
        
        text = text[:500]  # Limita tamanho
        
        # Tenta cache
        if self.cfg.cache_tts and cache_key:
            cached = self._get_cached(cache_key)
            if cached:
                return self._play_audio(cached, wait)
        
        # Sntese
        audio_data = self._synthesize(text)
        if not audio_data:
            logger.warning(f"[Voice TTS] Sntese falhou: {text[:50]}")
            return False
        
        # Cache
        if self.cfg.cache_tts and cache_key:
            self._cache_audio(cache_key, audio_data)
        
        # Reproduz
        return self._play_audio(audio_data, wait)
    
    def _synthesize(self, text: str) -> Optional[bytes]:
        """Sintetiza texto em udio"""
        try:
            if self._engine_type == "pyttsx3":
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    self._engine.save_to_file(text, f.name)
                    self._engine.runAndWait()
                    return Path(f.name).read_bytes()
            
            elif self._engine_type == "gtts":
                import tempfile
                tts = gTTS(text=text, lang=self.cfg.tts_language, slow=False)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    tts.save(f.name)
                    return Path(f.name).read_bytes()
            
            elif self._engine_type == "google_cloud":
                request = tts_google.SynthesizeSpeechRequest(
                    input=tts_google.SynthesisInput(text=text),
                    voice=tts_google.VoiceSelectionParams(
                        language_code=self.cfg.tts_language,
                    ),
                    audio_config=tts_google.AudioConfig(
                        audio_encoding=tts_google.AudioEncoding.LINEAR16,
                    ),
                )
                response = self._engine.synthesize_speech(request=request)
                return response.audio_content
            
            elif self._engine_type == "espeak":
                import subprocess
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                    subprocess.run([
                        "espeak", "-v", self.cfg.tts_language,
                        "-w", f.name, text
                    ], check=True, capture_output=True)
                    return Path(f.name).read_bytes()
            
            return None
        except Exception as e:
            logger.warning(f"[Voice TTS] Sntese error: {e}")
            return None
    
    def _play_audio(self, audio_data: bytes, wait: bool = False) -> bool:
        """Reproduz udio"""
        try:
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_data)
                f.flush()
                
                # Tenta usar ffplay, paplay, afplay ou similar
                for player in ["ffplay", "paplay", "afplay", "aplay", "play"]:
                    try:
                        args = [player, "-nodisp", "-autoexit", f.name] if player == "ffplay" else [player, f.name]
                        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if wait:
                            proc.wait()
                        return True
                    except FileNotFoundError:
                        continue
        except Exception as e:
            logger.debug(f"[Voice TTS] Play error: {e}")
        
        return False
    
    def _get_cached(self, key: str) -> Optional[bytes]:
        """Retorna udio em cache"""
        cache_file = self.cfg.cache_dir / f"{key}.wav"
        if cache_file.exists():
            try:
                return cache_file.read_bytes()
            except Exception:
                return None
        return None
    
    def _cache_audio(self, key: str, audio_data: bytes):
        """Salva udio em cache"""
        try:
            cache_file = self.cfg.cache_dir / f"{key}.wav"
            cache_file.write_bytes(audio_data)
        except Exception as e:
            logger.debug(f"[Voice TTS] Cache error: {e}")
    
    def get_available_voices(self) -> List[Dict]:
        """Lista vozes disponveis"""
        if self._engine_type == "pyttsx3":
            return [
                {"id": v.id, "name": v.name, "lang": v.languages}
                for v in self._engine.getProperty('voices')
            ]
        return []


# 
# ENGINE ASR (Automatic Speech Recognition)
# 

class ASREngine:
    """Gerencia reconhecimento de voz"""
    
    def __init__(self, cfg: VoiceConfig):
        self.cfg = cfg
        self._recognizer = None
        self._init_recognizer()
        self._recognition_history: deque = deque(maxlen=100)
    
    def _init_recognizer(self):
        """Inicializa o reconhecedor de voz"""
        if not HAS_SR:
            logger.warning("[Voice ASR] speech_recognition no disponvel")
            return
        
        try:
            self._recognizer = sr.Recognizer()
            logger.info("[Voice ASR] speech_recognition inicializado")
        except Exception as e:
            logger.warning(f"[Voice ASR] Erro: {e}")
    
    def listen(self, timeout: Optional[int] = None,
               phrase_limit: Optional[int] = None) -> Optional[str]:
        """
        Escuta do microfone e reconhece voz.
        Returns: texto reconhecido ou None
        """
        if not self._recognizer:
            logger.warning("[Voice ASR] Recognizer no inicializado")
            return None
        
        timeout = timeout or self.cfg.asr_timeout
        phrase_limit = phrase_limit or self.cfg.asr_timeout
        
        try:
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(
                    source, duration=self.cfg.asr_ambient_duration
                )
                
                if self.cfg.verbose:
                    logger.info("[Voice ASR] Ouvindo...")
                
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_limit
                )
        except sr.WaitTimeoutError:
            logger.debug("[Voice ASR] Timeout ao ouvir")
            return None
        except Exception as e:
            logger.warning(f"[Voice ASR] Erro ao capturar udio: {e}")
            return None
        
        # Tenta reconhecer com mltiplas APIs
        text = self._recognize_audio(audio)
        
        if text:
            self._recognition_history.append({
                "text": text,
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"[Voice ASR] Reconhecido: {text}")
        else:
            logger.debug("[Voice ASR] No foi possvel reconhecer")
        
        return text
    
    def _recognize_audio(self, audio) -> Optional[str]:
        """Tenta reconhecer udio com mltiplas APIs"""
        apis = [
            ("Google", self._recognize_google),
            ("Bing", self._recognize_bing),
            ("Sphinx", self._recognize_sphinx),
        ]
        
        for name, fn in apis:
            try:
                text = fn(audio)
                if text:
                    return text
            except Exception as e:
                logger.debug(f"[Voice ASR] {name} falhou: {e}")
        
        return None
    
    def _recognize_google(self, audio) -> Optional[str]:
        """Google Speech Recognition (requer internet)"""
        try:
            return self._recognizer.recognize_google(
                audio, language=self.cfg.asr_language
            )
        except sr.UnknownValueError:
            return None
    
    def _recognize_bing(self, audio) -> Optional[str]:
        """Bing Speech Recognition (requer API key)"""
        try:
            key = os.getenv("BING_SPEECH_KEY")
            if key:
                return self._recognizer.recognize_bing(audio, key)
        except Exception:
            pass
        return None
    
    def _recognize_sphinx(self, audio) -> Optional[str]:
        """Sphinx (offline, baixa qualidade)"""
        try:
            return self._recognizer.recognize_sphinx(audio)
        except Exception:
            return None
    
    def get_history(self, n: int = 10) -> List[Dict]:
        """Retorna histrico de reconhecimentos"""
        return list(self._recognition_history)[-n:]


# 
# NLU (Natural Language Understanding)  Interpretao de Inteno
# 

class CommandInterpreter:
    """Interpreta comandos de voz e mapeia para aes"""
    
    # Mapa de intenes e padres
    INTENTS = {
        "evolve": {
            "patterns": [
                r"evoluir?\b", r"mutate?\b", r"gerar? cdigo\b",
                r"melhor", r"prximo ciclo", r"continuar",
            ],
            "action": "evolve",
            "params": {},
        },
        "status": {
            "patterns": [
                r"status\b", r"como vai\b", r"estado\b",
                r"pontuao\b", r"score\b", r"gerao",
            ],
            "action": "status",
            "params": {},
        },
        "train": {
            "patterns": [
                r"treinar?\b", r"train\b", r"aprender?\b",
                r"learning", r"modelo",
            ],
            "action": "train",
            "params": {},
        },
        "pause": {
            "patterns": [
                r"parar\b", r"pause\b", r"interromper",
                r"stop", r"pausa",
            ],
            "action": "pause",
            "params": {},
        },
        "resume": {
            "patterns": [
                r"resumir?\b", r"continuar\b", r"resume",
                r"start", r"comear",
            ],
            "action": "resume",
            "params": {},
        },
        "info": {
            "patterns": [
                r"informao\b", r"info\b", r"qual\b",
                r"o que\b", r"diga", r"conte",
            ],
            "action": "info",
            "params": {},
        },
        "help": {
            "patterns": [
                r"ajuda\b", r"help\b", r"como funciona",
                r"commands\b", r"comandos",
            ],
            "action": "help",
            "params": {},
        },
    }
    
    def __init__(self, cfg: VoiceConfig):
        self.cfg = cfg
        self._intent_history: deque = deque(maxlen=50)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compila regex patterns"""
        self._compiled = {}
        for intent, spec in self.INTENTS.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE)
                for p in spec["patterns"]
            ]
    
    def interpret(self, text: str) -> Tuple[Optional[str], float]:
        """
        Interpreta texto e retorna (inteno, confiana).
        Retorna (None, 0.0) se no conseguir interpretar.
        """
        if not text or len(text.strip()) < 2:
            return None, 0.0
        
        text_lower = text.lower()
        scores = {}
        
        for intent, patterns in self._compiled.items():
            matches = sum(1 for p in patterns if p.search(text_lower))
            if matches > 0:
                # Escalonamento para comandos curtos de voz:
                # um único match já deve ultrapassar o threshold padrão.
                coverage = matches / max(1, len(patterns))
                confidence = min(1.0, 0.55 + 0.45 * coverage)
                scores[intent] = confidence
        
        if not scores:
            return None, 0.0
        
        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent]
        
        # Threshold
        if confidence < self.cfg.nlu_confidence_threshold:
            return None, confidence
        
        self._intent_history.append({
            "text": text,
            "intent": best_intent,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })
        
        return best_intent, confidence
    
    def get_history(self, n: int = 10) -> List[Dict]:
        """Retorna histrico de interpretaes"""
        return list(self._intent_history)[-n:]
    
    def get_help_text(self) -> str:
        """Retorna texto de ajuda com comandos"""
        lines = ["Comandos disponveis:"]
        for intent, spec in self.INTENTS.items():
            examples = ", ".join(spec["patterns"][:2])
            lines.append(f"   {intent.upper()}: {examples}")
        return "\n".join(lines)


# 
# ORQUESTRADOR PRINCIPAL
# 

class AtenaVoiceEnhanced:
    """
    Mdulo de voz integrado com Atena.
    
    Uso:
        voice = AtenaVoiceEnhanced()
        
        # Fala
        voice.speak("Ol mundo")
        
        # Ouve
        cmd = voice.listen()
        
        # Interpreta
        intent, conf = voice.interpret(cmd)
    """
    
    def __init__(self, cfg: Optional[VoiceConfig] = None, core=None):
        self.cfg = cfg or VoiceConfig()
        self.cfg.setup()
        self.core = core
        
        self.tts = TTSEngine(self.cfg)
        self.asr = ASREngine(self.cfg)
        self.interpreter = CommandInterpreter(self.cfg)
        
        self._listening = False
        self._listener_thread = None
        self._command_queue: queue.Queue = queue.Queue()
        self._metrics = {
            "commands_recognized": 0,
            "commands_executed": 0,
            "commands_failed": 0,
        }
        
        logger.info("[Voice] AtenaVoiceEnhanced v2.0 inicializado")
    
    def speak(self, text: str, wait: bool = False) -> bool:
        """Fala o texto"""
        if not self.cfg.auto_speak:
            logger.info(f"[Voice] (mudo): {text}")
            return True
        
        cache_key = hashlib.md5(text.encode()).hexdigest()[:16]
        success = self.tts.speak(text, wait=wait, cache_key=cache_key)
        
        if not success and self.cfg.verbose:
            logger.warning(f"[Voice] Falha ao falar: {text[:50]}")
        
        return success
    
    def listen(self, timeout: Optional[int] = None) -> Optional[str]:
        """Ouve um comando do usurio"""
        text = self.asr.listen(timeout=timeout)
        if text:
            self._metrics["commands_recognized"] += 1
        return text
    
    def interpret(self, text: str) -> Optional[str]:
        """Interpreta um comando e retorna a inteno"""
        if not text:
            return None
        
        intent, confidence = self.interpreter.interpret(text)
        
        if intent:
            logger.info(f"[Voice] Inteno: {intent} ({confidence:.0%})")
            return intent
        
        return None
    
    def execute_command(self, intent: str, core=None) -> bool:
        """
        Executa um comando baseado na inteno.
        Se core  fornecido, pode executar aes na Atena.
        """
        core = core or self.core
        
        if not intent:
            return False
        
        try:
            if intent == "evolve" and core:
                self.speak("Evoluindo...", wait=False)
                core.evolve_one_cycle()
                self.speak("Ciclo completo", wait=False)
                self._metrics["commands_executed"] += 1
                return True
            
            elif intent == "status" and core:
                status = f"Gerao {core.generation}, score {core.best_score:.2f}"
                self.speak(status, wait=False)
                self._metrics["commands_executed"] += 1
                return True
            
            elif intent == "help":
                help_text = self.interpreter.get_help_text()
                logger.info(help_text)
                self.speak("Veja a lista de comandos no log", wait=False)
                self._metrics["commands_executed"] += 1
                return True
            
            elif intent == "pause":
                self.speak("Pausado", wait=False)
                self._listening = False
                self._metrics["commands_executed"] += 1
                return True
            
            elif intent == "resume":
                self.speak("Resumido", wait=False)
                self._listening = True
                self._metrics["commands_executed"] += 1
                return True
            
            else:
                self.speak(f"Comando {intent} no implementado", wait=False)
                self._metrics["commands_failed"] += 1
                return False
        
        except Exception as e:
            logger.error(f"[Voice] Erro ao executar {intent}: {e}")
            self.speak("Erro ao executar comando", wait=False)
            self._metrics["commands_failed"] += 1
            return False
    
    def interactive_loop(self, core=None):
        """
        Loop interativo: fica ouvindo e executando comandos.
        Pressione Ctrl+C para parar.
        """
        core = core or self.core
        self.speak("Modo interativo. Diga seus comandos.", wait=True)
        
        try:
            while True:
                cmd = self.listen(timeout=10)
                if not cmd:
                    continue
                
                intent = self.interpret(cmd)
                if intent:
                    self.execute_command(intent, core)
                else:
                    self.speak("No entendi. Tente 'help'", wait=False)
        
        except KeyboardInterrupt:
            self.speak("Encerrando", wait=True)
            logger.info("[Voice] Interativo encerrado")
    
    def get_metrics(self) -> Dict:
        """Retorna mtricas de uso"""
        return dict(self._metrics)
    
    def print_status(self):
        """Imprime status do mdulo"""
        logger.info("\n" + ""*60)
        logger.info("   ATENA VOICE  STATUS")
        logger.info(""*60)
        logger.info(f"  TTS Engine  : {self.tts._engine_type}")
        logger.info(f"  ASR Engine  : {self.asr._recognizer is not None}")
        logger.info(f"  NLU Enabled : {self.cfg.nlu_enabled}")
        logger.info(f"  Comandos    : {self._metrics['commands_recognized']} reconhecidos, "
                    f"{self._metrics['commands_executed']} executados")
        logger.info(f"  Histrico ASR: {len(self.asr.get_history())} items")
        logger.info(f"  Histrico NLU: {len(self.interpreter.get_history())} items")
        logger.info(""*60)


# 
# INTEGRAO COM ATENA CORE
# 

def integrate_voice_with_core(core, cfg: Optional[VoiceConfig] = None):
    """
    Integra o mdulo de voz com AtenaCore.
    
    Uso em AtenaCore.__init__:
        from modules.voice_enhanced import integrate_voice_with_core
        self.voice = integrate_voice_with_core(self)
    """
    voice = AtenaVoiceEnhanced(cfg=cfg, core=core)
    core.voice = voice
    
    logger.info("[Voice] Integrado com AtenaCore")
    voice.speak("Atena ativada com voz", wait=False)
    
    return voice


# 
# DEMO STANDALONE
# 

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s  %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Atena Voice Enhanced  Demo")
    parser.add_argument("--speak", type=str, default="", help="Falar um texto")
    parser.add_argument("--listen", action="store_true", help="Ouvir um comando")
    parser.add_argument("--interactive", action="store_true", help="Modo interativo")
    parser.add_argument("--status", action="store_true", help="Status")
    args = parser.parse_args()
    
    cfg = VoiceConfig()
    voice = AtenaVoiceEnhanced(cfg)
    
    if args.speak:
        voice.speak(args.speak, wait=True)
    
    elif args.listen:
        print("Ouvindo...")
        cmd = voice.listen()
        if cmd:
            intent, conf = voice.interpreter.interpret(cmd)
            print(f"Reconhecido: {cmd}")
            print(f"Inteno: {intent} ({conf:.0%})")
    
    elif args.interactive:
        voice.interactive_loop()
    
    elif args.status:
        voice.print_status()
    
    else:
        # Demo padro
        voice.speak("Ol, sou Atena com voz!", wait=True)
        voice.speak("Fale um comando", wait=False)
        cmd = voice.listen()
        if cmd:
            print(f"Voc disse: {cmd}")
            intent = voice.interpret(cmd)
            print(f"Inteno: {intent}")
