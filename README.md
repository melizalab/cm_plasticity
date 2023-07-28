
# cm_plasticity

This repository contains the analysis code used in Lu et al, "Rapid, activity-dependent intrinsic plasticity in the developing zebra finch auditory cortex". The manuscript is currently under review but is available as a [preprint](https://doi.org/10.1101/2023.02.07.527481) on bioRxiv.

## Setup

Create a virtual environment and install dependencies:

``` shell
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## Get the data

The first step in the analysis extracts information about current injections and spike times from the raw intracellular recording data, which was generated in Axon Binary Format. Once the paper is published, the output of this step can be downloaded from [figshare](https://dx.doi.org/10.6084/m9.figshare.23799951) as a zip archive [here](https://figshare.com/ndownloader/files/41745645). Unpack the zip file, making sure that the files go into a `build` directory under this directory.

All of the other data and metadata for the analysis can be found in the `inputs` subdirectory:

- `immuno_counts.csv`: counts of immunopositive neurons in confocal images of CM sections from PR and CR animals
- `em_counts.csv`: counts of immunopositive clusters in electron microscopy images of CM sections from PR and CR animals
- `biocytin_cells.csv`: manual classification of biocytin- and Kv1.1-labeled cells as Kv1.1-positive/negative
- `kv11_puncta.csv`: automated (CellProfiler) counts of Kv1.1 puncta in biocytin-labeled neurons
- `plasticity_epochs.csv`: metadata for recording epochs examining plasticity under various conditions
- `reversal_epochs.csv`: metadata for recording epochs examining pharamcological reversal of plasticity

## Analysis

1. On our local cluster, we ran `batch/process-abfs.sh < inputs/spkstep_epochs.tbl` to extract spike times and other metadata from the raw ABF files and store them in pprox files. Skip this step if you're using the pprox files from figshare.
2. Run `venv/bin/python scripts/response-stats.py --output-dir build build/*.pprox` to collate data from all the pprox files.
3. `scripts/immuno.R` has the analysis code for the immunohistochemistry (Fig 1)
4. `scripts/colocalization.R` has the analysis code comparing Kv1.1 expression to intrinsic dynamics (Fig 2)
5. `scripts/plasticity.R` quantifies plasticity in CR, PR, minimal injection, and BAPTA-AM conditions (Figs 3, 4, 6, 7)
6. `scripts/reversal.R` tests whether 4-AP and/or alpha-dendrotoxin reverse intrinsic plasticity

