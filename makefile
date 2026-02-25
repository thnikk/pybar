.PHONY: help clean build install dev-install test lint format run

# Project configuration
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
SPEC_FILE := pybar.spec
DIST_DIR := dist
BUILD_DIR := build
INSTALL_DIR := $(HOME)/.local/bin
APP_NAME := pybar

help:
	@echo "Available targets:"
	@echo "  install      - Symlink binary to ~/.local/bin/"
	@echo "  dev-install  - Install development dependencies"
	@echo "  build        - Build executable with PyInstaller"
	@echo "  clean        - Remove build artifacts"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code"
	@echo "  run          - Run the application"

install: build
	@mkdir -p $(INSTALL_DIR)
	ln -sf $(CURDIR)/$(DIST_DIR)/$(APP_NAME)/$(APP_NAME) $(INSTALL_DIR)/$(APP_NAME)
	@echo "Linked $(APP_NAME) to $(INSTALL_DIR)"

dev-install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

build:
	$(VENV)/bin/pyinstaller $(SPEC_FILE) --noconfirm

clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.spec~" -delete

test:
	$(PYTHON) -m pytest tests/

lint:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m pylint .

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

run:
	$(PYTHON) main.py
