# ==========================================================================
# SONAR — Atalhos de execução
# ==========================================================================
# Uso rápido:
#   make up      → sobe o Ollama (+ modelo) e o dashboard — o atalho da demo
#   make help    → lista todos os alvos
#
# Convenção: os alvos que dependem do venv usam `poetry run`; o Ollama é um
# binário do sistema. O modelo LLM é lido do config.yaml (fonte única de
# verdade — nenhum número mágico duplicado aqui).
# --------------------------------------------------------------------------

# Modelo LLM extraído do config (ex.: qwen2.5:14b). Sobrescreva com: make up MODEL=...
MODEL      ?= $(shell grep -E '^[[:space:]]+model:' config/config.yaml | head -1 | awk '{print $$2}')
OLLAMA_URL ?= http://localhost:11434
APP        := src/dashboard/app.py
PORT       ?= 8501

.DEFAULT_GOAL := help
.PHONY: help install pipeline coleta insight ollama dashboard dash up demo test stop stop-all

help:  ## Lista os alvos disponíveis
	@echo "SONAR — atalhos (make <alvo>):"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Modelo LLM (config.yaml): $(MODEL)  ·  Dashboard: http://localhost:$(PORT)"

install:  ## Instala as dependências no venv (poetry install)
	poetry install

pipeline:  ## Pipeline offline (corpus congelado): PLN + scores
	poetry run sonar

coleta:  ## Pipeline INCLUINDO a coleta das 2 fontes (~6h, rate-limit educado)
	poetry run sonar --com-coleta

insight:  ## (Re)gera os briefings da IA — requer o Ollama no ar (ver 'make ollama')
	poetry run python -m src.insight.run

ollama:  ## Sobe o Ollama em background e garante o modelo baixado
	@if pgrep -x ollama >/dev/null 2>&1; then \
		echo "✓ Ollama já está rodando"; \
	else \
		echo "▶ Subindo 'ollama serve' em background (log: /tmp/ollama-sonar.log)"; \
		nohup ollama serve >/tmp/ollama-sonar.log 2>&1 & \
	fi
	@printf "▶ Aguardando o Ollama responder"; \
	for i in $$(seq 1 30); do \
		curl -sf $(OLLAMA_URL)/api/tags >/dev/null 2>&1 && { echo " ✓"; break; }; \
		printf "."; sleep 1; \
	done
	@if ollama list 2>/dev/null | grep -q "$(MODEL)"; then \
		echo "✓ Modelo $(MODEL) disponível"; \
	else \
		echo "▶ Baixando o modelo $(MODEL) (pode demorar na 1ª vez)..."; \
		ollama pull $(MODEL); \
	fi

dashboard:  ## Sobe só o dashboard Streamlit (não mexe no Ollama)
	poetry run streamlit run $(APP)

dash: dashboard  ## Alias curto de 'dashboard'

up: ollama  ## ★ Sobe o Ollama (+ modelo) e o dashboard — atalho da demo
	@echo "▶ Dashboard em http://localhost:$(PORT)  (Ctrl+C encerra; o Ollama segue em background)"
	poetry run streamlit run $(APP)

demo: pipeline up  ## Roda o pipeline offline e sobe tudo (do zero, corpus congelado)

test:  ## Roda a suíte de testes (pytest)
	poetry run pytest

stop:  ## Para o dashboard (deixa o Ollama no ar)
	-@pkill -f "streamlit run $(APP)" 2>/dev/null && echo "✓ Streamlit parado" || echo "· Streamlit não estava rodando"

stop-all: stop  ## Para o dashboard E o Ollama
	-@pkill -x ollama 2>/dev/null && echo "✓ Ollama parado" || echo "· Ollama não estava rodando"
