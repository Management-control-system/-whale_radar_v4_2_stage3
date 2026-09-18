import json
from pathlib import Path

ROOT = Path(__file__).parent / 'fixtures'

def load(name): return json.loads((ROOT/name).read_text())

def u256(hexword): return int(hexword, 16)
def i256(hexword):
    n=int(hexword,16); return n-(1<<256) if n >= (1<<255) else n

def test_v2_fixture_layout():
    x=load('v2_swap.json'); words=[x['data'][2+i:2+i+64] for i in range(0,256,64)]
    assert [u256(w) for w in words] == [10**18,0,0,2*10**6]
    assert len(x['topics']) == 3

def test_v3_fixture_signed_layout():
    x=load('v3_swap.json'); words=[x['data'][2+i:2+i+64] for i in range(0,320,64)]
    assert i256(words[0]) == 123456
    assert i256(words[1]) == -789
    assert u256(words[2]) == 2**96
    assert u256(words[3]) == 100000
    assert i256(words[4]) == -12
