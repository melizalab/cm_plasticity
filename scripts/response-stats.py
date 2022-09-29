#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Compute electrophysiology stats from epoch pprox files """
import datetime
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core import setup_log

log = logging.getLogger()
__version__ = "20220928"


def load_epoch(path):
    log.debug(" - reading %s", path)
    with open(path, "rt") as fp:
        data = json.load(fp)
        epoch = pd.json_normalize(
            data,
            "pprox",
            ["cell", "epoch", "bird", "sire", ["stats", "tau"], ["stats", "Cm"]],
        )
        return (
            epoch.rename(
                columns={"index": "sweep", "stats.tau": "tau", "stats.Cm": "Cm"}
            )
            .set_index(["cell", "epoch", "sweep"])
            .drop(columns=["offset", "interval"])
        )


def sweep_firing_stats(sweep):
    try:
        step = pd.Interval(*sweep["stimulus.interval"])
        spikes = [e for e in sweep.events if e in step]
        rate = len(spikes) / step.length
        if len(spikes) == 0:
            duration = np.nan
        elif len(spikes) == 1:
            duration = (
                sweep["first_spike.width"] + sweep["first_spike.trough_t"]
            ) / 1000.0
        else:
            duration = spikes[-1] - spikes[0]
    except TypeError:
        rate = duration = np.nan
    return pd.Series(
        {
            "current": sweep["stimulus.I"],
            "firing_rate": rate,
            "firing_duration": duration,
            "Rs": sweep.Rs,
            "Rm": sweep.Rm,
            "Vm": sweep.Vm,
            "temperature": sweep.temperature,
        }
    )


def sweep_iv_stats(sweep):
    """ Extract IV data from sweeps """
    nsteps = len(sweep["steps.I"])
    return pd.Series(
        np.concatenate([sweep["steps.I"], sweep["steps.V"]]),
        index=pd.MultiIndex.from_product(
            [["current", "voltage"], range(nsteps)], names=["value", "step"]
        ),
    )


def epoch_firing_stats(sweeps):
    """ Compute firing stats by epoch """
    # find sweeps with spikes
    (idx,) = (sweeps.firing_rate > 0).to_numpy().nonzero()
    # rheobase is undefined if there are no spikes
    if len(idx) == 0:
        I_0 = np.nan
        slope = 0
    else:
        df = sweeps.iloc[idx[0] - 1 :]
        # rheobase: midpoint between current levels that evoke firing
        I_0 = (df.current[1] + df.current[0]) / 2
        # f-I slope: average of the slopes (simpler and more stable than linear regression)
        slope = np.mean(np.diff(df.firing_rate) / np.diff(df.current))
    return pd.Series(
        {
            "duration_max": sweeps.firing_duration.max(),
            "duration_mean": sweeps.firing_duration.mean(),
            "rate_max": sweeps.firing_rate.max(),
            "rheobase": I_0,
            "slope": slope,
            "Rs": sweeps.Rs.mean(),
            "Rm": sweeps.Rm.mean(),
            "Vm": sweeps.Vm.mean(),
            "temperature": sweeps.temperature.mean(),
        }
    )


def compare_epochs(cell):
    """ Compare all the epochs within a cell and mark ones that may need to be excluded """
    pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--debug", help="show verbose log messages", action="store_true"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default="build",
        help="directory where output files should be stored"
    )
    parser.add_argument(
        "epochs", type=Path, nargs="+", help="epoch pprox files to process"
    )
    args = parser.parse_args()
    setup_log(log, args.debug)
    log.info("- date: %s", datetime.datetime.now())
    log.info("- version: %s", __version__)

    log.info("- loading pprox files")
    sweeps = pd.concat([load_epoch(path) for path in args.epochs])
    cells = (
        sweeps.reset_index()[["cell", "bird", "sire"]]
        .drop_duplicates()
        .set_index("cell")
    )
    epochs = (
        sweeps.reset_index()[["cell", "epoch", "tau", "Cm"]]
        .drop_duplicates()
        .set_index(["cell", "epoch"])
    )
    log.info("- computing sweep-level statistics")
    sweep_stats = sweeps.apply(sweep_firing_stats, axis=1)
    log.info("- computing I-V functions")
    iv_stats = sweeps.apply(sweep_iv_stats, axis=1).stack("step")
    log.info("- computing epoch-level statistics")
    epoch_stats = (
        sweep_stats.groupby(["cell", "epoch"]).apply(epoch_firing_stats).join(epochs)
    )
    out = args.output_dir / "epoch_stats.csv"
    epoch_stats.to_csv(out)
    log.info("  - wrote epoch stats to '%s'", out)
    log.info("- checking for bad epochs")
    
