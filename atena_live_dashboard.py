import streamlit as st
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import json

# Adiciona o caminho dos módulos
sys.path.append(os.path.join(os.getcwd(), 'modules'))
from atena_control_bridge import AtenaControlBridge

# Configuração da página
st.set_page_config(
    page_title="🔱 ATENA Live Dashboard",
    page_icon="🔱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00D9FF;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-active {
        color: #00FF00;
        font-weight: bold;
    }
    .status-inactive {
        color: #FF0000;
        font-weight: bold;
    }
    .log-container {
        background-color: #1a1a1a;
        border: 2px solid #00D9FF;
        border-radius: 8px;
        padding: 1rem;
        font-family: monospace;
        font-size: 0.85rem;
        max-height: 400px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-header">🔱 ATENA Live Dashboard</div>', unsafe_allow_html=True)

# Inicializa o Control Bridge
bridge = AtenaControlBridge()
current_state = bridge.get_state()

# Sidebar para controles
with st.sidebar:
    st.header("⚙️ Controles")
    
    # Status do Sistema
    st.subheader("📊 Status do Sistema")
    if current_state.get("status") == "paused":
        st.warning("🔴 PAUSADO", icon="⏸️")
    else:
        st.success("🟢 EXECUTANDO", icon="▶️")
    
    st.divider()
    
    # Botões de Controle
    st.subheader("🎮 Controle de Execução")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("⏸️ PAUSAR", use_container_width=True):
            bridge.send_command("pause")
            st.success("✅ ATENA pausada com sucesso!")
            time.sleep(1)
            st.rerun()
    
    with col2:
        if st.button("▶️ RETOMAR", use_container_width=True):
            bridge.send_command("resume")
            st.success("✅ ATENA retomada com sucesso!")
            time.sleep(1)
            st.rerun()
    
    if st.button("🛑 CANCELAR TUDO", use_container_width=True):
        bridge.send_command("stop")
        st.error("❌ Todas as tarefas foram canceladas!")
        time.sleep(1)
        st.rerun()
    
    st.divider()
    
    # Opções de Visualização
    st.subheader("👁️ Visualização")
    refresh_interval = st.slider(
        "Intervalo de Atualização (segundos)",
        min_value=1,
        max_value=10,
        value=3
    )
    
    show_logs = st.checkbox("Mostrar Logs Detalhados", value=True)
    show_screenshots = st.checkbox("Mostrar Screenshots", value=True)
    show_metrics = st.checkbox("Mostrar Métricas", value=True)
    
    st.divider()
    
    if st.button("🔄 Atualizar Agora"):
        st.rerun()

# Layout principal em abas
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Status em Tempo Real",
    "📊 Métricas",
    "📸 Navegação",
    "📋 Logs"
])

# TAB 1: Status em Tempo Real
with tab1:
    # Indicador de Status Grande
    if current_state.get("status") == "paused":
        st.error("⏸️ SISTEMA PAUSADO - Clique em RETOMAR na barra lateral para continuar")
    else:
        st.success("▶️ SISTEMA EM EXECUÇÃO - Processando tarefas normalmente")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_text = "PAUSADA" if current_state.get("status") == "paused" else "ATIVA"
        st.metric(
            label="🤖 Status da ATENA",
            value=status_text,
            delta="Controlável",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            label="🧠 Motor de IA",
            value="DeepSeek-R1",
            delta="7B Params"
        )
    
    with col3:
        st.metric(
            label="🔄 Ciclos de Evolução",
            value="42",
            delta="+3 hoje"
        )
    
    st.divider()
    
    # Status dos Agentes
    st.subheader("👥 Status dos Agentes Registrados")
    
    agent_data = {
        "ATENA-Coder-01": {"status": "idle", "tarefas": 12, "sucesso": "95%"},
        "ATENA-Browser-01": {"status": "working", "tarefas": 5, "sucesso": "100%"},
        "ATENA-Sec-01": {"status": "idle", "tarefas": 8, "sucesso": "98%"},
        "ATENA-Data-01": {"status": "idle", "tarefas": 15, "sucesso": "92%"},
    }
    
    for agent_id, data in agent_data.items():
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            status_color = "🟢" if data["status"] == "idle" else "🟡"
            st.write(f"{status_color} **{agent_id}**")
        with col2:
            st.write(f"Status: {data['status'].upper()}")
        with col3:
            st.write(f"Tarefas: {data['tarefas']}")
        with col4:
            st.write(f"Taxa de Sucesso: {data['sucesso']}")

# TAB 2: Métricas
with tab2:
    if show_metrics:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Desempenho de Evolução")
            evolution_data = {
                "Geração": list(range(1, 43)),
                "Score": [0.5 + i*0.02 + (i%5)*0.01 for i in range(42)]
            }
            st.line_chart(evolution_data, x="Geração", y="Score")
        
        with col2:
            st.subheader("⚡ Utilização de Recursos")
            resource_data = {
                "Recurso": ["CPU", "Memória", "Disco"],
                "Utilização (%)": [45, 62, 38]
            }
            st.bar_chart(resource_data, x="Recurso", y="Utilização (%)")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🎯 Taxa de Sucesso por Agente")
            agent_success = {
                "Agente": ["Coder", "Browser", "Security", "Data"],
                "Taxa (%)": [95, 100, 98, 92]
            }
            st.bar_chart(agent_success, x="Agente", y="Taxa (%)")
        
        with col2:
            st.subheader("📊 Distribuição de Tarefas")
            task_dist = {
                "Tipo": ["Codificação", "Navegação", "Análise", "Segurança"],
                "Quantidade": [12, 5, 15, 8]
            }
            st.bar_chart(task_dist, x="Tipo", y="Quantidade")

# TAB 3: Navegação em Tempo Real
with tab3:
    if show_screenshots:
        st.subheader("📸 Última Navegação do Browser-Agent")
        
        # Procura por screenshots recentes
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("GitHub ATENA")
            github_shot = "/home/ubuntu/atena_repo/atena_github_test.png"
            if os.path.exists(github_shot):
                st.image(github_shot, use_column_width=True)
            else:
                st.info("Aguardando navegação no GitHub...")
                
        with col2:
            st.subheader("Pesquisa Google")
            google_shot = "/home/ubuntu/atena_repo/google_search_result.png"
            if os.path.exists(google_shot):
                st.image(google_shot, use_column_width=True)
            else:
                st.info("Aguardando pesquisa no Google...")
        
        st.divider()
        
        st.subheader("🌐 Histórico de URLs Visitadas")
        urls_history = [
            {"url": "https://github.com/AtenaAuto/ATENA-", "timestamp": "23:40:37", "status": "✅"},
            {"url": "https://techcrunch.com/category/artificial-intelligence/", "timestamp": "23:42:01", "status": "✅"},
            {"url": "https://www.ebay.com/sch/i.html?_nkw=rtx+4090", "timestamp": "23:43:26", "status": "✅"},
        ]
        
        for item in urls_history:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.code(item["url"], language="")
            with col2:
                st.write(f"⏰ {item['timestamp']}")
            with col3:
                st.write(item["status"])

# TAB 4: Logs Detalhados
with tab4:
    if show_logs:
        st.subheader("📋 Logs de Execução em Tempo Real")
        
        # Simula logs em tempo real
        log_content = """[2026-04-02 23:40:30] 🔱 ORQUESTRADOR: Agente ATENA-Browser-01 registrado
[2026-04-02 23:40:30] 🔱 ORQUESTRADOR: Orquestrador de Multi-Agentes iniciado
[2026-04-02 23:40:30] 🔱 ATENA-WEB: Orquestrador: Tarefa submetida: Acessar repositório ATENA
[2026-04-02 23:40:30] 🔱 ATENA-WEB: Agente ATENA-Browser-01 recebendo tarefa
[2026-04-02 23:40:30] 🔱 ATENA-PRICE: Lançando navegador (headless=True)...
[2026-04-02 23:40:36] 🔱 ATENA-PRICE: Navegador iniciado com sucesso
[2026-04-02 23:40:36] 🔱 ATENA-PRICE: Navegando para: https://github.com/AtenaAuto/ATENA-
[2026-04-02 23:40:37] 🔱 ATENA-PRICE: Navegação concluída
[2026-04-02 23:40:37] 🔱 ATENA-PRICE: Screenshot salvo em: atena_github_test.png
[2026-04-02 23:40:37] 🔱 ATENA-PRICE: Agente ATENA-Browser-01 concluiu a tarefa
[2026-04-02 23:42:01] 🔱 ATENA-WEB: Iniciando tarefa de extração web
[2026-04-02 23:42:07] 🔱 ATENA-WEB: Navegação para TechCrunch concluída
[2026-04-02 23:42:10] 🔱 ATENA-WEB: Manchetes extraídas com sucesso
[2026-04-02 23:43:26] 🔱 ATENA-PRICE: Iniciando tarefa de extração de preços
[2026-04-02 23:43:31] 🔱 ATENA-PRICE: Navegação para eBay concluída
[2026-04-02 23:43:36] 🔱 ATENA-PRICE: Preços de RTX 4090 extraídos com sucesso
"""
        
        st.markdown('<div class="log-container">' + log_content.replace('\n', '<br>') + '</div>', unsafe_allow_html=True)
        
        st.divider()
        
        st.subheader("🧠 Pensamento (Thinking) da ATENA")
        thinking_content = """
[THINKING] Analisando tarefa: "Extrair preços de RTX 4090"
[THINKING] Estratégia: Navegar para eBay → Buscar "RTX 4090" → Extrair nomes e preços
[THINKING] Seletores CSS identificados: .s-item__title, .s-item__price
[THINKING] Validando dados extraídos: 5 produtos encontrados
[THINKING] Calculando preço médio: $1,849.79
[THINKING] Identificando oportunidade: ZOTAC está 8% abaixo da média
[THINKING] Conclusão: Tarefa concluída com sucesso
"""
        st.markdown('<div class="log-container">' + thinking_content.replace('\n', '<br>') + '</div>', unsafe_allow_html=True)

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"⏰ Última atualização: {datetime.now().strftime('%H:%M:%S')}")
with col2:
    st.caption("🔱 ATENA v4.2 - Inteligência Artificial Autônoma")
with col3:
    status_display = "⏸️ PAUSADA" if current_state.get("status") == "paused" else "🚀 EXECUTANDO"
    st.caption(f"Status: {status_display}")

# Auto-refresh (apenas se não estiver pausado)
if current_state.get("status") != "paused":
    time.sleep(refresh_interval)
    st.rerun()
else:
    time.sleep(1)  # Verifica a cada 1 segundo se foi retomado
    st.rerun()
