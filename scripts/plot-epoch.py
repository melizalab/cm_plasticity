#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
""" Plot an intracellular epoch for inspection or figure generation """

import datetime
import logging
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from neo import AxonIO
import nbank as nb

from core import setup_log, junction_potential, _units
from graphics import add_scalebar

log = logging.getLogger("plot-epoch")
__version__ = "20221005"


def hide_axes(*axes):
    for ax in axes:
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        ax.set_frame_on(False)


def adjust_raster_ticks(ax, gap=0):
    """Adjust raster marks to have gap pixels between them (sort of)"""
    miny, maxy = ax.get_ylim()
    ht = ax.get_window_extent().height
    for p in ax.lines:
        p.set_markersize(ht / ((maxy - miny)) - gap)


def offset_traces(ax, annotate=False):
    data_ranges = [x.get_ydata().ptp() for x in ax.lines]
    step = max(data_ranges)
    offset = 0
    # these should be in order of insertion
    for i, line in enumerate(ax.lines):
        x = line.get_xdata()
        y = line.get_ydata()
        line.set_ydata(y + offset)
        if annotate:
            ax.text(x[0], y[0] + offset, "%.0f" % y[0], fontsize=7, ha="right")
        offset += step
    ylim = ax.get_ylim()
    ax.set_ylim((ylim[0], ylim[1] + offset))


if __name__ == "__main__":
    import argparse

    # matplotlib.use("Agg", warn=False)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", help="show verbose log messages", action="store_true"
    )
    parser.add_argument("--width", "-W", help="plot width", type=float, default=6)
    parser.add_argument("--height", "-H", help="plot height", type=float, default=8)
    parser.add_argument("--output", "-O", type=Path, help="filename or directory to save plot")
    parser.add_argument("--combine", help="combine voltage plots", action="store_true")
    parser.add_argument("--xlim", "-x", help="set xlim", type=float, nargs=2)
    parser.add_argument(
        "--ylim", "-y", help="set ylim", type=float, nargs=2, default=[-140, 30]
    )
    parser.add_argument(
        "--xscale",
        "-X",
        help="set size of x scale bar (data units)",
        type=float,
        default=500,
    )
    parser.add_argument(
        "--vscale",
        "-V",
        help="set size of voltage scale bar (data units)",
        type=float,
        nargs=2,
        default=20,
    )
    parser.add_argument(
        "--iscale",
        "-I",
        help="set size of current scale bar (data units)",
        type=float,
        nargs=2,
        default=50,
    )
    parser.add_argument(
        "--annotate",
        "-a",
        help="annotate trace with spike threshold",
        action="store_true",
    )
    parser.add_argument("epoch", type=Path, help="epoch pprox file")
    args = parser.parse_args()

    setup_log(log, args.debug)
    log.info("- date: %s", datetime.datetime.now())
    log.info("- version: %s", __version__)
    log.info("- pprox file: %s", args.epoch)
    with open(args.epoch, "rt") as fp:
        pprox = json.load(fp)
    log.info("- neuron resource: %s", pprox["source"])
    registry_url, resource_id = nb.parse_resource_id(pprox["source"])
    resource_path = nb.get(resource_id, registry_url, local_only=True)
    abf_path = (Path(resource_path) / pprox["abf_file"]).with_suffix(".abf")

    log.info("- abf file: %s", abf_path)
    ifp = AxonIO(abf_path)
    block = ifp.read_block(lazy=True)

    # create figure and axes
    nsweeps = len(pprox["pprox"])
    fig = plt.figure(figsize=(args.width, args.height))
    s_ax = fig.add_axes((0.06, 0.80, 0.9, 0.10))
    v_ax = fig.add_axes((0.06, 0.17, 0.9, 0.68), sharex=s_ax)
    i_ax = fig.add_axes((0.06, 0.05, 0.9, 0.10), sharex=s_ax)
    for sweep_idx, segment in enumerate(block.segments):
        log.debug("- sweep %d:", sweep_idx)
        sampling_rate = segment.analogsignals[0].sampling_rate.rescale("kHz")
        sampling_period = segment.analogsignals[0].sampling_period.rescale("ms")
        # we can be fairly confident the signals are okay because this was
        # processed with abf2pprox
        V = (
            (segment.analogsignals[0].load() - junction_potential)
            .rescale(_units["voltage"])
        )
        I = (
            segment.analogsignals[1]
            .load()
            .rescale(_units["current"])
            .squeeze()
            .magnitude
        )
        t = (V.times - V.t_start).rescale("ms")
        V = V.squeeze().magnitude
        v_ax.plot(t, V)
        i_ax.plot(t, I)

        spikes = np.asarray(pprox["pprox"][sweep_idx]["events"]) * 1000
        s_ax.plot(spikes, [sweep_idx] * len(spikes), '|')

    title = "{cell}_{epoch}".format(**pprox)
    fig.text(0.5, 0.95, title, ha="center")
    # tidy up the spikes
    s_ax.set_ylim(0 - 0.5, nsweeps + 0.5)
    adjust_raster_ticks(s_ax, gap=1)
    hide_axes(s_ax)
    # standardize voltage axis
    if not args.combine:
        offset_traces(v_ax, annotate=True)
        add_scalebar(
                v_ax,
                barcolor="black",
                barwidth=0.5,
                sizey=args.vscale,
                labely="{} {}".format(args.vscale, _units["voltage"].symbol),
                sizex=args.xscale,
                labelx="{} {}".format(args.xscale, "ms"),
            )
        add_scalebar(
                i_ax,
                barcolor="black",
                barwidth=0.5,
                sizey=args.iscale,
                labely="{} {}".format(args.iscale, _units["current"].symbol),
                sizex=args.xscale,
                labelx="{} {}".format(args.xscale, "ms"),
            )
    else:
        v_ax.set_ylim(args.ylim)
        v_ax.xaxis.set_visible(False)
    if args.xlim:
        s_ax.set_xlim(args.xlim)

    if args.output is None:
        plt.show()
    elif args.output.is_dir():
        path = (args.output / args.epoch.stem).with_suffix(".pdf")
        log.info("- saving plot to %s", path)
        fig.savefig(path)
    else:
        path = args.output
        log.info("- saving plot to %s", path)
        fig.savefig(path)
