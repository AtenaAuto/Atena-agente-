#!/usr/bin/env bash
set -euo pipefail

PROMPT="Crie um site SaaS completo com landing page, dashboard, pricing e FAQ. Entregue estrutura de arquivos e código inicial."
OUT_FILE="analysis_reports/ATENA_DELIVERY_TEST_$(date -u +%Y%m%d_%H%M%S).log"
SPORTS_FILE="analysis_reports/ATENA_SPORTS_TEST_$(date -u +%Y%m%d_%H%M%S).log"
IMAGE_FILE="analysis_reports/ATENA_IMAGE_TEST_$(date -u +%Y%m%d_%H%M%S).log"
API_FILE="analysis_reports/ATENA_API_DISCOVERY_TEST_$(date -u +%Y%m%d_%H%M%S).log"
mkdir -p analysis_reports

env USER="${USER:-root}" bash -lc "printf '%s\n/sair\n' \"$PROMPT\" | bash ./atena" | tee "$OUT_FILE"

assert_pattern() {
  local pattern="$1"
  local message="$2"
  if ! rg -q "$pattern" "$OUT_FILE"; then
    echo "❌ $message (pattern: $pattern)" >&2
    echo "Log: $OUT_FILE" >&2
    exit 1
  fi
}

# 1) Boot básico
assert_pattern "ATENA Ω - Terminal Assistant" "ATENA não iniciou corretamente"
# 2) Plugin carregado
assert_pattern "\\[Plugin\\]" "Plugins não carregaram"
# 3) Módulos: deve carregar todos os módulos previstos (X/X), sem hardcode de quantidade
preload_line="$(rg -o "\\[ATENA preload\\] módulos carregados: [0-9]+/[0-9]+" "$OUT_FILE" | tail -n 1 || true)"
if [[ -z "${preload_line:-}" ]]; then
  echo "❌ Linha de preload não encontrada." >&2
  echo "Log: $OUT_FILE" >&2
  exit 1
fi
loaded_count="$(echo "$preload_line" | sed -E 's/.*: ([0-9]+)\/([0-9]+)/\1/')"
total_count="$(echo "$preload_line" | sed -E 's/.*: ([0-9]+)\/([0-9]+)/\2/')"
if [[ "$loaded_count" != "$total_count" ]]; then
  echo "❌ Nem todos os módulos foram carregados (${loaded_count}/${total_count})." >&2
  echo "Log: $OUT_FILE" >&2
  exit 1
fi
# 4) Prompt complexo processado e resposta gerada (scaffold útil ou resposta de API)
if ! rg -q "\\[local-scaffold\\]|\\[public-api\\].*site SaaS completo" "$OUT_FILE"; then
  echo "❌ ATENA não entregou resposta útil para geração de código." >&2
  echo "Log: $OUT_FILE" >&2
  exit 1
fi

# 4.1) Se retorno foi scaffold local, validar que arquivos reais foram criados.
if rg -q "\\[local-scaffold\\]" "$OUT_FILE"; then
  latest_site_dir="$(find atena_evolution/generated_apps -maxdepth 1 -type d -name 'site_*' | sort | tail -n 1)"
  if [[ -z "${latest_site_dir:-}" ]]; then
    echo "❌ Scaffold local não materializou diretório de entrega." >&2
    exit 1
  fi
  for f in index.html style.css app.js; do
    if [[ ! -f "${latest_site_dir}/${f}" ]]; then
      echo "❌ Arquivo esperado ausente no scaffold: ${latest_site_dir}/${f}" >&2
      exit 1
    fi
  done
fi

# 5) Skills: valida presença das skills essenciais no repositório
for skill in atena-orchestrator neural-reality-sync; do
  if [[ ! -f "skills/${skill}/SKILL.md" ]]; then
    echo "❌ Skill ausente: skills/${skill}/SKILL.md" >&2
    exit 1
  fi
done

echo "✅ ATENA validada: módulos, plugins, skills e resposta complexa. Log: $OUT_FILE"

# 6) Teste esportivo: deve usar fontes de esporte e tentar retornar data de jogo.
SPORTS_PROMPT="Que dia é o jogo do Santos?"
env USER="${USER:-root}" bash -lc "printf '%s\n/sair\n' \"$SPORTS_PROMPT\" | bash ./atena" | tee "$SPORTS_FILE"
if ! rg -q "TheSportsDB|Próximo jogo encontrado|não encontrei data confirmada" "$SPORTS_FILE"; then
  echo "❌ Fluxo esportivo não retornou resposta orientada por API pública." >&2
  echo "Log: $SPORTS_FILE" >&2
  exit 1
fi

echo "✅ Fluxo esportivo validado. Log: $SPORTS_FILE"

# 7) Teste de geração de imagem via API pública
IMAGE_PROMPT="Gere uma imagem de capa para um app de tecnologia."
env USER="${USER:-root}" bash -lc "printf '%s\n/sair\n' \"$IMAGE_PROMPT\" | bash ./atena" | tee "$IMAGE_FILE"
if ! rg -q "\\[local-image\\]|picsum.photos" "$IMAGE_FILE"; then
  echo "❌ Fluxo de geração de imagem não retornou fonte pública esperada." >&2
  echo "Log: $IMAGE_FILE" >&2
  exit 1
fi
latest_image_dir="$(find atena_evolution/generated_apps -maxdepth 1 -type d -name 'image_*' | sort | tail -n 1)"
if [[ -z "${latest_image_dir:-}" || ! -f "${latest_image_dir}/generated_image.jpg" ]]; then
  echo "❌ Imagem não foi materializada no disco." >&2
  exit 1
fi

# 8) Teste de descoberta de APIs diversas (não apenas pool público interno)
API_PROMPT="Quais APIs usar para app de notícias de futebol?"
env USER="${USER:-root}" bash -lc "printf '%s\n/sair\n' \"$API_PROMPT\" | bash ./atena" | tee "$API_FILE"
if ! rg -q "APIs públicas recomendadas|Catálogo ampliado|Ranking dinâmico|apis.guru|public-apis|Catálogo de APIs públicas salvo" "$API_FILE"; then
  echo "❌ Fluxo de descoberta de APIs diversas não respondeu como esperado." >&2
  echo "Log: $API_FILE" >&2
  exit 1
fi

echo "✅ Fluxos de imagem e descoberta ampliada de APIs validados."
