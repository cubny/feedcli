#!/usr/bin/env bash
# feedcli skill installer — installs the feedcli Python package and its
# dependencies from the pinned source in requirements.txt.
#
# Usage:
#   bash skills/feedcli/install.sh
#
# Requirements:
#   - python3 and pip must be available on PATH

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v pip >/dev/null 2>&1 || { echo "Error: pip not found on PATH. Install Python and pip first." >&2; exit 1; }

echo "Installing feedcli skill dependencies..."
pip install -r "${SCRIPT_DIR}/requirements.txt"
echo "Done. feedcli skill is ready to use."
