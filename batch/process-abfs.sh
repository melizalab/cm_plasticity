#!/bin/bash
set -e
PYTHON=venv/bin/python
OUTDIR="build/"

if [[ -t 0 ]]; then
    echo "usage: ${0} < table_of_epochs"
    exit 1
fi

mkdir -p ${OUTDIR}
echo "clearing ${OUTDIR}"
rm -f ${OUTDIR}/*.pprox

grep -v "^#" | \
    parallel --skip-first-line --colsep ' ' ${PYTHON} scripts/abf2pprox.py -O ${OUTDIR} ${OPTIONS} {}
