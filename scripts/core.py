# -*- coding: utf-8 -*-
# -*- mode: python -*-
from typing import Iterable, Optional, Tuple
import logging
import numpy as np
import quantities as pq
from functools import singledispatch


def setup_log(log, debug=False):
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    loglevel = logging.DEBUG if debug else logging.INFO
    log.setLevel(loglevel)
    ch.setLevel(loglevel)
    ch.setFormatter(formatter)
    log.addHandler(ch)


class Interval:
    """Class for facilitating selecting samples from time series"""

    def __init__(self, start_index: int, end_index: int, sampling_period: float):
        self.start_index = start_index
        self.end_index = end_index
        self.sampling_period = sampling_period

    @property
    def slice(self) -> slice:
        return slice(self.start_index, self.end_index)

    @property
    def times(self) -> Tuple[float, float]:
        return (self.start_index * self.sampling_period, self.end_index * self.sampling_period)
                
    def contains(self, events: Iterable[float]) -> bool:
        start, end = self.times
        return any((ev >= start and ev < end) for ev in events)

    def mean_of(
        self, timeseries: np.ndarray, events: Optional[Iterable[float]] = None
    ) -> Optional[float]:
        if events is not None and self.contains(events):
            return None
        return timeseries[self.slice].mean()


@singledispatch
def json_serializable(val):
    """Serialize a value for the json module."""
    return str(val)


@json_serializable.register(pq.Quantity)
def __js_quantity(val):
    """Used for scalar quantities with units"""
    return val.magnitude.item()


@json_serializable.register(np.generic)
def __js_numpy(val):
    """Used if *val* is an instance of a numpy scalar."""
    return val.item()


@json_serializable.register(np.ndarray)
def __js_numpy_arr(arr):
    """Used if *arr* is an instance of a numpy array."""
    return arr.tolist()
