"""Scheduling logic for the LS timetable application."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

from .models import Adult, Student, Timeslot, Workshop


@dataclass
class Assignment:
    workshop: Workshop
    students: set[str]
    adults: set[str]


class Schedule:
    """In-memory representation of all assignments."""

    def __init__(self, workshops: Iterable[Workshop]):
        self._workshops_by_id: Dict[str, Workshop] = {workshop.identifier: workshop for workshop in workshops}
        self._assignments: Dict[Timeslot, Dict[str, Assignment]] = defaultdict(dict)
        for workshop in workshops:
            self._assignments[workshop.timeslot][workshop.identifier] = Assignment(
                workshop=workshop, students=set(), adults=set()
            )

    @property
    def workshops(self) -> Mapping[str, Workshop]:
        return self._workshops_by_id

    def assignments_for_timeslot(self, timeslot: Timeslot) -> Mapping[str, Assignment]:
        return self._assignments[timeslot]

    def get_assignment(self, timeslot: Timeslot, workshop_id: str) -> Assignment:
        assignment = self._assignments[timeslot].get(workshop_id)
        if assignment is None:
            raise KeyError(f"No s'ha trobat el taller amb id '{workshop_id}'.")
        return assignment

    def _check_capacity(self, assignment: Assignment, *, for_students: bool, quantity: int) -> None:
        limit = assignment.workshop.capacity_students if for_students else assignment.workshop.capacity_adults
        if limit is not None and quantity > limit:
            audience = "alumnes" if for_students else "adults"
            raise ValueError(
                f"El taller '{assignment.workshop.name}' ja ha arribat al límit de {audience} ({limit})."
            )

    def _ensure_unique_timeslot(self, person_id: str, timeslot: Timeslot, *, kind: str) -> None:
        assignments = self._assignments[timeslot]
        for assignment in assignments.values():
            bucket = assignment.students if kind == "student" else assignment.adults
            if person_id in bucket:
                raise ValueError(
                    f"La persona amb id '{person_id}' ja està assignada en aquesta franja horària."
                )

    def assign_student(self, student: Student, *, timeslot: Timeslot, workshop_id: str) -> None:
        assignment = self.get_assignment(timeslot, workshop_id)
        self._ensure_unique_timeslot(student.identifier, timeslot, kind="student")
        new_count = len(assignment.students) + 1
        self._check_capacity(assignment, for_students=True, quantity=new_count)
        assignment.students.add(student.identifier)

    def unassign_student(self, student: Student, *, timeslot: Timeslot, workshop_id: str) -> None:
        assignment = self._assignments[timeslot].get(workshop_id)
        if assignment:
            assignment.students.discard(student.identifier)

    def assign_adult(self, adult: Adult, *, timeslot: Timeslot, workshop_id: str) -> None:
        assignment = self.get_assignment(timeslot, workshop_id)
        self._ensure_unique_timeslot(adult.identifier, timeslot, kind="adult")
        new_count = len(assignment.adults) + 1
        self._check_capacity(assignment, for_students=False, quantity=new_count)
        assignment.adults.add(adult.identifier)

    def unassign_adult(self, adult: Adult, *, timeslot: Timeslot, workshop_id: str) -> None:
        assignment = self._assignments[timeslot].get(workshop_id)
        if assignment:
            assignment.adults.discard(adult.identifier)

    def is_student_assigned(self, student_id: str, *, timeslot: Timeslot) -> bool:
        return any(
            student_id in assignment.students
            for assignment in self._assignments[timeslot].values()
        )

    def is_adult_assigned(self, adult_id: str, *, timeslot: Timeslot) -> bool:
        return any(
            adult_id in assignment.adults
            for assignment in self._assignments[timeslot].values()
        )

    def as_rows(self, *, students: Mapping[str, Student], adults: Mapping[str, Adult]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for timeslot, workshops in self._assignments.items():
            for assignment in workshops.values():
                rows.append(
                    {
                        "Franja": timeslot,
                        "Espai": assignment.workshop.space,
                        "Taller": assignment.workshop.name,
                        "Alumnes": ", ".join(
                            students[identifier].name for identifier in sorted(assignment.students)
                        ),
                        "Adults": ", ".join(adults[identifier].name for identifier in sorted(assignment.adults)),
                        "Notes": assignment.workshop.notes or "",
                    }
                )
        rows.sort(key=lambda row: (row["Franja"], row["Espai"]))
        return rows
