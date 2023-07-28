#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Compute electrophysiology stats from epoch pprox files """
import datetime
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from pandarallel import pandarallel

from core import setup_log

pandarallel.initialize(progress_bar=True)
log = logging.getLogger()
__version__ = "20230105"


def load_epoch(path):
    log.debug(" - reading %s", path)
    with open(path, "rt") as fp:
        data = json.load(fp)
        epoch = pd.json_normalize(
            data,
            "pprox",
            [
                "cell",
                "epoch",
                "bird",
                "age",
                "sex",
                "sire",
                "dam",
                "timestamp",
                ["stats", "tau"],
                ["stats", "Cm"],
            ],
        )
        return (
            epoch.rename(
                columns={"index": "sweep", "stats.tau": "tau", "stats.Cm": "Cm"}
            )
            .set_index(["cell", "epoch", "sweep"])
            .drop(columns=["interval"])
        )


def sweep_iv_stats(sweep):
    """Extract IV data from sweeps"""
    nsteps = len(sweep["steps.I"])
    return pd.Series(
        np.concatenate([sweep["steps.I"], sweep["steps.V"]]),
        index=pd.MultiIndex.from_product(
            [["current", "voltage"], range(nsteps)], names=["value", "step"]
        ),
    )


def iv_deviation(sweep_steps):
    """Determine absolute deviation from median (in MADs)"""
    dev = (sweep_steps - sweep_steps.median()).abs()
    return dev / dev.median()


def iv_slope_rest(iv_stats, frac=0.7, bin_data=False):
    """Get dV/dI (input resistance) around I=0. Uses loess regression for local interpolation"""
    from loess.loess_1d import loess_1d

    log.debug(
        "  - analyzing I-V slope for %s_%02d",
        iv_stats.index[0][0],
        iv_stats.index[0][1],
    )
    I_min = iv_stats.current.min()
    I_max = iv_stats.current.max()
    # loess regression may fail horribly if the data are not binned
    if bin_data:
        bins = pd.interval_range(np.floor(I_min), np.ceil(I_max))
        cuts = pd.cut(iv_stats.current, bins)
        binned = iv_stats.groupby(cuts).agg("mean").dropna()
    else:
        binned = iv_stats
    # interpolate right around I=0, with slight weight toward depolarized voltages
    xnew = np.arange(-5, 10, 0.1)
    try:
        xout, yout, _ = loess_1d(
            binned.current.to_numpy(),
            binned.voltage.to_numpy(),
            xnew=xnew,
            degree=1,
            frac=frac,
            npoints=None,
            rotate=False,
            sigy=None,
        )
    except SystemError:
        log.warning(
            "  - loess failed to converge for %s_%02d",
            iv_stats.index[0][0],
            iv_stats.index[0][1],
        )
        return np.nan
    smoothed = pd.DataFrame({"current": xout, "voltage": yout})
    return (smoothed.voltage.diff() / smoothed.current.diff()).mean() * 1000


def sweep_firing_stats(sweep):
    try:
        step = pd.Interval(*sweep["stimulus.interval"])
        spikes = [e for e in sweep.events if e in step]
        n_spikes = len(spikes)
        rate = n_spikes / step.length
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
        n_spikes = 0
    # spontaneous spikes
    spont_interval = pd.Interval(*sweep["spont_interval"])
    spont_spikes = [e for e in sweep.events if e in spont_interval]
    return pd.Series(
        {
            "current": sweep["stimulus.I"],
            "firing_rate": rate,
            "firing_duration": duration,
            "Rs": sweep.Rs,
            "Rm": sweep.Rm,
            "Vm": sweep.Vm,
            "temperature": sweep.temperature,
            "spike_width": sweep["first_spike.width"],
            "spike_trough": sweep["first_spike.trough_t"],
            "n_evoked": n_spikes,
            "n_spont": len(spont_spikes),
        }
    )


def epoch_firing_slope(sweeps):
    """Computes Δf/ΔI for all sweeps above rheobase"""
    (idx,) = (sweeps.firing_rate > 0).to_numpy().nonzero()
    # if there are no spikes, slope is undefined for all sweeps
    if len(idx) == 0:
        return pd.Series(np.nan, index=sweeps.index)
    # otherwise, slope is only undefined below the rheobase
    slope = sweeps.firing_rate.diff() / sweeps.current.diff()
    slope.iloc[: idx[0]] = np.nan
    return slope


def epoch_firing_stats(sweeps):
    """Compute firing stats by epoch"""
    # epoch_firing_slope already determines the rheobase, so we just need to
    # find the first valid index
    try:
        fr_slope = sweeps.firing_rate_slope
        slope = fr_slope.mean()
        idx = fr_slope.index.get_loc(fr_slope.first_valid_index())
        # this will be nan if idx is 0, which corresponds to spikes when zero
        # current was injected
        I_0 = sweeps.current.iloc[idx - 1 : idx + 1].mean()
    except KeyError:
        # if there are no spikes, rheobase is undefined and slope is zero
        I_0 = np.nan
        slope = 0
    return pd.Series(
        {
            "n_sweeps": sweeps.shape[0],
            "duration_max": sweeps.firing_duration.max(),
            "duration_mean": sweeps.firing_duration.mean(),
            "duration_sd": sweeps.firing_duration.std(),
            "rate_max": sweeps.firing_rate.max(),
            "rheobase": I_0,
            "slope": slope,
            "Rs": sweeps.Rs.mean(),
            "Rs_sd": sweeps.Rs.std(),
            "Rm": sweeps.Rm.mean(),
            "Rm_sd": sweeps.Rm.std(),
            "Vm": sweeps.Vm.mean(),
            "Vm_sd": sweeps.Vm.std(),
            "temperature": sweeps.temperature.mean(),
            "spike_width": sweeps.spike_width.mean(),
            "spike_trough": sweeps.spike_trough.mean(),
            "n_evoked": sweeps.n_evoked.sum(),
            "n_spont": sweeps.n_spont.sum(),
        }
    )


def write_results(df, path, name):
    df.to_csv(path)
    log.info("  - wrote %s to '%s'", name, path)


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
        help="directory where output files should be stored",
    )
    parser.add_argument(
        "--max-Vm-deviance",
        type=float,
        default=10.0,
        help="exclude sweeps where Vm deviates over this value (default %.1f MADs)",
    )
    parser.add_argument(
        "epochs", type=Path, nargs="+", help="epoch pprox files to process"
    )
    args = parser.parse_args()
    setup_log(log, args.debug)
    log.info("- date: %s", datetime.datetime.now())
    log.info("- version: %s", __version__)

    log.info("- loading %d pprox files", len(args.epochs))
    sweeps = pd.concat([load_epoch(path) for path in args.epochs])
    cells = (
        sweeps.reset_index()[["cell", "bird", "age", "sex", "sire", "dam"]]
        .drop_duplicates()
        .set_index("cell")
    )
    epochs = (
        sweeps.reset_index()[["cell", "epoch", "timestamp", "tau", "Cm"]]
        .drop_duplicates()
        .set_index(["cell", "epoch"])
    )
    ts = epochs.pop("timestamp").apply(pd.Timestamp)
    epochs["time"] = (
        ts.groupby(["cell"], group_keys=False)
        .apply(lambda x: (x - x.iloc[0]))
        .apply(lambda x: x.total_seconds())
    )
    log.info("- computing I-V functions")
    iv_stats = sweeps.parallel_apply(sweep_iv_stats, axis=1)
    log.info("- checking for bad sweeps (Vm deviance)")
    v_dev = (
        iv_stats["voltage"]
        .groupby(["cell", "epoch"], group_keys=False)
        .parallel_apply(iv_deviation)
    )
    # only look at baseline and hyperpolarization steps
    bad_sweeps = (v_dev[[0, 2, 3, 4]] > args.max_Vm_deviance).any(axis=1)
    log.info("  - excluded %d sweeps", bad_sweeps.sum())

    sweeps = sweeps.loc[~bad_sweeps]
    iv_stats = iv_stats.loc[~bad_sweeps].stack("step")

    log.info("- computing sweep-level statistics")
    sweep_stats = sweeps.parallel_apply(sweep_firing_stats, axis=1)
    sweep_slope_stats = (
        sweep_stats.groupby(["cell", "epoch"], group_keys=False)
        .apply(epoch_firing_slope)
        .rename("firing_rate_slope")
    )
    sweep_stats = sweep_stats.join(sweep_slope_stats)
    write_results(iv_stats, args.output_dir / "iv_stats.csv", "I-V steps")
    write_results(sweep_stats, args.output_dir / "sweep_stats.csv", "sweep statistics")

    log.info("- computing epoch-level statistics")
    epoch_stats = (
        sweep_stats.groupby(["cell", "epoch"]).apply(epoch_firing_stats).join(epochs)
    )
    r_dev = (
        epoch_stats[["Rs", "Rm"]]
        .groupby("cell", group_keys=False)
        .apply(lambda x: (x - x.iloc[0]) / x.iloc[0].abs())
        .rename(columns=lambda s: f"delta_{s}")
    )
    v_dev = (
        epoch_stats[["Vm"]]
        .groupby("cell", group_keys=False)
        .apply(lambda x: (x - x.iloc[0]))
        .rename(columns=lambda s: f"delta_{s}")
    )
    # NB: cumulative sum is the number of spikes before each epoch
    cum_spikes = (
        epoch_stats.groupby("cell", group_keys=False)
        .apply(
            lambda df: (df["n_spont"] + df["n_evoked"]).shift(1, fill_value=0).cumsum()
        )
        .rename("cum_spikes")
    )

    # to do: print out the epochs that deviate too much
    write_results(
        epoch_stats.join([r_dev, v_dev, cum_spikes]),
        args.output_dir / "epoch_stats.csv",
        "epoch statistics",
    )
    write_results(cells, args.output_dir / "cell_info.csv", "cell info")
