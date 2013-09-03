import flufl.enum
import math

WORD_BYTES = 4
WORD_BITS = WORD_BYTES * 8
MEMORY_WORDS = 1024
ADDRESS_SIZE = int(math.log(MEMORY_WORDS, 2))
START_ENERGY = 50000

class Opcode(flufl.enum.IntEnum):
    NOOP = 0x00

    # Binary operations.
    ADD = 0x01
    SUBTRACT = 0x02
    MULTIPLY = 0x03
    DIVIDE = 0x04
    MODULO = 0x05
    BAND = 0x06
    BOR = 0x07
    BXOR = 0x08

    # Unary operations.
    BINVERT = 0x09
    ZERO = 0x0a

    JUMP = 0x0b
    SKIP = 0x0c
    STOP = 0x0d

    SNIFF = 0x0e
    RANDOM = 0x0f

class Scent(flufl.enum.IntEnum):
    START_ENERGY = 1
    CURRENT_ENERGY = 2
    SOUL = 3
    BIRTH_POND_ID = 4
    CURRENT_POND_ID = 5
    LIGHT_LEVEL = 6 # How much energy you'd get if you BASK
    PASSIVE_LIGHT_THRESHOLD = 7
    # The light level where you start gaining energy 
    # every time you execute for free.
    BURN_THRESHOLD = 8
    # The energy level in which mutations start to happen. Higher levels
    # result in more mutations. High enough, and you'll quickly suicide
    # because you'll NUDGE thin air.

BINARY_OPCODES = (Opcode.ADD, Opcode.SUBTRACT, Opcode.DIVIDE, Opcode.MODULO,
                  Opcode.BAND, Opcode.BOR, Opcode.BXOR)
UNARY_OPCODES = (Opcode.BINVERT, Opcode.ZERO)
