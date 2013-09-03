import bitstring
import random

from constants import *

class Interpreter(object):
    def __init__(self,cell=None,memory=None,energy=None,pointer=0):
        if cell is None:
            if memory is None:
                memory = '\x00' * WORD_BYTES * MEMORY_WORDS
            self.memory = bitstring.BitStream(bytes=memory)

            if energy is None:
                energy = START_ENERGY
            self.energy = energy
            self.pointer = pointer

        else:
            self.memory = bitstring.BitStream(bytes=cell.memory)
            self.energy = cell.energy
            self.pointer = cell.pointer

        self.accumulator = 0

    def __call__(self):
        self._quitting = False
        self._start_energy = self.energy
        while not self._quitting and self.energy > 0:
            self._looplet()

    def _get_word(self, word_index):
        assert word_index < MEMORY_WORDS

        start_index = word_index * WORD_BITS
        end_index = start_index + WORD_BITS
        return self.memory[start_index:end_index]

    def _set_word(self, word_index, value):
        assert word_index < MEMORY_WORDS

        bits = bitstring.Bits(uint=value, length=WORD_BITS)
        bit_index = word_index * WORD_BITS

        self.memory.overwrite(bits, bit_index)
        assert self._get_word(word_index).uint == value

    def _get_value(self, address_mode, address):
        if address_mode == 0b001:
            # Ignore the address value
            return self.accumulator
        elif address_mode == 0b010:
            # Literal. Return the actual address.
            return address
        else:
            # Lookup. The address is a word index.
            word = self._get_word(address)
            return word.uintbe

    def _looplet(self):
        self.memory.pos = self.pointer * WORD_BITS
        # a 32 bit word.
        # 8 BIT OPCODE | 12 BIT ADDR1 | 12 BIT ADDR2
        fmt = ("uintbe:8", # OPCODE
               "uint:3", # ADDR1 ADDRESS MODE
               "uint:7", # ADDR1
               "uint:3", # ADDR2 ADDRESS MODE
               "uint:7", # ADDR2
               "bool","bool","bool","bool", # The ABCD flags
              )
        fields = self.memory.readlist(fmt)
        assert self.memory.pos == (self.pointer * WORD_BITS) + WORD_BITS

        self.energy -= 1

        opcode = fields[0]
        # Replace with the enum, good for debugging.
        try:
            opcode = Opcode[opcode]
        except ValueError:
            pass

        if opcode == Opcode.NOOP:
            pass

        # NUMERIC INSTRUCTIONS
        elif opcode in BINARY_OPCODES:
            src_mode = fields[1]
            src_address = fields[2]
            src_value = self._get_value(src_mode, src_address)

            dest_mode = fields[3]
            dest_address = fields[4]
            dest_value = self._get_value(dest_mode, dest_address)

            if dest_mode == 0b001:
                # we'll add direct to the accumulator, ignoring address 2.
                dest_value = self.accumulator
                self.accumulator = compute_binary(opcode,src_value,dest_value)
            # Other forms of addressing don't make sense, so just add it
            # to the destination address? YOUR MILAGE MAY VARY.
            else:
                index = fields[4]
                word = self._get_word(index)
                dest_value = word.uintbe

                new_value = compute_binary(opcode, src_value, dest_value)
                self._set_word(index, new_value)

        elif opcode in UNARY_OPCODES:
            dest_mode = fields[3]
            if dest_mode & 1:
                # We'll be doing something to the accumulator.
                if opcode == Opcode.ZERO:
                    self.accumulator = 0
                elif opcode == Opcode.BINVERT:
                    bits = bitstring.BitArray(uintbe=self.accumulator,
                                              length=WORD_BITS)
                    bits.invert()
                    self.accumulator = bits.uintbe
            else:
                # Do something to the targeted word.
                index = fields[4]
                if opcode == Opcode.ZERO:
                    self._set_word(index, 0)
                elif opcode == Opcode.BINVERT:
                    word = self._get_word(index)
                    word.invert()
                    self._set_word(index, word.uintbe)
        elif opcode == Opcode.JUMP:
            src_mode = fields[1]
            src_address = fields[2]

            test_value = self._get_value(src_mode, src_address)

            # XXX later we might invert this with the appropriate flag.
            jumping = bool(test_value)

            if jumping:
                # WE'RE JUMPING. wooooo
                # \o/
                dest_mode = fields[3]
                if dest_mode & 1:
                    destination = self.accumulator % 2**ADDRESS_SIZE
                else:
                    index = fields[4]
                    destination = index

                self.memory.pos = destination * WORD_BITS

        elif opcode == Opcode.SKIP:
            # if the src and the dest are the same, then skip the next
            # instruction
            src_mode = fields[1]
            src_address = fields[2]
            src_value = self._get_value(src_mode, src_address)

            dest_mode = fields[3]
            dest_address = fields[4]
            dest_value = self._get_value(dest_mode, dest_address)

            equal = src_value == dest_value
            if equal:
                self.memory.pos += WORD_BITS

        elif opcode == Opcode.STOP:
            self._quitting = True

        elif opcode == Opcode.SNIFF:
            pass

        elif opcode == Opcode.RANDOM:
            src_mode = fields[1]
            src_address = fields[2]
            src_value = self._get_value(src_mode, src_address)
            r = random.Random(src_value)
            new_value = r.randint(0,(2**WORD_BITS) - 1)

            dest_mode = fields[3]
            dest_address = fields[4]
            if dest_mode == 0b001:
                self.accumulator = new_value
            else:
                self._set_word(dest_address, new_value)

def compute_binary(opcode, src, dest):
    assert opcode in BINARY_OPCODES

    if opcode == Opcode.ADD:
        out = src + dest
    elif opcode == Opcode.SUBTRACT:
        out = src - dest
    elif opcode == Opcode.MULTIPLY:
        out = src * dest
    elif opcode == Opcode.DIVIDE:
        if dest == 0:
            # the closest we have to infinity
            out = (2**WORD_BITS) - 1
        else:
            out = int(src // dest)
    elif opcode == Opcode.MODULO:
        if dest == 0:
            # the closest we have to infinity
            out = (2**WORD_BITS) - 1
        else:
            out = src % dest
    elif opcode == Opcode.BAND:
        out = src & dest
    elif opcode == Opcode.BOR:
        out = src | dest
    elif opcode == Opcode.BXOR:
        out = src ^ dest

    return out % 2**WORD_BITS

def _main(seed=None):
    import pond

    if seed is None:
        r = random.SystemRandom()
        seed = r.getrandbits(100)

    random.seed(seed)
    print "Seed: {}".format(seed).ljust(40),

    c = pond.Cell()
    c.randomise()

    i = Interpreter(c)
    i.energy = random.randint(1000,3000)
    i()

    original = bitstring.BitArray(bytes=c.memory)
    new = i.memory

    changes = (original ^ new).count(1)
    format1 = format2 = msg = ''
    if changes:
        format1 = '\033[1;32m'
        format2 = '\033[0m'
    if i.energy != 0:
        msg = " \033[33m(Willingly STOP'd.)\033[0m"

    print "{}{} bits difference{}{}".format(format1,changes,format2,msg)


if __name__=='__main__':
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('-s','--seed',type=int,default=None)
    p.add_argument('-i','--iterations',type=int,default=1)
    ns = p.parse_args()
    if 0 == ns.iterations:
        while True:
            _main()
    else:
        for i in range(ns.iterations):
            _main()
