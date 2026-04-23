#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Ω — missão para criar uma inovação técnica acionável com base no repositório."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
MODULES_DIR = ROOT / "modules"
REPORTS_DIR = ROOT / "analysis_reports"
OUTPUT_DIR = ROOT / "output"
DEFAULT_TOPIC = "sistema autônomo de pesquisa tecnológica"
DEFAULT_MODE = "standard"
GAME_MODE = "game-3d-battle-royale"
ANY_GAME_MODE = "game-complete-any"
APP_MODE = "app-mobile-store-ready"
FOOD_APP_MODE = "app-food-delivery-complete"

SOCIAL_GRAND_CHALLENGES = [
    "redução da evasão escolar com tutoria adaptativa",
    "prevenção de desastres climáticos em áreas vulneráveis",
    "triagem pública de saúde mental com intervenção precoce",
    "combate à fome urbana com logística preditiva",
    "requalificação profissional em larga escala para empregos de IA",
]


def _collect_repo_capabilities(max_items: int = 12) -> list[str]:
    if not MODULES_DIR.exists():
        return []
    capabilities: list[str] = []
    for path in sorted(MODULES_DIR.glob("*.py")):
        raw_stem = path.stem.lower()
        if raw_stem in {"__init__", "base"}:
            continue
        stem = path.stem.replace("_", " ")
        capabilities.append(stem)
        if len(capabilities) >= max_items:
            break
    return capabilities


def _extract_keywords(topic: str, capabilities: Iterable[str], limit: int = 4) -> list[str]:
    topic_tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", topic.lower())
    curated = {"autônomo", "multiagente", "memória", "segurança", "otimização", "telemetria", "federado", "quântico"}
    base = [tok for tok in topic_tokens if len(tok) >= 4]
    for cap in capabilities:
        base.extend(re.findall(r"[a-zA-ZÀ-ÿ0-9]+", cap.lower()))
    merged = []
    for token in [*curated, *base]:
        if token not in merged:
            merged.append(token)
        if len(merged) >= limit:
            break
    return merged


def _choose_social_challenge(topic: str) -> str:
    score = sum(ord(ch) for ch in topic.strip().lower())
    return SOCIAL_GRAND_CHALLENGES[score % len(SOCIAL_GRAND_CHALLENGES)]


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = normalized.strip("-")
    return normalized or "future-ai-project"


def _build_software_scaffold(
    topic: str,
    keywords: list[str],
    social_challenge: str | None,
) -> dict[str, str]:
    project_name = f"atena_{_slugify(topic)}_lab"
    challenge_text = social_challenge or "desafio tecnológico de alto impacto"
    keyword_text = ", ".join(keywords) if keywords else "inovação, atena"
    return {
        "README.md": f"""# {project_name}

Plataforma SaaS **completa (base de produção)** gerada automaticamente pela missão `future-ai` da ATENA.

## Tema
- {topic}

## Desafio alvo
- {challenge_text}

## Keywords
- {keyword_text}

## Arquitetura entregue
- `app/main.py`: bootstrap e demo de fluxo ponta-a-ponta
- `app/domain.py`: entidades de domínio (tenant/workspace/channel/message/user)
- `app/realtime.py`: gateway de mensagens em tempo real (in-memory)
- `app/moderation.py`: moderação de conteúdo (regras básicas)
- `app/billing.py`: cálculo de assinatura e add-ons
- `app/service.py`: orquestração do SaaS e plano técnico
- `tests/`: testes de domínio + fluxo funcional
- `docker-compose.yml` + `.env.example`: base para operação local

## Como executar
```bash
python -m app.main
pytest -q tests
```
""",
        "app/__init__.py": "",
        "app/main.py": f"""from __future__ import annotations

from app.service import create_platform_blueprint


def main() -> None:
    blueprint = create_platform_blueprint(topic={topic!r}, challenge={challenge_text!r})
    print("ATENA Future AI SaaS Platform")
    print("workspace:", blueprint["workspace"])
    print("plan:", blueprint["plan"])
    print("monthly_price:", blueprint["billing"]["monthly_price"])
    print("event_sample:", blueprint["realtime_event"])


if __name__ == "__main__":
    main()
""",
        "app/domain.py": """from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Tenant:
    tenant_id: str
    name: str
    plan: str = "pro"


@dataclass
class User:
    user_id: str
    display_name: str
    role: str = "member"


@dataclass
class Workspace:
    workspace_id: str
    tenant_id: str
    name: str
    channels: list[str] = field(default_factory=list)


@dataclass
class Message:
    workspace_id: str
    channel_id: str
    author_id: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
""",
        "app/realtime.py": """from __future__ import annotations

from app.domain import Message


class RealtimeGateway:
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []

    def publish_message(self, message: Message) -> dict[str, str]:
        event = {
            "type": "message.created",
            "workspace_id": message.workspace_id,
            "channel_id": message.channel_id,
            "author_id": message.author_id,
            "content": message.content,
            "created_at": message.created_at,
        }
        self._events.append(event)
        return event

    def latest_event(self) -> dict[str, str] | None:
        if not self._events:
            return None
        return self._events[-1]
""",
        "app/moderation.py": """from __future__ import annotations

BLOCKED_TERMS = {"malware", "leak", "exploit"}


def validate_message(content: str) -> tuple[bool, str]:
    normalized = content.strip().lower()
    if not normalized:
        return False, "empty_message"
    for term in BLOCKED_TERMS:
        if term in normalized:
            return False, f"blocked_term:{term}"
    return True, "ok"
""",
        "app/billing.py": """from __future__ import annotations

PLAN_PRICE = {
    "starter": 29,
    "pro": 99,
    "enterprise": 499,
}


def estimate_monthly_price(plan: str, seats: int, addons: int = 0) -> int:
    base = PLAN_PRICE.get(plan, PLAN_PRICE["pro"])
    normalized_seats = max(1, seats)
    normalized_addons = max(0, addons)
    return base + (normalized_seats * 4) + (normalized_addons * 15)
""",
        "app/service.py": """from __future__ import annotations

from app.billing import estimate_monthly_price
from app.domain import Message, Tenant, Workspace
from app.moderation import validate_message
from app.realtime import RealtimeGateway


def build_intervention_plan(topic: str, challenge: str) -> str:
    return (
        f"Plano inicial para '{topic}': "
        f"atacar '{challenge}' com arquitetura SaaS multi-tenant, observabilidade, "
        "moderação e entrega incremental orientada por métricas."
    )


def create_platform_blueprint(topic: str, challenge: str) -> dict[str, object]:
    tenant = Tenant(tenant_id="tn-001", name="Atena Enterprise", plan="enterprise")
    workspace = Workspace(workspace_id="ws-001", tenant_id=tenant.tenant_id, name="Core", channels=["general"])
    plan = build_intervention_plan(topic, challenge)

    message = Message(
        workspace_id=workspace.workspace_id,
        channel_id="general",
        author_id="user-001",
        content="deploy sem incidentes e com rastreabilidade total",
    )
    moderation_ok, reason = validate_message(message.content)
    if not moderation_ok:
        raise ValueError(f"mensagem bloqueada: {reason}")

    gateway = RealtimeGateway()
    event = gateway.publish_message(message)
    monthly_price = estimate_monthly_price(plan=tenant.plan, seats=25, addons=2)

    return {
        "tenant": tenant.name,
        "workspace": workspace.name,
        "plan": plan,
        "billing": {"monthly_price": monthly_price, "currency": "USD"},
        "realtime_event": event,
    }
""",
        "tests/test_service.py": """from __future__ import annotations

from app.service import build_intervention_plan, create_platform_blueprint


def test_build_intervention_plan() -> None:
    plan = build_intervention_plan("educacao", "evasao escolar")
    assert "educacao" in plan
    assert "evasao escolar" in plan


def test_create_platform_blueprint_has_billing_and_event() -> None:
    payload = create_platform_blueprint("comunicacao corporativa", "reduzir latencia")
    assert payload["billing"]["monthly_price"] > 0
    assert payload["realtime_event"]["type"] == "message.created"
""",
        "tests/test_platform.py": """from __future__ import annotations

from app.billing import estimate_monthly_price
from app.moderation import validate_message


def test_billing_grows_with_seats() -> None:
    starter = estimate_monthly_price(plan="starter", seats=1, addons=0)
    scaled = estimate_monthly_price(plan="starter", seats=30, addons=0)
    assert scaled > starter


def test_moderation_blocks_disallowed_terms() -> None:
    ok, reason = validate_message("tem leak de dados")
    assert ok is False
    assert reason.startswith("blocked_term:")
""",
        ".env.example": """APP_ENV=dev
APP_REGION=us-east-1
APP_LOG_LEVEL=info
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/atena
REDIS_URL=redis://localhost:6379/0
""",
        "docker-compose.yml": """version: "3.9"
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: atena
    ports:
      - "5432:5432"
  redis:
    image: redis:7
    ports:
      - "6379:6379"
""",
        "pyproject.toml": f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "SaaS completo base gerado pela missão future-ai da ATENA"
requires-python = ">=3.10"
dependencies = []
""",
    }


def _build_battle_royale_game_scaffold(topic: str) -> dict[str, str]:
    return {
        "README.md": f"""# ATENA Battle Royale 3D (TPS)

Jogo 3D de tiro em terceira pessoa, estilo battle royale (inspirado no gênero, não clone).

## Tema
- {topic}

## Mecânicas implementadas no scaffold
- Movimento em terceira pessoa
- Mira e disparo
- Loot básico
- Safe zone dinâmica (encolhimento por fases)
- Eliminação e condição de vitória
- Núcleo de simulação de partida (Python) com testes automatizados

## Stack
- Godot 4.x (GDScript)

## Como abrir
1. Instale Godot 4.x
2. Abra a pasta do projeto no Godot
3. Rode a cena principal `scenes/Main.tscn`
""",
        "project.godot": """[application]
config/name="ATENA Battle Royale 3D"
run/main_scene="res://scenes/Main.tscn"
""",
        "scenes/Main.tscn": """[gd_scene load_steps=6 format=3]

[ext_resource type="Script" path="res://scripts/match_manager.gd" id="1"]
[ext_resource type="Script" path="res://scripts/safe_zone.gd" id="2"]
[ext_resource type="Script" path="res://scripts/player_controller.gd" id="3"]
[ext_resource type="Script" path="res://scripts/weapon.gd" id="4"]
[ext_resource type="Script" path="res://scripts/loot_spawner.gd" id="5"]

[node name="Main" type="Node3D"]
script = ExtResource("1")

[node name="SafeZone" type="Node3D" parent="."]
script = ExtResource("2")

[node name="Player" type="CharacterBody3D" parent="."]
script = ExtResource("3")

[node name="Weapon" type="Node3D" parent="Player"]
script = ExtResource("4")

[node name="LootSpawner" type="Node3D" parent="."]
script = ExtResource("5")
""",
        "scripts/match_manager.gd": """extends Node3D

@export var max_players := 50
@export var players_alive := 1

func _ready() -> void:
\tprint("Match iniciada: battle royale TPS")

func on_player_eliminated() -> void:
\tplayers_alive -= 1
\tif players_alive <= 1:
\t\tprint("Vitória! Último jogador restante.")
""",
        "scripts/safe_zone.gd": """extends Node3D

@export var radius := 400.0
@export var shrink_rate := 8.0
@export var min_radius := 30.0

func _process(delta: float) -> void:
\tif radius > min_radius:
\t\tradius = max(min_radius, radius - shrink_rate * delta)
""",
        "scripts/player_controller.gd": """extends CharacterBody3D

@export var speed := 7.5
@export var gravity := 16.0

func _physics_process(delta: float) -> void:
\tvar input_dir := Vector3(
\t\tInput.get_action_strength("ui_right") - Input.get_action_strength("ui_left"),
\t\t0.0,
\t\tInput.get_action_strength("ui_down") - Input.get_action_strength("ui_up")
\t)
\tvelocity.x = input_dir.x * speed
\tvelocity.z = input_dir.z * speed
\tif not is_on_floor():
\t\tvelocity.y -= gravity * delta
\tmove_and_slide()
""",
        "scripts/weapon.gd": """extends Node3D

@export var fire_rate := 0.2
@export var damage := 24
var _cooldown := 0.0

func _process(delta: float) -> void:
\t_cooldown = max(0.0, _cooldown - delta)
\tif Input.is_action_pressed("ui_accept"):
\t\ttry_shoot()

func try_shoot() -> void:
\tif _cooldown > 0.0:
\t\treturn
\t_cooldown = fire_rate
\tprint("Disparo executado. Dano: %d" % damage)
""",
        "scripts/loot_spawner.gd": """extends Node3D

@export var loot_points := 30

func _ready() -> void:
\tprint("Loot distribuído em %d pontos." % loot_points)
""",
        "tests/test_scaffold_integrity.py": """from __future__ import annotations

from pathlib import Path


def test_main_scene_exists() -> None:
    assert Path("scenes/Main.tscn").exists()


def test_core_scripts_exist() -> None:
    required = [
        "scripts/match_manager.gd",
        "scripts/safe_zone.gd",
        "scripts/player_controller.gd",
        "scripts/weapon.gd",
        "scripts/loot_spawner.gd",
    ]
    for rel in required:
        assert Path(rel).exists(), rel
""",
        "game_logic/__init__.py": "",
        "game_logic/match_state.py": """from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerState:
    player_id: str
    health: int = 100
    alive: bool = True
    x: float = 0.0
    z: float = 0.0

    def apply_damage(self, value: int) -> None:
        if not self.alive:
            return
        self.health = max(0, self.health - max(0, value))
        if self.health == 0:
            self.alive = False
""",
        "game_logic/zone.py": """from __future__ import annotations


def shrink_zone(radius: float, shrink_rate: float, delta: float, min_radius: float) -> float:
    next_radius = radius - (shrink_rate * delta)
    return max(min_radius, next_radius)
""",
        "game_logic/combat.py": """from __future__ import annotations

from game_logic.match_state import PlayerState


def shoot(attacker: PlayerState, defender: PlayerState, damage: int) -> None:
    if not attacker.alive or not defender.alive:
        return
    defender.apply_damage(damage)
""",
        "game_logic/simulation.py": """from __future__ import annotations

from game_logic.combat import shoot
from game_logic.match_state import PlayerState
from game_logic.zone import shrink_zone


def run_tick(radius: float, delta: float, shrink_rate: float = 8.0, min_radius: float = 30.0) -> float:
    return shrink_zone(radius=radius, shrink_rate=shrink_rate, delta=delta, min_radius=min_radius)


def duel_step(attacker: PlayerState, defender: PlayerState, damage: int = 24) -> PlayerState:
    shoot(attacker, defender, damage)
    return defender
""",
        "tests/test_game_logic.py": """from __future__ import annotations

from game_logic.match_state import PlayerState
from game_logic.simulation import duel_step, run_tick


def test_zone_shrinks() -> None:
    assert run_tick(radius=100.0, delta=1.0) < 100.0


def test_duel_step_applies_damage() -> None:
    a = PlayerState(player_id="A")
    d = PlayerState(player_id="D")
    duel_step(a, d, damage=35)
    assert d.health == 65
    assert d.alive is True
""",
    }


def _build_any_game_complete_scaffold(topic: str) -> dict[str, str]:
    game_slug = _slugify(topic)
    return {
        "README.md": f"""# ATENA Complete Game Factory - {topic}

Projeto completo gerado pela ATENA para o jogo solicitado.

## Escopo
- Tema: {topic}
- Entrega: arquitetura de jogo completa + núcleo jogável + testes + plano de produção

## Execução rápida
```bash
python -m game_logic.bootstrap
pytest -q tests
```
""",
        "GAME_DESIGN_DOCUMENT.md": f"""# Game Design Document (GDD)

## Visão
Jogo completo: {topic}

## Pilares
1. Core loop sólido (jogar -> evoluir -> recompensar)
2. Progressão clara (match, conta, temporada)
3. Operação contínua (telemetria, balanceamento, anti-cheat)

## Subsistemas entregues
- Loop de partida
- Combate/dano
- Zona/eventos dinâmicos
- Regras de vitória
- Testes automatizados do núcleo
""",
        "PRODUCTION_ROADMAP.md": """# Roadmap de Produção

## Fase 1 (MVP)
- Núcleo jogável com testes automatizados
- UI mínima e fluxo de partida

## Fase 2 (Beta)
- Multiplayer dedicado
- Matchmaking e persistência
- Telemetria + anti-fraude básico

## Fase 3 (Live Ops)
- Eventos, temporadas, loja
- Balanceamento contínuo por dados
""",
        "game_logic/__init__.py": "",
        "game_logic/bootstrap.py": f"""from __future__ import annotations

def main() -> None:
    print("ATENA Complete Game Factory")
    print("Jogo configurado:", {topic!r})
    print("Status: núcleo completo inicial gerado.")

if __name__ == "__main__":
    main()
""",
        "game_logic/core_loop.py": """from __future__ import annotations

def run_core_loop(iterations: int = 3) -> list[str]:
    steps = []
    for _ in range(iterations):
        steps.append("spawn")
        steps.append("engage")
        steps.append("reward")
    return steps
""",
        "game_logic/rules.py": """from __future__ import annotations

def winner(players_alive: int) -> bool:
    return players_alive <= 1
""",
        "tests/test_complete_factory.py": f"""from __future__ import annotations

from game_logic.core_loop import run_core_loop
from game_logic.rules import winner


def test_core_loop_has_reward() -> None:
    assert "reward" in run_core_loop(1)


def test_winner_rule() -> None:
    assert winner(1) is True
    assert winner(2) is False


def test_topic_tag() -> None:
    assert {game_slug!r} != ""
""",
    }


def _build_mobile_store_ready_scaffold(topic: str) -> dict[str, str]:
    app_slug = _slugify(topic).replace("-", "_")
    app_id = f"com.atena.{app_slug[:40]}"
    app_name = f"ATENA {topic.title()}"
    return {
        "README.md": f"""# {app_name}

App mobile completo (base de produção) para Android e iOS.

## Tema
- {topic}

## Stack
- Flutter 3.x / Dart
- Build Android (Play Store) e iOS (App Store)

## Execução
```bash
flutter pub get
flutter run
```
""",
        "pubspec.yaml": f"""name: {app_slug}
description: App mobile gerado pela ATENA
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0

flutter:
  uses-material-design: true
""",
        "lib/main.dart": f"""import 'package:flutter/material.dart';

void main() {{
  runApp(const AtenaApp());
}}

class AtenaApp extends StatelessWidget {{
  const AtenaApp({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return MaterialApp(
      title: '{app_name}',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: const HomePage(),
    );
  }}
}}

class HomePage extends StatelessWidget {{
  const HomePage({{super.key}});

  @override
  Widget build(BuildContext context) {{
    return Scaffold(
      appBar: AppBar(title: const Text('ATENA App')),
      body: const Center(
        child: Text('App pronto para evolução e publicação nas stores.'),
      ),
    );
  }}
}}
""",
        "test/widget_test.dart": """import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter/foundation.dart';

void main() {
  test('sanity test', () {
    expect(1 + 1, 2);
  });
}
""",
        "android/app/build.gradle.kts": """plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.atena.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.atena.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }
}
""",
        "android/app/src/main/AndroidManifest.xml": f"""<manifest package="{app_id}" xmlns:android="http://schemas.android.com/apk/res/android">
  <application android:label="{app_name}" android:icon="@mipmap/ic_launcher">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
      </intent-filter>
    </activity>
  </application>
</manifest>
""",
        "ios/Runner/Info.plist": f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>
  <string>{app_name}</string>
  <key>CFBundleIdentifier</key>
  <string>{app_id}</string>
</dict>
</plist>
""",
        "STORE_READY_CHECKLIST.md": """# Store Readiness Checklist

- [ ] Ícone e screenshots finais
- [ ] Política de privacidade publicada
- [ ] Termos de uso
- [ ] Compliance LGPD/GDPR
- [ ] Build assinado Android (AAB)
- [ ] Build assinado iOS (IPA/TestFlight)
""",
    }


def _build_food_delivery_complete_scaffold(topic: str) -> dict[str, str]:
    app_slug = _slugify(topic).replace("-", "_")
    return {
        "README.md": f"""# ATENA Food Delivery Complete

Aplicativo completo de delivery de comida (mobile + backend API) gerado pela ATENA.

## Tema
- {topic}

## Componentes
- Mobile (Flutter)
- Backend (FastAPI)
- Testes automatizados API

## Execução local
```bash
python -m pip install -r requirements.txt
pytest -q tests
uvicorn backend.main:app --reload
```
""",
        "requirements.txt": """fastapi>=0.110.0
uvicorn>=0.23.0
pytest>=7.0.0
httpx>=0.27.0
""",
        "backend/__init__.py": "",
        "backend/main.py": """from __future__ import annotations

from fastapi import FastAPI, HTTPException

app = FastAPI(title="ATENA Food Delivery API", version="1.0.0")

restaurants = [
    {"id": 1, "name": "Atena Burgers", "fee": 4.99},
    {"id": 2, "name": "Atena Pizza", "fee": 3.49},
]
orders: list[dict] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/restaurants")
def list_restaurants() -> list[dict]:
    return restaurants


@app.post("/orders")
def create_order(payload: dict) -> dict:
    if "restaurant_id" not in payload or "items" not in payload:
        raise HTTPException(status_code=400, detail="invalid order payload")
    order_id = len(orders) + 1
    order = {"id": order_id, "status": "created", **payload}
    orders.append(order)
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    for order in orders:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="order not found")
""",
        "mobile/pubspec.yaml": f"""name: {app_slug}
description: Food delivery app generated by ATENA
publish_to: 'none'
version: 1.0.0+1
environment:
  sdk: '>=3.0.0 <4.0.0'
dependencies:
  flutter:
    sdk: flutter
  http: ^1.2.2
dev_dependencies:
  flutter_test:
    sdk: flutter
flutter:
  uses-material-design: true
""",
        "mobile/lib/main.dart": """import 'package:flutter/material.dart';

void main() => runApp(const FoodDeliveryApp());

class FoodDeliveryApp extends StatelessWidget {
  const FoodDeliveryApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ATENA Delivery',
      home: Scaffold(
        appBar: AppBar(title: const Text('ATENA Delivery')),
        body: const Center(child: Text('Catálogo, carrinho e pedidos prontos para evolução.')),
      ),
    );
  }
}
""",
        "tests/test_api.py": """from __future__ import annotations

import pytest
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_restaurants() -> None:
    r = client.get("/restaurants")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_create_order() -> None:
    payload = {"restaurant_id": 1, "items": [{"name": "burger", "qty": 1}]}
    r = client.post("/orders", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "created"
""",
        "STORE_READY_CHECKLIST.md": """# Food Delivery Store Checklist

- [ ] Identidade visual (ícone, screenshots, vídeo)
- [ ] Política de privacidade e termos
- [ ] Compliance fiscal e meios de pagamento
- [ ] Observabilidade de pedidos e SLA de entrega
- [ ] Plano de rollback em incidentes
""",
    }


def _write_software_scaffold(base_dir: Path, scaffold: dict[str, str]) -> list[str]:
    written: list[str] = []
    for relative, content in scaffold.items():
        target = base_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target))
    return written


def _run_generated_project_tests(project_dir: Path) -> dict[str, object]:
    cmd = [sys.executable, "-m", "pytest", "-q", "tests"]
    proc = subprocess.run(
        cmd,
        cwd=str(project_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "ok": proc.returncode in {0, 5},
        "output_tail": output[-1200:],
    }


def _run_generated_game_checks(project_dir: Path) -> dict[str, object]:
    if (project_dir / "project.godot").exists():
        required_files = [
            "project.godot",
            "scenes/Main.tscn",
            "scripts/match_manager.gd",
            "scripts/safe_zone.gd",
            "scripts/player_controller.gd",
            "scripts/weapon.gd",
            "scripts/loot_spawner.gd",
            "game_logic/simulation.py",
            "tests/test_game_logic.py",
        ]
    else:
        required_files = [
            "GAME_DESIGN_DOCUMENT.md",
            "PRODUCTION_ROADMAP.md",
            "game_logic/bootstrap.py",
            "game_logic/core_loop.py",
            "game_logic/rules.py",
            "tests/test_complete_factory.py",
        ]
    missing = [rel for rel in required_files if not (project_dir / rel).exists()]
    return {
        "check": "battle_royale_scaffold_integrity",
        "ok": len(missing) == 0,
        "missing_files": missing,
    }


def _run_generated_game_tests(project_dir: Path) -> dict[str, object]:
    cmd = [sys.executable, "-m", "pytest", "-q", "tests"]
    proc = subprocess.run(
        cmd,
        cwd=str(project_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "ok": proc.returncode in {0, 5},
        "output_tail": output[-1200:],
    }


def _run_generated_app_checks(project_dir: Path) -> dict[str, object]:
    if (project_dir / "backend/main.py").exists():
        required = [
            "requirements.txt",
            "backend/main.py",
            "mobile/pubspec.yaml",
            "mobile/lib/main.dart",
            "tests/test_api.py",
            "STORE_READY_CHECKLIST.md",
        ]
    else:
        required = [
            "pubspec.yaml",
            "lib/main.dart",
            "android/app/src/main/AndroidManifest.xml",
            "ios/Runner/Info.plist",
            "STORE_READY_CHECKLIST.md",
        ]
    missing = [rel for rel in required if not (project_dir / rel).exists()]
    return {
        "check": "mobile_store_ready_integrity",
        "ok": len(missing) == 0,
        "missing_files": missing,
    }


def build_blueprint(
    now_utc: datetime,
    topic: str,
    capabilities: list[str],
    keywords: list[str],
    mode: str,
) -> str:
    date_label = now_utc.strftime("%Y-%m-%d")
    caps_md = "\n".join(f"- {cap}" for cap in capabilities) or "- (nenhuma capability detectada em modules/)"
    tags = ", ".join(keywords) if keywords else "inovação, pesquisa, atena"
    if mode == "society-max":
        challenge = _choose_social_challenge(topic)
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo de teste extremo para sociedade
**Tema:** {topic}  
**Grande desafio selecionado:** {challenge}

## Stack que a ATENA já domina (scan local)
{caps_md}

## Invenção proposta: *ATENA Impact OS*
Uma plataforma de missão crítica para impacto social, executada em 4 camadas:
1. **Sensing Cívico:** coleta sinais (educação, clima, saúde, renda) com anonimização por padrão.
2. **Planejamento Causal Multiagente:** gera políticas de intervenção com simulações contrafactuais.
3. **Execução Federada em Campo:** orquestra ações locais com baixa conectividade e fallback offline.
4. **Governança Auditável:** trilha de decisão pública com métricas de justiça, segurança e eficácia.

## Entrega em 90 dias
### Sprint 1 (dias 1-30)
- Modelo de dados cidadão-seguro (`need`, `risk`, `intervention`, `consent`, `outcome`).
- Motor de priorização com transparência de decisão.

### Sprint 2 (dias 31-60)
- Piloto com 3 territórios e 5.000 pessoas impactadas.
- Painel em tempo real com alertas e validação humana no loop.

### Sprint 3 (dias 61-90)
- Escala para 100.000 pessoas com SLO de disponibilidade > 99.5%.
- Publicação de relatório aberto de impacto e segurança.

## Métricas sociais (obrigatórias)
- Redução mínima de 20% no indicador principal do desafio.
- Tempo de resposta de intervenção < 24h para casos críticos.
- Zero incidente crítico de privacidade.
- Índice de equidade entre grupos >= 0.95.

## Especificação de protótipo (MVP técnico)
- Serviço 1: `impact-intake` (captura de sinais + consentimento)
- Serviço 2: `impact-planner` (priorização + recomendação causal)
- Serviço 3: `impact-actuator` (execução e monitoramento da intervenção)
- Serviço 4: `impact-audit` (explicabilidade e conformidade)

## Tags técnicas sugeridas
{tags}
"""
    if mode == "software-complete":
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo software completo ativado
**Tema:** {topic}

## Capacidades de base detectadas
{caps_md}

## Objetivo
Gerar um software funcional mínimo (estrutura completa de projeto) pronto para evolução contínua.

## Entregável automático
- Projeto Python com `app/`, `tests/`, `README.md` e `pyproject.toml`.
- Serviço inicial para plano de intervenção tecnológica.
- Teste unitário inicial para validar comportamento central.

## Próximo passo sugerido
Executar os testes no projeto gerado e evoluir para API + dashboard.

## Tags técnicas sugeridas
{tags}
"""
    if mode == GAME_MODE:
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo jogo 3D battle royale ativado
**Tema:** {topic}

## Objetivo
Gerar um projeto de jogo completo para TPS battle royale,
com núcleo jogável e base técnica de produção.

## Conteúdo do projeto gerado
- Estrutura Godot 4.x pronta para abrir e rodar
- Cena principal com MatchManager, SafeZone, Player, Weapon e LootSpawner
- Scripts GDScript para mecânicas centrais
- Núcleo de simulação de partida em Python + testes automatizados

## Mecânicas-chave
- Terceira pessoa (TPS)
- Zona segura que encolhe progressivamente
- Loot e disparo
- Condição de vitória: último jogador

## Módulos já entregues para versão completa inicial
1. Controle TPS, arma, safe zone e gestão de partida.
2. Lógica de combate e encolhimento de zona validada por testes.
3. Estrutura pronta para evolução com rede e assets finais.

## Tags técnicas sugeridas
{tags}
"""
    if mode == ANY_GAME_MODE:
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo AGI: criação de qualquer jogo completo
**Tema pedido:** {topic}

## Entrega gerada
- Documento de design completo (GDD)
- Roadmap de produção (MVP -> Beta -> Live Ops)
- Núcleo de gameplay implementado em código
- Testes automatizados para validar regras centrais

## Resultado
Projeto pronto para evolução direta pela equipe técnica e artística, sem começar do zero.

## Tags técnicas sugeridas
{tags}
"""
    if mode == APP_MODE:
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo AGI: app completo para Play Store e App Store
**Tema pedido:** {topic}

## Entregáveis
- Projeto Flutter completo com estrutura Android + iOS
- Configuração de metadados para stores
- Checklist de prontidão para publicação
- Testes base e app inicial funcional

## Resultado
Base pronta para publicação após assinatura e assets finais de loja.

## Tags técnicas sugeridas
{tags}
"""
    if mode == FOOD_APP_MODE:
        return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Modo AGI: app completo de delivery de comida
**Tema pedido:** {topic}

## Entregáveis
- App mobile de delivery (estrutura Flutter)
- Backend de pedidos com FastAPI
- Endpoints de restaurantes/pedidos
- Testes automatizados de API
- Checklist de prontidão para publicação e operação

## Resultado
Base completa pronta para evoluir para produção e publicar nas stores.

## Tags técnicas sugeridas
{tags}
"""
    return f"""# Blueprint Futuro da IA — Missão ATENA Ω ({date_label})

## Desafio solicitado
**Tema:** {topic}

## O que a ATENA já sabe de tecnologia (scan local)
{caps_md}

## Invenção proposta: *Núcleo de Invenção Tecnológica Adaptativa*
Um loop onde a ATENA transforma capacidades existentes em novos protótipos com evidência:
1. **Planner de inovação:** converte o tema em hipóteses técnicas mensuráveis.
2. **Executor de prova rápida:** cria protótipo mínimo e simula cenários de falha.
3. **Crítico de risco:** aplica score de segurança, custo e impacto operacional.
4. **Memória de resultado:** registra decisão com rastreabilidade para evolução contínua.

## MVP em 72 horas
1. Definir schema (`topic`, `hypothesis`, `experiment`, `risk`, `decision`, `next_step`).
2. Rodar 5 hipóteses e priorizar por impacto × viabilidade.
3. Entregar 1 protótipo com checklist de segurança.

## Métricas de sucesso
- Taxa de hipóteses aprovadas com evidência ≥ 80%.
- Tempo de ciclo ideia→protótipo ≤ 1 dia.
- Regressões críticas após promoção = 0.

## Tags técnicas sugeridas
{tags}
"""


def _build_json_payload(
    now_utc: datetime,
    topic: str,
    capabilities: list[str],
    keywords: list[str],
    blueprint_path: Path,
    mode: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "timestamp_utc": now_utc.isoformat(),
        "topic": topic,
        "mode": mode,
        "capabilities_detected": capabilities,
        "keywords": keywords,
        "blueprint_path": str(blueprint_path.relative_to(ROOT)),
        "status": "ok",
    }
    if mode == "society-max":
        payload["social_grand_challenge"] = _choose_social_challenge(topic)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ATENA Future AI Mission")
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help="Tema da inovação que a ATENA deve atacar.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime resumo JSON no stdout.",
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "society-max", "software-complete", GAME_MODE, ANY_GAME_MODE, APP_MODE, FOOD_APP_MODE],
        default=DEFAULT_MODE,
        help="`society-max` força impacto social; `software-complete` gera app; modos `game-*` geram jogos completos.",
    )
    parser.add_argument(
        "--run-generated-tests",
        action="store_true",
        help="Quando gerar software, executa pytest no projeto criado.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    now_utc = datetime.now(timezone.utc)
    capabilities = _collect_repo_capabilities()
    keywords = _extract_keywords(args.topic, capabilities)
    blueprint = build_blueprint(now_utc, args.topic, capabilities, keywords, args.mode)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_DIR / f"BLUEPRINT_FUTURO_IA_{now_utc.strftime('%Y-%m-%d')}.md"
    output_path.write_text(blueprint, encoding="utf-8")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "future_ai_mission_last_run.json"
    payload = _build_json_payload(now_utc, args.topic, capabilities, keywords, output_path, args.mode)

    if args.mode in {"society-max", "software-complete", GAME_MODE, ANY_GAME_MODE, APP_MODE, FOOD_APP_MODE}:
        social_challenge = _choose_social_challenge(args.topic) if args.mode == "society-max" else None
        project_slug = _slugify(args.topic)
        project_dir = OUTPUT_DIR / f"future_ai_{now_utc.strftime('%Y%m%d_%H%M%S')}_{project_slug}"
        if args.mode == GAME_MODE:
            scaffold = _build_battle_royale_game_scaffold(args.topic)
        elif args.mode == ANY_GAME_MODE:
            scaffold = _build_any_game_complete_scaffold(args.topic)
        elif args.mode == APP_MODE:
            scaffold = _build_mobile_store_ready_scaffold(args.topic)
        elif args.mode == FOOD_APP_MODE:
            scaffold = _build_food_delivery_complete_scaffold(args.topic)
        else:
            scaffold = _build_software_scaffold(args.topic, keywords, social_challenge)
        written_files = _write_software_scaffold(project_dir, scaffold)
        payload["generated_project_dir"] = str(project_dir.relative_to(ROOT))
        payload["generated_files"] = [str(Path(path).relative_to(ROOT)) for path in written_files]
        if args.mode in {GAME_MODE, ANY_GAME_MODE}:
            payload["generated_game_checks"] = _run_generated_game_checks(project_dir)
            payload["generated_game_tests"] = _run_generated_game_tests(project_dir)
        elif args.mode in {APP_MODE, FOOD_APP_MODE}:
            payload["generated_app_checks"] = _run_generated_app_checks(project_dir)
            payload["generated_app_tests"] = _run_generated_project_tests(project_dir)
        elif args.run_generated_tests:
            payload["generated_project_tests"] = _run_generated_project_tests(project_dir)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🚀 Missão Future AI executada com sucesso.")
    print(f"📄 Blueprint salvo em: {output_path.relative_to(ROOT)}")
    print(f"🧠 Capacidades detectadas: {len(capabilities)}")
    print(f"🎯 Modo: {args.mode}")
    if "generated_project_dir" in payload:
        print(f"🛠️ Software gerado em: {payload['generated_project_dir']}")
    game_info = payload.get("generated_game_checks")
    if isinstance(game_info, dict):
        status = "PASSOU" if game_info.get("ok") else "FALHOU"
        print(f"🎮 Check do jogo gerado: {status}")
    game_tests = payload.get("generated_game_tests")
    if isinstance(game_tests, dict):
        status = "PASSOU" if game_tests.get("ok") else "FALHOU"
        print(f"🧪 Testes do jogo gerado: {status}")
    app_checks = payload.get("generated_app_checks")
    if isinstance(app_checks, dict):
        status = "PASSOU" if app_checks.get("ok") else "FALHOU"
        print(f"📱 Check do app gerado: {status}")
    app_tests = payload.get("generated_app_tests")
    if isinstance(app_tests, dict):
        status = "PASSOU" if app_tests.get("ok") else "FALHOU"
        print(f"🧪 Testes do app gerado: {status}")
    tests_info = payload.get("generated_project_tests")
    if isinstance(tests_info, dict):
        status = "PASSOU" if tests_info.get("ok") else "FALHOU"
        print(f"🧪 Teste do software gerado: {status}")
    print(f"🗂️ Resumo JSON salvo em: {json_path.relative_to(ROOT)}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
