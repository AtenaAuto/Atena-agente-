#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão para criar plano de lançamento profissional da ATENA."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EVOLUTION = ROOT / "atena_evolution"


def _date_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _build_launch_markdown(product_name: str, target_segment: str, pilot_count: int) -> str:
    return f"""# Plano de Lançamento Profissional — {product_name}

Data: {_date_today()}

## Objetivo
Posicionar a {product_name} para adoção profissional no segmento **{target_segment}** com foco em previsibilidade operacional, segurança e ROI claro.

## Oferta recomendada (empacotamento)
1. **Starter** — onboarding guiado + doctor/guardian + playbook inicial.
2. **Team** — telemetria consolidada, rotinas operacionais e métricas semanais.
3. **Enterprise** — hardening, trilha de auditoria e suporte com SLA.

## Entregáveis de produto
- Comando dedicado de planejamento comercial/técnico.
- Kit de adoção com checklist de go-live.
- Documentação de uso e fluxo de validação em produção.

## Plano de execução (30 dias)
### Semana 1 — Fundamentos
- Definir ICP e proposta de valor principal.
- Padronizar onboarding com validação mínima (`doctor`, `guardian`, `production-ready`).
- Preparar demo técnica curta.

### Semana 2 — Prova de valor
- Rodar pilotos controlados.
- Coletar métricas de tempo economizado, falhas evitadas e velocidade de entrega.
- Consolidar depoimentos técnicos.

### Semana 3 — Operação e segurança
- Publicar política de logs e checklist de segurança.
- Fechar runbook para incidentes e rollback.
- Definir critérios objetivos de pronto para venda.

### Semana 4 — Lançamento
- Publicar landing page e estudos de caso.
- Rodar campanha com CTA para diagnóstico.
- Converter pelo menos {pilot_count} pilotos em uso recorrente.

## Métricas de sucesso
- Taxa de ativação (T+7 dias) > 70%.
- Tempo médio de onboarding < 1 dia.
- Redução de falhas em pré-release > 40%.
- Conversão de piloto para uso recorrente >= 30%.

## Próximos comandos ATENA
```bash
./atena doctor
./atena guardian
./atena production-ready
./atena professional-launch --segment "{target_segment}" --pilots {pilot_count}
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Professional Launch Mission")
    parser.add_argument("--product", default="ATENA Ω", help="Nome do produto")
    parser.add_argument("--segment", default="times de engenharia de software", help="Segmento-alvo")
    parser.add_argument("--pilots", type=int, default=3, help="Quantidade de pilotos-alvo")
    args = parser.parse_args()

    DOCS.mkdir(parents=True, exist_ok=True)
    EVOLUTION.mkdir(parents=True, exist_ok=True)

    date_str = _date_today()
    ts = _timestamp()

    md_path = DOCS / f"PROFESSIONAL_LAUNCH_PLAN_{date_str}.md"
    json_path = EVOLUTION / f"professional_launch_plan_{ts}.json"

    content = _build_launch_markdown(args.product, args.segment, args.pilots)
    md_path.write_text(content, encoding="utf-8")

    payload = {
        "status": "ok",
        "product": args.product,
        "segment": args.segment,
        "pilot_target": args.pilots,
        "doc_path": str(md_path),
        "timestamp": ts,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🚀 ATENA Professional Launch Mission")
    print("Status: ok")
    print(f"Produto: {args.product}")
    print(f"Segmento: {args.segment}")
    print(f"Pilotos-alvo: {args.pilots}")
    print(f"Plano: {md_path}")
    print(f"Artefato: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
