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
import random
import struct
import collections
import os.path

import bitstring

import algae
from constants import *

class Pond(object):
    def __init__(self, size=(640,480)):
        self.size = size
        self._random = random.Random(3)
        self._verbose = False

        self.alive = set()
        self.ethers = collections.defaultdict(dict)

        # Lazy pond only initialised cell when we need it.
        self.pond = collections.defaultdict(Cell)

        self.normal_space = []
        for i in range(size[0]):
            for j in range(size[1]):
                self.normal_space.append((i,j))

        self.light_level = collections.defaultdict(int)
        self._generate_suns()

    def _generate_suns(self):
        sun_coords = self._random.sample(self.normal_space, NUMBER_OF_SUNS)

        for sun_coord in sun_coords:
            self.pond[sun_coord] = SunCell()
            for coord in self.normal_space:
                distance_squared = (coord[0] - sun_coord[0])**2
                distance_squared += (coord[1] - sun_coord[1])**2

                self.light_level[coord] += LIGHT_FADE(distance_squared)

        for key in self.light_level:
            self.light_level[key] = int(self.light_level[key])


    def tick(self, N):
        self.run_alive_cell()

    def run_alive_cell(self):
        if self.alive:
            coord = self._random.choice(list(self.alive))
            self.run_cell(coord)

    def lightning(self, coord=None):
        # The spark of life happens. Also, it grants souls.
        if coord is None:
            coord = self._random.choice(self.normal_space)
        self.pond[coord] = cell = Cell(energy=START_ENERGY,
                                       randomised=self._random)

        self.alive.add(coord)
        self.run_cell(coord)

    def spawn(self, memory, soul=None, coord=None):
        if coord is None:
            coord = self._random.choice(self.normal_space)

        if soul is None:
            soul = algae.random_soul(random=self._random)

        cell = Cell(energy=START_ENERGY, soul=soul, memory=memory)
        self.pond[coord] = cell
        self.alive.add(coord)
        self.run_cell(coord)

    def run_cell(self, coord):
        cell = self.pond[coord]
        if cell.soul is None and cell.energy == 0:
            self.alive.discard(coord)
            return

        ether = self.ethers[cell.soul]
        interpreter = algae.Interpreter(cell, ether=ether)
        while True:
            try:
                try:
                    cell.energy = interpreter.energy
                    interpreter(self._verbose or cell.debug)
                except algae.AlgaeEnder:
                    interpreter.write_cell(cell)
                    raise
            except algae.SniffEnder as sniff:
                answer = 0

                if sniff.type == Scent.LIGHT_LEVEL:
                    answer = self.light_level[cell]

                sniff.callback(answer % MAX_INT)

            except algae.LadarEnder as ladar:
                def key(cell):
                    return cell.soul is not None
                hit = self._run_until(coord, interpreter.direction, key)
                if hit is None:
                    result = LadarAnswer.NOTHING
                else:
                    other = self.pond[hit]
                    if cell.soul == other.soul:
                        result = LadarAnswer.SOULMATE
                    else:
                        result = LadarAnswer.HEATHEN

                ladar.callback(result)
                continue

            except algae.NoEnergyEnder:
                assert not cell.energy
                break
            except algae.FinishedBookEnder:
                break
            except algae.NudgeEnder as nudge:
                nudge_energy = cell.energy
                nudge_soul = cell.soul

                cell.energy = 0
                cell.soul = None

                other_coord = apply_direction(coord, interpreter.direction)
                other = self.pond[other_coord]

                can_access = cell.can_access(other)
                if can_access and nudge_energy:
                    other.energy += nudge_energy
                    other.soul = nudge_soul

                    self.alive.add(other_coord)

                    bit_index = nudge.word_index * WORD_BITS
                    value = bitstring.Bits(uint=nudge.value, length=WORD_BITS)

                    other.memory.overwrite(value, bit_index)

                break

            except algae.TeachEnder as teach:
                word_index = teach.word_index
                value = teach.value

                other_coord = apply_direction(coord, interpreter.direction)
                other = self.pond[other_coord]

                if cell.can_access(other):
                    bit_index = word_index * WORD_BITS
                    bit_value = bitstring.Bits(uint=value, length=WORD_BITS)
                    other.memory.overwrite(bit_value, bit_index)
                # Drop straight back in.
                continue

            except algae.BaskEnder:
                cell.energy += self.light_level[coord]
                break
            except algae.ProcureEnder as procure:
                other_coord = apply_direction(coord, interpreter.direction)
                other = self.pond[other_coord]
                if cell.can_access(other) and other.energy:
                    amount = min(other.energy, procure.amount)
                    cell.energy += amount
                    other.energy -= amount

                    if other.energy == 0:
                        other.soul = None
                        self.alive.discard(other_coord)

                break

            except algae.BestowEnder as bestow:
                other_coord = apply_direction(coord, interpreter.direction)
                other = self.pond[other_coord]
                cell.energy -= bestow.amount
                if cell.can_access(other):
                    other.energy += bestow.amount
                    other.soul = cell.soul
                    self.alive.add(other_coord)
                continue

            except algae.StopEnder:
                break

            except algae.MoveEnder as move:
                cutoff_point = move.cutoff_point
                fuel = move.fuel
                assert cutoff_point and fuel

                direction = interpreter.direction

                assert move.cutoff_point <= MEMORY_WORDS

                interpreter.write_cell(cell)

                mobile_code = cell.memory[:WORD_BITS * cutoff_point]
                mobile_soul = cell.soul
                mobile_energy = cell.energy

                cell.energy = 0
                cell.soul = None
                self.alive.remove(coord)

                # Work out where we end up.
                current_coord = coord
                future_coord = None
                remaining_fuel = fuel

                while True:
                    future_coord = apply_direction(current_coord, direction)
                    future_cell = self.pond[future_coord]
                    # Then check to see if we have enough fuel, and whether
                    # we can end up there.
                    if not cell.can_access(future_cell):
                        break
                    cost = cutoff_point
                    if direction in DIAGONAL_DIRECTIONS:
                        cost = math.ceil(cost * ROOT_TWO)


                    if cost > remaining_fuel:
                        break

                    # otherwise we keep moving
                    remaining_fuel = int(remaining_fuel - cost)
                    current_coord = future_coord

                if remaining_fuel:
                    cell_in_front = self.pond[future_coord]
                    cell_in_front.energy += remaining_fuel
                    if cell_in_front.soul is None:
                        cell_in_front.soul = mobile_soul

                new_cell = self.pond[current_coord]
                new_cell.soul = mobile_soul
                new_cell.energy = mobile_energy
                new_cell.memory.overwrite(mobile_code, 0)
                self.alive.add(current_coord)

                break
            except algae.HandoffEnder:
                # Write back the changes.
                if cell.energy == 0:
                    cell.soul = None
                    self.alive.remove(coord)

                # Then load the new cell, and a new interpreter.
                new_coord = apply_direction(coord, interpreter.direction)
                assert new_coord != coord
                coord = new_coord
                cell = self.pond[coord]
                interpreter = algae.Interpreter(cell, ether=ether)
                continue

        # ENDWHILE
        if not cell.energy:
            cell.soul = None
        # phew.

    def _run_until(self, coord, direction, key, n=200):
        for i in range(n):
            coord = apply_direction(coord, direction)
            if key(self.pond[coord]):
                return coord



def apply_direction(coord, direction):
    # Returns a new coordinate with this distance applied to it.
    x,y = coord
    if direction == Direction.WEST:
        dx, dy = -1, 0
    elif direction == Direction.NORTHWEST:
        dx, dy = -1, -1
    elif direction == Direction.NORTH:
        dx, dy = 0, -1
    elif direction == Direction.NORTHEAST:
        dx, dy = 1, -1
    elif direction == Direction.EAST:
        dx, dy = 1, 0
    elif direction == Direction.SOUTHEAST:
        dx, dy = 1, 1
    elif direction == Direction.SOUTH:
        dx, dy = 0, 1
    elif direction == Direction.SOUTHWEST:
        dx, dy = -1, 1

    return (x + dx, y + dy)



class Cell(object):
    def __init__(self, energy=0, memory=None, soul=None, randomised=False):
        if not randomised:
            if memory is not None and soul is None:
                soul = algae.random_soul()

            if memory is None:
                memory = bitstring.BitStream(WORD_BITS * MEMORY_WORDS)
            self.memory = memory
            self.soul = soul 

        else:
            try:
                randomised.random
            except AttributeError:
                self.randomise()
                self.soul = algae.random_soul()
            else:
                self.randomise(random=randomised)
                self.soul = algae.random_soul(random=randomised)

        self._energy = energy
        self.debug = False
        self.inanimate = False

    def get_energy(self):
        return self._energy
    def set_energy(self, value):
        assert value >= 0
        self._energy = value

    energy = property(get_energy, set_energy)

    def __repr__(self):
        fmt = "<{name} soul={soul} energy={energy} colour={colour}>"
        name = self.__class__.__name__
        if self.soul is not None:
            soul = ''.join(('0x', self.soul.hex))
        else:
            soul = None

        return fmt.format(name=name, soul=soul, energy=self.energy,
                          colour=self.colour)

    def __eq__(self, other):
        try:
            return (self.memory == other.memory and
                    self.energy == other.energy and
                    self.soul == other.soul)
        except AttributeError:
            return False

    def randomise(self, random=random):
        self.memory = algae.random_memory(random=random)

    def can_access(self, other):
        if not other.alive:
            return True
        elif self.soul == other.soul:
            return True
        else:
            return False

    @property
    def alive(self):
        if self.inanimate:
            return False
        else:
            return self.soul is not None

    @property
    def checksum(self):
        return algae.memory_checksum(self.memory)

    @property
    def colour(self):
        checksum = self.checksum
        colour = [None, None, None, None]
        for i in range(4):
            colour[3 - i] = checksum & 0xFF
            checksum >>= 8

        assert None not in colour
        return colour

class SunCell(Cell):
    def __init__(self):
        Cell.__init__(self)
        self.inanimate = True

    colour = (255,255,255,255)

def pond_time():
    pond = Pond()
    N = 0
    while True:
        pond.tick(N)
        N += 1

def _main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('-n','--number-of-ticks',type=int,default=10000,
                        dest='N')

    namespace = parser.parse_args()

    _realmain(namespace.N, namespace.filename)

def _realmain(N, filename):
    assert os.path.exists(filename)
    pond = Pond()
    with open(filename) as f:
        txt = f.read()
    memory, instructions = algae.multiline_parse(txt)
    pond.spawn(memory=memory)

    for i in range(N):
        pond.tick(i)


if __name__=='__main__':
    _main()
