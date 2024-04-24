.PHONY: build test benchmark typecheck typecheck-strict clean

build:
	poetry install

test:
	python -m pytest tests -v --cov=sd_core --cov=sd_datastore --cov=sd_transform --cov=sd_query

.coverage:
	make test

coverage_html: .coverage
	python -m coverage html -d coverage_html

benchmark:
	python -m sd_datastore.benchmark

typecheck:
	export MYPYPATH=./stubs; python -m mypy sd_core sd_datastore sd_transform sd_query --show-traceback --ignore-missing-imports --follow-imports=skip

typecheck-strict:
	export MYPYPATH=./stubs; python -m mypy sd_core sd_datastore sd_transform sd_query --strict-optional --check-untyped-defs; echo "Not a failing step"

PYFILES=$(shell find . -type f -name '*.py')
PYIFILES=$(shell find . -type f -name '*.pyi')

lint:
	ruff check .

lint-fix:
	pyupgrade --py37-plus ${PYFILES} && true
	ruff check --fix .

format:
	black ${PYFILES} ${PYIFILES}

clean:
	rm -rf build dist
	rm -rf sd_core/__pycache__ sd_datastore/__pycache__
