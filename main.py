"""Scratchpad for Defcon's Hardware Hacking Village's Rube Goldberg Machine.

For local testing you can use `socat` to spin up two virtual RS-232 devices.
    socat -d -d pty,rawer,echo=0,link=/tmp/ttyV0,b9600 pty,rawer,echo=0,link=/tmp/ttyV1,b9600

The human signal will come from a switch connected to an Arduino's GPIO pin. The
Arduino will capture the signal at 4 baud and send the bit over its serial/USB
connection to the computer at 9600 baud.

"""
import queue
import random
import threading
import time

import matplotlib.pyplot as plt
import serial

# This in queue will contain bytes from DCE. It's the very start of our chain.
dce_inq = queue.Queue()
# The out queue will contain bits that we can pull at a very low baud rate and
# display to the meat bag.
dce_outq = queue.Queue()

dte_outq = queue.Queue()


class TransformerQueue:
    """Transforms values from an input queue and puts the transformation in an output queue.

    `transform` needs to be a function that returns a list, even if you're
    transforming a single value to a single value.

    This class is useful as both a buffer to throttle the incoming messages
    and a way to convert bytes to 1's and 0's so that we can display those 1's
    and 0's on a graph.

    If we want to terminate the manual work that we're doing of transcribing
    the 1's and 0's, then we still have the backing queue of messages that
    we can pass along by automated digital means, so we don't lose any
    messages and thus break the Rube Goldberg machine.
    """
    def __init__(self, q1, q2, transform):
        self.q1 = q1
        self.q2 = q2
        self.transform = transform

    def empty(self):
        return self.q2.empty() and self.q1.empty()

    def put(self, *args, **kwargs):
        return self.q1.put(*args, **kwargs)

    def get(self, *args, **kwargs):
        if self.empty():
            raise queue.Empty()
        if self.q2.empty():
            for v in self.transform(self.q1.get(*args, **kwargs)):
                self.q2.put(v)
        return self.q2.get(*args, **kwargs)


def byte_to_bits(byte):
    """Convert a byte to a list of 8 1's and 0's."""
    assert byte <= 255, "Can't send more than 8 bits in a single RS-232 message."
    out = []
    for _ in range(8):
        out.append(byte & 0x01)
        byte >>= 1
    return reversed(out)


dce_transformer = TransformerQueue(dce_inq, dce_outq, byte_to_bits)


# This in queue will contain the bits that the meat bag signaled.
# We'll probably receive each bit by way of an Arduino talking to us over RS-232
# where each RS-232 byte will contain a single human-entered bit.
human_signal_inq = queue.Queue()  # Bits
# This out queue will be the bytes we get when we combine those bits.
# (Maybe we could just write the byte directly to serial. But I'm going with
# this for now.)
human_signal_outq = queue.Queue()  # Bytes


# Pretend we're getting input from a DCE terminal.
# For testing purposes.
# Create a device like this with:
#     socat -d -d pty,rawer,echo=0,link=/tmp/ttyV0,b9600 pty,rawer,echo=0,link=/tmp/ttyV1,b9600
with serial.Serial("/dev/pts/6", 9600) as dce_out:
    dce_out.write(b"Hello, world!")


def dce_inq_listen():
    """
    Read one byte at a time from DCE and put in a queue.

    The queue is a "transformer" queue that will transform
    the byte values into a sequence of 0's and 1's.
    """
    with serial.Serial("/dev/pts/7", 9600) as dce_in:
        while True:
            dce_transformer.put(ord(dce_in.read()))


def speak():
    """Background thread to populate the in queue."""
    t = threading.Thread(target=dce_inq_listen)
    t.start()


def bits_to_byte(bits):
    """Convert list of 8 1's and 0's to a single int value."""
    out = 0
    for bit in bits:
        out = (out << 1) | bit
    return out


def display_dce():
    """
    Display a graph of the input signal, slow enough for a human to transcribe.

    This is probably the most finicky part of the process right now. It's not a very
    clean display. The framerate isn't great. It's a bit choppy.
    """
    SAMPLE_RATE = 500  # In milliseconds
    FRAME_RATE = 60
    FRAME_SIZE = 1000
    SLEEP = 1 / FRAME_RATE

    fig, ax = plt.subplots()

    ax.set_xlim(0, 1000, auto=False)
    ax.spines["left"].set_position("center")
    ax.spines["bottom"].set_position("center")
    ax.spines["right"].set_color("none")
    ax.spines["top"].set_color("none")

    points = []

    prev = time.time_ns()

    plt.ion()
    plt.show()
    while True:
        # Advance all points
        for point in points:
            point[0] += 1/80 * FRAME_SIZE

        # If we've passed 250ms, take a sample.
        if time.time_ns() - prev > SAMPLE_RATE * 1e6:
            prev += SAMPLE_RATE * 1e6
            new_sample = [0, dce_transformer.get()]
            if points and new_sample[1] != points[-1][1]:
                points.append([points[-1][0], new_sample[1]])  # prev point's x, new sample's y.
            points.append(new_sample)

        filtered = []
        for point in points:
            if point[0] < FRAME_SIZE:
                filtered.append(point)

        points = filtered

        lines = ax.get_lines()
        for line in lines:
            line.remove()

        ax.plot(*zip(*points), color="black")
        plt.draw()
        plt.pause(SLEEP)


def sample_signal():
    """Get a signal from the human-managed switch."""
    # The signal will come from an Arduino or something.
    # This fakes it until that's setup.
    return [0, random.randint(0, 1)]


def human_signal_listen():
    """Read one byte (which represents 1 bit) at a time from human input."""
    bits = [0] * 8
    i = 0
    with serial.Serial("/dev/pts/11", 9600) as human_signal_in:
        while True:
            bits[i] = human_signal_in.put(human_signal_inq.read())
            i += 1
            if i == 8:
                i = 0
                human_signal_outq.put()
