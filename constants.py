import flufl.enum
import math

ROOT_TWO = math.sqrt(2)
# Moving diagonally costs more. Keep this number around.

WORD_BYTES = 4
WORD_BITS = WORD_BYTES * 8
MAX_INT = 2**WORD_BITS
MEMORY_WORDS = 1024
ADDRESS_SIZE = int(math.log(MEMORY_WORDS, 2))
START_ENERGY = 500
NUMBER_OF_SUNS = 3
SUN_MAX_BRIGHTNESS = 100000

def LIGHT_FADE(distance):
    try:
        inverse = 1 / float(distance)
    except ZeroDivisionError:
        inverse = 1

    return SUN_MAX_BRIGHTNESS * inverse
            


OPCODE_BITS = 8
ADDRESS_MODE_BITS = 2

# Pi multiplied to be big enough to fit in a standard word.
BIG_PI = int(math.pi * 1000000000)
BIG_E = int(math.e * 1000000000)
assert BIG_PI < MAX_INT
assert BIG_E < MAX_INT

INSTRUCTION_FORMAT = (
    "uintbe:{}".format(OPCODE_BITS),     # OPCODE
    "uint:{}".format(ADDRESS_MODE_BITS), # SRC MODE
    "uint:{}".format(ADDRESS_SIZE),      # SRC ADDR
    "uint:{}".format(ADDRESS_MODE_BITS), # DEST MODE
    "uint:{}".format(ADDRESS_SIZE),      # DEST ADDRESS
)

assert OPCODE_BITS + 2*ADDRESS_MODE_BITS + 2*ADDRESS_SIZE == WORD_BITS

class Opcode(flufl.enum.IntEnum):
    # only have a defined enum member if there's actual behaviour defined.
    # with the humble exception of noop.
    NOOP = 0x00

    COPY = 0x1f

    # Binary operations.
    ADD = 0x01
    SUBTRACT = 0x02
    MULTIPLY = 0x03
    DIVIDE = 0x04
    MODULO = 0x05
    BAND = 0x06
    BOR = 0x07
    BXOR = 0x08
    LEFTSHIFT = 0x09
    RIGHTSHIFT = 0x0a
    EXCHANGE = 0x0b

    # Unary operations.
    BINVERT = 0x0c
    ZERO = 0x0d

    JUMP = 0x0e
    SKIP = 0x0f
    SKIPLESS = 0x10
    STOP = 0x11

    SNIFF = 0x12
    RANDOM = 0x13

    FACE = 0x14

    # In the direction you're pointing, tells you the type of thing you're
    # pointed straight at, whether an edgeline, a trunkport, sun, soulmate,
    # etc.
    # I suppose the src_value passed to the Ladar determines what sort of
    # "mode" it's in?
    LADAR = 0x15

    ETHERREAD = 0x16
    ETHERWRITE = 0x17

    # Transfer all energy in direction you're pointing; and if allowed
    # write src_value in (dest_value % WORD_INDEX) to the corresponding cell
    # Can be used for message passing, as well as offence.
    # Remember, that nudging a soulless cell give it your energy, and your
    # soul. But a random memory. That'll be fun.
    NUDGE = 0x18

    # Like STOP, except you actively gain energy proportional to the
    # Scent.LIGHT_LEVEL. No arguments. Handled at a higher level, but
    # the end of interpreter execution.
    BASK = 0x19
    
    # At an energy penalty, give execution to the cell you're pointing at.
    # No arguments.
    HANDOFF = 0x1a

    # Move the first SRC_VALUE words of yourself, using DEST_VALUE energy.
    # Any unused energy vanishes.
    MOVE = 0x1b

    PROCURE = 0x1c
    # Take src_value energy from the cell that you're facing, if allowed.
    # If src_value is greater than their energy, then just drain them dry.
    # However, this ends execution, probably. And it's not a one hundred
    # percent efficent.

    BESTOW = 0x1d
    # Give src_value energy in the cell you're facing. If it was a soulless,
    # congrats, you just had a baby. If src_value is more than you have,
    # then you drain yourself for your child. Kudos.
    # does not end execution. You know. Unless you dry up.

    TEACH = 0x1e

class AddressMode(flufl.enum.IntEnum):
    NORMAL = 0b00
    ACCUMULATOR = 0b01
    LITERAL = 0b10
    INDIRECT = 0b11

class Direction(flufl.enum.IntEnum):
    WEST = 0
    NORTHWEST = 1
    NORTH = 2
    NORTHEAST = 3
    EAST = 4
    SOUTHEAST = 5
    SOUTH = 6
    SOUTHWEST = 7

DIRECTIONS = len(list(Direction))
DIAGONAL_DIRECTIONS = (Direction.NORTHWEST,
                       Direction.NORTHEAST,
                       Direction.SOUTHEAST,
                       Direction.SOUTHWEST)

class Scent(flufl.enum.IntEnum):
    # I'm going to guess that sniffing for some of these scents are
    # more expensive, due to them involving more complex stuff.
    # Uncomment the value when you've implemented it.
    CURRENT_ENERGY = 0
    START_ENERGY = 1

    SOUL = 2
    #BIRTH_POND_ID = 3
    #CURRENT_POND_ID = 4
    LIGHT_LEVEL = 5 # How much energy you'd get if you BASK
    #PASSIVE_LIGHT_THRESHOLD = 6

    # The light level where you start gaining energy 
    # every time you execute for free.

    #BURN_THRESHOLD = 7

    # The energy level in which mutations start to happen. Higher levels
    # result in more mutations. High enough, and you'll quickly suicide
    # because you'll NUDGE thin air.
    PI = 8
    # The beautiful smell of pie.
    E = 9
    # The incredible smell of... E?
    CHECKSUM = 10
    # The checksum of the memory RIGHT now. As in, the checksum is calculated
    # and if it's written to memory, then it'll probably change.

    # Distances measurements are probably for the sake of the children,
    # be without the accompanying sqrt, to save time.

    #SUN_DISTANCE = 12
    #SUN_DIRECTION = 13

    #TRUNKPORT_DISTANCE = 14
    #TRUNKPORT_DIRECTION = 15

    #SOULMATE_DISTANCE = 16
    #SOULMATE_DIRECTION = 17

    #HEATHEN_DISTANCE = 18
    #HEATHEN_DIRECTION = 19

    # Edgespace is somewhat lethal, in that you'll start losing energy
    # automatically, akin to being too close to the sun, but in reverse.

    #EDGE_DISTANCE = 20
    #EDGE_DIRECTION = 21

    # I suppose you could have "black holes", which have an edge border

    # If non-zero, you're in edge space, and are losing that much energy
    # every time you're executed. If this is non zero, then edge sniffing,
    # as above, indicates the closest way back.

    #EDGE_LEVEL = 22


class LadarAnswer(flufl.enum.IntEnum):
    EDGELINE = 1
    SOULMATE = 2
    TRUNKPORT = 3
    SUN = 4
    HEATHEN = 5
    NOTHING = 6 # not entirely sure how you'd get this.

BINARY_OPCODES = (Opcode.ADD, Opcode.SUBTRACT, Opcode.DIVIDE, Opcode.MODULO,
                  Opcode.BAND, Opcode.BOR, Opcode.BXOR, Opcode.LEFTSHIFT,
                  Opcode.RIGHTSHIFT)
UNARY_OPCODES = (Opcode.BINVERT, Opcode.ZERO)
PRICEY_OPCODES = (Opcode.LADAR, Opcode.ETHERREAD, Opcode.ETHERWRITE,
                  Opcode.NUDGE, Opcode.HANDOFF, Opcode.MOVE, Opcode.PROCURE,
                  Opcode.BESTOW, Opcode.TEACH)

