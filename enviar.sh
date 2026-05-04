#!/bin/bash
git pull origin main --rebase
git add .
git commit -m "🧬 ATENA Ω - Evolução Automática: $(date +'%d/%m/%Y %H:%M')"
git push origin main
