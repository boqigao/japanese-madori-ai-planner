SHELL := /bin/zsh

SPEC ?= tmp/spec.yaml
OUTDIR ?= tmp/plan_output
TIMEOUT ?= 90

.PHONY: help sync run run-default clean-tmp clean-output check-syntax verify fmt lint

help:
	@echo "AI-Driven Plan Engine - Common Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make <target> [SPEC=tmp/spec.yaml] [OUTDIR=tmp/plan_output] [TIMEOUT=90]"
	@echo ""
	@echo "Targets:"
	@echo "  make sync          Install/update dependencies via uv"
	@echo "  make run           Run generator with SPEC/OUTDIR/TIMEOUT"
	@echo "  make run-default   Run generator with default tmp/spec.yaml"
	@echo "  make check-syntax  Python syntax check for main.py and plan_engine/"
	@echo "  make verify        check-syntax + run-default"
	@echo "  make fmt           Auto-format Python files with ruff"
	@echo "  make lint          Lint Python files with ruff (format check + lint rules)"
	@echo "  make clean-output  Remove generated output directory (OUTDIR)"
	@echo "  make clean-tmp     Remove everything under tmp/"

sync:
	uv sync

run:
	uv run python main.py --spec "$(SPEC)" --outdir "$(OUTDIR)" --solver-timeout "$(TIMEOUT)"

run-default:
	uv run python main.py --spec "tmp/spec.yaml" --outdir "tmp/plan_output" --solver-timeout "90"

fmt:
	uv run ruff check --fix-only --unsafe-fixes main.py plan_engine
	uv run ruff format main.py plan_engine

lint:
	uv run ruff format --diff main.py plan_engine
	uv run ruff check main.py plan_engine

check-syntax:
	python -m compileall main.py plan_engine

verify: check-syntax run-default

clean-output:
	rm -rf "$(OUTDIR)"

clean-tmp:
	rm -rf tmp/*
