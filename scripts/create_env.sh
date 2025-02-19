#!/bin/bash

set -e  # Exit immediately if any command fails

echo "Adding system packages"
apt-get update && apt-get install -y tmux tree

echo "Installing project requirements"
python -m pip install --upgrade pip
pip install -r ./requirements.txt

echo "Configuring Git"
git config --global user.name "Sam Hardy"
git config --global user.email "samhardyhey@gmail.com"