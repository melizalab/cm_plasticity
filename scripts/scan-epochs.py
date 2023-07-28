#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- mode: python -*-
""" Scan all the epochs for a cell and output if they are gapfree or epochal """
import datetime
import logging
from pathlib import Path

import nbank as nb
from neo import AxonIO

from core import _units, setup_log

log = logging.getLogger()
__version__ = "20221017"

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--debug", help="show verbose log messages", action="store_true"
    )
    parser.add_argument(
        "--command-channel",
        type=int,
        default=1,
        help="ABF protocol channel with current steps used (default %(default)d)",
    )
    parser.add_argument("neuron", help="identifier for the neuron")
    args = parser.parse_args()
    setup_log(log, args.debug)

    log.info("- date: %s", datetime.datetime.now())
    log.info("- version: %s", __version__)
    log.info("- analyzing: %s", args.neuron)
    info = nb.describe(args.neuron)
    path = nb.get(args.neuron, local_only=True)
    if path is None:
        log.error("  - error: `%s` is not in neurobank registry", args.neuron)
        parser.exit(-1)
    for epoch_idx, abf in enumerate(sorted(Path(path).glob("*.abf")), 1):
        log.debug("- reading %s", abf)
        ifp = AxonIO(abf)
        protocols = ifp.read_protocol()
        sweep_idx = 0
        try:
            Ic = (
                protocols[sweep_idx]
                .analogsignals[args.command_channel]
                .rescale(_units["current"])
                .squeeze()
                .magnitude
            )
        except IndexError:
            log.debug("%s %d: gapfree", args.neuron, epoch_idx)
        except ValueError:
            log.debug("%s %d: not current clamp", args.neuron, epoch_idx)
        else:
            print(f"{args.neuron} {epoch_idx}")
