#    PondALGAE - A simulated networked life simulation
#    Copyright (C) 2013  Jack Edge
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
import sys
import os
import os.path
import random
import datetime
import bitstring

import pyglet
import pyglet.window
import pyglet.graphics
import pyglet.gl
import pyglet.app
import pyglet.clock

import algae
import pond
from constants import *

class PondWindow(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(PondWindow, self).__init__(*args, **kwargs)

        self.pond = pond.Pond(size=self.get_size())
        self.tick_counter = 0
        self.last_draw = datetime.datetime.now()

        self.fpses = []

        pyglet.clock.schedule_interval(self.do_pond_things, 0.01)
        pyglet.clock.set_fps_limit(1)

    def do_pond_things(self, dt):
        self.pond.tick(self.tick_counter)
        self.tick_counter += 1

    def on_draw(self):
        now = datetime.datetime.now()
        dt = (now - self.last_draw).total_seconds()
        if self.last_draw is not None and dt < 1.0:
            return

        self.last_draw = now
        self.clear()

        for coord in self.pond.normal_space:
            if coord in self.pond.pond:
                cell = self.pond.pond[coord]
            else:
                cell = None
            draw = False
            if cell is not None and (cell.alive or cell.inanimate):
                draw = True

            if draw:
                self._set_pixel(coord, cell.colour)
            else:
                light_level = self.pond.light_level[coord]

                r = random.Random(light_level)

                self._set_pixel(coord,
                                tuple(r.randint(0,255) for i in range(4)))

        self.fpses.append(pyglet.clock.get_fps())

    def _set_pixel(self, coord, colour):
        pyglet.graphics.draw(1, pyglet.gl.GL_POINTS,
                             ('v2i', coord),
                             ('c4B', colour))

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v','--verbose',action='store_true')
    parser.add_argument('-f','--file',default=None)
    ns = parser.parse_args()


    window = PondWindow()

    if ns.file is not None:
        with open(ns.file) as f:
            memory = algae.multiline_parse(f.read())
        coord = random.choice(window.pond.normal_space)
        print(coord)

        cell = window.pond.pond[coord]
        window.pond.alive.add(coord)
        cell.energy = 500
        cell.memory = memory
        cell.soul = bitstring.Bits(bytes="COOL")
        cell.debug = True

    window.pond._verbose = ns.verbose
    pyglet.app.run()

    print sum(window.fpses) / float(len(window.fpses))
