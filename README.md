# 🔱 ATENA Ω (Atena-AGI) v3.2.0

[![CI/CD Pipeline](https://github.com/AtenaAuto/ATENA-/actions/workflows/ci.yml/badge.svg)](https://github.com/AtenaAuto/ATENA-/actions)
[![Code Coverage](https://codecov.io/gh/AtenaAuto/ATENA-/branch/main/graph/badge.svg)](https://codecov.io/gh/AtenaAuto/ATENA-)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**ATENA Ω** é um sistema de IA autônomo avançado para execução de assistentes de terminal, missões autônomas e gates de qualidade com evolução segura de sistemas. Combinando arquitetura moderna de agentes, a ATENA integra execução local com capacidades avançadas de orquestração multi-LLM.

---

## 🏁 Status Oficial (Projeto)

> **ATENA AGI (oficial do projeto): ATIVA**
>
> A classificação oficial deste repositório considera a ATENA como AGI operacional, com score interno e score externo máximos nos gates atuais do projeto.

- Internal AGI Uplift: `10.0/10`
- External AGI Validation: `10.0/10`

---

## ✨ Características Principais

- 🤖 **Assistente de Terminal Interativo** - Interface conversacional inteligente
- 🚀 **Sistema de Missões Autônomas** - Execução assíncrona de tarefas complexas
- 🛡️ **Gates de Segurança e Qualidade** - Validação automática robusta
- 🧬 **Motor de Auto-Evolução** - Aprendizado contínuo e otimização
- 🔄 **Orquestração Multi-LLM** - Suporte a OpenAI, Anthropic, modelos locais
- 🔐 **Validação de Código Segura** - Proteção contra execução maliciosa
- 📊 **Dashboard em Tempo Real** - Monitoramento e visualizações
- 🧪 **Sistema de Testes Robusto** - Cobertura completa com pytest

---

## 🚀 Início Rápido

### Requisitos

- **Python 3.10+** (Python 3.11 recomendado)
- **Git** para clonar o repositório
- **Pip** para gerenciamento de pacotes
- **(Opcional)** Chaves de API para OpenAI, Anthropic, etc.

### Instalação em Windows 💻

```bash
# Ir para uma pasta onde você quer baixar o projeto
cd C:\Users\AtenaAuto

# Remover pasta existente (se existir)
Remove-Item -Recurse -Force Atena-agente- - -ErrorAction SilentlyContinue

# Clonar o repositório
git clone https://github.com/AtenaAuto/Atena-agente-.git

# Entrar na pasta
cd Atena-agente-

# Ir para setup
cd setup

# Instalar dependências
pip install -r requirements-pinned.txt
pip install -r requirements-dev.txt

# Voltar para raiz
cd ..

# Rodar o assistente
.\atena assistant
```

### Instalação em Linux/macOS 🐧🍎

```bash
# Go to the root content directory
cd /path/to/your/projects

# Remove any existing ATENA- directory
rm -rf ATENA-

# Clone the repository
git clone https://github.com/AtenaAuto/atena-agente-.git

# Enter directory
cd ATENA-

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r setup/requirements-pinned.txt
pip install -r setup/requirements-dev.txt

# (Optional) Install Playwright for browser agent
playwright install chromium

# Run the assistant
bash atena assistant
```



### Quickstart Universal ✅

Se você só quer funcionar rápido em qualquer ambiente:

```bash
python3 setup/bootstrap_portable.py --full-auto
bash atena assistant
```

Se estiver sem permissão de administrador, use:

```bash
python3 setup/bootstrap_portable.py --full-auto --skip-system
bash atena assistant
```

### Bootstrap Portátil (Linux/macOS/Windows/Colab) 🌍

Para deixar a Atena pronta em qualquer ambiente, rode:

```bash
python3 setup/bootstrap_portable.py --full-auto
```

Modo simulação (não instala nada):

> Dica: use `--skip-system` se estiver sem permissão de administrador.

```bash
python3 setup/bootstrap_portable.py --full-auto --dry-run
```

### Google Colab (corrigido) ☁️

Se estiver dando erro no Colab, use o bootstrap pronto:

> Importante: esse comando já faz o clone do repositório.

```bash
# Dentro do Colab
!bash setup/colab_bootstrap.sh /content/projects/ATENA-
```

Depois execute:

```bash
!cd /content/projects/atena-agente- && bash atena doctor
!cd /content/projects/atena-agente- && ATENA_AUTO_ENDPOINT_SETUP=false USER=colab bash atena assistant
```

Uma célula única no Colab (clone + bootstrap + run):

```bash
!mkdir -p /content/projects && cd /content/projects && rm -rf ATENA- && git clone https://github.com/AtenaAuto/ATENA-.git && bash /content/projects/ATENA-/setup/colab_bootstrap.sh /content/projects/ATENA- && cd /content/projects/ATENA- && ATENA_AUTO_ENDPOINT_SETUP=false USER=colab bash atena assistant
```

Uma célula Python alternativa (com fallback de `pip` no venv):

```python
# Ir para uma pasta onde você quer baixar o projeto
# Colab usa um ambiente Linux, então caminhos Windows como C:\Users não são válidos.
# Usaremos /content como um diretório de trabalho comum no Colab.
%cd /content

# Remover pasta existente (se existir)
# 'Remove-Item' é um comando PowerShell. No Linux, 'rm -rf' é usado.
!rm -rf Atena-agente-

# Clonar o repositório
!git clone https://github.com/AtenaAuto/Atena-agente-.git

# Entrar na pasta
%cd Atena-agente-

# Ir para setup
%cd setup

# Instalar dependências
!pip install -r requirements-pinned.txt
!pip install -r requirements-dev.txt

# Voltar para raiz
%cd ..

# Conceder permissão de execução ao script 'atena'
!chmod +x atena

# Rodar o assistente
# '.\atena assistant' é um caminho de executável Windows.
# Assumindo que 'atena' é um executável ou script disponibilizado após a instalação via pip,
# podemos tentar executá-lo diretamente.
# O executável 'atena' está na raiz do repositório, então usamos './atena'
!./atena assistant
```

> Dica: no Colab prefira `bash atena ...` em vez de `./atena ...` para evitar erro de permissão em alguns mounts.

### Instalação em Android (Termux) 📱

```bash
# Atualizar pacotes
pkg update && pkg upgrade -y

# Instalar dependências
pkg install git python clang make -y

# Clonar e instalar
git clone https://github.com/AtenaAuto/atena-agente-.git
cd ATENA-
cd setup
pip install -r requirements.txt
cd ..
```

### Verificação de Instalação

```bash
# Verificar se ambiente está pronto
./atena doctor

# Deve mostrar status de todos os componentes
```

---

## 🎮 Uso

### Comandos Principais

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `./atena assistant` | Inicia assistente interativo | `./atena assistant` |
| `./atena doctor` | Diagnóstico de ambiente | `./atena doctor` |
| `./atena guardian` | Gate de segurança essencial | `./atena guardian` |
| `./atena production-ready` | Validação completa para release | `./atena production-ready` |
| `./atena hacker-recon --topic <tópico>` | Executa Hacker Recon avançado (batch, paralelo, retries, score, histórico adaptativo, `--json`, `--output-json`, `--timeout`) | `./atena hacker-recon --batch-file topics.txt --parallel 3 --retries 1 --prioritize-history --json --output-json analysis_reports/recon.json` |
| `/api-scan <tarefa>` | Escaneia APIs públicas e retorna ranking por aderência | `/api-scan "agenda de futebol e resultados"` |
| `/api-filter <tarefa>` | Filtra Top APIs por tarefa/pergunta com score | `/api-filter "criar agente programável com SDK"` |
| `/api-pick <tarefa>` | Escolhe 1 API e já gera exemplo de request | `/api-pick "cotação de moedas em tempo real"` |
| `./atena code-build` | Gerador automático de projetos | `./atena code-build --type api` |
| `./atena research-lab` | Propostas de evolução | `./atena research-lab` |
| `./atena future-ai` | Gera inovação técnica; inclui `app-food-delivery-complete` para app completo de delivery com backend + mobile | `./atena future-ai --mode app-food-delivery-complete --topic "delivery de comida" --json` |
| `./atena go-no-go` | Checklist pré-divulgação | `./atena go-no-go` |
| `./atena agi-uplift` | Missão AGI interna (memória/eval/segurança) | `./atena agi-uplift` |
| `./atena agi-external-validation` | Validação AGI externa independente | `./atena agi-external-validation` |
| `./atena digital-organism-audit` | Auditoria automática de maturidade como organismo digital | `./atena digital-organism-audit` |
| `./atena digital-organism-live-cycle` | Aprende na internet, cria software, executa/testa, auto-recupera falhas e roda em daemon; use `--challenge-level agi-only` para tarefa extremamente difícil | `./atena digital-organism-live-cycle --challenge-level agi-only --iterations 3 --batches 2 --strict --recovery-attempts 2` |

> CI evolução: o workflow `ATENA-EVO` agora inclui um *stagnation guard* que reduz ciclos e ativa `--checker` quando detecta plateau de mutações.

### Exemplos de Uso

#### 0. Modo Computador — Varredura de Códigos

```bash
# Executa o modo computador da ATENA e salva artefatos de varredura + diff incremental em analysis_reports/
bash scripts/run_computer_mode_code_scan.sh

# Modo profundo: adiciona diff por hash de conteúdo dos arquivos de código
bash scripts/run_computer_mode_code_scan.sh --deep-hash
```

#### 1. Assistente Interativo

```bash
./atena assistant

# Interface conversacional
> Olá ATENA!
ATENA: Olá! Como posso ajudar hoje?

> Crie uma API REST em FastAPI
ATENA: Gerando projeto FastAPI...
✅ Projeto criado em ./output/api_project/
```

#### 2. Executar Missão Específica

```python
# Em Python
from protocols.atena_invoke import run_mission

result = await run_mission(
    mission_type="code_build",
    params={
        "project_type": "api",
        "framework": "fastapi"
    }
)
```

#### 3. Resolver problema complexo com subagente especialista

```bash
./atena production-center subagent-solve --problem "Invente um algoritmo que ordene números usando apenas operações de comparação, mas sem if/else ou operadores ternários; explorar truques com min/max e arrays"
```

Saída esperada (resumida): `status: ok`, `subagent: specialist-solver`, plano incremental, recomendações de rollout e `contract_valid: true`.

#### 4. Validação de Código

```python
from core.security_validator import validate_code_safe, SecurityLevel

code = """
def hello():
    return "Hello, World!"
"""

is_valid, violations = validate_code_safe(code, SecurityLevel.STANDARD)
if is_valid:
    print("✅ Código seguro!")
else:
    print(f"❌ Violações: {violations}")
```

---

## 📂 Estrutura do Projeto

```
ATENA-/
├── 📁 core/                    # Núcleo executivo
│   ├── main.py                # Motor principal
│   ├── atena_pipeline.py      # Pipeline de processamento
│   ├── atena_launcher.py      # Ponto de entrada
│   ├── security_validator.py  # ✨ Validação de segurança
│   └── [30+ módulos]
│
├── 📁 modules/                 # Módulos funcionais
│   ├── atena_engine.py        # Motor auxiliar
│   ├── atena_codex.py         # Gerador de código
│   ├── atena_browser_agent.py # Automação web
│   ├── atena_tasks.py         # Executor de tarefas
│   └── [50+ módulos]
│
├── 📁 protocols/               # Missões e protocolos
│   ├── atena_invoke.py        # Orquestrador
│   └── [20+ missões]
│
├── 📁 tests/                   # ✨ Testes completos
│   ├── unit/                  # Testes unitários
│   ├── integration/           # Testes de integração
│   ├── e2e/                   # Testes end-to-end
│   └── conftest.py            # Fixtures compartilhadas
│
├── 📁 setup/                   # Instalação
│   ├── requirements.txt       # Dependências originais
│   ├── requirements-pinned.txt # ✨ Versões pinadas
│   └── requirements-dev.txt   # ✨ Ferramentas de dev
│
├── 📁 docs/                    # Documentação
├── 📁 atena_evolution/         # Estado e evolução
├── 📁 reference_dna/           # Interface React/TS
│
├── .env.example               # ✨ Template de configuração
├── .gitignore                 # ✨ Atualizado com segurança
├── .pre-commit-config.yaml    # ✨ Hooks de qualidade
├── pyproject.toml             # ✨ Configuração do projeto
├── README.md                  # ✨ Este arquivo
└── LICENSE                    # Licença MIT
```

---

## 🔧 Desenvolvimento

### Configurando Ambiente de Desenvolvimento

```bash
# Instalar ferramentas de desenvolvimento
pip install -r setup/requirements-dev.txt

# Configurar pre-commit hooks
pre-commit install

# Executar formatação
black core/ modules/ protocols/
isort core/ modules/ protocols/

# Executar linting
pylint core/ modules/ --fail-under=7.0
flake8 core/ modules/ protocols/

# Executar type checking
mypy core/ modules/ --ignore-missing-imports
```

### Executando Testes

```bash
# Todos os testes
pytest

# Apenas testes unitários
pytest tests/unit/ -v

# Com cobertura
pytest --cov=core --cov=modules --cov-report=html

# Testes específicos
pytest tests/unit/test_atena_engine.py -v

# Testes lentos (marcados com @pytest.mark.slow)
pytest -m "not slow"  # Pula testes lentos
pytest -m slow        # Apenas testes lentos
```

### Verificação de Qualidade

```bash
# Executar todas as verificações
./scripts/run_quality_checks.sh

# Ou manualmente:
black --check core/ modules/
pylint core/ modules/
mypy core/ modules/
bandit -r core/ modules/
pytest --cov=core --cov=modules
```

---

## 🛡️ Fluxo de Qualidade (CI/CD)

Para garantir estabilidade, use o fluxo recomendado antes de qualquer alteração importante:

```bash
# 1. Verificar ambiente
./atena doctor

# 2. Executar testes
pytest

# 3. Verificar segurança
./atena guardian

# 4. Validação final
./atena production-ready
```

### Pipeline CI/CD

O projeto inclui pipeline completo de CI/CD com GitHub Actions:

- ✅ **Linting** - Black, isort, flake8, pylint
- ✅ **Type Checking** - mypy
- ✅ **Security Scan** - Bandit, Safety
- ✅ **Unit Tests** - pytest com cobertura
- ✅ **Integration Tests** - Testes de integração
- ✅ **Build Check** - Verificação de build

---

## 🔐 Segurança

### Validação de Código

ATENA inclui validação robusta de código para prevenir execução maliciosa:

```python
from core.security_validator import CodeSecurityValidator, SecurityLevel

validator = CodeSecurityValidator(SecurityLevel.STRICT)
result = validator.validate(user_code)

if not result.is_valid:
    print(f"❌ Código rejeitado:")
    for violation in result.violations:
        print(f"  - {violation}")
```

### Níveis de Segurança

- **STRICT** - Máxima segurança, funcionalidade mínima
- **STANDARD** - Balanceado (padrão)
- **PERMISSIVE** - Menos restrições (use com cuidado)

### Proteções Implementadas

- ✅ Bloqueio de imports perigosos (os, sys, subprocess, etc.)
- ✅ Bloqueio de funções builtin perigosas (exec, eval, __import__)
- ✅ Validação de AST antes de execução
- ✅ Sandbox isolado para execução
- ✅ Timeout configurável
- ✅ Limite de recursos (memória, CPU)

---

## 📊 Monitoramento e Telemetria

### Dashboard Local

```bash
# Iniciar dashboard Streamlit
streamlit run atena_live_dashboard.py

# Acessar em http://localhost:8501
```

### Métricas Disponíveis

- Taxa de sucesso de missões
- Tempo médio de execução
- Gerações de evolução
- Score de qualidade
- Uso de recursos

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Execute os testes (`pytest`)
4. Execute verificações de qualidade (`black`, `pylint`, `mypy`)
5. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
6. Push para a branch (`git push origin feature/AmazingFeature`)
7. Abra um Pull Request

### Checklist para PRs

- [ ] Testes passando (`pytest`)
- [ ] Cobertura >60% para código novo
- [ ] Linting sem erros (`black`, `pylint`)
- [ ] Type hints adicionados
- [ ] Documentação atualizada
- [ ] Changelog atualizado

---

## 📝 Changelog

### v3.2.0 (2026-04-14) - Melhorias de Qualidade ✨

**Adicionado:**
- ✨ Sistema completo de testes (pytest)
- ✨ Validação de código com AST
- ✨ CI/CD pipeline com GitHub Actions
- ✨ Pre-commit hooks para qualidade
- ✨ Dependências pinadas para estabilidade
- ✨ Configuração .env para segurança
- ✨ Type hints e documentação melhorada

**Melhorado:**
- 🔧 .gitignore com proteções de segurança
- 🔧 Estrutura de diretórios organizada
- 🔧 README expandido e atualizado
- 🔧 Configuração pyproject.toml

**Segurança:**
- 🔐 Proteção contra código malicioso
- 🔐 Validação de imports
- 🔐 Sandbox melhorado

### v3.1.0 - Versão Original

- Implementação inicial do motor de evolução
- Assistente de terminal
- Sistema de missões

---

## 📚 Documentação

Para documentação detalhada, consulte:

- [Análise Completa](analysis_reports/ATENA_Analise_Completa.md)
- [Guia de Implementação](analysis_reports/ATENA_Guia_Implementacao.md)
- [Roadmap Executivo](analysis_reports/ATENA_Roadmap_Executivo.md)
- [Modo Manual Internet](analysis_reports/ATENA_Modo_Manual_Internet.md)

---

## 📜 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 👥 Equipe

**Desenvolvido por:** Danilo AtenaAuto Team

---

## 🙏 Agradecimentos

- Comunidade Python
- Criadores do FastAPI, Streamlit, PyTorch
- Todos os contribuidores open-source

---

## 📞 Suporte

Para questões e suporte:

- 📧 Issues: [GitHub Issues](https://github.com/AtenaAuto/ATENA-/issues)
- 📖 Documentação: [Wiki](https://github.com/AtenaAuto/ATENA-/wiki)
- 💬 Discussões: [GitHub Discussions](https://github.com/AtenaAuto/ATENA-/discussions)

---

<div align="center">

**⚡ Feito com 💙 e Python**

[⬆ Voltar ao topo](#-atena-ω-atena-code-v320)

</div>
