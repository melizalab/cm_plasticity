#!/bin/bash
set -e
OUTDIR="build/"

mkdir -p ${OUTDIR}
rm -f ${OUTDIR}/*.pprox

grep -v "^#" inputs/spkstep_epochs_test.tbl | \
    poetry run parallel --skip-first-line --colsep ' ' python scripts/abf2pprox.py -O ${OUTDIR} {}
