"""Utilities to load CSV data for the scheduling app."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

from .models import Adult, Student, Workshop, Timeslot


class DataLoaderError(RuntimeError):
    """Raised when a CSV file cannot be parsed correctly."""


def _validate_headers(headers: Sequence[str], expected: Sequence[str], *, file_path: Path) -> None:
    missing = [name for name in expected if name not in headers]
    if missing:
        raise DataLoaderError(
            f"El fitxer '{file_path}' no té les columnes requerides: {', '.join(missing)}"
        )


def load_students(csv_path: str | Path) -> list[Student]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _validate_headers(reader.fieldnames or [], ["id", "name"], file_path=path)
        students = [
            Student(identifier=row["id"].strip(), name=row["name"].strip(), group=row.get("group") or None)
            for row in reader
            if row.get("id") and row.get("name")
        ]
    return students


def load_adults(csv_path: str | Path) -> list[Adult]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _validate_headers(reader.fieldnames or [], ["id", "name"], file_path=path)
        adults = [
            Adult(identifier=row["id"].strip(), name=row["name"].strip(), role=row.get("role") or None)
            for row in reader
            if row.get("id") and row.get("name")
        ]
    return adults


def load_workshops(csv_path: str | Path, *, valid_timeslots: Iterable[Timeslot]) -> list[Workshop]:
    path = Path(csv_path)
    valid_timeslots = set(valid_timeslots)
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _validate_headers(
            reader.fieldnames or [],
            ["id", "name", "space", "timeslot", "capacity_students", "capacity_adults"],
            file_path=path,
        )
        workshops: list[Workshop] = []
        for row in reader:
            raw_timeslot = row.get("timeslot", "").strip()
            if raw_timeslot not in valid_timeslots:
                raise DataLoaderError(
                    f"El taller '{row.get('name')}' té una franja horària invàlida: '{raw_timeslot}'"
                )
            try:
                capacity_students = int(row["capacity_students"]) if row.get("capacity_students") else None
            except ValueError as exc:  # pragma: no cover - defensive programming
                raise DataLoaderError(
                    f"La capacitat d'alumnes del taller '{row.get('name')}' ha de ser numèrica"
                ) from exc
            try:
                capacity_adults = int(row["capacity_adults"]) if row.get("capacity_adults") else None
            except ValueError as exc:  # pragma: no cover - defensive programming
                raise DataLoaderError(
                    f"La capacitat d'adults del taller '{row.get('name')}' ha de ser numèrica"
                ) from exc

            workshops.append(
                Workshop(
                    identifier=row["id"].strip(),
                    name=row["name"].strip(),
                    space=row["space"].strip(),
                    timeslot=raw_timeslot,  # type: ignore[assignment]
                    capacity_students=capacity_students,
                    capacity_adults=capacity_adults,
                    notes=row.get("notes") or None,
                )
            )
    return workshops
