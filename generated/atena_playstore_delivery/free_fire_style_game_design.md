# Projeto: ATENA Battle Royale 3D (estilo Free Fire) — Play Store

## 1) Visão do Produto
- **Nome provisório:** Atena Firezone
- **Plataforma:** Android (Play Store)
- **Engine recomendada:** Unity 6 LTS + URP
- **Modo principal:** Battle Royale 50 jogadores
- **Meta de sessão:** 10–15 minutos por partida

## 2) Arquitetura Técnica
- **Cliente móvel (Unity/C#)**
  - Módulos: login, matchmaking, inventário, loja, HUD, replay.
- **Backend (FastAPI + Redis + PostgreSQL)**
  - Serviços: auth, profile, matchmaking, leaderboard, anti-cheat signals.
- **Tempo real**
  - Photon Fusion/Quantum ou alternativa dedicada (Nakama + UDP relay).
- **Observabilidade**
  - OpenTelemetry + Prometheus + Grafana.

## 3) Sistemas de Jogo
1. **Loop Battle Royale**
   - Lobby -> avião -> queda -> loot -> zona segura -> fim.
2. **Combate**
   - Hitscan e projétil; recoil; balística simples.
3. **Movimentação**
   - Corrida, agachar, pular, deslizar, escalada leve.
4. **Inventário**
   - Armas primária/secundária, consumíveis, granadas.
5. **Progressão**
   - Passe de temporada, missões diárias, ranking.

## 4) Pipeline de Produção
- Pré-produção (4 semanas): GDD, protótipo jogável, netcode spike.
- Produção Alpha (8 semanas): mapa 1, armas base, matchmaking.
- Beta fechado (6 semanas): telemetria, balanceamento, monetização.
- Lançamento soft (4 semanas): 1 país, retenção D1/D7.
- Lançamento global: estabilidade e UA escalável.

## 5) Monetização e Compliance
- IAP cosméticos, battle pass, bundles.
- Sem pay-to-win em stats de armas.
- LGPD/GDPR + Play Data Safety + classificação indicativa.

## 6) Entregáveis Play Store
- APK/AAB assinado.
- Feature graphic, screenshots, ícone 512x512.
- Política de privacidade e termos.
- Checklist QA (FPS, crash-free, ANR, aquecimento).

## 7) Backlog Técnico Inicial (Sprint 1)
- [ ] Base project Unity URP Android.
- [ ] Input mobile + câmera TPS.
- [ ] Protótipo de tiro + loot.
- [ ] API auth/profile + JWT.
- [ ] Matchmaking básico + sala de 10 bots.
- [ ] Telemetria de eventos chave.

## 8) Prompt operacional para ATENA
"Crie os módulos do cliente Unity e backend FastAPI para um battle royale mobile 3D com foco em 60 FPS em aparelhos médios, incluindo plano de otimização, anti-cheat por heurística, e roteiro de publicação Play Store com ASO."
