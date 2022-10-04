from abc import abstractmethod
from typing import Generic, Protocol, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ISerializer(Protocol, Generic[T]):
    @abstractmethod
    def parse(self, data: Union[str, bytes]) -> T:
        ...

    @abstractmethod
    def serialize(self, message: T) -> Union[str, bytes]:
        ...
