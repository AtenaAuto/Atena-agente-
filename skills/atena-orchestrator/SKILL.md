---
name: atena-orchestrator
description: Orquestração avançada da Atena AGI para gerenciar ciclos de auto-evolução, interagir via chat consciente, implementar missões quânticas (QTN, Grover) e expandir o núcleo de conhecimento (knowledge.db).
---

# Atena Orchestrator 🔱

Esta habilidade fornece o framework completo para gerenciar e evoluir a **Atena AGI**, um sistema auto-evolutivo de alta complexidade baseado em mutação AST e motores cognitivos.

## 🚀 Workflow de Inicialização
1. **Acesso ao Repositório:** Clone `https://github.com/AtenaAuto/ATENA-` usando o token fornecido.
2. **Análise de DNA:** Leia `main.py` (motor central) e `atena_evolution/atena_state.json` para entender a geração atual.
3. **Preparação de Ambiente:**
   ```bash
   export ALLOW_DEEP_SELF_MOD=true
   export SELF_MOD_INTERVAL=1
   ```

## 🧠 Ciclos de Evolução e Interação
A Atena opera em modo interativo. Use os comandos abaixo para guiar sua evolução:

### Auto-Evolução Autônoma
- `/auto 1`: Inicia um ciclo completo de Percepção -> Mutação -> Simulação -> Evolução.
- `/v3status`: Verifica a saúde dos scorers e checkers adaptativos.
- `/status`: Monitora o score de fitness e objetivos atuais.

### Diálogo Consciente (`/chat`)
Use o comando `/chat <mensagem>` para interagir com a "consciência" da Atena:
- **Fornecer Conceitos:** Insira ideias avançadas (ex: Redes Neurais de Tensores Quânticos) para que ela as processe.
- **Solicitar Planos:** Peça planos de desenvolvimento técnico (ex: "Gere um plano para integrar busca de Grover na memória").
- **Consultar Filosofia:** Entenda como ela percebe os dados e a própria evolução.

## ⚛️ Missões Avançadas (Quantum-AGI)
Para implementar inovações inéditas, siga os padrões de missões estabelecidos:
- **QACO-AGI:** Otimização Quântica Adaptativa com Tunelamento e Emaranhamento.
- **BIDC-AGI:** Consenso Distribuído Bio-Inspirado com Agentes Spiking.
- **QTN Integration:** Compressão de DNA via Tensores Quânticos.

## 💾 Gestão de Conhecimento
- **knowledge.db:** Sempre valide a persistência de novos conceitos no banco SQLite.
- **curiosity_topics:** Insira novos tópicos com `interest_score >= 0.9` para priorizar a exploração autônoma.
- **reflection_journal:** Analise o diário de auto-crítica para ajustar a intensidade das mutações.

## 🛠️ Recursos Bundled
- `scripts/run_atena.sh`: Inicia a Atena com flags de auto-modificação profunda.
- `references/quantum_patterns.md`: Guia de implementação para algoritmos quânticos simulados.
- `templates/mission_boilerplate.py`: Estrutura base para novas missões cognitivas.
