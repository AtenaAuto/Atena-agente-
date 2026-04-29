"""
Testes aprimorados para core/atena_secret_scan.py

Cobertura:
  - Todos os padrões de segredo (github_classic, github_pat, openai_key, aws_access_key)
  - Detecção multi-linha e multi-segredo por arquivo
  - Número correto de linha reportado
  - Exclusão de diretórios padrão (.git, .venv, __pycache__, etc.)
  - Exclusão de testes por padrão; inclusão via include_tests=True
  - Extensões de arquivo cobertas e ignoradas
  - Conteúdo seguro (sem falsos positivos)
  - Tokens curtos demais (abaixo do limiar do regex)
  - Múltiplas ocorrências na mesma linha
  - include_tests=True expõe arquivos de teste
  - Comportamento com diretório vazio
  - Comportamento com arquivo ilegível (OSError)
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from core.atena_secret_scan import scan_repo, _iter_candidate_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, content: str) -> Path:
    """Cria arquivo com conteúdo dentro de tmp_path."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _findings_for(tmp_path: Path, rel: str, content: str, **kw) -> list[dict]:
    _write(tmp_path, rel, content)
    return scan_repo(tmp_path, **kw)


# ---------------------------------------------------------------------------
# Padrão: github_classic  (ghp_...)
# ---------------------------------------------------------------------------

class TestGithubClassicToken:
    def test_detecta_token_em_atribuicao(self, tmp_path):
        findings = _findings_for(tmp_path, "config.py",
                                 'TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        assert len(findings) == 1
        assert findings[0]["pattern"] == "github_classic"

    def test_reporta_nome_de_arquivo_relativo(self, tmp_path):
        findings = _findings_for(tmp_path, "config.py",
                                 'TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        assert findings[0]["file"] == "config.py"

    def test_reporta_numero_de_linha_correto(self, tmp_path):
        content = "# comentário\n# linha 2\nTOKEN = \"ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\"\n"
        findings = _findings_for(tmp_path, "cfg.py", content)
        assert findings[0]["line"] == 3

    def test_token_exatamente_20_chars_apos_prefixo(self, tmp_path):
        # Limiar mínimo: ghp_ + 20 chars = válido
        findings = _findings_for(tmp_path, "a.py",
                                 'X = "ghp_ABCDEFGHIJKLMNOPQRST"\n')
        assert len(findings) == 1

    def test_token_19_chars_nao_detectado(self, tmp_path):
        # ghp_ + 19 chars = abaixo do limiar
        findings = _findings_for(tmp_path, "a.py",
                                 'X = "ghp_ABCDEFGHIJKLMNOPQRS"\n')
        assert findings == []


# ---------------------------------------------------------------------------
# Padrão: github_pat  (github_pat_...)
# ---------------------------------------------------------------------------

class TestGithubPATToken:
    def test_detecta_pat_em_yaml(self, tmp_path):
        findings = _findings_for(tmp_path, "deploy.yml",
                                 "token: github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ\n")
        assert len(findings) == 1
        assert findings[0]["pattern"] == "github_pat"

    def test_pat_curto_nao_detectado(self, tmp_path):
        findings = _findings_for(tmp_path, "a.py",
                                 'X = "github_pat_SHORT"\n')
        assert findings == []


# ---------------------------------------------------------------------------
# Padrão: openai_key  (sk-...)
# ---------------------------------------------------------------------------

class TestOpenAIKey:
    def test_detecta_chave_openai(self, tmp_path):
        findings = _findings_for(tmp_path, "settings.py",
                                 'OPENAI_KEY = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"\n')
        assert len(findings) == 1
        assert findings[0]["pattern"] == "openai_key"

    def test_chave_openai_curta_nao_detectada(self, tmp_path):
        findings = _findings_for(tmp_path, "a.py", 'K = "sk-SHORT"\n')
        assert findings == []


# ---------------------------------------------------------------------------
# Padrão: aws_access_key  (AKIA...)
# ---------------------------------------------------------------------------

class TestAWSAccessKey:
    def test_detecta_chave_aws(self, tmp_path):
        # Nota: .tf não está em TEXT_EXTENSIONS — usar .py ou .env
        findings = _findings_for(tmp_path, "infra.py",
                                 'aws_key = "AKIAIOSFODNN7EXAMPLE"\n')
        assert len(findings) == 1
        assert findings[0]["pattern"] == "aws_access_key"

    def test_aws_menos_de_16_chars_nao_detectado(self, tmp_path):
        # AKIA + 13 chars — abaixo do exato {16} exigido pelo regex
        findings = _findings_for(tmp_path, "a.py", 'K = "AKIAIOSFODNN7EXAM"\n')
        assert findings == []

    def test_aws_mais_de_16_chars_nao_detectado(self, tmp_path):
        # AKIA + 17 chars — word boundary (\b) bloqueia casamento
        findings = _findings_for(tmp_path, "a.py", 'K = "AKIAIOSFODNN7EXAMPLES"\n')
        assert findings == []

    def test_aws_em_env_file(self, tmp_path):
        findings = _findings_for(tmp_path, ".env",
                                 "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n")
        assert len(findings) == 1
        assert findings[0]["pattern"] == "aws_access_key"


# ---------------------------------------------------------------------------
# Conteúdo seguro — sem falsos positivos
# ---------------------------------------------------------------------------

class TestConteudoSeguro:
    def test_arquivo_sem_segredos(self, tmp_path):
        findings = _findings_for(tmp_path, "safe.md", "sem segredos aqui\n")
        assert findings == []

    def test_comentario_normal_nao_detectado(self, tmp_path):
        findings = _findings_for(tmp_path, "a.py", "# apenas um comentário\n")
        assert findings == []

    def test_placeholder_fake_nao_detectado(self, tmp_path):
        # Strings genéricas que não casam com os padrões
        findings = _findings_for(tmp_path, "a.py",
                                 'TOKEN = "your-token-here"\n')
        assert findings == []


# ---------------------------------------------------------------------------
# Múltiplos segredos
# ---------------------------------------------------------------------------

class TestMultiplosSegredos:
    def test_dois_segredos_no_mesmo_arquivo(self, tmp_path):
        content = (
            'GH = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n'
            'OAI = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"\n'
        )
        findings = _findings_for(tmp_path, "secrets.py", content)
        patterns = {f["pattern"] for f in findings}
        assert "github_classic" in patterns
        assert "openai_key" in patterns
        assert len(findings) == 2

    def test_segredo_em_multiplos_arquivos(self, tmp_path):
        _write(tmp_path, "a.py", 'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        _write(tmp_path, "b.env", 'T = "ghp_ZYXWVUTSRQPONMLKJIHGFEDCBA654321"\n')
        findings = scan_repo(tmp_path)
        assert len(findings) == 2

    def test_dois_segredos_na_mesma_linha(self, tmp_path):
        line = 'X = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456" + "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"\n'
        findings = _findings_for(tmp_path, "a.py", line)
        patterns = {f["pattern"] for f in findings}
        assert "github_classic" in patterns
        assert "openai_key" in patterns


# ---------------------------------------------------------------------------
# Exclusão de testes
# ---------------------------------------------------------------------------

class TestExclusaoDeTestes:
    def test_ignora_pasta_tests_por_padrao(self, tmp_path):
        _write(tmp_path, "tests/unit/test_cfg.py",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path)
        assert findings == []

    def test_ignora_arquivo_test_underscore_por_padrao(self, tmp_path):
        _write(tmp_path, "test_something.py",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path)
        assert findings == []

    def test_include_tests_expoe_arquivos_de_teste(self, tmp_path):
        _write(tmp_path, "tests/unit/test_cfg.py",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path, include_tests=True)
        assert len(findings) == 1
        assert findings[0]["pattern"] == "github_classic"

    def test_include_tests_expoe_arquivo_test_underscore(self, tmp_path):
        _write(tmp_path, "test_something.py",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path, include_tests=True)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Exclusão de diretórios padrão
# ---------------------------------------------------------------------------

class TestExclusaoDeDiretorios:
    @pytest.mark.parametrize("excluded_dir", [
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"
    ])
    def test_ignora_diretorios_padrao(self, tmp_path, excluded_dir):
        _write(tmp_path, f"{excluded_dir}/secrets.py",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path)
        assert findings == [], f"Deveria ignorar {excluded_dir}/"


# ---------------------------------------------------------------------------
# Extensões de arquivo
# ---------------------------------------------------------------------------

class TestExtensoes:
    @pytest.mark.parametrize("ext", [
        ".py", ".md", ".txt", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".env", ".sh"
    ])
    def test_escaneia_extensao_suportada(self, tmp_path, ext):
        _write(tmp_path, f"arquivo{ext}",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path)
        assert len(findings) == 1, f"Deveria escanear *{ext}"

    def test_ignora_extensao_binaria(self, tmp_path):
        # .pyc e .exe não são extensões de texto — devem ser ignorados
        _write(tmp_path, "compiled.pyc",
               'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        findings = scan_repo(tmp_path)
        assert findings == []

    def test_escaneia_dotenv_sem_extensao_extra(self, tmp_path):
        _write(tmp_path, ".env",
               'TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n')
        findings = scan_repo(tmp_path)
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Casos de borda
# ---------------------------------------------------------------------------

class TestCasosDeBorda:
    def test_diretorio_vazio(self, tmp_path):
        findings = scan_repo(tmp_path)
        assert findings == []

    def test_arquivo_vazio(self, tmp_path):
        _write(tmp_path, "empty.py", "")
        findings = scan_repo(tmp_path)
        assert findings == []

    def test_arquivo_sem_permissao_nao_quebra_scanner(self, tmp_path):
        p = _write(tmp_path, "locked.py",
                   'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n')
        p.chmod(0o000)
        try:
            # Não deve lançar exceção — OSError é capturado internamente
            findings = scan_repo(tmp_path)
            # O arquivo ilegível é silenciado; nenhum resultado esperado
            assert isinstance(findings, list)
        finally:
            p.chmod(stat.S_IRUSR | stat.S_IWUSR)  # restaura para limpeza

    def test_arquivo_unicode_com_caracteres_especiais(self, tmp_path):
        # Conteúdo misto: segredo + texto unicode
        content = 'Olá mundo 🌍\nT = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n'
        findings = _findings_for(tmp_path, "unicode.py", content)
        assert len(findings) == 1
        assert findings[0]["line"] == 2

    def test_numero_de_linha_em_arquivo_longo(self, tmp_path):
        linhas_vazias = "\n" * 49
        content = linhas_vazias + 'T = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n'
        findings = _findings_for(tmp_path, "long.py", content)
        assert findings[0]["line"] == 50


# ---------------------------------------------------------------------------
# Testes de _iter_candidate_files diretamente
# ---------------------------------------------------------------------------

class TestIterCandidateFiles:
    def test_retorna_lista(self, tmp_path):
        _write(tmp_path, "a.py", "x = 1\n")
        result = _iter_candidate_files(tmp_path)
        assert isinstance(result, list)
        assert any(p.name == "a.py" for p in result)

    def test_exclui_testes_por_padrao(self, tmp_path):
        _write(tmp_path, "src/main.py", "x = 1\n")
        _write(tmp_path, "tests/test_main.py", "x = 1\n")
        result = _iter_candidate_files(tmp_path)
        names = [p.name for p in result]
        assert "main.py" in names
        assert "test_main.py" not in names

    def test_inclui_testes_quando_solicitado(self, tmp_path):
        _write(tmp_path, "tests/test_main.py", "x = 1\n")
        result = _iter_candidate_files(tmp_path, include_tests=True)
        assert any(p.name == "test_main.py" for p in result)
