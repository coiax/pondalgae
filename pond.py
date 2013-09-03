import sys
import random
import struct

import pyglet
import pyglet.window
import pyglet.graphics
import pyglet.gl
import pyglet.app
import pyglet.clock

WORD = 4
MEMORY_WORDS = 1024
START_ENERGY = 50000

class Pond(object):
    def __init__(self, size=(640,480)):
        self.size = size

        self.pond = {}
        for i in range(size[0]):
            for j in range(size[1]):
                self.pond[i,j] = Cell()

class Cell(object):
    def __init__(self):
        self.memory = b'\x00' * WORD * MEMORY_WORDS
        self.energy = START_ENERGY
        self.pointer = 0

    def __eq__(self, other):
        try:
            return (self.memory == other.memory and
                    self.energy == other.energy and
                    self.pointer == other.pointer)
        except AttributeError:
            return False

    def randomise(self):
        r = random.SystemRandom()
        new_memory = bytearray()
        for i in range(WORD * MEMORY_WORDS):
            new_memory.append(r.randint(0,255))

        self.memory = bytes(new_memory)

    @property
    def checksum(self):
        sum = 0
        for i in range(MEMORY_WORDS):
            tup = struct.unpack('>I', self.memory[i * WORD : (i + 1) * WORD])
            value = tup[0]
            sum += value
        return sum % 2**(WORD * 8)

    @property
    def colour(self):
        checksum = self.checksum
        colour = [None, None, None, None]
        for i in range(4):
            colour[3 - i] = checksum & 0xFF
            checksum >>= 8

        assert None not in colour
        return colour

class PondWindow(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(PondWindow, self).__init__(*args, **kwargs)

        self.fpses = []

    def on_draw(self):
        X, Y = self.get_size()

        x = random.randint(0,X)
        y = random.randint(0,Y)

        colour = tuple(random.randint(0,255) for i in range(4))
        self._set_pixel((x,y), colour)

        self.fpses.append(pyglet.clock.get_fps())

    def _set_pixel(self, coord, colour):
        pyglet.graphics.draw(1, pyglet.gl.GL_POINTS,
                             ('v2i', coord),
                             ('c4B', colour))

if __name__=='__main__':
    pond = Pond()
    window = PondWindow(width=pond.size[0], height=pond.size[1])
    pyglet.app.run()

    print sum(window.fpses) / float(len(window.fpses))
