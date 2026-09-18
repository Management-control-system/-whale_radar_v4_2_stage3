import json
from pathlib import Path

from abi_decode import decode_v2_pair_created, decode_v3_pool_created
from constants import DEFAULT_FACTORY_REGISTRY


ROOT = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((ROOT / name).read_text())


def test_v2_pair_created_fixture():
    item = load("v2_pair_created.json")
    decoded = decode_v2_pair_created(item, 1, DEFAULT_FACTORY_REGISTRY[0])
    assert decoded.event_name == "PairCreated"
    assert decoded.pool.version == "v2"
    assert decoded.pool.pool_address.lower() == "0x2f2fbf8ea318dc6425f006afc92a837ac29f95ce"


def test_v3_pool_created_fixture():
    item = load("v3_pool_created.json")
    decoded = decode_v3_pool_created(item, 1, DEFAULT_FACTORY_REGISTRY[1])
    assert decoded.event_name == "PoolCreated"
    assert decoded.pool.version == "v3"
    assert decoded.pool.fee == 3000
    assert decoded.pool.tick_spacing == 60
    assert decoded.pool.pool_address.lower() == "0x39941a99ea5625926057d26d226f6c203f6b8505"

from abi_decode import decode_v2_swap, decode_v3_swap


def test_v2_swap_fixture_normalizes_input_output():
    item = load("v2_swap.json")
    decoded = decode_v2_swap(item, 1)
    assert decoded["version"] == "v2"
    assert decoded["sender"].lower() == "0x1111111111111111111111111111111111111111"
    assert decoded["recipient"].lower() == "0x2222222222222222222222222222222222222222"
    assert decoded["amount_in"] == 10**18
    assert decoded["amount_out"] == 2*10**6
    assert decoded["token_in_index"] == 0
    assert decoded["token_out_index"] == 1


def test_v3_swap_fixture_signed_deltas():
    item = load("v3_swap.json")
    decoded = decode_v3_swap(item, 1)
    assert decoded["version"] == "v3"
    assert decoded["amount0"] == 123456
    assert decoded["amount1"] == -789
    assert decoded["amount_in"] == 123456
    assert decoded["amount_out"] == 789
    assert decoded["token_in_index"] == 0
    assert decoded["token_out_index"] == 1
    assert decoded["tick"] == -12
