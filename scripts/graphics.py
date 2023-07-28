# -*- coding: utf-8 -*-
# -*- mode: python -*-
""" common functions for graphics """
import matplotlib as mpl
from matplotlib.offsetbox import AnchoredOffsetbox

# from mpl_toolkits.axes_grid1 import Grid
# import mpl_toolkits.axisartist as AA
# import matplotlib.gridspec as gridspec

tickparams = {
    "major.size": 2,
    "minor.size": 1,
    "labelsize": "small",
    "direction": "out",
}
grparams = {
    "font": {"size": 6},
    "axes": {"linewidth": 0.5, "unicode_minus": False},
    "lines": {"linewidth": 0.5},
    "xtick": tickparams,
    "ytick": tickparams,
    "image": {"aspect": "auto", "origin": "lower"},
    "pdf": {"fonttype": 42},
}

RANDOMSEED = 10024

for k, v in grparams.items():
    mpl.rc(k, **v)


class AnchoredScaleBar(AnchoredOffsetbox):
    def __init__(
        self,
        transform,
        sizex=0,
        sizey=0,
        labelx=None,
        labely=None,
        loc=4,
        pad=0.1,
        borderpad=0.1,
        sep=2,
        prop=None,
        barcolor="black",
        barwidth=None,
        **kwargs
    ):
        """
        Draw a horizontal and/or vertical  bar with the size in data coordinate
        of the give axes. A label will be drawn underneath (center-aligned).

        - transform : the coordinate frame (typically axes.transData)
        - sizex,sizey : width of x,y bar, in data units. 0 to omit
        - labelx,labely : labels for x,y bars; None to omit
        - loc : position in containing axes
        - pad, borderpad : padding, in fraction of the legend font size (or prop)
        - sep : separation between labels and bars in points.
        - **kwargs : additional arguments passed to base class constructor
        """
        from matplotlib.offsetbox import (
            AuxTransformBox,
            DrawingArea,
            HPacker,
            TextArea,
            VPacker,
        )
        from matplotlib.patches import Rectangle

        bars = AuxTransformBox(transform)
        if sizex:
            bars.add_artist(
                Rectangle((0, 0), sizex, 0, ec=barcolor, lw=barwidth, fc="none")
            )
        if sizey:
            bars.add_artist(
                Rectangle((0, 0), 0, sizey, ec=barcolor, lw=barwidth, fc="none")
            )

        if sizex and labelx:
            self.xlabel = TextArea(labelx)
            bars = VPacker(children=[bars, self.xlabel], align="center", pad=0, sep=sep)
        if sizey and labely:
            self.ylabel = TextArea(labely)
            bars = HPacker(children=[self.ylabel, bars], align="center", pad=0, sep=sep)

        AnchoredOffsetbox.__init__(
            self,
            loc,
            pad=pad,
            borderpad=borderpad,
            child=bars,
            prop=prop,
            frameon=False,
            **kwargs
        )


def add_scalebar(ax, hidex=True, hidey=True, **kwargs):
    """Add scalebars to axes

    Adds a set of scale bars to *ax*, matching the size to the ticks of the plot
    and optionally hiding the x and y axes

    - ax : the axis to attach ticks to
    - matchx,matchy : if True, set size of scale bars to spacing between ticks
                    if False, size should be set using sizex and sizey params
    - hidex,hidey : if True, hide x-axis and y-axis of parent
    - **kwargs : additional arguments passed to AnchoredScaleBars

    Returns created scalebar object
    """
    if "sizex" not in kwargs:
        xl = ax.xaxis.get_majorticklocs()
        kwargs["sizex"] = len(xl) > 1 and (xl[1] - xl[0])
        kwargs["labelx"] = str(kwargs["sizex"])
    if "sizey" not in kwargs:
        yl = ax.yaxis.get_majorticklocs()
        kwargs["sizey"] = len(yl) > 1 and (yl[1] - yl[0])
        kwargs["labely"] = str(kwargs["sizey"])

    sb = AnchoredScaleBar(ax.transData, **kwargs)
    ax.add_artist(sb)

    if hidex:
        ax.xaxis.set_visible(False)
    if hidey:
        ax.yaxis.set_visible(False)
    if hidex and hidey:
        ax.set_frame_on(False)

    return sb


def simple_axes(*axes):
    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.get_xaxis().tick_bottom()
        ax.get_yaxis().tick_left()


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
