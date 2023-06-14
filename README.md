
# cm_plasticity

Authors: Yao Lu, Dan Meliza
Status: ongoing
Related projects: cm_devel, cm_physiology

This project looks at how experience affects intrinsic membrane properties in CM. Some of the analyses, particularly the methods used to calculate phasicness, are derived from Chen and Meliza 2018 (cm_physiology) and Chen and Meliza 2020 (cm_devel), but there has been a substantial reorganization and simplification of the analysis pipeline.

The purpose of this file is to identify directories, file, and scripts, as well as instructions on the analysis workflow.

## Setup

Create a virtual environment and install dependencies:

``` shell
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

If your goal is to reproduce the last good analysis, you should install dependencies from the `requirements.txt` file.

``` shell
python -m pip install -r requirements.txt
```

If you're doing development, you should instead install the most recent versions of all the dependencies:

``` shell
python -m pip install -e .
```

If you want to use Jupyter Lab, you'll need to install that as well:

``` shell
python -m pip install jupyterlab==3.4.3
```

## Running the code

You'll always need to activate your venv (`source venv/bin/activate`) before running any scripts or the jupyter lab server.

See the [lab wiki](https://gracula.psyc.virginia.edu/wiki/Computing/RemotePythonGuide/) for instructions on how to run a persistent jupyter lab server for your project.

## Workflow

1. Deposit data to neurobank archive. The data type needs to be `intracellular-abfdir`, and you **must** ensure that the uuid of the bird is stored as metadata. Example: `nbank deposit -k experimenter=anc4kj -k bird=a44b322f-d582-4b69-87c7-7de4a7945478 -k name=20180709_1_2 -A -d intracellular-abfdir /home/data/intracellular/ 20180709_1_2`
2. Add cells to `inputs/cells_new.tbl`.
3. Scan the the recordings for current step epochs: `batch/scan-cells.sh < inputs/cells_new.tbl > inputs/spkstep_epochs_new.tbl`
4. Process the recordings to generate pprox files: `batch/process-abfs.sh < inputs/spkstep_epochs_new.tbl`
5. Plot the recordings (this will plot every pprox in the `build` directory): `batch/plot-epochs.sh`
6. Remove any obviously bad epochs from `inputs/spkstep_epochs_new.tbl`
7. Add the epochs to `inputs/plasticity_epochs.csv`, `inputs/reversal_epochs.csv`, or `inputs/colocalization_epochs.csv` depending on which experiment you ran.
8. Move the new cells from `inputs/cells_new.tbl` to `inputs/cells.tbl` and the new epochs from `inputs/spkstep_epochs_new.tbl` to `inputs/spkstep_epochs.tbl`. 
9. Run `batch/process-abfs.sh < inputs/spkstep_epochs.tbl` to process all of your epochs
10. Run `scripts/response-stats.py --output-dir build build/*.pprox`
10. Check the updated control files (`.tbl` and `.csv` files in the `inputs` directory) into version control.
11. Delete `inputs/cells_new.tbl` and `inputs/spkstep_epochs_new.tbl` to clear the decks for the next time.

