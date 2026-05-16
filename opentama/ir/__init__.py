"""IR layer for OpenTama: protocol, transport, and high-level sessions."""

from .protocol import (
    BadCRC,
    BadLength,
    BadMagic,
    BadVersion,
    Frame,
    FrameError,
    FrameType,
    crc16,
    decode,
    encode,
    parse_stream,
)
from .session import PeerInfo, Session, SessionResult
from .transport import (
    IRTransport,
    LoopbackIRTransport,
    SerialIRTransport,
    open_transport,
)

__all__ = [
    "BadCRC",
    "BadLength",
    "BadMagic",
    "BadVersion",
    "Frame",
    "FrameError",
    "FrameType",
    "IRTransport",
    "LoopbackIRTransport",
    "PeerInfo",
    "SerialIRTransport",
    "Session",
    "SessionResult",
    "crc16",
    "decode",
    "encode",
    "open_transport",
    "parse_stream",
]
