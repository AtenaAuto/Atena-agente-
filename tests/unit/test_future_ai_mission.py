from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from protocols.atena_future_ai_mission import (
    ANY_GAME_MODE,
    APP_MODE,
    FOOD_APP_MODE,
    GAME_MODE,
    ROOT,
    _build_battle_royale_game_scaffold,
    _build_any_game_complete_scaffold,
    _build_mobile_store_ready_scaffold,
    _build_food_delivery_complete_scaffold,
    _build_software_scaffold,
    _build_json_payload,
    _choose_social_challenge,
    _extract_keywords,
    _run_generated_game_checks,
    _run_generated_game_tests,
    _run_generated_app_checks,
    _run_generated_project_tests,
    _write_software_scaffold,
    build_blueprint,
)


def test_build_blueprint_society_max_contains_social_sections() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="saúde preventiva",
        capabilities=["atena engine", "federated learning"],
        keywords=["saúde", "segurança"],
        mode="society-max",
    )

    assert "Modo de teste extremo para sociedade" in blueprint
    assert "ATENA Impact OS" in blueprint
    assert "Métricas sociais (obrigatórias)" in blueprint


def test_build_json_payload_includes_society_challenge_in_society_mode() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    payload = _build_json_payload(
        now_utc=now,
        topic="educação",
        capabilities=["atena engine"],
        keywords=["educação"],
        blueprint_path=ROOT / "docs/BLUEPRINT_FUTURO_IA_2026-04-20.md",
        mode="society-max",
    )

    assert payload["status"] == "ok"
    assert payload["mode"] == "society-max"
    assert payload["social_grand_challenge"] == _choose_social_challenge("educação")


def test_extract_keywords_prioritizes_uniques() -> None:
    keywords = _extract_keywords("plano de saúde e memória", ["memory engine", "secure planner"], limit=4)

    assert len(keywords) == 4
    assert len(set(keywords)) == len(keywords)


def test_build_blueprint_software_complete_mentions_full_project() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="plataforma cidadã",
        capabilities=["atena engine"],
        keywords=["cidadã"],
        mode="software-complete",
    )

    assert "Modo software completo ativado" in blueprint
    assert "Projeto Python com `app/`, `tests/`, `README.md` e `pyproject.toml`." in blueprint


def test_software_scaffold_writer_creates_core_files(tmp_path: Path) -> None:
    scaffold = _build_software_scaffold("plataforma cidadã", ["impacto"], "evasão escolar")
    written = _write_software_scaffold(tmp_path, scaffold)

    assert len(written) >= 5
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "app/main.py").exists()
    assert (tmp_path / "tests/test_service.py").exists()


def test_generated_project_tests_run_successfully(tmp_path: Path) -> None:
    scaffold = _build_software_scaffold("plataforma cidadã", ["impacto"], "evasão escolar")
    _write_software_scaffold(tmp_path, scaffold)

    result = _run_generated_project_tests(tmp_path)

    assert result["ok"] is True
    assert result["exit_code"] == 0


def test_battle_royale_scaffold_integrity_check_passes(tmp_path: Path) -> None:
    scaffold = _build_battle_royale_game_scaffold("battle royale tps")
    _write_software_scaffold(tmp_path, scaffold)

    result = _run_generated_game_checks(tmp_path)
    assert result["ok"] is True
    assert result["missing_files"] == []


def test_build_blueprint_game_mode_mentions_tps() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="battle royale",
        capabilities=["atena engine"],
        keywords=["battle", "royale"],
        mode=GAME_MODE,
    )
    assert "Modo jogo 3D battle royale ativado" in blueprint
    assert "Terceira pessoa (TPS)" in blueprint


def test_generated_game_tests_run_successfully(tmp_path: Path) -> None:
    scaffold = _build_battle_royale_game_scaffold("battle royale tps")
    _write_software_scaffold(tmp_path, scaffold)

    result = _run_generated_game_tests(tmp_path)
    assert result["ok"] is True
    assert result["exit_code"] == 0


def test_any_game_mode_blueprint_mentions_complete_creation() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="rpg tático sci-fi",
        capabilities=["atena engine"],
        keywords=["rpg", "sci-fi"],
        mode=ANY_GAME_MODE,
    )
    assert "Modo AGI: criação de qualquer jogo completo" in blueprint


def test_any_game_complete_scaffold_and_checks_pass(tmp_path: Path) -> None:
    scaffold = _build_any_game_complete_scaffold("rpg tático sci-fi")
    _write_software_scaffold(tmp_path, scaffold)

    checks = _run_generated_game_checks(tmp_path)
    assert checks["ok"] is True

    tests_result = _run_generated_game_tests(tmp_path)
    assert tests_result["ok"] is True


def test_app_mode_blueprint_mentions_store_ready() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="app de produtividade",
        capabilities=["atena engine"],
        keywords=["mobile", "flutter"],
        mode=APP_MODE,
    )
    assert "app completo para Play Store e App Store" in blueprint


def test_mobile_store_ready_scaffold_checks_pass(tmp_path: Path) -> None:
    scaffold = _build_mobile_store_ready_scaffold("app de produtividade")
    _write_software_scaffold(tmp_path, scaffold)

    checks = _run_generated_app_checks(tmp_path)
    assert checks["ok"] is True


def test_food_app_mode_blueprint_mentions_delivery() -> None:
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    blueprint = build_blueprint(
        now_utc=now,
        topic="delivery de comida",
        capabilities=["atena engine"],
        keywords=["delivery", "mobile"],
        mode=FOOD_APP_MODE,
    )
    assert "app completo de delivery de comida" in blueprint


def test_food_delivery_scaffold_checks_and_tests_pass(tmp_path: Path) -> None:
    scaffold = _build_food_delivery_complete_scaffold("delivery de comida")
    _write_software_scaffold(tmp_path, scaffold)

    checks = _run_generated_app_checks(tmp_path)
    assert checks["ok"] is True

    test_result = _run_generated_project_tests(tmp_path)
    assert test_result["ok"] is True
