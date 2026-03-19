---
title: "Setup"
weight: 1
---

## Installation

### Archlinux and derivatives
Pybar is available in the AUR as `pybar-bin`.

### Ubuntu 25.10
This is the most recent version of ubuntu that provides `gtk4-layer-shell` in the official repos. A release for ubuntu is provided on github.

### Other distros
You should be able to run pybar on any distro that provides `gtk4-layer-shell`, but you may need to run it directly through python or make your own pyinstaller binary.

## Development

I've included a makefile for simplifying venv setup and building with pyinstaller. The simple workflow is:

- `make setup` sets up a virtual environment in `.venv` and installs dependencies from `requirements.txt`
- `make build` creates the pyinstaller executable.
- `make install` symlinks the executable to `~/.local/bin`
