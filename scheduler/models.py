from dataclasses import dataclass
from typing import Literal


Timeslot = Literal[
    "8:45-9:30",
    "9:30-10:15",
    "10:15-11:00",
    "11:30-12:15",
    "12:15-13:00",
]


@dataclass(frozen=True)
class Student:
    identifier: str
    name: str
    stage: str | None = None
    group: str | None = None


@dataclass(frozen=True)
class Adult:
    identifier: str
    name: str
    role: str | None = None


@dataclass(frozen=True)
class Workshop:
    identifier: str
    name: str
    space: str
    timeslot: Timeslot
    capacity_students: int | None = None
    capacity_adults: int | None = 1
    notes: str | None = None
