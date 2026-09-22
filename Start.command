#!/bin/zsh
cd -- "${0:A:h}" || exit 1
runtime="/Users/morguewhite/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$runtime" ]]; then
  runtime="$(command -v python3)"
fi
if [[ -z "$runtime" ]]; then
  print 'Python 3 is required to run this application.'
  read '?Press Return to close.'
  exit 1
fi
"$runtime" server.py --open
if [[ $? -ne 0 ]]; then
  read '?Press Return to close.'
fi
