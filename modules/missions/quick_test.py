#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quick_test.py — Testes rápidos de sanidade da ATENA Ω
Verifica se os módulos essenciais estão disponíveis e funcionando.
"""

import sys
import importlib

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []

def check(label, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
        results.append((label, True))
    except Exception as e:
        print(f"  {FAIL} {label}: {e}")
        results.append((label, False))

def check_optional(label, fn):
    try:
        fn()
        print(f"  {PASS} {label}")
    except Exception as e:
        print(f"  {WARN} {label} (opcional): {e}")

print("=" * 60)
print("ATENA Ω — Testes rápidos de sanidade")
print("=" * 60)

# --- Módulos da stdlib ---
print("\n[1] Módulos da biblioteca padrão:")
for mod in ["os", "sys", "json", "sqlite3", "ast", "subprocess", "threading", "logging"]:
    check(mod, lambda m=mod: importlib.import_module(m))

# --- Dependências essenciais ---
print("\n[2] Dependências essenciais:")
check("astor", lambda: importlib.import_module("astor"))
check("requests", lambda: importlib.import_module("requests"))
check("numpy", lambda: importlib.import_module("numpy"))
check("psutil", lambda: importlib.import_module("psutil"))
check("pandas", lambda: importlib.import_module("pandas"))

# --- Dependências opcionais ---
print("\n[3] Dependências opcionais (falha não bloqueia):")
check_optional("torch", lambda: importlib.import_module("torch"))
check_optional("sentence_transformers", lambda: importlib.import_module("sentence_transformers"))
check_optional("transformers", lambda: importlib.import_module("transformers"))
check_optional("radon", lambda: importlib.import_module("radon"))
check_optional("sklearn", lambda: importlib.import_module("sklearn"))

# --- Verificar SQLite ---
print("\n[4] SQLite:")
def test_sqlite():
    import sqlite3, tempfile, os
    db = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'ok')")
    conn.commit()
    row = conn.execute("SELECT val FROM test WHERE id=1").fetchone()
    conn.close()
    os.unlink(db)
    assert row[0] == "ok"

check("sqlite3 read/write", test_sqlite)

# --- Verificar AST + astor ---
print("\n[5] AST + astor:")
def test_astor():
    import ast, astor
    code = "def hello():\n    return 42\n"
    tree = ast.parse(code)
    out = astor.to_source(tree)
    assert "hello" in out

check("ast.parse + astor.to_source", test_astor)

# --- Resumo ---
print("\n" + "=" * 60)
failed = [l for l, ok in results if not ok]
if failed:
    print(f"RESULTADO: {len(failed)} teste(s) falharam: {', '.join(failed)}")
    sys.exit(1)
else:
    print(f"RESULTADO: Todos os {len(results)} testes essenciais passaram! ✅")
    sys.exit(0)
