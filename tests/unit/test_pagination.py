import pytest
from pydantic import ValidationError

from app.core.pagination import Page, PageParams


def test_page_size_is_bounded() -> None:
    """Client page sizes above the documented maximum must be rejected."""
    with pytest.raises(ValidationError):
        PageParams(page=1, page_size=101)


@pytest.mark.parametrize("page", [0, -1])
def test_page_must_be_positive(page: int) -> None:
    """Zero and negative pages cannot produce database offsets."""
    with pytest.raises(ValidationError):
        PageParams(page=page)


def test_default_page_parameters_and_offset() -> None:
    """The first page uses the documented default size and zero offset."""
    params = PageParams()

    assert (params.page, params.page_size, params.offset) == (1, 20, 0)


def test_later_page_offset() -> None:
    """Repository pagination skips exactly the preceding rows."""
    assert PageParams(page=3, page_size=25).offset == 50


def test_page_response_contains_requested_pagination() -> None:
    """A typed page keeps records, totals, and request coordinates."""
    page = Page[int](items=[4, 5], total=8, page=2, page_size=2)

    assert page.model_dump() == {"items": [4, 5], "total": 8, "page": 2, "page_size": 2}
