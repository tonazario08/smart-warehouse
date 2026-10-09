import pytest
from pydantic import ValidationError

from app.core.pagination import PageParams


def test_page_size_is_bounded() -> None:
    """Client page sizes above the documented maximum must be rejected."""
    with pytest.raises(ValidationError):
        PageParams(page=1, page_size=101)
