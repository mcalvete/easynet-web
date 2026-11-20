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

