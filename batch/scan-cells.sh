#!/bin/bash
set -e

echo "cell epoch"
grep -v "^#" $1 | \
    poetry run parallel --skip-first-line --colsep ' ' python scripts/scan-epochs.py {2}
