#!/bin/bash
echo "🔄 Sincronizando com o GitHub..."
git pull origin main --rebase
git add .
git commit -m "🧬 ATENA Ω - Evolução Automática: $(date +'%d/%m/%Y %H:%M')"
echo "🚀 Enviando atualizações..."
git push origin main
