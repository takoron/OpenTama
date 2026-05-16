"""Example IR plugin: send a tiny ping frame and report what came back.

A minimal demo of the IR_TRANSMIT + IR_RECEIVE capabilities. Wraps the
low-level transport with the protocol layer.
"""

from opentama.ir.protocol import Frame, FrameType, decode, encode
from opentama.plugins import Plugin


class IRPing(Plugin):
    name = "ir_ping"
    version = "0.1.0"

    def run(self, ctx) -> str:
        ctx.ir_send(encode(Frame.of(FrameType.HELLO, {"ping": True})))
        raw = ctx.ir_recv(timeout=2.0)
        if not raw:
            return "no response from peer"
        reply = decode(raw)
        return f"got {reply.type.name}: {reply.json()}"


PLUGIN = IRPing()
