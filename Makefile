# Sample app for ai-api-unified.
#
# The library can come from two sources:
#   - local checkout (default): editable install from LOCAL_LIB
#   - PyPI: latest published release, upgraded on every run
#
# Both are installed into the Poetry virtualenv with pip so switching never
# touches pyproject.toml or poetry.lock.

LOCAL_LIB ?= ../ai_api_unified
EXTRAS ?= openai,google_gemini,bedrock,anthropic,azure_tts,elevenlabs,video_frames,similarity_score,middleware-pii-redaction
POETRY ?= poetry
PIP := $(POETRY) run pip

.PHONY: help venv env setup setup-local setup-pypi use-local use-pypi run run-local run-pypi \
	which spacy-model assets test lint format clean

help:
	@echo "Targets:"
	@echo "  setup        alias for setup-local (default source is the local library)"
	@echo "  setup-local  install app deps + editable local ai_api_unified with all extras"
	@echo "  setup-pypi   install app deps + latest ai-api-unified from PyPI with all extras"
	@echo "  run          alias for run-local (launches the Textual TUI)"
	@echo "  run-local    ensure local editable install, then launch the Textual TUI"
	@echo "  run-pypi     upgrade to latest PyPI release, then launch the Textual TUI"
	@echo "  which        show which ai_api_unified source and version is active"
	@echo "  env          copy .env from the local library checkout if missing"
	@echo "  assets       regenerate the bundled sample images"
	@echo "  test         run unit tests (no network)"
	@echo "  lint         ruff + black --check"
	@echo "  format       black + ruff --fix"

venv:
	$(POETRY) install --all-extras

env:
	@if [ ! -f .env ]; then \
		if [ -f "$(LOCAL_LIB)/.env" ]; then \
			cp "$(LOCAL_LIB)/.env" .env && echo "Copied .env from $(LOCAL_LIB)"; \
		else \
			cp env_template .env && echo "Created .env from env_template"; \
		fi; \
	else \
		echo ".env already present"; \
	fi

use-local:
	$(PIP) install --quiet -e "$(LOCAL_LIB)[$(EXTRAS)]"
	@$(MAKE) --no-print-directory which

use-pypi:
	$(PIP) install --quiet --upgrade "ai-api-unified[$(EXTRAS)]"
	@$(MAKE) --no-print-directory which

spacy-model:
	$(POETRY) run python -m spacy download en_core_web_sm

setup: setup-local

setup-local: venv env use-local spacy-model

setup-pypi: venv env use-pypi spacy-model

run: run-local

run-local: use-local
	$(POETRY) run python -m sample_ai_api_unified

run-pypi: use-pypi
	$(POETRY) run python -m sample_ai_api_unified

which:
	@$(POETRY) run python -c "import ai_api_unified, pathlib; \
p = pathlib.Path(ai_api_unified.__file__).resolve(); \
src = 'PyPI (site-packages)' if 'site-packages' in str(p) else 'local editable checkout'; \
print(f'ai_api_unified {ai_api_unified.__version__} from {src}'); print(f'  {p.parent}')"

assets:
	$(POETRY) run python scripts/generate_sample_assets.py

test:
	$(POETRY) run pytest

lint:
	$(POETRY) run ruff check src tests scripts
	$(POETRY) run black --check src tests scripts

format:
	$(POETRY) run black src tests scripts
	$(POETRY) run ruff check --fix src tests scripts

clean:
	rm -rf .pytest_cache .ruff_cache dist generated_images generated_videos generated_frames
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
