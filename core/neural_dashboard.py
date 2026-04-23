#!/usr/bin/env python3
"""
Neural Dashboard - Interface de Visualização em Tempo Real da ATENA Ω
Mostra o fluxo de pensamento, evolução de scores e decisões do conselho.
"""

import streamlit as st
import sqlite3
import json
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path

# Configuração da página
st.set_page_config(page_title="ATENA Ω - Neural Dashboard", layout="wide", initial_sidebar_state="expanded")

# Título e descrição
st.markdown("# 🧠 ATENA Ω - Neural Dashboard")
st.markdown("*Interface de Visualização em Tempo Real da Inteligência Digital*")

# Sidebar para configurações
st.sidebar.markdown("## ⚙️ Configurações")
db_path = st.sidebar.text_input("Caminho do Banco de Dados", "atena_evolution/knowledge/knowledge.db")
refresh_interval = st.sidebar.slider("Intervalo de Atualização (segundos)", 5, 60, 10)

# Função para conectar ao banco de dados
def get_db_connection():
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Função para obter métricas de evolução
def get_evolution_metrics(limit=50):
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    try:
        query = "SELECT * FROM evolution_metrics ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        return df
    except Exception as e:
        st.warning(f"Tabela de evolução não encontrada: {e}")
        return pd.DataFrame()

# Função para obter estado atual
def get_current_state():
    state_file = Path("atena_evolution/atena_state.json")
    if state_file.exists():
        with open(state_file, 'r') as f:
            return json.load(f)
    return {}

# Seção 1: Status Atual
st.markdown("## 📊 Status Atual")
col1, col2, col3, col4 = st.columns(4)

state = get_current_state()
with col1:
    st.metric("Geração", state.get("generation", "N/A"))
with col2:
    st.metric("Melhor Score", f"{state.get('best_score', 0):.2f}")
with col3:
    st.metric("Timestamp", state.get("timestamp", "N/A")[:10])
with col4:
    st.metric("Modo CI", "Ativo" if state.get("is_ci") else "Inativo")

# Seção 2: Gráfico de Evolução do Score
st.markdown("## 📈 Evolução do Score")
metrics_df = get_evolution_metrics(100)

if not metrics_df.empty:
    # Preparar dados
    metrics_df['timestamp'] = pd.to_datetime(metrics_df['timestamp'])
    metrics_df = metrics_df.sort_values('timestamp')
    
    # Gráfico de linha
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=metrics_df['timestamp'],
        y=metrics_df['new_score'],
        mode='lines+markers',
        name='Score',
        line=dict(color='#00D9FF', width=2),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title="Score ao Longo das Gerações",
        xaxis_title="Tempo",
        yaxis_title="Score",
        hovermode='x unified',
        template='plotly_dark'
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhuma métrica de evolução disponível ainda.")

# Seção 3: Tipos de Mutações
st.markdown("## 🧬 Distribuição de Mutações")
if not metrics_df.empty:
    mutation_counts = metrics_df['mutation'].value_counts().head(10)
    
    fig = go.Figure(data=[
        go.Bar(x=mutation_counts.index, y=mutation_counts.values, marker_color='#FF006E')
    ])
    fig.update_layout(
        title="Top 10 Tipos de Mutações",
        xaxis_title="Tipo de Mutação",
        yaxis_title="Frequência",
        template='plotly_dark'
    )
    st.plotly_chart(fig, use_container_width=True)

# Seção 4: Histórico Recente
st.markdown("## 📋 Histórico Recente (Últimas 10 Gerações)")
if not metrics_df.empty:
    recent = metrics_df.head(10)[['timestamp', 'generation', 'mutation', 'new_score']].copy()
    recent.columns = ['Timestamp', 'Geração', 'Mutação', 'Score']
    st.dataframe(recent, use_container_width=True)
else:
    st.info("Nenhum histórico disponível.")

# Rodapé
st.markdown("---")
st.markdown(f"*Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
st.markdown("*ATENA Ω - Inteligência Digital Evolutiva*")
