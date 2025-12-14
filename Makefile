.PHONY: install dev test clean lint

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/

lint:
	flake8 src/ tests/
	black --check src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -exec rm -rf {} +
