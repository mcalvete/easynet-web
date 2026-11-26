from unittest.mock import AsyncMock

import pytest
from easynet_web.easynet.client import EasyNetClient, EasyNetError


def test_legacy_register_response_is_parsed() -> None:
    raw = "error_geo_get_reg=0\ndir=6100&num=2&0001&0000\n0"

    assert EasyNetClient._parse_address_response(raw, 2002, 6100, 2) == ["0001", "0000"]


def test_block_rejects_wrong_operation() -> None:
    with pytest.raises(EasyNetError, match="Unexpected"):
        EasyNetClient._parse_block("error_2149=0\n0000\n0", 2148)


@pytest.mark.parametrize(
    ("raw", "retryable"),
    [
        ("error_2002=-7", True),
        ("error_2002=-1", False),
    ],
)
def test_register_errors_preserve_retryability(raw: str, retryable: bool) -> None:
    with pytest.raises(EasyNetError) as error:
        EasyNetClient._parse_address_response(raw, 2002, 6100, 1)

    assert error.value.retryable is retryable


def test_write_response_is_validated() -> None:
    EasyNetClient._parse_write_response("error_2012=0\n0", 2012)

    with pytest.raises(EasyNetError, match="Incomplete"):
        EasyNetClient._parse_write_response("error_2012=0\n", 2012)


@pytest.mark.asyncio
async def test_write_register_encodes_signed_int16() -> None:
    client = EasyNetClient("http://127.0.0.1")
    client._serialized_post = AsyncMock(return_value="error_2012=0\n0")  # type: ignore[method-assign]

    await client.write_register(6105, -15)

    client._serialized_post.assert_awaited_once_with(  # type: ignore[attr-defined]
        "idOperacion=2012&dir=6105&num=1&fff1"
    )
    await client.close()


@pytest.mark.asyncio
async def test_write_coil_encodes_boolean() -> None:
    client = EasyNetClient("http://127.0.0.1")
    client._serialized_post = AsyncMock(return_value="error_2011=0\n0")  # type: ignore[method-assign]

    await client.write_coil(1524, True)

    client._serialized_post.assert_awaited_once_with(  # type: ignore[attr-defined]
        "idOperacion=2011&dir=1524&num=1&1"
    )
    await client.close()
