#!/bin/bash

set -e

python3 -m venv .venv
source .venv/bin/activate

pip install pip --upgrade

# Install package in editable mode
# With all dependencies: to be able to run all the tools
pip install -e .[all]

deactivate
