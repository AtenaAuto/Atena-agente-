#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Ω — Council Orchestrator v3.0
Sistema de conselho multi-especialista para validação de mutações.

Recursos:
- 🧠 Múltiplos especialistas arquiteturais (estrutura, segurança, performance, qualidade)
- 📊 Ponderação dinâmica baseada em contexto
- 🔄 Aprendizado contínuo a partir de decisões anteriores
- 📈 Métricas de confiança por especialista
- 🎯 Votação ponderada com veto crítico
- 📝 Rastreamento completo de deliberações
"""

import logging
import random
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from collections import defaultdict
import threading

logger = logging.getLogger("atena.council")


# =============================================================================
# = Enums e Data Models
# =============================================================================

class VoteSeverity(Enum):
    """Severidade do voto do especialista."""
    CRITICAL = "critical"   # Veto absoluto
    HIGH = "high"           # Forte objeção
    MEDIUM = "medium"       # Preocupação moderada
    LOW = "low"             # Leve preocupação
    APPROVE = "approve"     # Aprova


@dataclass
class AgentVote:
    """Voto de um especialista."""
    agent_name: str
    score: float  # 0-1
    severity: VoteSeverity
    comment: str
    confidence: float = 0.8
    findings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "agent": self.agent_name,
            "score": self.score,
            "severity": self.severity.value,
            "comment": self.comment,
            "confidence": self.confidence,
            "findings": self.findings
        }


@dataclass
class CouncilDecision:
    """Decisão final do conselho."""
    consensus_score: float
    weighted_score: float
    approved: bool
    vetoed: bool
    veto_reason: Optional[str] = None
    votes: List[AgentVote] = field(default_factory=list)
    deliberation_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "consensus_score": self.consensus_score,
            "weighted_score": self.weighted_score,
            "approved": self.approved,
            "vetoed": self.vetoed,
            "veto_reason": self.veto_reason,
            "votes": [v.to_dict() for v in self.votes],
            "deliberation_time_ms": self.deliberation_time_ms,
            "timestamp": self.timestamp
        }


# =============================================================================
# = Especialistas Base
# =============================================================================

class AgentSpecialist:
    """Classe base para especialistas do conselho."""
    
    def __init__(self, name: str, focus: str, weight: float = 1.0):
        self.name = name
        self.focus = focus
        self.weight = weight
        self.history: List[Dict] = []
        self._lock = threading.RLock()
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        """Analisa código sob perspectiva do especialista."""
        raise NotImplementedError
    
    def record_outcome(self, code_hash: str, was_accepted: bool, actual_score: float):
        """Registra resultado para aprendizado contínuo."""
        with self._lock:
            self.history.append({
                "code_hash": code_hash,
                "accepted": was_accepted,
                "actual_score": actual_score,
                "timestamp": datetime.now().isoformat()
            })
            # Mantém histórico limitado
            if len(self.history) > 1000:
                self.history = self.history[-500:]
    
    def get_accuracy(self) -> float:
        """Calcula precisão histórica do especialista."""
        if not self.history:
            return 0.5
        correct = sum(1 for h in self.history 
                     if (h["accepted"] and h["actual_score"] > 0.5) or
                        (not h["accepted"] and h["actual_score"] <= 0.5))
        return correct / len(self.history)


class ArchitectAgent(AgentSpecialist):
    """Especialista em estrutura, elegância e manutenibilidade."""
    
    def __init__(self):
        super().__init__("Arquiteto", "Estrutura", weight=1.0)
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        complexity = metrics.get("complexity", 0)
        lines = metrics.get("lines", 0)
        functions = metrics.get("num_functions", 0)
        classes = metrics.get("num_classes", 0)
        
        findings = []
        score = 1.0
        
        # Complexidade
        if complexity > 10:
            score -= 0.3
            findings.append(f"Complexidade alta ({complexity})")
        elif complexity > 5:
            score -= 0.1
            findings.append(f"Complexidade moderada ({complexity})")
        
        # Tamanho
        if lines > 500:
            score -= 0.2
            findings.append(f"Arquivo muito longo ({lines} linhas)")
        elif lines > 200:
            score -= 0.05
        
        # Modularidade
        if functions == 0 and classes == 0:
            score -= 0.3
            findings.append("Nenhuma função ou classe definida")
        elif functions > 15:
            score -= 0.1
            findings.append(f"Muitas funções ({functions}) potencialmente desorganizadas")
        
        # Densidade de código
        if classes > 0:
            avg_methods = functions / max(classes, 1)
            if avg_methods > 10:
                findings.append(f"Classes com muitos métodos (média {avg_methods:.1f})")
                score -= 0.1
        
        score = max(0.0, min(1.0, score))
        
        severity = VoteSeverity.APPROVE if score >= 0.7 else (
            VoteSeverity.MEDIUM if score >= 0.5 else VoteSeverity.HIGH
        )
        
        comment = "Estrutura sólida" if score >= 0.7 else (
            "Estrutura aceitável, mas com ressalvas" if score >= 0.5 else "Estrutura problemática"
        )
        
        return AgentVote(
            agent_name=self.name,
            score=score,
            severity=severity,
            comment=comment,
            confidence=0.85,
            findings=findings
        )


class SecurityAgent(AgentSpecialist):
    """Especialista em segurança, vulnerabilidades e riscos."""
    
    # Padrões inseguros conhecidos
    UNSAFE_PATTERNS = [
        ("eval(", "Uso de eval() - permite execução arbitrária"),
        ("exec(", "Uso de exec() - permite execução arbitrária"),
        ("__import__", "Importação dinâmica pode ser perigosa"),
        ("os.system", "Chamada de sistema sem validação"),
        ("subprocess.", "Subprocess pode executar comandos arbitrários"),
        ("pickle.loads", "Pickle pode executar código arbitrário"),
        ("yaml.load(", "YAML.load inseguro - use safe_load"),
        ("open(.*'w'", "Escrita em arquivo sem validação"),
        ("password", "Hardcoded password detectado"),
        ("token", "Hardcoded token detectado"),
        ("secret", "Hardcoded secret detectado"),
    ]
    
    def __init__(self):
        super().__init__("Segurança", "Riscos", weight=1.2)
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        findings = []
        score = 1.0
        critical_finding = False
        
        for pattern, message in self.UNSAFE_PATTERNS:
            if pattern in code:
                findings.append(message)
                score -= 0.2
                if pattern in ["eval(", "exec(", "os.system", "subprocess."]:
                    critical_finding = True
                    score -= 0.3
        
        # Verifica imports perigosos
        dangerous_imports = ["os", "subprocess", "socket", "ctypes"]
        for imp in dangerous_imports:
            if f"import {imp}" in code or f"from {imp}" in code:
                findings.append(f"Import potencialmente perigoso: {imp}")
                score -= 0.1
        
        score = max(0.0, min(1.0, score))
        
        severity = VoteSeverity.CRITICAL if critical_finding else (
            VoteSeverity.HIGH if score < 0.5 else (
                VoteSeverity.MEDIUM if score < 0.8 else VoteSeverity.APPROVE
            )
        )
        
        comment = "Código seguro" if score >= 0.9 else (
            "Riscos de segurança detectados" if score >= 0.6 else "Múltiplos riscos críticos!"
        )
        
        return AgentVote(
            agent_name=self.name,
            score=score,
            severity=severity,
            comment=comment,
            confidence=0.95 if critical_finding else 0.8,
            findings=findings
        )


class PerformanceAgent(AgentSpecialist):
    """Especialista em performance e eficiência."""
    
    def __init__(self):
        super().__init__("Performance", "Eficiência", weight=0.9)
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        findings = []
        score = 1.0
        execution_time = metrics.get("execution_time", 0)
        
        # Análise de loops
        loop_count = code.count("for ") + code.count("while ")
        if loop_count > 5:
            findings.append(f"Muitos loops ({loop_count}) - potencial impacto em performance")
            score -= 0.2
        
        # Loops aninhados
        nested_loops = 0
        lines = code.split('\n')
        indent_level = 0
        for line in lines:
            if 'for ' in line or 'while ' in line:
                indent_level += 1
                if indent_level > 1:
                    nested_loops += 1
            elif line.strip() and line[0] not in ' \t':
                indent_level = 0
        
        if nested_loops > 0:
            findings.append(f"Loops aninhados detectados ({nested_loops})")
            score -= 0.15 * min(nested_loops, 3)
        
        # Complexidade
        complexity = metrics.get("complexity", 0)
        if complexity > 8:
            findings.append(f"Alta complexidade ({complexity}) - difícil otimizar")
            score -= 0.1
        
        # Tempo de execução
        if execution_time > 0:
            if execution_time > 0.5:
                findings.append(f"Tempo de execução elevado ({execution_time:.2f}s)")
                score -= 0.2
            elif execution_time > 0.1:
                score -= 0.05
        
        # Uso de operações custosas
        expensive_ops = ["sort(", "sorted(", "reverse(", "copy("]
        for op in expensive_ops:
            if op in code:
                findings.append(f"Operação potencialmente custosa: {op}")
                score -= 0.05
        
        score = max(0.0, min(1.0, score))
        
        severity = VoteSeverity.HIGH if score < 0.4 else (
            VoteSeverity.MEDIUM if score < 0.7 else VoteSeverity.APPROVE
        )
        
        comment = "Eficiente" if score >= 0.8 else (
            "Pode ser otimizado" if score >= 0.6 else "Ineficiente, requer otimização"
        )
        
        return AgentVote(
            agent_name=self.name,
            score=score,
            severity=severity,
            comment=comment,
            confidence=0.75,
            findings=findings
        )


class QualityAgent(AgentSpecialist):
    """Especialista em qualidade geral, testes e documentação."""
    
    def __init__(self):
        super().__init__("Qualidade", "Testes e Documentação", weight=0.8)
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        findings = []
        score = 1.0
        
        # Documentação
        has_docstring = "def " in code and '"""' in code
        if not has_docstring:
            findings.append("Falta documentação/docstrings")
            score -= 0.2
        
        # Testabilidade
        has_tests = "if __name__" in code or "unittest" in code or "pytest" in code
        if not has_tests:
            findings.append("Sem testes ou bloco __main__")
            score -= 0.15
        
        # Type hints
        has_type_hints = "->" in code and ":" in code
        if has_type_hints:
            score += 0.1
        else:
            findings.append("Recomenda-se adicionar type hints")
            score -= 0.1
        
        # Erros tratados
        has_try_except = "try:" in code and "except" in code
        if not has_try_except and len(code.splitlines()) > 50:
            findings.append("Pouco ou nenhum tratamento de exceções")
            score -= 0.1
        
        # Comentários
        comment_lines = sum(1 for line in code.split('\n') if line.strip().startswith('#'))
        total_lines = len(code.splitlines())
        comment_ratio = comment_lines / max(1, total_lines)
        
        if comment_ratio < 0.02 and total_lines > 50:
            findings.append("Poucos comentários em código extenso")
            score -= 0.1
        elif comment_ratio > 0.2:
            findings.append("Muitos comentários - código pode ser auto-documentado")
            score -= 0.05
        
        score = max(0.0, min(1.0, score))
        
        if score >= 0.8:
            comment = "Qualidade excelente"
        elif score >= 0.6:
            comment = "Qualidade aceitável"
        else:
            comment = "Qualidade precisa melhorar"
        
        severity = VoteSeverity.HIGH if score < 0.5 else VoteSeverity.APPROVE
        
        return AgentVote(
            agent_name=self.name,
            score=score,
            severity=severity,
            comment=comment,
            confidence=0.8,
            findings=findings
        )


class MaintainabilityAgent(AgentSpecialist):
    """Especialista em manutenibilidade e evolução futura."""
    
    def __init__(self):
        super().__init__("Manutenibilidade", "Evolução", weight=0.7)
    
    def analyze(self, code: str, metrics: Dict[str, Any]) -> AgentVote:
        findings = []
        score = 1.0
        lines = metrics.get("lines", 0)
        
        # Tamanho de funções
        long_functions = 0
        for line in code.split('\n'):
            if 'def ' in line and lines > 30:
                long_functions += 1
        
        if long_functions > 0:
            findings.append(f"{long_functions} função(ões) longa(s) (>30 linhas)")
            score -= 0.1 * min(long_functions, 3)
        
        # Código duplicado (detecção simples)
        code_lines = [l.strip() for l in code.split('\n') if l.strip()]
        unique_lines = len(set(code_lines))
        duplication = 1 - (unique_lines / max(len(code_lines), 1))
        
        if duplication > 0.3:
            findings.append(f"Alta duplicação de código ({duplication:.1%})")
            score -= 0.15
        
        # Acoplamento
        imports = code.count("import ") + code.count("from ")
        if imports > 15:
            findings.append(f"Muitas dependências ({imports})")
            score -= 0.1
        
        score = max(0.0, min(1.0, score))
        
        comment = "Código bem estruturado para evolução" if score >= 0.7 else (
            "Pode ser difícil manter/evoluir"
        )
        
        return AgentVote(
            agent_name=self.name,
            score=score,
            severity=VoteSeverity.MEDIUM if score < 0.6 else VoteSeverity.APPROVE,
            comment=comment,
            confidence=0.7,
            findings=findings
        )


# =============================================================================
# = Council Orchestrator
# =============================================================================

class CouncilOrchestrator:
    """
    Orquestra múltiplos especialistas para validar mutações.
    Sistema de votação ponderada com veto crítico e aprendizado contínuo.
    """
    
    def __init__(self, history_path: Optional[Path] = None):
        self.specialists: List[AgentSpecialist] = [
            ArchitectAgent(),
            SecurityAgent(),
            PerformanceAgent(),
            QualityAgent(),
            MaintainabilityAgent()
        ]
        
        self.history_path = history_path or Path("atena_evolution/council_history.json")
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._decisions: List[CouncilDecision] = []
        self._lock = threading.RLock()
        self._load_history()
        
        # Pesos ajustáveis (podem evoluir)
        self.weights = {
            "Arquiteto": 1.0,
            "Segurança": 1.2,    # Peso maior para segurança
            "Performance": 0.9,
            "Qualidade": 0.8,
            "Manutenibilidade": 0.7
        }
        
        # Thresholds
        self.approval_threshold = 0.65
        self.veto_threshold = 0.3
        self.confidence_threshold = 0.7
        
        logger.info(f"🔱 Council Orchestrator v3.0 inicializado com {len(self.specialists)} especialistas")
        logger.info(f"   Especialistas: {', '.join(s.name for s in self.specialists)}")
    
    def _load_history(self):
        """Carrega histórico de decisões."""
        if not self.history_path.exists():
            return
        
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            for item in data[-100:]:  # Últimas 100 decisões
                # Converte de volta (simplificado)
                self._decisions.append(CouncilDecision(**item))
            logger.info(f"📜 Histórico carregado: {len(self._decisions)} decisões")
        except Exception as e:
            logger.warning(f"⚠️ Falha ao carregar histórico: {e}")
    
    def _save_decision(self, decision: CouncilDecision):
        """Salva decisão no histórico."""
        with self._lock:
            self._decisions.append(decision)
            if len(self._decisions) > 500:
                self._decisions = self._decisions[-500:]
            
            try:
                data = [d.to_dict() for d in self._decisions]
                self.history_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            except Exception as e:
                logger.warning(f"⚠️ Falha ao salvar histórico: {e}")
    
    def consensus_score(
        self,
        code: str,
        metrics: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calcula o consenso do conselho sobre uma mutação.
        
        Args:
            code: Código a analisar
            metrics: Métricas do código
            context: Contexto adicional (objetivo, prioridade, etc.)
        
        Returns:
            Score de consenso (0-1)
        """
        import time
        start_time = time.time()
        
        logger.info(f"[Council] Iniciando deliberação sobre nova mutação...")
        
        votes: List[AgentVote] = []
        veto_detected = False
        veto_reason = None
        
        for specialist in self.specialists:
            try:
                vote = specialist.analyze(code, metrics)
                votes.append(vote)
                
                # Verifica veto crítico
                if vote.severity == VoteSeverity.CRITICAL:
                    veto_detected = True
                    veto_reason = f"{specialist.name}: {vote.comment}"
                    logger.warning(f"  🚨 VETO CRÍTICO de {specialist.name}: {vote.comment}")
                else:
                    logger.info(f"  - {specialist.name}: {vote.score:.2f} ({vote.severity.value}) - {vote.comment}")
                    if vote.findings:
                        for finding in vote.findings[:2]:
                            logger.debug(f"      • {finding}")
            
            except Exception as e:
                logger.error(f"  ❌ Erro em {specialist.name}: {e}")
                votes.append(AgentVote(
                    agent_name=specialist.name,
                    score=0.5,
                    severity=VoteSeverity.MEDIUM,
                    comment=f"Falha na análise: {e}",
                    confidence=0.3
                ))
        
        # Calcula scores
        total_weight = 0
        weighted_sum = 0
        raw_sum = 0
        
        for vote in votes:
            weight = self.weights.get(vote.agent_name, 1.0)
            total_weight += weight
            weighted_sum += vote.score * weight
            raw_sum += vote.score
        
        consensus = weighted_sum / total_weight if total_weight > 0 else 0
        raw_consensus = raw_sum / len(votes) if votes else 0
        
        # Veto anula qualquer score positivo
        if veto_detected:
            consensus = 0.0
        
        deliberation_time = (time.time() - start_time) * 1000
        
        decision = CouncilDecision(
            consensus_score=raw_consensus,
            weighted_score=consensus,
            approved=consensus >= self.approval_threshold and not veto_detected,
            vetoed=veto_detected,
            veto_reason=veto_reason,
            votes=votes,
            deliberation_time_ms=deliberation_time
        )
        
        self._save_decision(decision)
        
        logger.info(f"[Council] Consenso final: {consensus:.3f} | Aprovado: {decision.approved} | "
                   f"Deliberação: {deliberation_time:.1f}ms")
        
        return consensus if not veto_detected else 0.0
    
    def get_decision_details(self, last_n: int = 10) -> List[Dict]:
        """Retorna detalhes das últimas decisões."""
        return [d.to_dict() for d in self._decisions[-last_n:]]
    
    def get_specialist_accuracy(self) -> Dict[str, float]:
        """Retorna acurácia histórica de cada especialista."""
        return {s.name: s.get_accuracy() for s in self.specialists}
    
    def adjust_weights(self, learning_rate: float = 0.05) -> None:
        """Ajusta pesos dos especialistas baseado em acurácia."""
        accuracies = self.get_specialist_accuracy()
        
        for name, accuracy in accuracies.items():
            if name in self.weights:
                # Aumenta peso de especialistas precisos, reduz de imprecisos
                adjustment = (accuracy - 0.5) * learning_rate
                self.weights[name] = max(0.3, min(2.0, self.weights[name] + adjustment))
        
        logger.debug(f"Pesos ajustados: {self.weights}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do conselho."""
        decisions = self._decisions[-100:] if self._decisions else []
        
        return {
            "total_decisions": len(self._decisions),
            "approval_rate": sum(1 for d in decisions if d.approved) / max(1, len(decisions)),
            "veto_rate": sum(1 for d in decisions if d.vetoed) / max(1, len(decisions)),
            "avg_consensus_score": sum(d.weighted_score for d in decisions) / max(1, len(decisions)),
            "avg_deliberation_ms": sum(d.deliberation_time_ms for d in decisions) / max(1, len(decisions)),
            "weights": self.weights.copy(),
            "specialist_accuracy": self.get_specialist_accuracy()
        }


# =============================================================================
# = Instância Global
# =============================================================================

council = CouncilOrchestrator()


# =============================================================================
# = Demonstração
# =============================================================================

def main():
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="ATENA Council Orchestrator v3.0")
    parser.add_argument("--code", type=str, help="Código a analisar")
    parser.add_argument("--file", type=str, help="Arquivo com código")
    parser.add_argument("--metrics", type=str, default="{}", help="Métricas em JSON")
    parser.add_argument("--stats", action="store_true", help="Mostra estatísticas")
    parser.add_argument("--history", type=int, nargs="?", const=5, help="Mostra histórico")
    
    args = parser.parse_args()
    
    if args.stats:
        stats = council.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        return 0
    
    if args.history:
        decisions = council.get_decision_details(args.history)
        print(json.dumps(decisions, indent=2, default=str))
        return 0
    
    # Carrega código
    code = args.code
    if args.file:
        code = Path(args.file).read_text(encoding="utf-8")
    
    if not code:
        code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def main():
    for i in range(10):
        print(fibonacci(i))

if __name__ == "__main__":
    main()
"""
        print("📝 Usando código de exemplo")
    
    # Parse metrics
    try:
        metrics = json.loads(args.metrics)
    except json.JSONDecodeError:
        metrics = {}
    
    # Adiciona métricas básicas
    metrics.update({
        "lines": len(code.splitlines()),
        "complexity": code.count("if ") + code.count("for ") + code.count("while "),
        "num_functions": code.count("def "),
        "num_classes": code.count("class "),
    })
    
    # Analisa
    score = council.consensus_score(code, metrics)
    
    print(f"\n📊 Resultado: Score={score:.3f}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
