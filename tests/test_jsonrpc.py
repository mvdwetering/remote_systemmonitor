import asyncio
import json
import logging
from unittest.mock import Mock, call
import pytest

from jsonrpc import JsonRpc, JsonRpcResponse, JsonRpcResponseError
from jsonrpc.transports.dummy_transport import JsonRpcDummyTransport

_LOGGER = logging.getLogger(__name__)

@pytest.fixture
def transport_mock():
    return Mock()

@pytest.fixture
def dummy_transport():
    return JsonRpcDummyTransport()

@pytest.fixture
def jsonrpc_with_subtract(dummy_transport):

    async def subtract(subtrahend, minuend):
        return subtrahend - minuend

    jrpc = JsonRpc(dummy_transport)
    jrpc.register_request_handler("subtract", subtract)

    return jrpc


def assert_json_strings(left, right):
    left = json.loads(left)
    right = json.loads(right)
    assert left == right

async def test_rpc_call_with_positional_parameters(dummy_transport, jsonrpc_with_subtract):
    # receive = transport_mock.register_on_receive_handler.call_args[0][0]
    # receive(
    #     '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}'
    # )

    # dummy_transport.call_receive('{"jsonrpc": "2.0", "method": "foobar", "id": "1"}')
    # assert_json_strings(dummy_transport.receive_responses[0], '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}')

    # # Need to wait until the send is done, but how??
    # # Could make a real mock/dummy transport for easier testing?
    # # Have it raise an exception or set an event when data is received?
    # await asyncio.sleep(0.1)
    # assert_json_strings(transport_mock.send.call_args[0][0], '{"jsonrpc": "2.0", "result": 19, "id": 1}')


    # receive(
    #     '{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}'
    # )

    # # Need to wait until the send is done, but how??
    # # Could make a real mock/dummy transport for easier testing?
    # # Have it raise an exception or set an event when data is received?
    # await asyncio.sleep(0.1)
    # assert_json_strings(transport_mock.send.call_args[0][0], '{"jsonrpc": "2.0", "result": -19, "id": 2}')

    await dummy_transport.call_receive('{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}')
    assert_json_strings(dummy_transport.receive_responses[0], '{"jsonrpc": "2.0", "result": 19, "id": 1}')


    await dummy_transport.call_receive('{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}')
    assert_json_strings(dummy_transport.receive_responses[1], '{"jsonrpc": "2.0", "result": -19, "id": 2}')



async def test_rpc_call_with_named_parameters(transport_mock, jsonrpc_with_subtract):
    receive = transport_mock.register_on_receive_handler.call_args[0][0]
    receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}'
    )

    # Need to wait until the send is done, but how??
    # Could make a real mock/dummy transport for easier testing?
    # Have it raise an exception or set an event when data is received?
    await asyncio.sleep(0.1)
    assert_json_strings(transport_mock.send.call_args[0][0], '{"jsonrpc": "2.0", "result": 19, "id": 3}')



    receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}'
    )

    # Need to wait until the send is done, but how??
    # Could make a real mock/dummy transport for easier testing?
    # Have it raise an exception or set an event when data is received?
    await asyncio.sleep(0.1)
    assert_json_strings(transport_mock.send.call_args[0][0], '{"jsonrpc": "2.0", "result": 19, "id": 4}')



async def test_rpc_call_of_non_existent_method(dummy_transport):
    j = JsonRpc(dummy_transport)

    await dummy_transport.call_receive('{"jsonrpc": "2.0", "method": "foobar", "id": "1"}')
    assert_json_strings(dummy_transport.receive_responses[0], '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}')
