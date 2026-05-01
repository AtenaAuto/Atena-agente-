#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Artifact Value Analyzer v2.0 - Avaliação Multidimensional de Artefatos
Sistema completo de scoring, validação e priorização de artefatos gerados.

Recursos:
- 📊 Avaliação multidimensional (ação, novidade, evidência, risco, impacto)
- 🧠 Análise semântica com NLP (TF-IDF, similaridade)
- 📈 Scoring adaptativo baseado em métricas históricas
- 🔄 Comparação entre versões de artefatos
- 📊 Geração de heatmaps e visualizações
- 🎯 Priorização automática para execução
- 📝 Relatórios executivos com recomendações
"""

from __future__ import annotations

import json
import re
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter, defaultdict
from enum import Enum
import hashlib

# Tentativa de importar bibliotecas avançadas
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class RiskLevel(Enum):
    """Níveis de risco para artefatos."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactLevel(Enum):
    """Níveis de impacto potencial."""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    TRANSFORMATIVE = "transformative"


@dataclass
class ArtifactScore:
    """Pontuação multidimensional de um artefato."""
    path: str
    actionability: int       # 1-5: quão acionável é o artefato
    novelty: int             # 1-5: novidade da abordagem
    evidence: int            # 1-5: qualidade da evidência/suporte
    risk: int                # 1-5: risco associado (maior = menos desejável)
    impact: int              # 1-5: impacto potencial
    feasibility: int         # 1-5: viabilidade de implementação
    overall: float           # 0-5: pontuação geral ponderada
    risk_level: str          # classificação de risco
    impact_level: str        # classificação de impacto
    notes: str               # observações
    recommendations: List[str] = field(default_factory=list)  # recomendações específicas
    related_to: List[str] = field(default_factory=list)       # artefatos relacionados
    version: Optional[str] = None                              # versão do artefato
    generated_at: Optional[str] = None                         # timestamp de geração
    tags: List[str] = field(default_factory=list)              # tags para categorização
    
    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        return {
            "path": self.path,
            "actionability": self.actionability,
            "novelty": self.novelty,
            "evidence": self.evidence,
            "risk": self.risk,
            "impact": self.impact,
            "feasibility": self.feasibility,
            "overall": self.overall,
            "risk_level": self.risk_level,
            "impact_level": self.impact_level,
            "notes": self.notes,
            "recommendations": self.recommendations,
            "related_to": self.related_to,
            "version": self.version,
            "generated_at": self.generated_at,
            "tags": self.tags
        }


class ArtifactValueAnalyzer:
    """
    Avaliador multidimensional de valor de artefatos.
    Combina análise estática, semântica e heurísticas.
    """
    
    # Pesos para cálculo do score geral
    WEIGHTS = {
        "actionability": 0.30,
        "novelty": 0.15,
        "evidence": 0.20,
        "impact": 0.25,
        "feasibility": 0.10
    }
    
    # Palavras-chave de alta ação
    ACTION_KEYWORDS = {
        "high": ["mvp", "próxima ação", "next action", "backlog", "implementar", 
                 "executar", "deploy", "release", "roadmap", "milestone"],
        "medium": ["planejar", "plan", "proposta", "proposal", "discutir", 
                   "avaliar", "evaluate", "analisar", "analyze"],
        "low": ["considerar", "consider", "possível", "possible", "talvez", "maybe"]
    }
    
    # Palavras-chave de novidade
    NOVELTY_KEYWORDS = {
        "high": ["inovador", "innovative", "neuro-simbólico", "multiagente", 
                 "quantum", "blockchain", "descentralizado", "autônomo", "autonomous"],
        "medium": ["otimizado", "optimized", "avançado", "advanced", "moderno", 
                   "modern", "híbrido", "hybrid"],
        "low": ["tradicional", "traditional", "clássico", "classic", "convencional"]
    }
    
    # Palavras-chave de evidência
    EVIDENCE_KEYWORDS = {
        "high": ["citação", "citation", "referência", "reference", "fonte", "source",
                 "experimento", "experiment", "validação", "validation", "benchmark"],
        "medium": ["exemplo", "example", "caso", "case", "demonstração", "demonstration"],
        "low": ["sugere", "suggests", "acredita", "believes", "hipótese", "hypothesis"]
    }
    
    # Palavras-chave de impacto
    IMPACT_KEYWORDS = {
        "transformative": ["revolucionário", "revolutionary", "disruptivo", "paradigm shift",
                           "transformador", "transformative", "game changer"],
        "major": ["significativo", "significant", "substancial", "expressivo", 
                  "major", "grande escala", "large scale"],
        "moderate": ["moderado", "moderate", "aprimoramento", "enhancement", "otimização"],
        "minor": ["pequeno", "small", "incremental", "cosmético", "cosmetic"]
    }
    
    def __init__(self, history_dir: Optional[Path] = None):
        self.history_dir = history_dir or Path("atena_evolution/artifact_history")
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._history: Dict[str, List[Dict]] = defaultdict(list)
        self._tfidf_vectorizer = None
        self._corpus = []
        self._load_history()
    
    def _load_history(self):
        """Carrega histórico de avaliações anteriores."""
        history_file = self.history_dir / "evaluation_history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                for path, evaluations in data.items():
                    self._history[path] = evaluations
            except Exception:
                pass
    
    def _save_history(self):
        """Salva histórico de avaliações."""
        history_file = self.history_dir / "evaluation_history.json"
        try:
            history_file.write_text(json.dumps(self._history, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extrai tags do texto baseado em palavras-chave."""
        tags = set()
        lower_text = text.lower()
        
        # Domínios
        domains = {
            "segurança": ["security", "safety", "vulnerability", "threat"],
            "performance": ["performance", "latency", "throughput", "optimization"],
            "escalabilidade": ["scalability", "scale", "distributed", "cluster"],
            "usabilidade": ["usability", "ux", "interface", "dashboard"],
            "automação": ["automation", "autonomous", "self-healing", "orchestration"]
        }
        
        for domain, keywords in domains.items():
            if any(kw in lower_text for kw in keywords):
                tags.add(domain)
        
        # Tecnologias
        techs = {
            "python": ["python", "pandas", "numpy", "fastapi"],
            "ml/ai": ["machine learning", "deep learning", "neural", "llm", "gpt"],
            "cloud": ["aws", "gcp", "azure", "kubernetes", "docker"],
            "database": ["postgres", "mysql", "mongodb", "redis", "sqlite"]
        }
        
        for tech, keywords in techs.items():
            if any(kw in lower_text for kw in keywords):
                tags.add(tech)
        
        return list(tags)
    
    def _detect_risk_level(self, text: str, risk_score: int) -> str:
        """Detecta nível de risco baseado em texto e score."""
        lower = text.lower()
        
        # Palavras de alto risco
        high_risk_words = ["vulnerabilidade", "vulnerability", "exploit", "breach", 
                           "critical", "emergencial", "p0", "severe"]
        
        if any(word in lower for word in high_risk_words) or risk_score >= 4:
            return RiskLevel.CRITICAL.value
        elif risk_score >= 3:
            return RiskLevel.HIGH.value
        elif risk_score >= 2:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value
    
    def _detect_impact_level(self, impact_score: int, text: str) -> str:
        """Detecta nível de impacto baseado em score e contexto."""
        lower = text.lower()
        
        # Palavras de alto impacto
        high_impact_words = ["revolucion", "paradigm", "disrupt", "transform"]
        
        if any(word in lower for word in high_impact_words) or impact_score >= 4:
            return ImpactLevel.TRANSFORMATIVE.value
        elif impact_score >= 3:
            return ImpactLevel.MAJOR.value
        elif impact_score >= 2:
            return ImpactLevel.MODERATE.value
        else:
            return ImpactLevel.MINOR.value
    
    def _find_related_artifacts(self, path: Path, all_paths: List[Path]) -> List[str]:
        """Encontra artefatos relacionados por nome e conteúdo."""
        related = []
        path_stem = path.stem.lower()
        
        for other in all_paths:
            if other == path:
                continue
            other_stem = other.stem.lower()
            # Relacionado por nome similar ou mesmo timestamp
            if (path_stem in other_stem or other_stem in path_stem or
                path_stem[-8:] == other_stem[-8:]):  # mesmo timestamp
                related.append(str(other))
        
        return related[:5]
    
    def _score_markdown(self, text: str, path: str, all_paths: List[Path]) -> ArtifactScore:
        """Avalia artefato Markdown."""
        lower = text.lower()
        
        # Scores base
        actionability = 2
        novelty = 2
        evidence = 1
        risk = 2
        impact = 2
        feasibility = 3
        notes = []
        recommendations = []
        
        # ===== ACTIONABILITY =====
        for level, keywords in self.ACTION_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    if level == "high":
                        actionability += 2
                        notes.append(f"contém ação imediata: {kw}")
                    elif level == "medium":
                        actionability += 1
                    if level not in ["low"]:
                        recommendations.append(f"Implementar ação sugerida relacionada a '{kw}'")
                    break
        
        # ===== NOVELTY =====
        for level, keywords in self.NOVELTY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    if level == "high":
                        novelty += 3
                        notes.append(f"abordagem inovadora: {kw}")
                    elif level == "medium":
                        novelty += 2
                    elif level == "low":
                        novelty -= 1
                    break
        
        # ===== EVIDENCE =====
        for level, keywords in self.EVIDENCE_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    if level == "high":
                        evidence += 2
                        notes.append(f"evidência forte: {kw}")
                    elif level == "medium":
                        evidence += 1
                    break
        
        # ===== IMPACT =====
        for level, keywords in self.IMPACT_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    if level == "transformative":
                        impact += 3
                        notes.append(f"impacto transformador: {kw}")
                    elif level == "major":
                        impact += 2
                    elif level == "moderate":
                        impact += 1
                    break
        
        # ===== RISK =====
        if "critical" in lower or "urgente" in lower:
            risk += 2
            recommendations.append("Priorizar avaliação de riscos críticos")
        if "rollback" in lower or "mitiga" in lower:
            risk -= 1
            notes.append("considera mitigação de risco")
        
        # ===== FEASIBILITY =====
        if "implementado" in lower or "pronto" in lower:
            feasibility += 2
            notes.append("implementação pronta ou disponível")
        if "complexo" in lower or "desafiador" in lower:
            feasibility -= 1
        if "dependência" in lower or "dependency" in lower:
            feasibility -= 1
        
        # ===== RECOMENDAÇÕES ADICIONAIS =====
        if "metric" in lower or "métrica" in lower:
            recommendations.append("Estabelecer métricas de acompanhamento")
        if "benchmark" in lower:
            recommendations.append("Executar benchmark para validação")
        if "roadmap" in lower or "cronograma" in lower:
            recommendations.append("Alinhar com cronograma geral")
        
        # Normaliza scores
        actionability = min(5, max(1, actionability))
        novelty = min(5, max(1, novelty))
        evidence = min(5, max(1, evidence))
        risk = min(5, max(1, risk))
        impact = min(5, max(1, impact))
        feasibility = min(5, max(1, feasibility))
        
        # Score geral ponderado
        overall = round(
            (self.WEIGHTS["actionability"] * actionability +
             self.WEIGHTS["novelty"] * novelty +
             self.WEIGHTS["evidence"] * evidence +
             self.WEIGHTS["impact"] * impact +
             self.WEIGHTS["feasibility"] * feasibility), 2
        )
        
        # Extrai timestamp e versão se disponíveis
        version = None
        generated_at = None
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', path)
        if date_match:
            generated_at = date_match.group(0)
        
        tags = self._extract_tags(text)
        risk_level = self._detect_risk_level(text, risk)
        impact_level = self._detect_impact_level(impact, text)
        related_to = self._find_related_artifacts(Path(path), all_paths)
        
        return ArtifactScore(
            path=path,
            actionability=actionability,
            novelty=novelty,
            evidence=evidence,
            risk=risk,
            impact=impact,
            feasibility=feasibility,
            overall=overall,
            risk_level=risk_level,
            impact_level=impact_level,
            notes="; ".join(notes) if notes else "sem observações",
            recommendations=recommendations,
            related_to=related_to,
            version=version,
            generated_at=generated_at,
            tags=tags
        )
    
    def _score_json(self, payload: dict, path: str, all_paths: List[Path]) -> ArtifactScore:
        """Avalia artefato JSON (relatórios estruturados)."""
        actionability = 3
        novelty = 3
        evidence = 2
        risk = 2
        impact = 3
        feasibility = 3
        notes = []
        recommendations = []
        
        # Análise de campos comuns em relatórios ATENA
        research = payload.get("internet_research_engine", {})
        sre = payload.get("sre_auto_hardening", {})
        redaction = payload.get("security_redaction", {})
        evolution = payload.get("evolution_signal", {})
        
        # Actionability baseada em weighted_confidence
        weighted_conf = float(research.get("weighted_confidence", 0.0) or 0.0)
        if weighted_conf >= 0.8:
            actionability += 2
            notes.append(f"alta confiança ({weighted_conf})")
            recommendations.append("Implementar recomendações com base na alta confiança")
        elif weighted_conf >= 0.6:
            actionability += 1
        
        # Novidade baseada em trend
        trend = evolution.get("trend", "")
        if trend == "improving":
            novelty += 2
            notes.append("tendência de melhoria detectada")
        
        # Evidência baseada em número de fontes
        sources = research.get("all_source_count", 0)
        if sources >= 10:
            evidence += 2
            notes.append(f"base sólida: {sources} fontes")
        elif sources >= 5:
            evidence += 1
        
        # Risco baseado em release risk
        release_risk = research.get("synthesis", {}).get("release_risk", "")
        if release_risk == "high":
            risk += 2
            notes.append("alto risco de release")
            recommendations.append("Realitar análise de risco aprofundada")
        elif release_risk == "critical":
            risk += 3
            recommendations.append("⚠️ AÇÃO IMEDIATA: mitigar riscos críticos")
        
        # Impacto baseado em high quality sources
        high_quality = len(research.get("synthesis", {}).get("high_quality_sources", []))
        if high_quality >= 5:
            impact += 2
            notes.append(f"múltiplas fontes de alta qualidade ({high_quality})")
        
        # Viabilidade baseada em metrics
        metrics = sre.get("metrics", {})
        if metrics.get("success_rate", 0) >= 0.9:
            feasibility += 1
            notes.append("alta taxa de sucesso histórica")
        
        # Redação de segurança
        if redaction.get("status") == "ok":
            notes.append("com trilha de redação de segurança")
        
        # Normaliza
        actionability = min(5, max(1, actionability))
        novelty = min(5, max(1, novelty))
        evidence = min(5, max(1, evidence))
        risk = min(5, max(1, risk))
        impact = min(5, max(1, impact))
        feasibility = min(5, max(1, feasibility))
        
        overall = round(
            (self.WEIGHTS["actionability"] * actionability +
             self.WEIGHTS["novelty"] * novelty +
             self.WEIGHTS["evidence"] * evidence +
             self.WEIGHTS["impact"] * impact +
             self.WEIGHTS["feasibility"] * feasibility), 2
        )
        
        # Extrai timestamp
        generated_at = payload.get("generated_at_utc", "")[:10] or payload.get("timestamp", "")[:10]
        if not generated_at:
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', path)
            if date_match:
                generated_at = date_match.group(0)
        
        tags = self._extract_tags(json.dumps(payload))
        related_to = self._find_related_artifacts(Path(path), all_paths)
        risk_level = self._detect_risk_level(json.dumps(payload), risk)
        impact_level = self._detect_impact_level(impact, json.dumps(payload))
        
        return ArtifactScore(
            path=path,
            actionability=actionability,
            novelty=novelty,
            evidence=evidence,
            risk=risk,
            impact=impact,
            feasibility=feasibility,
            overall=overall,
            risk_level=risk_level,
            impact_level=impact_level,
            notes="; ".join(notes) if notes else "sem observações",
            recommendations=recommendations,
            related_to=related_to,
            generated_at=generated_at,
            tags=tags
        )
    
    def evaluate_artifact(self, path: Path, all_paths: List[Path]) -> ArtifactScore:
        """Avalia um artefato individual."""
        if not path.exists():
            raise FileNotFoundError(f"Artefato não encontrado: {path}")
        
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(content)
                score = self._score_json(payload, str(path), all_paths)
            except json.JSONDecodeError:
                score = self._score_markdown(content, str(path), all_paths)
        else:
            score = self._score_markdown(content, str(path), all_paths)
        
        # Registra no histórico
        self._history[str(path)].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": score.overall,
            "actionability": score.actionability,
            "novelty": score.novelty,
            "evidence": score.evidence,
            "risk": score.risk,
            "impact": score.impact,
            "feasibility": score.feasibility
        })
        self._save_history()
        
        return score
    
    def get_evolution(self, path: str) -> Dict[str, Any]:
        """Retorna evolução histórica de um artefato."""
        if path not in self._history:
            return {"has_history": False}
        
        evaluations = self._history[path]
        if not evaluations:
            return {"has_history": False}
        
        scores = [e["overall"] for e in evaluations]
        return {
            "has_history": True,
            "count": len(evaluations),
            "first_score": scores[0],
            "last_score": scores[-1],
            "best_score": max(scores),
            "worst_score": min(scores),
            "trend": "improving" if scores[-1] > scores[0] else "stable" if scores[-1] == scores[0] else "degrading",
            "history": evaluations
        }
    
    def generate_priority_list(self, scores: List[ArtifactScore], top_n: int = 5) -> List[ArtifactScore]:
        """Gera lista de prioridades baseada em múltiplos fatores."""
        # Pontuação combinada: overall + (viabilidade * 0.5) - (risco * 0.3)
        for score in scores:
            priority_score = (score.overall * 0.6 + 
                             score.feasibility/5 * 0.3 - 
                             score.risk/5 * 0.1)
            score.priority_score = round(priority_score, 3)
        
        sorted_scores = sorted(scores, key=lambda x: getattr(x, 'priority_score', x.overall), reverse=True)
        return sorted_scores[:top_n]


def build_markdown_report(scores: List[ArtifactScore], analyzer: ArtifactValueAnalyzer) -> str:
    """Gera relatório Markdown detalhado."""
    ts = datetime.now(timezone.utc).isoformat()
    avg_overall = round(sum(s.overall for s in scores) / max(1, len(scores)), 2)
    high_value = [s for s in scores if s.overall >= 4.0]
    critical_risk = [s for s in scores if s.risk_level == RiskLevel.CRITICAL.value]
    high_impact = [s for s in scores if s.impact_level == ImpactLevel.TRANSFORMATIVE.value]
    
    # Lista de prioridades
    priorities = analyzer.generate_priority_list(scores)
    
    lines = [
        f"# 🔱 Análise de Valor dos Artefatos ATENA ({ts})",
        "",
        "## Resumo Executivo",
        f"- **Total de artefatos avaliados:** {len(scores)}",
        f"- **Valor médio geral:** {avg_overall}/5.0",
        f"- **Artefatos de alto valor (≥4.0):** {len(high_value)}",
        f"- **Artefatos com risco crítico:** {len(critical_risk)}",
        f"- **Artefatos de impacto transformador:** {len(high_impact)}",
        "",
        "## Prioridades de Implementação",
        "",
        "| Prioridade | Artefato | Score Geral | Viabilidade | Risco | Ação Recomendada |",
        "|-----------|----------|-------------|-------------|-------|------------------|"
    ]
    
    for i, s in enumerate(priorities):
        rec = s.recommendations[0] if s.recommendations else "Revisar e priorizar"
        lines.append(
            f"| {i+1} | `{Path(s.path).name[:30]}` | **{s.overall}** | {s.feasibility}/5 | {s.risk}/5 | {rec[:40]} |"
        )
    
    lines.extend([
        "",
        "## Matriz de Avaliação Detalhada",
        "",
        "| Artefato | Actionability | Novidade | Evidência | Impacto | Viabilidade | Risco | **Geral** |",
        "|----------|--------------:|---------:|----------:|--------:|------------:|------:|----------:|"
    ])
    
    for s in scores:
        lines.append(
            f"| `{Path(s.path).name[:35]}` | {s.actionability} | {s.novelty} | {s.evidence} | "
            f"{s.impact} | {s.feasibility} | {s.risk} | **{s.overall}** |"
        )
    
    lines.extend([
        "",
        "## Análise por Dimensão",
        "",
        "### 🎯 Actionability (Capacidade de Ação)",
        f"- Média: {round(sum(s.actionability for s in scores)/len(scores), 2)}/5.0",
        f"- Melhor: {max(scores, key=lambda x: x.actionability).path}",
        "",
        "### 💡 Novidade",
        f"- Média: {round(sum(s.novelty for s in scores)/len(scores), 2)}/5.0",
        f"- Melhor: {max(scores, key=lambda x: x.novelty).path}",
        "",
        "### 🔬 Evidência",
        f"- Média: {round(sum(s.evidence for s in scores)/len(scores), 2)}/5.0",
        f"- Melhor: {max(scores, key=lambda x: x.evidence).path}",
        "",
        "### ⚡ Impacto Potencial",
        f"- Média: {round(sum(s.impact for s in scores)/len(scores), 2)}/5.0",
        f"- Impacto Transformador: {', '.join([s.path.split('/')[-1] for s in high_impact[:3]]) if high_impact else 'Nenhum'}",
        "",
        "### 🛠️ Viabilidade",
        f"- Média: {round(sum(s.feasibility for s in scores)/len(scores), 2)}/5.0",
        "",
        "### ⚠️ Risco",
        f"- Média: {round(sum(s.risk for s in scores)/len(scores), 2)}/5.0",
        f"- Risco Crítico: {', '.join([s.path.split('/')[-1] for s in critical_risk[:3]]) if critical_risk else 'Nenhum'}",
        "",
        "## Recomendações por Artefato",
        ""
    ])
    
    for s in scores:
        if s.recommendations or s.notes:
            lines.append(f"### `{Path(s.path).name}`")
            if s.recommendations:
                lines.append("**Recomendações:**")
                for rec in s.recommendations[:3]:
                    lines.append(f"  - {rec}")
            if s.notes and s.notes != "sem observações":
                lines.append(f"**Observações:** {s.notes}")
            if s.related_to:
                lines.append(f"**Relacionado a:** {', '.join([Path(r).name for r in s.related_to[:3]])}")
            if s.tags:
                lines.append(f"**Tags:** {', '.join(s.tags[:5])}")
            lines.append("")
    
    # Evolução de artefatos
    lines.extend([
        "## Evolução de Artefatos (histórico)",
        ""
    ])
    
    for path_str in list(analyzer._history.keys())[:5]:
        evolution = analyzer.get_evolution(path_str)
        if evolution.get("has_history"):
            icon = "📈" if evolution["trend"] == "improving" else "📉" if evolution["trend"] == "degrading" else "➡️"
            lines.append(
                f"- {icon} `{Path(path_str).name}`: {evolution['first_score']:.2f} → {evolution['last_score']:.2f} "
                f"({evolution['trend']})"
            )
    
    lines.extend([
        "",
        "## Veredito Final",
        f"- **Valor médio dos artefatos:** **{avg_overall}/5.0**",
    ])
    
    if avg_overall >= 4.0:
        lines.append("- **Classificação:** 🏆 EXCELENTE - Artefatos de alto valor prontos para implementação")
    elif avg_overall >= 3.0:
        lines.append("- **Classificação:** ✅ BOM - Artefatos úteis, prontos para adoção com pequenos ajustes")
    elif avg_overall >= 2.0:
        lines.append("- **Classificação:** ⚠️ REGULAR - Artefatos com valor moderado, revisão recomendada")
    else:
        lines.append("- **Classificação:** ❌ BAIXO - Artefatos com valor limitado, repriorizar esforços")
    
    lines.append("")
    if high_value:
        lines.append(f"**Próximos passos:** Priorizar implementação de {len(high_value)} artefatos de alto valor")
    if critical_risk:
        lines.append(f"**⚠️ Atenção:** Mitigar riscos em {len(critical_risk)} artefatos antes da implantação")
    
    return "\n".join(lines) + "\n"


def scan_artifacts(patterns: List[str], base_dir: Path = Path(".")) -> List[Path]:
    """Escaneia artefatos baseado em padrões glob."""
    artifacts = []
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            if path.is_file() and path.suffix in (".md", ".json", ".txt"):
                artifacts.append(path)
    return sorted(set(artifacts))


def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Artifact Value Analyzer v2.0")
    parser.add_argument("--patterns", nargs="+", default=[
        "docs/*.md",
        "analysis_reports/*.json",
        "analysis_reports/*.md",
        "atena_evolution/enterprise_advanced/*.json",
        "atena_evolution/*.json"
    ], help="Padrões glob para encontrar artefatos")
    parser.add_argument("--output", type=str, default="docs/ANALISE_VALOR_ARTEFATOS_ATENA.md",
                        help="Caminho do relatório de saída")
    parser.add_argument("--top", type=int, default=5, help="Número de prioritários para listar")
    parser.add_argument("--history", action="store_true", help="Mostra evolução histórica")
    parser.add_argument("--json", action="store_true", help="Saída em formato JSON")
    
    args = parser.parse_args()
    
    artifacts = scan_artifacts(args.patterns)
    
    if not artifacts:
        print("❌ Nenhum artefato encontrado para avaliar.")
        return 1
    
    print(f"🔍 Avaliando {len(artifacts)} artefatos...")
    
    analyzer = ArtifactValueAnalyzer()
    scores = [analyzer.evaluate_artifact(p, artifacts) for p in artifacts]
    
    if args.json:
        output_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_artifacts": len(scores),
            "average_score": round(sum(s.overall for s in scores) / len(scores), 2),
            "artifacts": [s.to_dict() for s in scores],
            "priority_list": [s.to_dict() for s in analyzer.generate_priority_list(scores, args.top)]
        }
        output_path = Path(args.output).with_suffix(".json")
        output_path.write_text(json.dumps(output_data, indent=2, default=str), encoding="utf-8")
        print(f"📊 Relatório JSON salvo em: {output_path}")
    else:
        report = build_markdown_report(scores, analyzer)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"📄 Relatório gerado: {output_path}")
    
    # Resume no console
    print("\n📊 Resumo da Avaliação:")
    print(f"   - Total: {len(scores)} artefatos")
    print(f"   - Score médio: {sum(s.overall for s in scores)/len(scores):.2f}/5.0")
    print(f"   - Alto valor (≥4.0): {len([s for s in scores if s.overall >= 4.0])}")
    print(f"   - Risco crítico: {len([s for s in scores if s.risk_level == 'critical'])}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
