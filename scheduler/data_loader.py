"""Utilities to load CSV data for the scheduling app."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Iterable, Sequence, TextIO

from .models import Adult, Student, Workshop, Timeslot


class DataLoaderError(RuntimeError):
    """Raised when a CSV file cannot be parsed correctly."""


CsvSource = str | Path | TextIO


def _validate_headers(headers: Sequence[str], expected: Sequence[str], *, file_label: str) -> None:
    missing = [name for name in expected if name not in headers]
    if missing:
        raise DataLoaderError(
            f"El fitxer '{file_label}' no té les columnes requerides: {', '.join(missing)}"
        )


def _prepare_reader(csv_source: CsvSource) -> tuple[csv.DictReader, Callable[[], None], str]:
    if isinstance(csv_source, (str, Path)):
        path = Path(csv_source)
        fh = path.open(newline="", encoding="utf-8")
        file_label = str(path)

        def closer() -> None:
            fh.close()

    else:
        fh = csv_source
        if hasattr(fh, "seek"):
            fh.seek(0)
        file_label = getattr(fh, "name", "<arxiu carregat>")

        def closer() -> None:  # pragma: no cover - simple passthrough
            return None

    reader = csv.DictReader(fh)
    return reader, closer, file_label


def load_students(csv_source: CsvSource) -> list[Student]:
    reader, closer, label = _prepare_reader(csv_source)
    try:
        _validate_headers(reader.fieldnames or [], ["id", "name", "stage"], file_label=label)
        students = []
        for row in reader:
            if not row.get("id") or not row.get("name"):
                continue
            stage_raw = (row.get("stage") or "").strip()
            stage_value = stage_raw.lower() if stage_raw else None
            students.append(
                Student(
                    identifier=row["id"].strip(),
                    name=row["name"].strip(),
                    stage=stage_value,
                    group=row.get("group") or None,
                )
            )
    finally:
        closer()
    return students


def load_adults(csv_source: CsvSource) -> list[Adult]:
    reader, closer, label = _prepare_reader(csv_source)
    try:
        _validate_headers(reader.fieldnames or [], ["id", "name"], file_label=label)
        adults = [
            Adult(identifier=row["id"].strip(), name=row["name"].strip(), role=row.get("role") or None)
            for row in reader
            if row.get("id") and row.get("name")
        ]
    finally:
        closer()
    return adults


def load_workshops(csv_source: CsvSource, *, valid_timeslots: Iterable[Timeslot]) -> list[Workshop]:
    reader, closer, label = _prepare_reader(csv_source)
    valid_timeslots = set(valid_timeslots)
    try:
        _validate_headers(
            reader.fieldnames or [],
            ["id", "name", "space", "timeslot", "capacity_students", "capacity_adults"],
            file_label=label,
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
    finally:
        closer()
    return workshops
