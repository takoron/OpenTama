"""Tests for capability enforcement in :class:`PluginContext`."""

import pytest

from opentama.core import Tamagotchi
from opentama.ir.transport import LoopbackIRTransport
from opentama.plugins import (
    Capability,
    CapabilityDenied,
    PluginContext,
    StateView,
    make_context,
)
from opentama.state import TamaState


def _pet() -> Tamagotchi:
    return Tamagotchi(
        TamaState(name="Cap", last_tick_at=1.0, company_ssid=""),
        ssid_provider=lambda: None,
        clock=lambda: 1.0,
    )


def test_state_read_denied_without_capability():
    ctx = PluginContext(capabilities=set(), tama=_pet())
    with pytest.raises(CapabilityDenied):
        ctx.get_state()


def test_state_read_allowed_with_capability():
    ctx = PluginContext(capabilities={Capability.STATE_READ}, tama=_pet())
    view = ctx.get_state()
    assert isinstance(view, StateView)
    assert view.name == "Cap"


def test_state_write_denied_without_capability():
    ctx = PluginContext(capabilities={Capability.STATE_READ}, tama=_pet())
    with pytest.raises(CapabilityDenied):
        ctx.feed()
    with pytest.raises(CapabilityDenied):
        ctx.play()


def test_state_write_allowed_with_capability():
    pet = _pet()
    pet.state.hunger = 50.0
    ctx = PluginContext(capabilities={Capability.STATE_WRITE}, tama=pet)
    ctx.feed()
    assert pet.state.hunger > 50.0


def test_ir_send_denied_without_capability():
    a, _b = LoopbackIRTransport.pair()
    ctx = PluginContext(
        capabilities={Capability.STATE_READ},
        tama=_pet(),
        ir_send=a.send,
        ir_recv=lambda t=1.0: a.recv(timeout=t),
    )
    with pytest.raises(CapabilityDenied):
        ctx.ir_send(b"x")


def test_ir_recv_denied_without_capability():
    a, _b = LoopbackIRTransport.pair()
    ctx = PluginContext(
        capabilities={Capability.STATE_READ},
        tama=_pet(),
        ir_send=a.send,
        ir_recv=lambda t=1.0: a.recv(timeout=t),
    )
    with pytest.raises(CapabilityDenied):
        ctx.ir_recv()


def test_ir_send_allowed_when_capability_granted():
    a, b = LoopbackIRTransport.pair()
    ctx = PluginContext(
        capabilities={Capability.IR_TRANSMIT},
        tama=_pet(),
        ir_send=a.send,
        ir_recv=lambda t=1.0: a.recv(timeout=t),
    )
    ctx.ir_send(b"hi")
    assert b.recv(timeout=0.2) == b"hi"


def test_make_context_skips_ir_wiring_for_display_only_plugin():
    """A display plugin must not get IR send/recv even if a transport exists."""
    a, _ = LoopbackIRTransport.pair()
    ctx = make_context(
        capabilities={Capability.DISPLAY},
        tama=_pet(),
        transport=a,
    )
    # ir_send/ir_recv should be unwired.
    assert ctx._ir_send is None
    assert ctx._ir_recv is None


def test_make_context_wires_ir_when_capability_present():
    a, _ = LoopbackIRTransport.pair()
    ctx = make_context(
        capabilities={Capability.IR_TRANSMIT, Capability.IR_RECEIVE},
        tama=_pet(),
        transport=a,
    )
    assert ctx._ir_send is not None
    assert ctx._ir_recv is not None


def test_state_view_is_read_only():
    """StateView is a frozen dataclass — mutations must fail."""
    ctx = PluginContext(capabilities={Capability.STATE_READ}, tama=_pet())
    view = ctx.get_state()
    with pytest.raises(Exception):  # FrozenInstanceError subclasses AttributeError
        view.name = "hacked"  # type: ignore[misc]


def test_no_state_no_pet_attached():
    ctx = PluginContext(capabilities={Capability.STATE_READ})
    with pytest.raises(RuntimeError):
        ctx.get_state()


def test_ir_send_without_transport_raises_runtime_error():
    ctx = PluginContext(capabilities={Capability.IR_TRANSMIT}, tama=_pet())
    with pytest.raises(RuntimeError):
        ctx.ir_send(b"x")
