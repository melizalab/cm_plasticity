
# cm_plasticity

Authors: Yao Lu, Dan Meliza
Status: ongoing
Related projects: cm_devel, cm_physiology

This project looks at how experience affects intrinsic membrane properties in CM. Some of the analyses, particularly the methods used to calculate phasicness, are derived from Chen and Meliza 2018 (cm_physiology) and Chen and Meliza 2020 (cm_devel), but there has been a substantial reorganization and simplification of the analysis pipeline.

The purpose of this file is to identify directories, file, and scripts, as well as instructions on the analysis workflow.

## Setup

poetry is used to manage software dependencies. Run `poetry install` to install any requirements.

## Workflow

1. Deposit data to neurobank archive. The data type needs to be `intracellular-abfdir`, and you **must** ensure that the uuid of the bird is stored as metadata. Example: `nbank deposit -k experimenter=anc4kj -k bird=a44b322f-d582-4b69-87c7-7de4a7945478 -k name=20180709_1_2 -A -d intracellular-abfdir /home/data/intracellular/ 20180709_1_2`
1. Add cells to `inputs/cells.tbl`, and epochs with spiking step currents to `inputs/spkstep_epochs.tbl`
1. `batch/process-abfs.sh inputs/spkstep_epochs.tbl` to extract spike time and other information from the ABF files for all epochs.
