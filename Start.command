#!/bin/zsh
cd -- "${0:A:h}" || exit 1
runtime="$(command -v python3)"
if [[ -z "$runtime" ]]; then
  print 'Python 3 is required to run this application.'
  read '?Press Return to close.'
  exit 1
fi

# Make sure Ollama is running and the model is loaded into memory, in the
# background, so the first "Analyze request" click doesn't stall on a cold
# start during a demo. The app still works without this (rule-based
# findings never depend on it); this just warms the optional explanation.
if ! curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  open -ga Ollama 2>/dev/null
fi
(
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
  curl -s -m 60 http://127.0.0.1:11434/api/generate \
    -d '{"model":"llama3.2:3b","prompt":"Say ready.","stream":false,"keep_alive":"30m"}' \
    >/dev/null 2>&1
) &

"$runtime" server.py --open
if [[ $? -ne 0 ]]; then
  read '?Press Return to close.'
fi
