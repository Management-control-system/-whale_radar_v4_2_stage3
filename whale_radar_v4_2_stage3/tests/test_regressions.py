import inspect

import factory_discovery
import abi_decode


def test_v3_regression_symbol_is_defined():
    source = inspect.getsource(factory_discovery.process_factory_log_async)
    assert "V3_POOL_CREATED" not in source or "decode_v3_pool_created" in source


def test_decoder_uses_codec():
    source = inspect.getsource(abi_decode.decode_event)
    assert "get_event_data(_DECODER" in source
    assert "_DECODER = Web3().codec" in inspect.getsource(abi_decode)


def test_no_silent_decode_exception():
    source = inspect.getsource(abi_decode.decode_event)
    assert "log.exception" in source
