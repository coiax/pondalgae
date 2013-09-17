#!/usr/bin/env python
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
import argparse

import algae
def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    ns = parser.parse_args()
    with open(ns.filename) as f:
        memory = algae.multiline_parse(f.read())
    print(algae.pretty_print_memory(memory,colour=True))

if __name__=='__main__':
    _main()
