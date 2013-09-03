import sys
import random
import struct

from constants import *

class Pond(object):
    def __init__(self, size=(640,480)):
        self.size = size

        self.pond = {}
        for i in range(size[0]):
            for j in range(size[1]):
                self.pond[i,j] = Cell()

class Cell(object):
    def __init__(self):
        self.memory = b'\x00' * WORD_BYTES * MEMORY_WORDS
        self.energy = START_ENERGY
        self.pointer = 0

    def __eq__(self, other):
        try:
            return (self.memory == other.memory and
                    self.energy == other.energy and
                    self.pointer == other.pointer)
        except AttributeError:
            return False

    def randomise(self, r=random):
        new_memory = bytearray()
        for i in range(WORD_BYTES * MEMORY_WORDS):
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


