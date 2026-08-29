#!/usr/bin/env bash
# Install the zai CLI: symlink to ~/.local/bin, ensure curl_cffi + playwright.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.local/bin"
mkdir -p "$TARGET"
ln -sf "$REPO/zai.py" "$TARGET/zai"
echo "Linked $TARGET/zai -> $REPO/zai.py"

if ! python3 -c "import curl_cffi" 2>/dev/null; then
  echo "Installing curl_cffi (required for HTTP layer)..."
  pip install --quiet curl_cffi || pip install --quiet --break-system-packages curl_cffi
fi
if ! python3 -c "import playwright" 2>/dev/null; then
  echo "Installing playwright (required for 'zai chat')..."
  pip install --quiet playwright || pip install --quiet --break-system-packages playwright
  python3 -m playwright install chromium 2>/dev/null || true
fi
echo "Done. Run: zai login"
