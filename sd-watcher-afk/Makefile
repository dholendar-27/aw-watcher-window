.PHONY: build test package clean

build:
	poetry install

test:
	poetry run sd-watcher-afk --help  # Ensures that it at least starts
	make typecheck

typecheck:
	poetry run mypy sd_watcher_afk --ignore-missing-imports

package:
	pyinstaller sd-watcher-afk.spec --clean --noconfirm

clean:
	rm -rf build dist
	rm -rf sd_watcher_afk/__pycache__
