#!/usr/bin/env python
# coding: utf-8
""" Plot epochs from a neuron for figure generation """
import json
import logging
import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from core import setup_log, junction_potential
from graphics import simple_axes, adjust_raster_ticks, add_scalebar, hide_axes, offset_traces

log = logging.getLogger("plot-plasticity")
__version__ = "20221031"


def load_abf(pprox):
    """Reads the ABF file associated with an epoch """
    import nbank as nb
    from neo.io import AxonIO
    registry_url, resource_id = nb.parse_resource_id(pprox["source"])
    resource_path = nb.get(resource_id, registry_url, local_only=True)
    abf_path = (Path(resource_path) / pprox["abf_file"]).with_suffix(".abf")
    ifp = AxonIO(abf_path)
    return ifp.read_block(lazy=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", help="show verbose log messages", action="store_true"
    )
    parser.add_argument(
        "--build-dir", 
        type=Path, 
        default="build", 
        help="directory where response stats and pprox files are stored", 
    )
    parser.add_argument("--output", "-O", type=Path, help="filename or directory to save plot")
    parser.add_argument(
        "--epoch-list", 
        type=Path, 
        default="inputs/plasticity_epochs.csv", 
        help="file with list of cells/epochs used to analyze plasticity", 
    )
    parser.add_argument(
        "--sweeps", "-s", 
        type=int,
        nargs="+",
        default=[10, 14, 17],
        help="list of sweeps to display", 
    )
    parser.add_argument("cell", help="cell identifier (short)")
    args = parser.parse_args()
    setup_log(log, args.debug)

    iv_stats = pd.read_csv(args.build_dir / "iv_stats.csv", index_col=["cell", "epoch", "sweep"])
    sweep_stats = pd.read_csv(args.build_dir / "sweep_stats.csv", index_col=["cell", "epoch", "sweep"])
    epoch_stats = pd.read_csv(args.build_dir / "epoch_stats.csv", index_col=["cell", "epoch"])
    epoch_list = pd.read_csv(args.epoch_list, index_col=["cell"])
    epoch_list.index = ([x.split("-")[0] for x in epoch_list.index])

    epoch_idx = epoch_list.loc[args.cell].epoch
    epochs = epoch_stats.loc[args.cell].loc[epoch_idx]
    sweeps = sweep_stats.loc[args.cell].loc[epoch_idx]
    steps = iv_stats.loc[args.cell].loc[epoch_idx]

    bin_size = 10
    floor = np.floor(steps.current.min() / bin_size) * bin_size
    ceil  = np.ceil(steps.current.max() / bin_size) * bin_size
    bins = np.arange(floor, ceil + bin_size, bin_size)
    steps_binned = steps.groupby(["epoch", pd.cut(steps.current, bins, labels=False)]).mean()

    fig = plt.figure(figsize=(7.5, 5))
    subfigs = fig.subfigures(1, 3, wspace=0.02)

    axes = subfigs[1].subplots(2, sharex=True)
    for enumber, epoch in steps_binned.groupby("epoch"):
        axes[0].plot(epoch.current, epoch.voltage, label="%d s" % int(epochs.loc[enumber].time))
    axes[0].set_ylabel("V (mV)")
    for enumber, epoch in sweeps.groupby("epoch"):
        axes[1].plot(epoch.current, epoch.firing_rate, label="%d s" % int(epochs.loc[enumber].time))
    axes[1].set_ylabel("Freq (Hz)")
    axes[1].set_xlabel("Current (pA)")
    axes[1].legend()
    simple_axes(*axes)
    subfigs[1].align_ylabels(axes)

    marker_style = {"marker": 'o', "linestyle": 'none', "fillstyle": "none"}
    axes = subfigs[2].subplots(5, sharex=True, height_ratios=(2, 2, 2, 1, 1))
    axes[0].errorbar(epochs.time, epochs.duration_mean, epochs.duration_sd / np.sqrt(epochs.n_spike_sweeps), **marker_style)
    axes[0].set_ylim(0, 2.0)
    axes[0].set_ylabel("Duration (s)")
    axes[1].plot(epochs.time, epochs.slope, **marker_style)
    axes[1].set_ylim(0, epochs.slope.max() * 1.1)
    axes[1].set_ylabel("f-I slope (Hz/pA)")
    axes[2].plot(epochs.time, epochs.rheobase, **marker_style)
    axes[2].set_ylim(0, epochs.rheobase.max() * 1.1)
    axes[2].set_ylabel("rheobase (pA)")
    axes[3].errorbar(epochs.time, epochs.Vm, epochs.Vm_sd / np.sqrt(epochs.n_sweeps), **marker_style)
    axes[3].set_ylim(epochs.Vm.mean() - 10, epochs.Vm.mean() + 10)
    axes[3].set_ylabel("Vm (mV)")                  
    axes[4].errorbar(epochs.time, epochs.Rm, epochs.Rm_sd / np.sqrt(epochs.n_sweeps), **marker_style)
    Rmm = epochs.Rm.mean()
    axes[4].set_ylim(Rmm * 0.7, Rmm * 1.3)
    axes[4].set_ylabel("Rm (MΩ)")
    axes[4].set_xlabel("Time (s)")
    simple_axes(*axes)
    #subfigs[2].subplots_adjust(hspace=0.08)
    subfigs[2].align_ylabels(axes)

    axes = subfigs[0].subplots(6, sharex=True, height_ratios=(2, 3, 0.5, 2, 3, 0.5))
    aidx = 0
    for eidx in [epoch_idx[0], epoch_idx[-1]]:
        s_ax = axes[aidx + 0]
        v_ax = axes[aidx + 1]
        i_ax = axes[aidx + 2]
        pprox = args.build_dir / "{}_{:02}.pprox".format(args.cell, eidx)
        with open(pprox, "rt") as fp:
            epoch = json.load(fp)
        for idx, pproc in enumerate(epoch["pprox"]):
            s_ax.plot(pproc["events"], [idx] * len(pproc["events"]), '|')
        adjust_raster_ticks(s_ax, gap=2)

        block = load_abf(epoch)
        for sidx in args.sweeps:
            segment = block.segments[sidx]
            V = (
                (segment.analogsignals[0].load() - junction_potential)
                .rescale("mV")
            )
            I = (
                segment.analogsignals[1]
                .load()
                .rescale("pA")
            )
            color = s_ax.lines[sidx].get_color()
            t = V.times - V.t_start
            v_ax.plot(t, V.magnitude, color=color)
            i_ax.plot(t, I, color=color)
        offset_traces(v_ax)
        aidx += 3
    hide_axes(axes[0], axes[3])
    simple_axes(axes[1], axes[2], axes[4], axes[5])
    axes[0].set_xlim(0.1, 2.3);

    if args.output is None:
        plt.show()
    elif args.output.is_dir():
        path = (args.output / f"{args.cell}_plasticity").with_suffix(".pdf")
        log.info("- saving plot to %s", path)
        fig.savefig(path)
    else:
        path = args.output
        log.info("- saving plot to %s", path)
        fig.savefig(path)



