#!/bin/bash
# scan-cells runs the scan-epochs script over a batch of cells
set -e
PYTHON=venv/bin/python3

if [[ -t 0 ]]; then
    echo "usage: batch/scan-cells.sh < table_of_cells > table_of_epochs"
    exit 1
fi
echo "cell epoch"
grep -v "^#" | \
    parallel --skip-first-line --colsep ' ' ${PYTHON} scripts/scan-epochs.py {2}
