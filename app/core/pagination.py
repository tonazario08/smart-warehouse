"""Reusable pagination request and response models."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Validated one-based pagination parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        """Return the zero-based offset for the requested page."""
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):  # noqa: UP046 - Pydantic needs Generic on Python 3.12.
    """A page of records and the parameters used to retrieve it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    total: int
    page: int
    page_size: int
