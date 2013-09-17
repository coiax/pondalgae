from __future__ import print_function

import argparse
import bitstring
import random
import re
import struct
import functools
import datetime
import sys

from constants import *

class Interpreter(object):
    def __init__(self,cell=None,random_memory=False,memory=None,
                 energy=None,ether=None,cell_soul=None):
        if random_memory:
            # Generates random valid instructions.
            memory = []
            for i in range(MEMORY_WORDS):
                memory.append(random_instruction())
            memory = ''.join(memory)

        if cell is None:
            if memory is None:
                memory = bitstring.BitStream(WORD_BITS * MEMORY_WORDS)
            self.memory = bitstring.BitStream(memory)

            if energy is None:
                energy = START_ENERGY
            self.energy = energy
            if cell_soul is None:
                cell_soul = 0
            self.cell_soul = cell_soul

        else:
            self.memory = bitstring.BitStream(cell.memory)
            self.energy = cell.energy
            self.cell_soul = cell.soul

        if ether is None:
            ether = {}
        self.ether = ether

        self.accumulator = 0
        self.pointer = 0
        self.direction = Direction.WEST
        self._start_energy = self.energy

    def write_cell(self, cell):
        cell.memory = self.memory
        cell.energy = self.energy

    def __call__(self, verbose=False):
        self._verbose = verbose

        self.memory.pos = self.pointer * WORD_BITS

        while True:
            try:
                if self.energy <= 0:
                    raise NoEnergyEnder
                self._looplet()
            except bitstring.ReadError:
                # Reading off the edge of the memory makes you stop.
                raise FinishedBookEnder
            finally:
                self.pointer = (self.memory.pos // WORD_BITS)

    def _get_word(self, word_index):
        assert word_index < MEMORY_WORDS

        start_index = word_index * WORD_BITS
        end_index = start_index + WORD_BITS
        return self.memory[start_index:end_index]

    def _set_word(self, word_index, value):
        assert word_index < MEMORY_WORDS
        value %= 2**WORD_BITS

        bits = bitstring.Bits(uint=value, length=WORD_BITS)
        bit_index = word_index * WORD_BITS

        _old_pos = self.memory.pos
        self.memory.overwrite(bits, bit_index)
        self.memory.pos = _old_pos

        assert self._get_word(word_index).uint == value

    def _get_value(self, address_mode, address):
        if address_mode == AddressMode.ACCUMULATOR:
            # Ignore the address value
            return self.accumulator
        elif address_mode == AddressMode.LITERAL:
            # Return the actual address as an integer.
            return address
        elif address_mode == AddressMode.INDIRECT:
            # Read the word at address, and take that as the index.
            index = self._get_word(address).uint % 2**ADDRESS_SIZE
            return self._get_word(index).uint

        else:
            # Lookup. The address is a word index.
            # Lookup that word, and interpret it as an unsigned big endian
            # integer.
            word = self._get_word(address)
            return word.uintbe

    def _set_value(self, address_mode, address, new_value):
        if address_mode == AddressMode.ACCUMULATOR:
            self.accumulator = new_value
        elif address_mode == AddressMode.LITERAL:
            # Storing using a literal as an address is undefined. I think.
            # TODO probaly need to define the spec a little bit better.
            pass
        else:
            # Interpret the address as a word index.
            self._set_word(address, new_value)

    def _describe_current_instruction(self, colour=True):
        fmt = "{position} {word} {accumulator} {energy}"
        position = "<POS #{:>4}>".format(self.memory.pos // WORD_BITS)
        # pretty_print_word only peeks, so we don't have to worry about the
        # memory position being changed.
        word = pretty_print_word(self.memory)
        accumulator = "<ACC #{:>10}>".format(self.accumulator)
        energy = "<ENERGY #{:>4}>".format(self.energy)

        return fmt.format(position=position, word=word,
                          accumulator=accumulator, energy=energy)

    def _looplet(self):
        if self._verbose:
            description = self._describe_current_instruction()
            print(description)

        fields = self.memory.readlist(INSTRUCTION_FORMAT)


        opcode = fields[0]
        # Replace with the enum, good for debugging.
        try:
            opcode = Opcode[opcode]
        except ValueError:
            pass

        self.energy -= OPCODE_COST[opcode]
        # Attemtping to run an opcode that costs into the negatives doesn't
        # work, and all your energy disappears anyway.
        if self.energy < 0:
            self.energy = 0
            raise NoEnergyEnder

        src_mode = AddressMode[fields[1]]
        src_address = fields[2]
        dest_mode = AddressMode[fields[3]]
        dest_address = fields[4]

        src_value = self._get_value(src_mode, src_address)
        dest_value = self._get_value(dest_mode, dest_address)

        if opcode == Opcode.NOOP:
            pass

        elif opcode == Opcode.COPY:
            self._set_value(dest_mode, dest_address, src_value)

        # NUMERIC INSTRUCTIONS
        elif opcode in BINARY_OPCODES:
            try:
                result = compute_binary(opcode, src_value, dest_value)
            except ZeroDivisionError:
                result = MAX_INT - 1
            self._set_value(dest_mode, dest_address, result)

        elif opcode in UNARY_OPCODES:
            if opcode == Opcode.ZERO:
                value = 0
            else:
                bits = bitstring.Bits(uint=src_value, length=WORD_BITS)
                value = (~bits).uint
            self._set_value(dest_mode, dest_address, value)

        elif opcode == Opcode.EXCHANGE:
            # Probably does weird stuff with the literal address mode
            old_src_value = src_value
            old_dest_value = dest_value

            self._set_value(dest_mode, dest_address, old_src_value)
            self._set_value(src_mode, src_address, old_dest_value)

        elif opcode == Opcode.JUMP:
            test_value = src_value

            # XXX later we might invert this with the appropriate flag.
            jumping = bool(test_value)

            if jumping:
                # WE'RE JUMPING. wooooo
                # \o/
                destination = self._get_value(dest_mode, dest_address)
                destination %= MEMORY_WORDS

                self.memory.pos = destination * WORD_BITS

        elif opcode == Opcode.SKIP or opcode == Opcode.SKIPLESS:
            # SKIP
            # if the src and the dest are the same, then skip the next
            # instruction
            # SKIPLESS
            # if the src is less than the dest, then skip the next
            # instruction
            if opcode == Opcode.SKIP:
                skipping = src_value == dest_value
            elif opcode == Opcode.SKIPLESS:
                skipping = src_value < dest_value

            if skipping:
                # Skipping the instruction can make us go off the end of
                # memory, so treat it like we're finished.
                try:
                    self.memory.pos += WORD_BITS
                except ValueError:
                    raise FinishedBookEnder
        elif opcode == Opcode.STOP:
            # That's it. Everything else is ignored.
            raise StopEnder

        elif opcode == Opcode.SNIFF:
            sniff_type = src_value

            answer = 0
            # We may need this callback for any sniffs that need to
            # ask the pond.
            def callback(answer):
                self._set_value(dest_mode, dest_address, answer)

            if sniff_type == Scent.START_ENERGY:
                answer = self._start_energy
            elif sniff_type == Scent.CURRENT_ENERGY:
                answer = self.energy
            elif sniff_type == Scent.PI:
                answer = BIG_PI
            elif sniff_type == Scent.E:
                answer = BIG_E
            elif sniff_type == Scent.CHECKSUM:
                answer = memory_checksum(self.memory)
            elif sniff_type == Scent.SOUL:
                answer = self.cell_soul.uint
            elif sniff_type == Scent.LIGHT_LEVEL:

                raise SniffEnder(sniff_type, callback)
            #FIXME all other sniff types are currently unimplemented.

            # If we haven't thrown a sniffender, then the answer is simple.
            self._set_value(dest_mode, dest_address, answer)

        elif opcode == Opcode.RANDOM:
            seed = src_value
            r = random.Random(src_value)
            new_value = r.randint(0,MAX_INT - 1)

            self._set_value(dest_mode, dest_address, new_value)
        elif opcode == Opcode.FACE:
            # TODO might cost more than usual?
            facing = src_value
            # Ignore dest_value, I guess?
            new_direction = facing % DIRECTIONS

            self.direction = Direction[new_direction]

        elif opcode == Opcode.ETHERREAD:
            ether_address = src_value % MEMORY_WORDS
            # Ether is a collective memory shared by all cells with the
            # same soul. For sanity reasons, it's the same size as a memory
            # cell, but more expensive to access and write?
            # Luckily, since it's literally word_index->int, it's very
            # easy to deal with programatically.
            # Technically, we should probably say that ether values that
            # haven't been written to are "undefined", but I'm lazy, so
            # we'll just say it's a 0.
            ether_value = self.ether.get(ether_address,0)
            self._set_value(dest_mode, dest_address, ether_value)

        elif opcode == Opcode.ETHERWRITE:
            # dest is where it's going, and src is where the value comes from
            self.ether[dest_value % MEMORY_WORDS] = src_value

        elif opcode == Opcode.BASK:
            raise BaskEnder

        elif opcode == Opcode.HANDOFF:
            raise HandoffEnder

        elif opcode == Opcode.MOVE:
            cutoff_point = src_value % MEMORY_WORDS
            assert cutoff_point <= MEMORY_WORDS
            fuel = min(self.energy, dest_value)

            if cutoff_point != 0 and fuel != 0:
                self.energy -= fuel
                assert self.energy >= 0

                raise MoveEnder(cutoff_point, fuel)

        elif opcode == Opcode.NUDGE:
            raise NudgeEnder(src_value % MEMORY_WORDS, dest_value)
        elif opcode == Opcode.TEACH:
            raise TeachEnder(src_value % MEMORY_WORDS, dest_value)

        elif opcode == Opcode.PROCURE:
            raise ProcureEnder(src_value)
        elif opcode == Opcode.BESTOW:
            drained = min(self.energy, src_value)
            # The subtraction of energy is done above.
            raise BestowEnder(drained)
        elif opcode == Opcode.LADAR:
            # The callback will be called with the answer.
            def callback(answer):
                self._set_value(dest_mode, dest_address, answer)
            raise LadarEnder(callback)

OPCODE_COST = {}
for opcode in Opcode:
    if opcode in PRICEY_OPCODES:
        value = 5
    elif opcode == Opcode.NOOP:
        # XXX Remember, if we have addressing modes that modify values
        # they still need to cost energy. You don't get something for nothing.
        value = 0
    else:
        value = 1
    OPCODE_COST[opcode] = value

del opcode

class AlgaeEnder(Exception):
    pass

class SniffEnder(AlgaeEnder):
    def __init__(self, type, callback):
        AlgaeEnder.__init__(self)
        self.type = type
        self.callback = callback

class NudgeEnder(AlgaeEnder):
    def __init__(self, word_index, value):
        AlgaeEnder.__init__(self)
        self.word_index = word_index
        self.value = value

class TeachEnder(AlgaeEnder):
    def __init__(self, word_index, value):
        AlgaeEnder.__init__(self)
        self.word_index = word_index
        self.value = value

class BaskEnder(AlgaeEnder):
    pass

class HandoffEnder(AlgaeEnder):
    pass

class ProcureEnder(AlgaeEnder):
    def __init__(self, amount):
        AlgaeEnder.__init__(self)
        self.amount = amount

class BestowEnder(AlgaeEnder):
    def __init__(self, amount):
        AlgaeEnder.__init__(self)
        self.amount = amount

class StopEnder(AlgaeEnder):
    pass

class MoveEnder(AlgaeEnder):
    def __init__(self, cutoff_point, fuel):
        AlgaeEnder.__init__(self)
        self.cutoff_point = cutoff_point
        self.fuel = fuel

class NoEnergyEnder(AlgaeEnder):
    pass

class FinishedBookEnder(AlgaeEnder):
    pass

class LadarEnder(AlgaeEnder):
    def __init__(self, callback):
        super(LadarEnder, self).__init__(self)
        self.callback = callback

def compute_binary(opcode, src, dest):
    assert opcode in BINARY_OPCODES

    if opcode == Opcode.ADD:
        out = src + dest
    elif opcode == Opcode.SUBTRACT:
        out = dest - src
    elif opcode == Opcode.MULTIPLY:
        out = src * dest
    elif opcode == Opcode.DIVIDE:
        out = int(dest // src)
    elif opcode == Opcode.MODULO:
        out = dest % src
    elif opcode == Opcode.BAND:
        out = src & dest
    elif opcode == Opcode.BOR:
        out = src | dest
    elif opcode == Opcode.BXOR:
        out = src ^ dest
    elif opcode == Opcode.LEFTSHIFT:
        # This prevents us from doing heavy duty power multiplcation stuff
        # when we only care about the last WORD_BITS
        bits = bitstring.Bits(uint=dest, length=WORD_BITS)
        bits = bits << dest

        return bits.uint

    elif opcode == Opcode.RIGHTSHIFT:
        out = src >> dest

    return out % MAX_INT

def pretty_print_word(input_stream):
    fields = input_stream.peeklist(INSTRUCTION_FORMAT)
    opcode, src_mode, src_addr, dest_mode, dest_addr = fields

    values = {}

    try:
        opcode_enum = Opcode[opcode]
        opcode_str = opcode_enum.name
    except ValueError:
        opcode_bits = bitstring.Bits(uint=opcode, length=OPCODE_BITS)
        opcode_str = '0x{}'.format(opcode_bits.hex)

    values['opcode'] = opcode_str

    for address_type in ('src','dest'):
        if address_type == 'src':
            mode = AddressMode[src_mode]
            addr = src_addr
        else:
            mode = AddressMode[dest_mode]
            addr = dest_addr

        if mode == AddressMode.ACCUMULATOR:
            fmt = '<ACC>'
        else:
            fmt = '{symbol}{address}'

        if mode == AddressMode.LITERAL:
            symbol = '#'
        elif mode == AddressMode.INDIRECT:
            symbol = '@'
        else:
            symbol = '$'

        values[address_type] = fmt.format(symbol=symbol, address=addr)


    fmt = "{opcode:<11}{src:>5}, {dest:>5}"
    return fmt.format(**values)

def pretty_print_memory(input_memory, colour=True):
    strings = []
    stream = bitstring.ConstBitStream(input_memory)
    while stream.pos < WORD_BITS * MEMORY_WORDS:
        strings.append(pretty_print_word(stream, colour=colour))
        stream.pos += WORD_BITS
    trimmed = False
    while strings[-1] == strings[-2]:
        strings.pop()
        trimmed = True
    strings.append('...')

    return '\n'.join(strings)

def interesting_until(strings):
    strings = list(strings)
    while strings[-1] == strings[-2]:
        strings.pop()
    return len(strings)

def multiline_parse(text):
    memory = bitstring.BitStream(WORD_BITS * MEMORY_WORDS)
    references = {}
    line_number = 0
    codes = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        mo = re.match("(?i)(?P<label>[A-Z_]+:)?\s*(?P<remaining>.*)", line)
        assert mo is not None

        label = mo.group('label')
        if label is not None:
            label = label[:-1].upper()
            references[label] = line_number

        remaining = mo.group('remaining')
        codes.append(remaining)
        line_number += 1

    for i, code in enumerate(codes):
        fields = line_parse(code)

        opcode = fields[0]
        src_mode = fields[1]

        src_addr = fields[2]
        if type(src_addr) == str:
            src_addr = references[src_addr]

        dest_mode = fields[3]

        dest_addr = fields[4]
        if type(dest_addr) == str:
            dest_addr = references[dest_addr]

        bs = bitstring.pack(INSTRUCTION_FORMAT,
                            opcode,
                            src_mode, src_addr,
                            dest_mode, dest_addr)
        memory.overwrite(bs)
    return memory, len(codes)

def line_parse(string, return_bitstring=False):
    return _tuple_interpret(_regex_extract(string),
                            return_bitstring=return_bitstring)

def _regex_extract(string):
    regexfmt = (r'(?i)'
           r'(?P<opcode>[A-Z_]+)'
           r'\s*'
           r'(?P<src>(<ACC>)|([$#@]?(\d+|[A-Z_]+)))?'
           r'\s*'
           r'(?P<dest>(<ACC>)|([$#@]?(\d+|[A-Z_]+)))?'
           r'(\s*#.*)?' # ignore comments at the end.
          )
    mo = re.match(regexfmt, string)
    if mo is None:
        raise TypeError("Bad input line.") # TODO check if better exception?

    opcode_str = mo.group('opcode').upper()
    src_str = mo.group('src') or ''
    dest_str = mo.group('dest') or ''

    return (opcode_str, src_str.upper(), dest_str.upper())

def _tuple_interpret(tup, return_bitstring):
    opcode_str, src_str, dest_str = tup

    opcode = Opcode[opcode_str.upper()]

    def interpret(str):
        if not str:
            return 0,0
        mode = 0
        addr = 0

        if str == "<ACC>":
            mode = AddressMode.ACCUMULATOR
        elif str.isdigit():
            addr = int(str)
        else:
            if str.startswith('#'):
                mode = AddressMode.LITERAL
            elif str.startswith('$'):
                mode = AddressMode.NORMAL
            elif str.startswith('@'):
                mode = AddressMode.INDIRECT
            remaining = str[1:]
            if remaining.isdigit():
                addr = int(remaining)
            else:
                # reference
                addr = remaining


        return mode, addr

    src_mode, src_addr = interpret(src_str)
    # A single instruction is duplicated twice.
    if src_str and not dest_str:
        dest_mode, dest_addr = src_mode, src_addr
    else:
        dest_mode, dest_addr = interpret(dest_str)

    return opcode, src_mode, src_addr, dest_mode, dest_addr



def _main(seed=None,verbose=False):

    if seed is None:
        r = random.SystemRandom()
        seed = r.getrandbits(100)

    random.seed(seed)
    #print("Seed: {}".format(seed).ljust(40))

    energy = random.randint(1000,3000)
    original_memory = random_memory()
    i = Interpreter(memory=original_memory,energy=energy)
    try:
        i(verbose=verbose)
    except FinishedBookEnder:
        reason = "finishedbook"
    except NoEnergyEnder:
        reason = "exhausted"
    except StopEnder:
        reason = "stop"
    except AlgaeEnder:
        # Ignore ending actiony things.
        reason = None

    changes = (original_memory ^ i.memory).count(1)
    format1 = format2 = msg = ''
    if changes:
        format1 = '\033[1;32m'
        format2 = '\033[0m'
    if reason == "stop":
        msg = " \033[33m(Willingly STOP'd.)\033[0m"
    elif reason == "finishedbook":
        msg = " \033[31m(Executed to end of memory.)\033[0m"

    #print("Seed: {}".format(seed).ljust(40))
    #print("{}{} bits difference{}{}".format(format1,changes,format2,msg))

def random_instruction(random=random):
    fmt = INSTRUCTION_FORMAT
    # Select opcode.
    opcode = random.choice(list(Opcode))

    # XXX no flags to select.
    # Select address mode/address, twice.
    src_mode = random.choice(list(AddressMode))
    dest_mode = random.choice(list(AddressMode))

    src_addr = random.randint(0, MEMORY_WORDS - 1)
    dest_addr = random.randint(0, MEMORY_WORDS - 1)

    bs = bitstring.pack(fmt, opcode, src_mode, src_addr, dest_mode, dest_addr)
    return bs

def random_memory(random=random):
    new_memory = bytearray()
    for i in range(WORD_BYTES * MEMORY_WORDS):
        new_memory.append(random.randint(0,255))

    return bitstring.BitStream(bytes=new_memory)

def random_soul(random=random):
    new_soul = bytearray()
    # A soul is the size of a word.
    for i in range(WORD_BYTES):
        new_soul.append(random.randint(0,255))

    return bitstring.Bits(bytes=new_soul)

def memory_checksum(memory):
    # is a bytes.
    if len(memory) == 4096:
        pass
    elif len(memory) == WORD_BITS * MEMORY_WORDS:
        memory = memory.bytes
    else:
        assert False # unrecognised length TODO proper exception?

    sum = 0
    for i in range(MEMORY_WORDS):
        tup = struct.unpack('>I', memory[i * WORD_BYTES : (i + 1)*WORD_BYTES])
        value = tup[0]
        sum += value
    return sum % MAX_INT

def _make_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_thrash = subparsers.add_parser('thrash')

    parser_thrash.add_argument('-s','--seed',type=int,nargs='+',
                               default=None,dest='seeds')
    parser_thrash.add_argument('-i','--iterations',type=int,default=1)
    parser_thrash.add_argument('-v','--verbose',action='store_true')

    parser_thrash.set_defaults(func=_thrash)

    parser_parse = subparsers.add_parser('parse')
    parser_parse.add_argument('file')

    parser_parse.set_defaults(func=_parse)


    return parser

def _parse(namespace):
    with open(namespace.file) as f:
        txt = f.read()
    memory, instructions = multiline_parse(txt)
    words = []
    for i in range(instructions):
        words.append(pretty_print_word(memory[i*WORD_BITS:]))
    print("\n".join(words))

def _thrash(namespace):
    seeds = ns.seeds
    if namespace.iterations == 0:
        iterations = None
    else:
        iterations = namespace.iterations

    _last_progress_length = None
    count = 0
    start_time = datetime.datetime.now()

    while iterations is None or iterations > 0:
        count += 1
        if seeds:
            seed = seeds.pop()
        else:
            seed = None
        try:
            _main(None, verbose=ns.verbose)
        except Exception:
            print("Seed: {}".format(seed))
            raise

        if iterations is not None:
            iterations -= 1

        if not namespace.verbose:
            _thrash_progress(count, start_time)

def _thrash_progress(count, start_time):
    progress_fmt = "Seeds: {}, Average Execution Time: {:.5f} seconds"
    total_time = (datetime.datetime.now() - start_time).total_seconds()
    average_time = total_time / count

    progress = progress_fmt.format(count, average_time)

    sys.stderr.write("\r{}".format(progress))
    sys.stderr.flush()

if __name__=='__main__':
    ns = _make_parser().parse_args()
    ns.func(ns)

