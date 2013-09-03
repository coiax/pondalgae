from constants import WORD, MEMORY_WORDS, START_ENERGY

class Interpreter(object):
    def __init__(self,memory=None,energy=None):
        if memory is None:
            memory = bytearray('\x00' * WORD * MEMORY_WORDS)
        self.memory = memory

        if energy is None:
            energy = START_ENERGY
        self.energy = energy
