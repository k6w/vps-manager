.PHONY: install dev test clean lint setup install-full

install:
	pip install .

install-full:
	@echo "Running full installation script..."
	@if [ -f /bin/bash ]; then \
		chmod +x install.sh && ./install.sh; \
	else \
		echo "On Windows, run install.sh with bash or follow SETUP.md"; \
	fi

dev:
	pip install -e ".[dev]"

test:
	pytest tests/

lint:
	flake8 src/ tests/
	black --check src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info vps-manager-env/
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -exec rm -rf {} +

setup:
	python test_setup.py
