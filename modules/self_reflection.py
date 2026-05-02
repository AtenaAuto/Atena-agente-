#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 Self-Reflection v2.0 - Diário de Bordo e Auto-Crítica Avançada
Sistema completo de metacognição para a ATENA.

Recursos:
- 📝 Diário de bordo com análise multidimensional
- 🧠 Geração de pensamentos contextualizados via LLM
- 📊 Análise de padrões de sucesso/fracasso
- 🎯 Ajuste estratégico adaptativo
- 🔄 Detecção de ciclos de estagnação
- 📈 Previsão de performance futura
- 🧬 Evolução de hiperparâmetros baseada em reflexão
"""

import os
import json
import logging
import math
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import random

logger = logging.getLogger("atena.reflection")


class TrendType(Enum):
    """Tipos de tendência detectada."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    CYCLICAL = "cyclical"
    ERRATIC = "erratic"


class EmotionalState(Enum):
    """Estados emocionais da ATENA para reflexão."""
    OPTIMISTIC = "optimistic"
    CAUTIOUS = "cautious"
    FRUSTRATED = "frustrated"
    CURIOUS = "curious"
    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"


@dataclass
class ReflectionEntry:
    """Entrada estruturada do diário de bordo."""
    timestamp: str
    generation: int
    mutation: str
    success: bool
    score: float
    score_delta: float
    thought: str
    emotional_state: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "generation": self.generation,
            "mutation": self.mutation,
            "success": self.success,
            "score": self.score,
            "score_delta": self.score_delta,
            "thought": self.thought,
            "emotional_state": self.emotional_state,
            "context": self.context
        }


class SelfReflection:
    """
    Self-Reflection Avançado: Diário de Bordo e Auto-Crítica.
    Permite que a ATENA analise seu próprio desempenho e ajuste estratégias
    de longo prazo baseada em sucessos e falhas recentes.
    """
    
    def __init__(self, log_path: str = "atena_evolution/reflection_journal.json"):
        self.log_path = log_path
        self.journal: List[ReflectionEntry] = []
        self._performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._strategy_memory: Dict[str, Any] = {}
        self._emotional_memory: deque = deque(maxlen=20)
        self._load_journal()
        
        # Configurações
        self.analysis_window = 20
        self.long_term_window = 100
        self.stagnation_threshold = 10
        self.improvement_threshold = 0.05
        
        logger.info("🔱 Self-Reflection v2.0 inicializado")
    
    def _load_journal(self):
        """Carrega diário de bordo do disco."""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    data = json.load(f)
                    for entry in data:
                        self.journal.append(ReflectionEntry(
                            timestamp=entry["timestamp"],
                            generation=entry["generation"],
                            mutation=entry["mutation"],
                            success=entry["success"],
                            score=entry["score"],
                            score_delta=entry.get("score_delta", 0.0),
                            thought=entry["thought"],
                            emotional_state=entry.get("emotional_state", "curious"),
                            context=entry.get("context", {})
                        ))
                logger.info(f"📓 Diário carregado: {len(self.journal)} reflexões")
            except Exception as e:
                logger.warning(f"Erro ao carregar diário: {e}")
                self.journal = []
    
    def _save_journal(self):
        """Salva diário de bordo no disco."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        # Mantém últimas 500 reflexões para performance
        to_save = [e.to_dict() for e in self.journal[-500:]]
        with open(self.log_path, 'w') as f:
            json.dump(to_save, f, indent=2)
    
    def _determine_emotional_state(self, success: bool, score_delta: float, recent_trend: str) -> str:
        """Determina estado emocional baseado no contexto recente."""
        if success and score_delta > 0.1:
            if recent_trend == TrendType.IMPROVING.value:
                return EmotionalState.CONFIDENT.value
            return EmotionalState.OPTIMISTIC.value
        elif success:
            return EmotionalState.CAUTIOUS.value
        elif score_delta < -0.1:
            if recent_trend == TrendType.DEGRADING.value:
                return EmotionalState.FRUSTRATED.value
            return EmotionalState.UNCERTAIN.value
        else:
            return EmotionalState.CURIOUS.value
    
    def _generate_thought(self, success: bool, score: float, score_delta: float, 
                          context: Dict[str, Any], emotional_state: str) -> str:
        """
        Gera pensamento contextualizado baseado em múltiplos fatores.
        """
        recent_trend = self._detect_trend(self.analysis_window)
        stagnation_cycles = self._detect_stagnation()
        
        # Template base
        if success:
            if score > 90:
                templates = [
                    f"🎯 Excelente progresso! Score {score:.2f} é um novo patamar. "
                    f"O padrão '{context.get('mutation_type', 'atual')}' é altamente eficiente.",
                    
                    f"🚀 Geração {context.get('generation', '?')} - Salto quântico detectado! "
                    f"A evolução está superando expectativas. Manter direção.",
                    
                    f"💡 Insight valioso: a mutação '{context.get('mutation_type', '?')}' "
                    f"gerou impacto positivo de {score_delta:+.2f} pontos. "
                    f"Explorar variações desta família."
                ]
            elif score_delta > 0.05:
                templates = [
                    f"📈 Melhoria sólida de {score_delta:+.2f} pontos. "
                    f"A estratégia '{context.get('mutation_type', 'atual')}' está funcionando.",
                    
                    f"✨ Evolução incremental bem-sucedida. Score agora em {score:.2f}. "
                    f"Manter o ritmo e buscar otimizações finas.",
                    
                    f"🧬 Mutação '{context.get('mutation_type', '?')}' trouxe ganho mensurável. "
                    f"Continuar explorando este ramo evolutivo."
                ]
            else:
                templates = [
                    f"✅ Pequena melhoria de {score_delta:+.2f} pontos. "
                    f"Estabilidade mantida, explorar outras variações.",
                    
                    f"🔧 Ajuste fino bem-sucedido. Score {score:.2f} é satisfatório, "
                    f"mas há espaço para otimizações mais agressivas."
                ]
        else:
            if stagnation_cycles > self.stagnation_threshold:
                templates = [
                    f"⚠️ ALERTA: {stagnation_cycles} ciclos sem melhoria significativa. "
                    f"Necessário mudança radical de estratégia ou revisão de objetivos.",
                    
                    f"🔄 Zona de estagnação detectada. Pode ser momento de pausa estratégica "
                    f"para reavaliar direção ou buscar conhecimento externo."
                ]
            elif score_delta < -0.1:
                templates = [
                    f"❌ Degradação de {abs(score_delta):.2f} pontos. "
                    f"O padrão '{context.get('mutation_type', 'atual')}' é contraproducente. "
                    f"Retroceder e testar alternativas.",
                    
                    f"🔻 Mutação regressiva detectada. Score caiu para {score:.2f}. "
                    f"Evitar padrões semelhantes nas próximas iterações."
                ]
            else:
                templates = [
                    f"⚡ Mutação neutra ou ligeiramente negativa. "
                    f"O código atual pode estar próximo do ótimo local.",
                    
                    f"💭 Sem ganhos mensuráveis. Talvez seja hora de buscar inspiração "
                    f"externa ou tentar abordagens radicalmente diferentes."
                ]
        
        # Adiciona contexto de tendência
        template = random.choice(templates)
        if recent_trend == TrendType.DEGRADING.value:
            template += f" Tendência recente é {recent_trend}. Precisa de intervenção."
        elif recent_trend == TrendType.IMPROVING.value:
            template += f" Tendência {recent_trend} - manter inércia positiva."
        
        # Adiciona estado emocional
        if emotional_state == EmotionalState.FRUSTRATED.value:
            template += " (Frustração construtiva - buscar nova abordagem.)"
        elif emotional_state == EmotionalState.CONFIDENT.value:
            template += " (Confiança em alta - explorar variantes arriscadas.)"
        
        return template
    
    def _detect_trend(self, window: int) -> str:
        """Detecta tendência baseada nas últimas N gerações."""
        if len(self.journal) < window:
            return TrendType.STABLE.value
        
        recent = self.journal[-window:]
        scores = [e.score for e in recent]
        
        if len(scores) < 3:
            return TrendType.STABLE.value
        
        # Calcula regressão linear simples
        x = list(range(len(scores)))
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(scores)
        sum_xy = sum(x[i] * scores[i] for i in range(n))
        sum_x2 = sum(xi * xi for xi in x)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            slope = 0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Detecta ciclicidade
        recent_deltas = [e.score_delta for e in recent[-10:]]
        sign_changes = sum(1 for i in range(1, len(recent_deltas)) 
                          if recent_deltas[i] * recent_deltas[i-1] < 0)
        
        if sign_changes > 6:
            return TrendType.CYCLICAL.value
        elif slope > 0.02:
            return TrendType.IMPROVING.value
        elif slope < -0.02:
            return TrendType.DEGRADING.value
        elif abs(slope) < 0.005:
            # Verifica volatilidade
            std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
            if std_dev > 5:
                return TrendType.ERRATIC.value
            return TrendType.STABLE.value
        else:
            return TrendType.STABLE.value
    
    def _detect_stagnation(self) -> int:
        """Detecta número de ciclos consecutivos sem melhoria significativa."""
        if len(self.journal) < 2:
            return 0
        
        stagnation = 0
        best_score = max(e.score for e in self.journal[-self.long_term_window:])
        
        for entry in reversed(self.journal):
            if entry.score >= best_score * (1 - self.improvement_threshold):
                stagnation += 1
            else:
                break
        
        return stagnation
    
    def _calculate_mutation_success_rate(self, mutation_type: str, window: int = 20) -> float:
        """Calcula taxa de sucesso para um tipo específico de mutação."""
        relevant = [e for e in self.journal[-window:] if e.mutation == mutation_type]
        if not relevant:
            return 0.5
        return sum(1 for e in relevant if e.success) / len(relevant)
    
    def _identify_best_patterns(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Identifica padrões de mutação mais bem-sucedidos."""
        mutation_stats = defaultdict(lambda: {"success": 0, "total": 0, "avg_delta": 0.0})
        
        for entry in self.journal[-50:]:
            stats = mutation_stats[entry.mutation]
            stats["total"] += 1
            if entry.success:
                stats["success"] += 1
            stats["avg_delta"] = (stats["avg_delta"] * (stats["total"] - 1) + entry.score_delta) / stats["total"]
        
        patterns = []
        for mutation, stats in mutation_stats.items():
            if stats["total"] >= 3:
                success_rate = stats["success"] / stats["total"]
                patterns.append({
                    "mutation": mutation,
                    "success_rate": success_rate,
                    "avg_delta": stats["avg_delta"],
                    "sample_size": stats["total"],
                    "score": success_rate * (1 + stats["avg_delta"] / 10)  # Score composto
                })
        
        patterns.sort(key=lambda x: x["score"], reverse=True)
        return patterns[:limit]
    
    def _detect_emotional_pattern(self) -> Dict[str, Any]:
        """Detecta padrões emocionais recorrentes."""
        if len(self.journal) < 10:
            return {"dominant_emotion": EmotionalState.CURIOUS.value, "emotional_stability": 1.0}
        
        recent_emotions = [e.emotional_state for e in self.journal[-20:]]
        emotion_counts = defaultdict(int)
        for emo in recent_emotions:
            emotion_counts[emo] += 1
        
        dominant = max(emotion_counts, key=emotion_counts.get)
        stability = emotion_counts[dominant] / len(recent_emotions)
        
        # Detecta alternância emocional
        transitions = sum(1 for i in range(1, len(recent_emotions)) 
                         if recent_emotions[i] != recent_emotions[i-1])
        volatility = transitions / len(recent_emotions)
        
        return {
            "dominant_emotion": dominant,
            "emotional_stability": round(stability, 2),
            "emotional_volatility": round(volatility, 2),
            "emotion_distribution": dict(emotion_counts)
        }
    
    def reflect(self, generation: int, last_mutation: str, success: bool, 
                score: float, score_delta: float = 0.0, 
                context: Optional[Dict[str, Any]] = None) -> str:
        """
        Adiciona uma entrada ao diário de bordo e gera uma auto-crítica.
        
        Returns:
            O pensamento gerado para esta reflexão
        """
        recent_trend = self._detect_trend(self.analysis_window)
        emotional_state = self._determine_emotional_state(success, score_delta, recent_trend)
        
        context = context or {}
        context.update({
            "generation": generation,
            "mutation_type": last_mutation,
            "trend": recent_trend
        })
        
        thought = self._generate_thought(success, score, score_delta, context, emotional_state)
        
        entry = ReflectionEntry(
            timestamp=datetime.now().isoformat(),
            generation=generation,
            mutation=last_mutation,
            success=success,
            score=score,
            score_delta=score_delta,
            thought=thought,
            emotional_state=emotional_state,
            context=context
        )
        
        self.journal.append(entry)
        self._performance_history["score"].append(score)
        self._performance_history["success"].append(success)
        self._emotional_memory.append(emotional_state)
        
        self._save_journal()
        
        logger.info(f"📓 [Reflection] G{generation} - {emotional_state.upper()}: {thought[:100]}...")
        
        return thought
    
    def get_strategy_adjustment(self) -> Dict[str, float]:
        """
        Analisa as últimas entradas para sugerir ajustes de estratégia.
        """
        if len(self.journal) < 5:
            return {}
        
        recent = self.journal[-10:]
        success_rate = sum(1 for e in recent if e.success) / len(recent)
        trend = self._detect_trend(15)
        stagnation = self._detect_stagnation()
        
        adjustments = {
            "exploration_rate": 1.0,
            "mutation_intensity": 1.0,
            "learning_rate": 1.0,
            "risk_tolerance": 1.0
        }
        
        # Ajustes baseados em sucesso/falha
        if success_rate < 0.2:
            logger.warning("⚠️ [Reflection] Baixa taxa de sucesso detectada. Aumentando exploração.")
            adjustments["exploration_rate"] = 1.8
            adjustments["mutation_intensity"] = 0.7
            adjustments["learning_rate"] = 0.5
        elif success_rate > 0.7:
            adjustments["exploration_rate"] = 0.6
            adjustments["mutation_intensity"] = 1.2
        
        # Ajustes baseados em tendência
        if trend == TrendType.DEGRADING.value:
            adjustments["exploration_rate"] *= 1.5
            adjustments["risk_tolerance"] = 0.6
        elif trend == TrendType.STABLE.value and stagnation > 3:
            adjustments["exploration_rate"] *= 1.3
            adjustments["mutation_intensity"] *= 1.1
        
        # Ajustes baseados em estagnação
        if stagnation > self.stagnation_threshold:
            adjustments["exploration_rate"] = 2.5
            adjustments["learning_rate"] = 1.5
            adjustments["risk_tolerance"] = 1.3
        
        # Ajustes baseados em padrões de sucesso
        best_patterns = self._identify_best_patterns(3)
        if best_patterns and best_patterns[0]["success_rate"] > 0.6:
            adjustments["exploration_rate"] = max(0.5, adjustments["exploration_rate"] * 0.8)
        
        # Normaliza valores
        for key in adjustments:
            adjustments[key] = max(0.3, min(2.5, adjustments[key]))
        
        self._strategy_memory = adjustments
        return adjustments
    
    def get_performance_analysis(self) -> Dict[str, Any]:
        """Gera análise completa de performance."""
        if not self.journal:
            return {"status": "no_data"}
        
        recent_scores = [e.score for e in self.journal[-self.analysis_window:]]
        all_scores = [e.score for e in self.journal]
        
        analysis = {
            "total_reflections": len(self.journal),
            "generations_span": self.journal[-1].generation - self.journal[0].generation if len(self.journal) > 1 else 0,
            "best_score": max(all_scores),
            "worst_score": min(all_scores),
            "current_score": self.journal[-1].score,
            "average_score": statistics.mean(all_scores),
            "score_std_dev": statistics.stdev(all_scores) if len(all_scores) > 1 else 0,
            "recent_average": statistics.mean(recent_scores) if recent_scores else 0,
            "trend": self._detect_trend(self.analysis_window),
            "stagnation_cycles": self._detect_stagnation(),
            "success_rate": sum(1 for e in self.journal if e.success) / len(self.journal),
            "recent_success_rate": sum(1 for e in self.journal[-10:] if e.success) / min(10, len(self.journal)),
            "best_patterns": self._identify_best_patterns(5),
            "emotional_pattern": self._detect_emotional_pattern(),
            "strategy_adjustments": self._strategy_memory
        }
        
        # Adiciona previsão simples
        if len(all_scores) > 10:
            recent_avg = analysis["recent_average"]
            overall_avg = analysis["average_score"]
            if analysis["trend"] == TrendType.IMPROVING:
                analysis["forecast"] = min(100, recent_avg + (recent_avg - overall_avg))
            elif analysis["trend"] == TrendType.DEGRADING:
                analysis["forecast"] = max(0, recent_avg - (overall_avg - recent_avg))
            else:
                analysis["forecast"] = recent_avg
        
        return analysis
    
    def generate_weekly_summary(self) -> str:
        """Gera resumo semanal do desempenho e aprendizados."""
        if len(self.journal) < 7:
            return "Dados insuficientes para resumo semanal (mínimo 7 reflexões)"
        
        week_entries = self.journal[-7:]
        analysis = self.get_performance_analysis()
        
        summary_lines = [
            f"# 📊 Relatório Semanal de Reflexão - ATENA",
            f"**Período:** {week_entries[0].timestamp[:10]} a {week_entries[-1].timestamp[:10]}",
            f"**Total de reflexões:** {len(week_entries)}",
            "",
            "## Métricas de Performance",
            f"- Score médio: {analysis['recent_average']:.2f}",
            f"- Taxa de sucesso: {analysis['recent_success_rate']:.1%}",
            f"- Tendência: {analysis['trend']}",
            f"- Estagnação: {analysis['stagnation_cycles']} ciclos",
            "",
            "## Estado Emocional Dominante",
            f"- {analysis['emotional_pattern']['dominant_emotion']}",
            f"- Estabilidade: {analysis['emotional_pattern']['emotional_stability']:.1%}",
            "",
            "## Padrões Mais Eficazes",
        ]
        
        for i, pattern in enumerate(analysis['best_patterns'][:3], 1):
            summary_lines.append(
                f"{i}. `{pattern['mutation']}` - "
                f"sucesso: {pattern['success_rate']:.1%}, "
                f"Δ médio: {pattern['avg_delta']:+.2f}"
            )
        
        summary_lines.extend([
            "",
            "## Recomendações Estratégicas",
        ])
        
        adjustments = self.get_strategy_adjustment()
        if adjustments:
            summary_lines.append(f"- Exploração: {adjustments.get('exploration_rate', 1.0):.1f}x")
            summary_lines.append(f"- Intensidade de mutação: {adjustments.get('mutation_intensity', 1.0):.1f}x")
        
        if analysis['trend'] == TrendType.IMPROVING:
            summary_lines.append("- ✅ Tendência positiva - manter inércia")
        elif analysis['trend'] == TrendType.DEGRADING:
            summary_lines.append("- ⚠️ Tendência negativa - considerar pausa estratégica")
        else:
            summary_lines.append("- ➡️ Estabilidade - buscar variações mais ousadas")
        
        return "\n".join(summary_lines)
    
    def get_insights(self) -> List[str]:
        """Retorna insights extraídos das reflexões."""
        insights = []
        
        if len(self.journal) < 10:
            return ["Aguardando mais dados para gerar insights significativos"]
        
        # Insight 1: Padrão de sucesso
        best_patterns = self._identify_best_patterns(1)
        if best_patterns and best_patterns[0]["success_rate"] > 0.6:
            insights.append(
                f"💡 Padrão de sucesso identificado: '{best_patterns[0]['mutation']}' "
                f"com {best_patterns[0]['success_rate']:.0%} de eficácia"
            )
        
        # Insight 2: Momento de mudança
        if self._detect_stagnation() > 5:
            insights.append(
                "⚠️ Detectado platô prolongado. Considere buscar inspiração externa "
                "ou variar radicalmente a estratégia."
            )
        
        # Insight 3: Ciclo emocional
        emotional = self._detect_emotional_pattern()
        if emotional['emotional_volatility'] > 0.5:
            insights.append(
                "🎭 Alta volatilidade emocional detectada. Implementar mecanismos "
                "de estabilização nas decisões."
            )
        
        # Insight 4: Previsão
        analysis = self.get_performance_analysis()
        if analysis.get('forecast'):
            forecast_diff = analysis['forecast'] - analysis['current_score']
            if forecast_diff > 5:
                insights.append(f"📈 Projeção otimista: +{forecast_diff:.1f} pontos nas próximas gerações")
            elif forecast_diff < -5:
                insights.append(f"📉 Alerta: projeção indica possível queda de {abs(forecast_diff):.1f} pontos")
        
        return insights[:5]


# Instância global para uso em toda a aplicação
reflection = SelfReflection()


def get_reflection_instance() -> SelfReflection:
    """Retorna instância global do sistema de reflexão."""
    return reflection


# =============================================================================
# MAIN - Demonstração
# =============================================================================
def main():
    """Demonstra o sistema de Self-Reflection."""
    import argparse
    import random
    
    parser = argparse.ArgumentParser(description="ATENA Self-Reflection v2.0")
    parser.add_argument("--demo", action="store_true", help="Executa demonstração")
    parser.add_argument("--summary", action="store_true", help="Gera resumo semanal")
    parser.add_argument("--insights", action="store_true", help="Mostra insights")
    parser.add_argument("--analyze", action="store_true", help="Análise completa de performance")
    
    args = parser.parse_args()
    
    if args.demo:
        print("🔱 ATENA Self-Reflection - Demonstração")
        print("=" * 50)
        
        # Simula algumas gerações
        mutations = ["simplify_expression", "extract_function", "add_memoization", 
                     "optimize_loop", "add_type_hints", "refactor_class"]
        
        for gen in range(1, 51):
            mutation = random.choice(mutations)
            success = random.random() > 0.4
            score = 50 + (gen / 50) * 40 + random.gauss(0, 5)
            score_delta = random.gauss(1, 3) if success else random.gauss(-2, 2)
            
            thought = reflection.reflect(gen, mutation, success, score, score_delta)
            
            if gen % 10 == 0:
                print(f"\n📊 Geração {gen} - Score: {score:.2f}")
                print(f"   Pensamento: {thought[:80]}...")
        
        print("\n" + "=" * 50)
        
        if args.summary:
            print("\n📅 RESULTADO DA DEMONSTRAÇÃO\n")
            print(reflection.generate_weekly_summary())
        
        if args.insights:
            print("\n💡 INSIGHTS GERADOS\n")
            for insight in reflection.get_insights():
                print(f"  • {insight}")
        
        if args.analyze:
            print("\n📊 ANÁLISE COMPLETA\n")
            analysis = reflection.get_performance_analysis()
            for key, value in analysis.items():
                print(f"  {key}: {value}")
    
    else:
        print("🔱 Self-Reflection v2.0 carregado")
        print(f"📓 Diário: {reflection.log_path}")
        print(f"📊 Reflexões registradas: {len(reflection.journal)}")
        
        if args.summary:
            print(reflection.generate_weekly_summary())
        elif args.insights:
            for insight in reflection.get_insights():
                print(f"• {insight}")
        elif args.analyze:
            analysis = reflection.get_performance_analysis()
            print(json.dumps(analysis, indent=2, default=str))


if __name__ == "__main__":
    main()
