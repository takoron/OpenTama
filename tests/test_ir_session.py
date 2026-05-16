"""Tests for the high-level IR session (greet / gift / visit)."""

import threading

import pytest

from opentama.core import Tamagotchi
from opentama.ir.session import (
    GIFT_HAPPINESS_DELTA,
    GIFT_HUNGER_DELTA,
    GREET_HAPPINESS_DELTA,
    VISIT_HAPPINESS_DELTA,
    Session,
)
from opentama.ir.transport import LoopbackIRTransport
from opentama.state import TamaState


def _make_pet(name: str, **kwargs) -> Tamagotchi:
    state = TamaState(
        name=name,
        company_ssid="",
        last_tick_at=1_000_000.0,
        **kwargs,
    )
    return Tamagotchi(state, ssid_provider=lambda: None, clock=lambda: 1_000_000.0)


def _run_pair(initiator_call, responder_action="serve_once"):
    """Run an initiator method and a responder serve_once in parallel."""
    pet_a = _make_pet("Alice")
    pet_b = _make_pet("Bob")
    t_a, t_b = LoopbackIRTransport.pair()
    sess_a = Session(pet_a, t_a, timeout=2.0)
    sess_b = Session(pet_b, t_b, timeout=2.0)

    results: dict[str, object] = {}

    def responder():
        # Some flows expect more than one inbound frame.
        if responder_action == "serve_twice":
            results["b1"] = sess_b.serve_once()
            results["b2"] = sess_b.serve_once()
        else:
            results["b"] = sess_b.serve_once()

    t = threading.Thread(target=responder)
    t.start()
    results["a"] = initiator_call(sess_a)
    t.join(timeout=3.0)
    return pet_a, pet_b, results


# --- greet ------------------------------------------------------------------


def test_greet_exchanges_names_and_bumps_happiness():
    pet_a, pet_b, res = _run_pair(lambda s: s.greet())
    a_result = res["a"]
    b_result = res["b"]

    assert a_result.ok, a_result.error
    assert a_result.peer.name == "Bob"
    assert b_result.ok
    assert b_result.peer.name == "Alice"
    assert pet_a.state.happiness == 80.0 + GREET_HAPPINESS_DELTA
    assert pet_b.state.happiness == 80.0 + GREET_HAPPINESS_DELTA


def test_greet_records_met_achievement():
    pet_a, pet_b, _ = _run_pair(lambda s: s.greet())
    assert "met:Bob" in pet_a.state.achievements
    assert "met:Alice" in pet_b.state.achievements


# --- gift -------------------------------------------------------------------


def test_gift_food_increases_recipient_hunger():
    pet_a = _make_pet("Alice")
    pet_b = _make_pet("Bob", hunger=40.0)
    t_a, t_b = LoopbackIRTransport.pair()
    sess_a = Session(pet_a, t_a)
    sess_b = Session(pet_b, t_b)

    def responder():
        sess_b.serve_once()

    t = threading.Thread(target=responder)
    t.start()
    r = sess_a.gift(kind="food")
    t.join(timeout=3.0)

    assert r.ok, r.error
    assert pet_b.state.hunger == 40.0 + GIFT_HUNGER_DELTA
    # Recipient happiness bumped once for "food".
    assert pet_b.state.happiness == 80.0 + GIFT_HAPPINESS_DELTA


def test_gift_toy_double_happiness_bump():
    pet_a = _make_pet("Alice")
    pet_b = _make_pet("Bob")
    t_a, t_b = LoopbackIRTransport.pair()
    sess_a = Session(pet_a, t_a)
    sess_b = Session(pet_b, t_b)

    t = threading.Thread(target=sess_b.serve_once)
    t.start()
    r = sess_a.gift(kind="toy")
    t.join(timeout=3.0)

    assert r.ok
    # Toy gives the base gift bump plus the toy bonus.
    assert pet_b.state.happiness == 80.0 + 2 * GIFT_HAPPINESS_DELTA


def test_gift_unknown_kind_rejected():
    pet = _make_pet("X")
    t, _ = LoopbackIRTransport.pair()
    sess = Session(pet, t)
    with pytest.raises(ValueError):
        sess.gift(kind="rocket")


# --- visit ------------------------------------------------------------------


def test_visit_full_flow_boosts_both_pets():
    pet_a, pet_b, res = _run_pair(lambda s: s.visit(), responder_action="serve_twice")
    a = res["a"]
    assert a.ok, a.error
    # Each side gets greet bonus + visit bonus.
    expected = 80.0 + GREET_HAPPINESS_DELTA + VISIT_HAPPINESS_DELTA
    assert pet_a.state.happiness == expected
    assert pet_b.state.happiness == expected
    assert "visited:Bob" in pet_a.state.achievements
    assert "visited:Alice" in pet_b.state.achievements


# --- error paths ------------------------------------------------------------


def test_greet_times_out_when_peer_silent():
    pet = _make_pet("Lonely")
    t, _ = LoopbackIRTransport.pair()
    sess = Session(pet, t, timeout=0.05)
    r = sess.greet()
    assert not r.ok
    assert "no response" in r.error
