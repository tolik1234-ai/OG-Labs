.PHONY: setup fmt lint test run

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	python -c "import solcx; solcx.install_solc('0.8.20')"

fmt:
	black .
	ruff --fix .

lint:
	ruff .

run:
	python main_ferma.py