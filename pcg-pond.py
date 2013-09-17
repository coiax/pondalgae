#!/usr/bin/env python

from pycallgraph import PyCallGraph, Config, GlobbingFilter
from pycallgraph.output import GraphvizOutput

import pond

graphviz = GraphvizOutput(output_file='out.png')
config = Config()
config.trace_filter = GlobbingFilter(exclude=[
    'argparse.*',
    'pycallgraph.*',
])

with PyCallGraph(output=graphviz, config=config):
    pond._main()
