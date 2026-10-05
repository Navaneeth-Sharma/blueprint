#!/bin/bash
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/../_fixtures/seed.sh" explore adr
