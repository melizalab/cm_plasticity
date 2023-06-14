#!/bin/bash
set -e
OUTDIR="inspect/"
PPROCDIR="build"
PYTHON=venv/bin/python

mkdir -p ${OUTDIR}
echo "clearing ${OUTDIR}"
rm ${OUTDIR}/*.pdf

echo "generating epoch plots"
parallel ${PYTHON} scripts/plot-epoch.py -O ${OUTDIR} {} ::: ${PPROCDIR}/*.pprox
