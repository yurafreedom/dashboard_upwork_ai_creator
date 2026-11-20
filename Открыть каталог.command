#!/bin/zsh
cd -- "${0:A:h}"
exec python3 -B site/server.py --open

