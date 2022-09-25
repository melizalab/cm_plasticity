#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Extract spike times and other statistics from ABF files and store in pprox format.

This script assumes that the data in the ABF file has a pretty specific
structure generated by a current-clamp recording in which the neuron was
stimulated with a single depolarizing step current followed by hyperpolarizing
step currents to check input and series resistance.

"""
import datetime
import logging
import json
from collections import defaultdict
from pathlib import Path

from neo import AxonIO
import nbank as nb
import quantities as pq
import quickspikes as qs
import quickspikes.tools as qst
from quickspikes.intracellular import SpikeFinder

from core import setup_log, json_serializable

log = logging.getLogger()
__version__ = "20220923"

kOhm = pq.UnitQuantity("kiloohm", pq.ohm * 1e3, symbol="kΩ")
MOhm = pq.UnitQuantity("megaohm", pq.ohm * 1e6, symbol="MΩ")
GOhm = pq.UnitQuantity("gigaohm", pq.ohm * 1e9, symbol="GΩ")
pFarad = pq.UnitQuantity("picofarad", pq.farad * 1e-9, symbol="pF")
fFarad = pq.UnitQuantity("femtofarad", pq.farad * 1e-12, symbol="fF")
junction_potential = pq.Quantity(11.6, "mV")  # measured at 32 C


def with_units(unit: pq.UnitQuantity):
    return lambda x: x * unit


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--debug", help="show verbose log messages", action="store_true"
    )
    parser.add_argument(
        "--output-dir",
        "-O",
        type=Path,
        default="build",
        help="directory to store output file (default `%(default)s`)",
    )
    parser.add_argument(
        "--rise-ms",
        type=with_units(pq.ms),
        default=1.0,
        help="approximate rise time for spikes (default %(default).1f ms)",
    )
    parser.add_argument(
        "--first-spike-amplitude-min",
        type=with_units(pq.mV),
        default=30,
        help="minimum amplitude for first spike (default %(default).1f mV)",
    )
    parser.add_argument(
        "--spike-amplitude-min",
        type=with_units(pq.mV),
        default=10,
        help="minimum amplitude for subsequent spikes (default %(default).1f mV)",
    )
    parser.add_argument(
        "--spike-thresh-rel",
        type=float,
        default=0.35,
        help="threshold for dynamic spike detection (default %(default).2f of first spike height)",
    )
    parser.add_argument(
        "--spike-thresh-min",
        type=with_units(pq.mV),
        default=-50,
        help="alternate minimum threshold for spike detection (default %(default).2f mV)",
    )
    parser.add_argument(
        "--spike-analysis-window",
        type=with_units(pq.ms),
        nargs=2,
        default=[-7, 100],
        help="the window around each spike to analyze (default %(default)s ms)",
    )
    parser.add_argument(
        "--spike-upsample",
        type=int,
        default=2,
        help="upsampling ratio for spike shape analysis (default %(default)d)",
    )
    parser.add_argument("neuron", help="identifier for the neuron")
    parser.add_argument("epoch", help="index of the epoch to analyze", type=int)
    args = parser.parse_args()
    setup_log(log, args.debug)
    log.info("- date: %s", datetime.datetime.now())
    log.info("- version: %s", __version__)
    log.info("- analyzing: %s/%s", args.neuron, args.epoch)
    path = nb.get(args.neuron, local_only=True)
    if path is None:
        log.error("  - error: `%s` is not in neurobank registry", args.neuron)
        parser.exit(-1)
    files = sorted(Path(path).glob("*.abf"))
    try:
        abf = files[args.epoch - 1]
    except IndexError:
        log.error("  - error: there is no epoch %d", args.epoch)
        parser.exit(-1)

    log.info("- reading %s", abf)
    ifp = AxonIO(abf)
    block = ifp.read_block(lazy=True)

    pprox = {
        "$schema": "https://meliza.org/spec:2/pprox.json#",
        "source": nb.full_url(args.neuron),
        "epoch": args.epoch,
        "abf_file": abf.stem,
        "timestamp": block.rec_datetime,
        "pprox": []
    }
    # TODO look up subject info from neurobank

    for sweep_idx, segment in enumerate(block.segments):
        log.debug("- sweep %d:", sweep_idx)
        sampling_rate = segment.analogsignals[0].sampling_rate.rescale("kHz")
        sampling_period = segment.analogsignals[0].sampling_period.rescale("ms")
        try:
            V = segment.analogsignals[0].load().rescale("mV").squeeze().magnitude
        except ValueError:
            log.error(
                "   - error: not a current clamp recording (signal 0 units not voltage)"
            )
            parser.exit(-1)
        try:
            I = segment.analogsignals[1].load().rescale("pA").squeeze().magnitude
        except ValueError:
            log.error(
                "   - error: not a current clamp recording (signal 1 units not current)"
            )
            parser.exit(-1)

        trial = {
            "index": sweep_idx,
            "offset": segment.t_start,
            "events": [],
            "marks": defaultdict(list),
            "interval": [0.0 * pq.s, segment.t_stop - segment.t_start]
        }

        # detect spikes
        # we set the threshold based on the amplitude of the first spike
        n_rise = int(args.rise_ms * sampling_rate)
        n_before = int(-args.spike_analysis_window[0] * sampling_rate)
        n_after = int(args.spike_analysis_window[1] * sampling_rate)
        detector = SpikeFinder(n_rise, n_before, n_after)
        try:
            peak, thresh, takeoff, base = detector.calculate_threshold(
                V, args.spike_thresh_rel, args.spike_thresh_min
            )
        except TypeError:
            log.debug("  ✗ no spikes")
            pprox["pprox"].append(trial)
            continue
        if V[peak] - base < args.first_spike_amplitude_min * pq.mV:
            log.debug("  ✗ first spike amplitude is too low")
            pprox["pprox"].append(trial)
            continue
        log.debug(
            "  - first spike: time=%.1f ms, peak=%.1f mV, base=%.1f mV, takeoff=-%.2f ms",
            peak * sampling_period,
            V[peak],
            base,
            takeoff * sampling_period,
        )
        trial.update(spike_base=base, spike_thresh=thresh)
            
        for time, spike in detector.extract_spikes(
            V, args.spike_amplitude_min, args.spike_upsample
        ):
            # calculate statistics
            # add to pprox
            trial["events"].append(time * sampling_period.rescale("s"))
        pprox["pprox"].append(trial)
    
    # output to json
    short_name = args.neuron.split("-")[0]
    output_file = args.output_dir / f"{short_name}_{args.epoch}.pprox"
    with open(output_file, "wt") as fp:
        json.dump(pprox, fp, default=json_serializable)
    log.info("- wrote results to `%s`", output_file)
    
