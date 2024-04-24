.PHONY: build test package clean

build:
	poetry install
	# if macOS, build swift
	if [ "$(shell uname)" = "Darwin" ]; then \
		make build-swift; \
	fi

build-swift: sd_watcher_window/sd-watcher-window-macos

sd_watcher_window/sd-watcher-window-macos: sd_watcher_window/macos.swift
	swiftc $^ -o $@

test:
	sd-watcher-window --help

typecheck:
	poetry run mypy sd_watcher_window/ --ignore-missing-imports

package:
	pyinstaller sd-watcher-window.spec --clean --noconfirm

clean:
	rm -rf build dist
	rm -rf sd_watcher_window/__pycache__
	rm sd_watcher_window/sd-watcher-window-macos
