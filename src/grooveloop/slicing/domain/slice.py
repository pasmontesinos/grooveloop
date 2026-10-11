from __future__ import annotations

from typing import TYPE_CHECKING, Self

from grooveloop.slicing.domain.slice_id import SliceId

if TYPE_CHECKING:
    from grooveloop.slicing.domain.slice_order import SliceOrder


class Slice:
    def __init__(
        self,
        id: SliceId,
        title: str,
        order: SliceOrder,
        description: str = "",
        verify_deploy: bool = False,
        depends_on: list[SliceOrder] | None = None,
    ) -> None:
        self._id = id
        self._title = title
        self._order = order
        self._description = description
        self._verify_deploy = verify_deploy
        self._depends_on = depends_on

    @classmethod
    def create(
        cls,
        title: str,
        order: SliceOrder,
        description: str,
        verify_deploy: bool,
        depends_on: list[SliceOrder] | None,
    ) -> Self:
        return cls(
            id=SliceId.generate(),
            title=title,
            order=order,
            description=description,
            verify_deploy=verify_deploy,
            depends_on=depends_on,
        )

    @property
    def id(self) -> SliceId:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def order(self) -> SliceOrder:
        return self._order

    @property
    def description(self) -> str:
        return self._description

    @property
    def verify_deploy(self) -> bool:
        return self._verify_deploy

    @property
    def depends_on(self) -> list[SliceOrder] | None:
        return self._depends_on
