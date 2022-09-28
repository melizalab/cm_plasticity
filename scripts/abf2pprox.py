#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
"""Extract spike times and other statistics from ABF files and store in pprox format.

This script assumes that the data in the ABF file has a pretty specific
structure generated by a current-clamp recording in which the neuron was
stimulated with a single depolarizing step current followed by hyperpolarizing
step currents to check input and series resistance. 

For the script to successfully determine when these steps start and stop, the
user has to point it to the ABF channel that contains the command protocol using
`--command-channel`.

"""
import datetime
import logging
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from neo import AxonIO
import nbank as nb
import quantities as pq
import quickspikes.tools as qst
from quickspikes.intracellular import SpikeFinder, spike_shape, fit_exponentials

from core import setup_log, json_serializable, Interval

log = logging.getLogger()
__version__ = "20220923"

kOhm = pq.UnitQuantity("kiloohm", pq.ohm * 1e3, symbol="kΩ")
MOhm = pq.UnitQuantity("megaohm", pq.ohm * 1e6, symbol="MΩ")
GOhm = pq.UnitQuantity("gigaohm", pq.ohm * 1e9, symbol="GΩ")
pFarad = pq.UnitQuantity("picofarad", pq.farad * 1e-12, symbol="pF")
fFarad = pq.UnitQuantity("femtofarad", pq.farad * 1e-15, symbol="fF")
junction_potential = pq.Quantity(11.6, "mV")  # measured at 32 C

_units = {
    "voltage": pq.mV,
    "current": pq.pA,
    "resistance": MOhm,
    "time": pq.ms,
    "temperature": "C",
    "capacitance": pFarad,
}

# some hard-coded intervals
interval_padding = 2 * pq.ms
steady_interval_depol = 300 * pq.ms
steady_interval_hypol = 150 * pq.ms


def with_units(unit: pq.UnitQuantity):
    return lambda x: x * unit


def first_index(fn, seq):
    """Returns the index of the first value in seq where fn(x) is True"""
    return next((i for (i, x) in enumerate(seq) if fn(x)), None)


def series_resistance(current, voltage, idx, i_before, i_after):
    """Calculates ΔV/ΔI around idx. The differences are calculated using the
    mean of current and voltage between [idx - i_before, idx) and the spot value
    of current and voltage at idx + i_after.

    """
    before = Interval(idx - i_before, idx, None)
    dI = before.mean_of(current) - current[idx + i_after]
    dV = before.mean_of(voltage) - voltage[idx + i_after]
    return (dV * _units["voltage"]) / (dI * _units["current"])


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
    parser.add_argument(
        "--compute-stats",
        action="store_true",
        help="if set, compute and store spike shape statistics",
    )
    parser.add_argument(
        "--command-channel",
        type=int,
        default=1,
        help="ABF protocol channel with current steps used (default %(default)d)",
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
    protocols = ifp.read_protocol()

    pprox = {
        "$schema": "https://meliza.org/spec:2/pprox.json#",
        "source": nb.full_url(args.neuron),
        "units": _units,
        "epoch": args.epoch,
        "abf_file": abf.stem,
        "timestamp": block.rec_datetime,
        "pprox": [],
    }
    # TODO look up subject info from neurobank

    hypol_I = []
    hypol_V = []

    for sweep_idx, segment in enumerate(block.segments):
        log.debug("- sweep %d:", sweep_idx)
        sampling_rate = segment.analogsignals[0].sampling_rate.rescale("kHz")
        sampling_period = segment.analogsignals[0].sampling_period.rescale("ms")
        try:
            V = (
                segment.analogsignals[0]
                .load()
                .rescale(_units["voltage"])
                .squeeze()
                .magnitude
            )
        except ValueError:
            log.error(
                "   - error: not a current clamp recording (signal 0 units not voltage)"
            )
            parser.exit(-1)
        try:
            I = (
                segment.analogsignals[1]
                .load()
                .rescale(_units["current"])
                .squeeze()
                .magnitude
            )
        except ValueError:
            log.error(
                "   - error: not a current clamp recording (signal 1 units not current)"
            )
            parser.exit(-1)
        try:
            Ic = (
                protocols[sweep_idx]
                .analogsignals[args.command_channel]
                .rescale(_units["current"])
                .squeeze()
                .magnitude
            )
        except IndexError:
            log.error(
                "   - error: no protocol information - gapfree?",
                args.command_channel,
            )
            parser.exit(-1)
        except ValueError:
            log.error(
                "   - error: protocol channel %d is not in units of current",
                args.command_channel,
            )
            parser.exit(-1)
        try:
            T = segment.analogsignals[2].load().rescale(_units["temperature"]).mean()
        except ValueError:
            T = None
        # values are truncated to make finding zeros easier
        step_len, step_start, step_val = qst.runlength_encode(Ic.astype("i"))
        step_end = step_start + step_len
        if len(step_len) == 0:
            log.error(
                "   - error: protocol channel %d does not have any current steps",
                args.command_channel,
            )
            parser.exit(-1)

        trial = {
            "index": sweep_idx,
            "offset": segment.t_start,
            "events": [],
            "interval": [0.0 * pq.s, segment.t_stop - segment.t_start],
            "temperature": T,
            # "stimulus": list(
            #     summarize_currents(I, step_start, step_len, sampling_period)
            # ),
        }
        if args.compute_stats:
            trial["marks"] = defaultdict(list)

        # detect spikes
        # we set the threshold based on the amplitude of the first spike
        n_rise = int(args.rise_ms * sampling_rate)
        n_before = int(-args.spike_analysis_window[0] * sampling_rate)
        n_after = int(args.spike_analysis_window[1] * sampling_rate)
        detector = SpikeFinder(n_rise, n_before, n_after)
        first_spike = detector.calculate_threshold(
            V, args.spike_thresh_rel, args.spike_thresh_min
        )
        if first_spike is None:
            log.debug("  ✗ no spikes")
        elif (
            first_spike.peak_V - first_spike.takeoff_V
            < args.first_spike_amplitude_min * pq.mV
        ):
            log.debug("  ✗ first spike amplitude is too low")
        else:
            trial.update(
                spike_base=first_spike.takeoff_V, spike_thresh=detector.spike_thresh
            )
            for time, spike in detector.extract_spikes(
                V, args.spike_amplitude_min, args.spike_upsample
            ):
                trial["events"].append(time * sampling_period.rescale("s"))
                if args.compute_stats:
                    shape = spike_shape(spike, sampling_period)
                    for k, v in zip(shape._fields, shape):
                        trial["marks"][k].append(v)

        # parsing the command steps. Only expected to work for the current
        # protocols used in this project, which consist of one depolarizing step
        # (which may be 0 amplitude) and two nested hyperpolarizing steps (e.g.
        # -50, -100, -50). Each of the intervals is treated differently.
        steps = {"I": [], "V": []}
        # baseline: use the whole interval. Spikes are not filtered out.
        padding_samples = int(interval_padding * sampling_rate)
        steady_hypol_samples = int(steady_interval_hypol * sampling_rate)
        step = first_index(lambda x: x == 0, step_val)
        interval = Interval(
            step_start[step] + padding_samples,
            step_end[step] - padding_samples,
            sampling_period,
        )
        steps["I"].append(interval.mean_of(I))
        steps["V"].append(interval.mean_of(V))
        # depolarization: use the last part. voltage is nan if there are spikes
        step = first_index(lambda x: x > 0, step_val) or 0
        interval = Interval(
            step_end[step] - int(steady_interval_depol * sampling_rate),
            step_end[step] - padding_samples,
            sampling_period,
        )
        steps["I"].append(interval.mean_of(I))
        steps["V"].append(interval.mean_of(V, trial["events"]))
        if step > 0:
            trial["stimulus"] = {
                "I": steps["I"][-1],
                "interval": Interval(
                    step_start[step], step_end[step], sampling_period
                ).times,
            }
        # hyperpolarization
        step = first_index(lambda x: x < 0, step_val)
        interval = Interval(
            step_end[step] - steady_hypol_samples,
            step_end[step] - padding_samples,
            sampling_period,
        )
        steps["I"].append(interval.mean_of(I))
        steps["V"].append(interval.mean_of(V, trial["events"]))
        hypol_I.append(I[step_start[step] : step_end[step]])
        hypol_V.append(V[step_start[step] : step_end[step]])
        Rs_1 = series_resistance(
            I, V, step_start[step], padding_samples, int(sampling_rate * pq.ms)
        )
        Rm_1 = (
            (steps["V"][-1] - steps["V"][0])
            / (steps["I"][-1] - steps["I"][0])
            * _units["voltage"]
            / _units["current"]
        )
        # hyperpolarization step 2
        step = step + 1
        interval = Interval(
            step_end[step] - steady_hypol_samples,
            step_end[step] - padding_samples,
            sampling_period,
        )
        steps["I"].append(interval.mean_of(I))
        steps["V"].append(interval.mean_of(V, trial["events"]))
        Rs_2 = series_resistance(
            I, V, step_start[step], padding_samples, int(sampling_rate * pq.ms)
        )
        Rm_2 = (
            (steps["V"][-1] - steps["V"][-2])
            / (steps["I"][-1] - steps["I"][-2])
            * _units["voltage"]
            / _units["current"]
        )
        trial["steps"] = steps
        trial["Rs"] = (Rs_1 + Rs_2).rescale(_units["resistance"]) / 2
        trial["Rm"] = (Rm_1 + Rm_2).rescale(_units["resistance"]) / 2
        pprox["pprox"].append(trial)

    # calculate tau and Cm from the average of all sweeps
    hI = np.mean(hypol_I, axis=0)
    hV = np.mean(hypol_V, axis=0)
    params, est = fit_exponentials(
        hV, 2, 20, sampling_period.rescale(_units["time"]), axis=0
    )
    err = np.mean((hV - est) ** 2)
    # use the faster component with positive amplitude
    pos = params["amplitude"] > 0
    idx = params["lifetime"][pos].argmin()
    tau = params["lifetime"][pos][idx] * _units["time"]
    dV = params["amplitude"][pos][idx] * _units["voltage"]
    dI = (hI[0] - hI[-steady_hypol_samples:].mean()) * _units["current"]
    # This Rm should not be used, because it reflects both the sag and the leak
    # current. It's only used to get Cm from the time constant.
    Rm = (dV / dI).rescale(_units["resistance"])
    pprox["epoch_stats"] = {
        "tau": tau,
        "Cm": (tau / Rm).rescale(_units["capacitance"]),
        "mse": err,
    }

    # output to json
    short_name = args.neuron.split("-")[0]
    output_file = args.output_dir / f"{short_name}_{args.epoch}.pprox"
    with open(output_file, "wt") as fp:
        json.dump(pprox, fp, default=json_serializable)
    log.info("- wrote results to `%s`", output_file)
