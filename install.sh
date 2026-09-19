#!/usr/bin/env bash
# Tansaku one-line install
# Usage: curl -sSL https://raw.githubusercontent.com/pawellach/tansaku/master/install.sh | bash
set -e

echo "Installing Tansaku..."

if ! command -v python3 &>/dev/null; then
  echo "Error: Python 3.11+ required." >&2; exit 1
fi
if ! command -v pip &>/dev/null; then
  echo "Error: pip required." >&2; exit 1
fi

git clone https://github.com/pawellach/tansaku.git
cd tansaku
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp knowledge-base.example.json knowledge-base.json

echo ""
echo "✓ Tansaku installed."
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml — add your Jira URL, project key, and API keys"
echo "  2. Set environment variables (JIRA_API_TOKEN, ANTHROPIC_API_KEY, ...)"
echo "  3. Run: tansaku setup   # verify connections"
echo "  4. Run: tansaku run --dry-run   # preview without writing to Jira"
