#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n ${DISPLAY:-} ]]; then
    export QT_QPA_PLATFORM=xcb
fi
exec "$root/.venv/bin/python" "$root/src/dock.py" --profile-dir "$root/perfiles/principal" "$@"
