#!/bin/bash
set -e
OUTDIR="inspect/"
PPROCDIR="build"

mkdir -p ${OUTDIR}
echo "clearing ${OUTDIR}"
rm ${OUTDIR}/*.pdf

echo "generating epoch plots"
poetry run parallel python scripts/plot-epoch.py -O ${OUTDIR} {} ::: ${PPROCDIR}/*.pprox
