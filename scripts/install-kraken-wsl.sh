#!/usr/bin/env bash
set -euo pipefail
if [ -x "$HOME/.cargo/bin/kraken" ]; then
  exec "$HOME/.cargo/bin/kraken" --version
fi
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
# shellcheck disable=SC1091
source "$HOME/.cargo/env" 2>/dev/null || export PATH="$HOME/.cargo/bin:$PATH"
kraken --version
which kraken
