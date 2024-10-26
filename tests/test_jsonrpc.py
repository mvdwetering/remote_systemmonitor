import asyncio
import json
import logging
from unittest.mock import Mock
import pytest

from jsonrpc import JsonRpc
from jsonrpc.transports.dummy_transport import JsonRpcDummyTransport

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def transport_mock():
    return Mock()


@pytest.fixture
def dummy_transport():
    return JsonRpcDummyTransport()


@pytest.fixture
def jsonrpc_with_dummy_transport(dummy_transport):
    return JsonRpc(dummy_transport)


async def subtract(minuend, subtrahend):
    return minuend - subtrahend


def assert_json_strings(left, right):
    left = json.loads(left)
    right = json.loads(right)
    assert left == right


async def test_rpc_call_with_positional_parameters(
    dummy_transport, jsonrpc_with_dummy_transport
):
    jsonrpc_with_dummy_transport.register_request_handler("subtract", subtract)

    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "result": 19, "id": 1}',
    )

    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "result": -19, "id": 2}',
    )


async def test_rpc_call_with_named_parameters(
    dummy_transport, jsonrpc_with_dummy_transport
):
    jsonrpc_with_dummy_transport.register_request_handler("subtract", subtract)

    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "result": 19, "id": 3}',
    )

    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "result": 19, "id": 4}',
    )


async def test_a_notification(dummy_transport, jsonrpc_with_dummy_transport):

    update_params = None
    foobar_called = False

    async def update_handler(a, b, c, d, e):
        nonlocal update_params
        update_params = f"{a},{b},{c},{d},{e}"

    async def foobar_handler():
        nonlocal foobar_called
        foobar_called = True

    jsonrpc_with_dummy_transport.register_notification_handler("update", update_handler)
    jsonrpc_with_dummy_transport.register_notification_handler("foobar", foobar_handler)

    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}'
    )
    assert dummy_transport.last_received_response() is None
    assert update_params == "1,2,3,4,5"

    await dummy_transport.call_receive('{"jsonrpc": "2.0", "method": "foobar"}')
    assert dummy_transport.last_received_response() is None
    assert foobar_called


async def test_rpc_call_of_non_existent_method(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "foobar", "id": "1"}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}',
    )

async def test_rpc_call_with_invalid_json(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}',
    )

async def test_rpc_call_with_invalid_request_object(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive(
        '{"jsonrpc": "2.0", "method": 1, "params": "bar"}'
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}',
    )

async def test_rpc_call_batch_invalid_json(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive(
        '''[
  {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
  {"jsonrpc": "2.0", "method"
  ]
  '''
    )
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}',
    )

@pytest.mark.skip(reason="Batch not implemented yet")
async def test_rpc_call_with_empty_array(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive('[]')
    assert_json_strings(
        dummy_transport.last_received_response(),
        '{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}',
    )

@pytest.mark.skip(reason="Batch not implemented yet")
async def test_rpc_call_with_invalid_batch_but_not_empty(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive('[1]')
    assert_json_strings(
        dummy_transport.last_received_response(),
        '[{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}]',
    )

@pytest.mark.skip(reason="Batch not implemented yet")
async def test_rpc_call_with_invalid_batch(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive('[1,2,3]')
    assert_json_strings(
        dummy_transport.last_received_response(),
        '''[
  {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
  {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
  {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
]'''
    )

@pytest.mark.skip(reason="Batch not implemented yet")
async def test_rpc_call_batch(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive('''[
        {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
        {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
        {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
        {"foo": "boo"},
        {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
        {"jsonrpc": "2.0", "method": "get_data", "id": "9"} 
    ]''')
    assert_json_strings(
        dummy_transport.last_received_response(),
        '''[
        {"jsonrpc": "2.0", "result": 7, "id": "1"},
        {"jsonrpc": "2.0", "result": 19, "id": "2"},
        {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
        {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "5"},
        {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
    ]'''
    )

@pytest.mark.skip(reason="Batch not implemented yet")
async def test_rpc_call_batch_all_notifications(
    dummy_transport, jsonrpc_with_dummy_transport
):
    await dummy_transport.call_receive('''[
        {"jsonrpc": "2.0", "method": "notify_sum", "params": [1,2,4]},
        {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]}
    ]''')
    assert jsonrpc_with_dummy_transport.last_received_response() is None
