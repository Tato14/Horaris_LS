"""Streamlit front-end for the LS timetable scheduler."""

from __future__ import annotations

import csv
import io
import hashlib
from html import escape
from pathlib import Path

import streamlit as st

from scheduler import data_loader
from scheduler.data_loader import DataLoaderError
from scheduler.models import Adult, Student, Timeslot
from scheduler.scheduling import Schedule

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_TIMESLOTS: list[Timeslot] = [
    "8:45-9:30",
    "9:30-10:15",
    "10:15-11:00",
    "11:30-12:15",
    "12:15-13:00",
]

STAGE_CLASS_MAP: dict[str, str] = {
    "mitjans": "stage-mitjans",
    "grans": "stage-grans",
}


def build_table_html(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not rows:
        header_html = "".join(f"<th>{column}</th>" for column in columns)
        return f"<table class='horaris-table'><thead><tr>{header_html}</tr></thead><tbody></tbody></table>"

    header_html = "".join(f"<th>{column}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = [row.get(column, "") for column in columns]
        cell_html = "".join(f"<td>{escape(str(value))}</td>" for value in cells)
        body_rows.append(f"<tr>{cell_html}</tr>")
    body_html = "".join(body_rows)
    return (
        "<table class='horaris-table'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
    )


def rows_to_csv(rows: list[dict[str, str]], columns: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def stringio_from_bytes(data: bytes, *, name: str) -> io.StringIO:
    text = data.decode("utf-8-sig")
    buffer = io.StringIO(text)
    setattr(buffer, "name", name)
    return buffer


def compute_signature(*datasets: bytes) -> str:
    hasher = hashlib.sha256()
    for data in datasets:
        hasher.update(data)
    return hasher.hexdigest()


def stage_to_class(stage: str | None) -> str:
    if not stage:
        return "stage-altres"
    slug = stage.lower().strip().replace(" ", "-")
    return STAGE_CLASS_MAP.get(slug, "stage-altres")


def sort_timeslots(timeslots: set[str]) -> list[str]:
    order = {timeslot: index for index, timeslot in enumerate(DEFAULT_TIMESLOTS)}
    return sorted(timeslots, key=lambda slot: (order.get(slot, len(order)), slot))


def derive_space_order(schedule: Schedule, timeslot_order: list[str]) -> list[str]:
    ordered: list[str] = []
    for timeslot in timeslot_order:
        assignments = schedule.assignments_for_timeslot(timeslot)
        for assignment in assignments.values():
            space = assignment.workshop.space
            if space not in ordered:
                ordered.append(space)
    for workshop in schedule.workshops.values():
        if workshop.space not in ordered:
            ordered.append(workshop.space)
    return ordered


def render_assignment_html(assignment, *, students: dict[str, Student], adults: dict[str, Adult]) -> str:
    workshop = assignment.workshop
    parts = [f"<div class='workshop-title'>{escape(workshop.name)}</div>"]
    if workshop.notes:
        parts.append(f"<div class='workshop-notes'>{escape(workshop.notes)}</div>")

    adult_names = [escape(adults[a_id].name) for a_id in sorted(assignment.adults) if a_id in adults]
    if adult_names:
        parts.append(
            "<div class='adult-list'><span class='label'>Adults:</span> "
            + ", ".join(adult_names)
            + "</div>"
        )

    if assignment.students:
        chips = []
        for student_id in sorted(assignment.students):
            student = students.get(student_id)
            if student is None:
                continue
            css_class = stage_to_class(student.stage)
            chips.append(f"<span class='student-chip {css_class}'>{escape(student.name)}</span>")
        if chips:
            parts.append(
                "<div class='student-list'><span class='label'>Alumnes:</span> "
                + "".join(chips)
                + "</div>"
            )

    return f"<div class='cell-wrapper'>{''.join(parts)}</div>"


def build_schedule_grid_html(
    schedule: Schedule,
    *,
    students: dict[str, Student],
    adults: dict[str, Adult],
    timeslots: list[str],
    spaces: list[str],
) -> str:
    header_cells = "".join(f"<th class='space-header'>{escape(space)}</th>" for space in spaces)
    body_rows: list[str] = []

    for timeslot in timeslots:
        assignments = schedule.assignments_for_timeslot(timeslot)
        row_cells: list[str] = []
        for space in spaces:
            assignment = next(
                (item for item in assignments.values() if item.workshop.space == space),
                None,
            )
            if assignment is None:
                row_cells.append("<td class='schedule-cell empty'></td>")
            else:
                content = render_assignment_html(assignment, students=students, adults=adults)
                row_cells.append(f"<td class='schedule-cell'>{content}</td>")

        body_rows.append(
            "<tr>"
            f"<th class='timeslot-cell'>{escape(timeslot)}</th>"
            + "".join(row_cells)
            + "</tr>"
        )

    return (
        "<table class='schedule-grid'>"
        f"<thead><tr><th class='timeslot-header'>Franja</th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def get_dataset_bytes(state_key: str, label: str, *, default_bytes: bytes) -> tuple[bytes, bool]:
    uploaded = st.file_uploader(label, type="csv", key=f"{state_key}_uploader")
    if uploaded is not None:
        st.session_state[state_key] = uploaded.getvalue()
    if state_key in st.session_state:
        return st.session_state[state_key], True
    return default_bytes, False


def main() -> None:
    st.set_page_config(
        page_title="Planificador de Tallers LS",
        layout="wide",
    )

    st.title("Planificador de Tallers de La Serra")
    st.caption("Assigna alumnes i adults a cada franja horària i espai.")
    st.markdown(
        """
        <style>
        .horaris-table {width: 100%; border-collapse: collapse;}
        .horaris-table th, .horaris-table td {
            border: 1px solid #d9d9d9;
            padding: 0.5rem;
            text-align: left;
        }
        .horaris-table thead tr {background-color: #f8f9fa;}

        .schedule-grid {width: 100%; border-collapse: collapse; table-layout: fixed;}
        .schedule-grid th, .schedule-grid td {
            border: 1px solid #cdd0d5;
            vertical-align: top;
        }
        .schedule-grid .timeslot-header {
            width: 110px;
            background-color: #eef2f7;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .schedule-grid .space-header {
            background-color: #f6f7fb;
            font-size: 0.95rem;
            text-transform: uppercase;
        }
        .schedule-grid .timeslot-cell {
            background-color: #eef2f7;
            font-weight: 600;
            padding: 0.6rem;
            text-align: center;
        }
        .schedule-grid .schedule-cell {
            padding: 0.55rem;
            background-color: #ffffff;
        }
        .schedule-grid .schedule-cell.empty {
            background-color: #fafafa;
        }
        .cell-wrapper {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            min-height: 110px;
        }
        .workshop-title {
            font-weight: 700;
            font-size: 0.95rem;
            text-transform: uppercase;
            color: #343a40;
        }
        .workshop-notes {
            font-size: 0.75rem;
            font-style: italic;
            color: #6c757d;
        }
        .label {
            font-weight: 600;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-right: 0.35rem;
            color: #495057;
        }
        .adult-list, .student-list {
            font-size: 0.8rem;
            line-height: 1.3;
        }
        .student-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.25rem;
        }
        .student-chip {
            display: inline-block;
            padding: 0.2rem 0.45rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.75rem;
        }
        .student-chip.stage-mitjans {background-color: #fde2cf; color: #8b3d1a;}
        .student-chip.stage-grans {background-color: #d6eaf8; color: #1f4e79;}
        .student-chip.stage-altres {background-color: #e2e3e5; color: #343a40;}
        .sidebar-hint {font-size: 0.75rem; color: #6c757d;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    default_students_bytes = (DATA_DIR / "students.csv").read_bytes()
    default_adults_bytes = (DATA_DIR / "adults.csv").read_bytes()
    default_workshops_bytes = (DATA_DIR / "workshops.csv").read_bytes()

    with st.sidebar:
        st.header("Dades")
        st.caption("Carrega fitxers CSV amb el mateix format per utilitzar dades puntuals.")
        students_bytes, students_custom = get_dataset_bytes(
            "students_csv",
            "Alumnes (CSV)",
            default_bytes=default_students_bytes,
        )
        adults_bytes, adults_custom = get_dataset_bytes(
            "adults_csv",
            "Adults (CSV)",
            default_bytes=default_adults_bytes,
        )
        workshops_bytes, workshops_custom = get_dataset_bytes(
            "workshops_csv",
            "Tallers (CSV)",
            default_bytes=default_workshops_bytes,
        )

        if students_custom or adults_custom or workshops_custom:
            st.markdown(
                "<p class='sidebar-hint'>Les dades carregades es mantenen només durant la sessió actual.</p>",
                unsafe_allow_html=True,
            )

        if st.button("Restableix dades carregades", use_container_width=True):
            for key in (
                "students_csv",
                "adults_csv",
                "workshops_csv",
                "schedule_signature",
                "schedule",
                "selected_workshop_id",
                "selected_timeslot",
            ):
                st.session_state.pop(key, None)
            st.experimental_rerun()

    try:
        students = {
            student.identifier: student
            for student in data_loader.load_students(
                stringio_from_bytes(students_bytes, name="alumnes.csv")
            )
        }
    except DataLoaderError as exc:
        st.error(f"Error carregant els alumnes: {exc}")
        st.stop()

    try:
        adults = {
            adult.identifier: adult
            for adult in data_loader.load_adults(
                stringio_from_bytes(adults_bytes, name="adults.csv")
            )
        }
    except DataLoaderError as exc:
        st.error(f"Error carregant els adults: {exc}")
        st.stop()

    signature = compute_signature(students_bytes, adults_bytes, workshops_bytes)
    rebuild_schedule = (
        "schedule" not in st.session_state
        or st.session_state.get("schedule_signature") != signature
    )

    if rebuild_schedule:
        try:
            workshops = data_loader.load_workshops(
                stringio_from_bytes(workshops_bytes, name="tallers.csv"),
                valid_timeslots=DEFAULT_TIMESLOTS,
            )
        except DataLoaderError as exc:
            st.error(f"Error carregant els tallers: {exc}")
            st.stop()

        st.session_state.schedule = Schedule(workshops)
        st.session_state.schedule_signature = signature
        st.session_state.pop("selected_workshop_id", None)
        st.session_state.pop("selected_timeslot", None)

    schedule: Schedule = st.session_state.schedule

    timeslot_options = sort_timeslots({workshop.timeslot for workshop in schedule.workshops.values()})
    if not timeslot_options:
        st.info("No hi ha franges horàries disponibles als tallers carregats.")
        st.stop()

    if st.session_state.get("selected_timeslot") not in timeslot_options:
        st.session_state.selected_timeslot = timeslot_options[0]

    with st.sidebar:
        st.divider()
        st.header("Filtres")
        selected_timeslot = st.selectbox(
            "Franja horària",
            timeslot_options,
            key="selected_timeslot",
        )

        workshops_in_slot = {
            workshop_id: workshop
            for workshop_id, workshop in schedule.workshops.items()
            if workshop.timeslot == selected_timeslot
        }
        workshop_options = list(workshops_in_slot.keys())
        if not workshop_options:
            st.info("No hi ha tallers disponibles en aquesta franja horària.")
            st.stop()

        if st.session_state.get("selected_workshop_id") not in workshop_options:
            st.session_state.selected_workshop_id = workshop_options[0]

        selected_workshop_id = st.selectbox(
            "Espai / Taller",
            options=workshop_options,
            format_func=lambda key: f"{workshops_in_slot[key].space} — {workshops_in_slot[key].name}",
            key="selected_workshop_id",
        )

    selected_assignment = schedule.get_assignment(selected_timeslot, selected_workshop_id)

    def format_student_option(student: Student) -> str:
        bits: list[str] = [student.name]
        if student.stage:
            bits.append(student.stage.capitalize())
        if student.group:
            bits.append(student.group)
        return " · ".join(bits)

    def format_adult_option(adult: Adult) -> str:
        return f"{adult.name} · {adult.role}" if adult.role else adult.name

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Assignació d'alumnes")
        available_students = [
            student
            for student in students.values()
            if not schedule.is_student_assigned(student.identifier, timeslot=selected_timeslot)
            or student.identifier in selected_assignment.students
        ]
        student_names = {student.identifier: format_student_option(student) for student in available_students}
        selected_students = st.multiselect(
            "Selecciona alumnes",
            options=list(student_names.keys()),
            format_func=student_names.get,
        )
        if st.button("Afegeix alumnes", type="primary", use_container_width=True):
            try:
                for student_id in selected_students:
                    schedule.assign_student(
                        students[student_id],
                        timeslot=selected_timeslot,
                        workshop_id=selected_workshop_id,
                    )
                st.success("Alumnes assignats correctament.")
            except ValueError as exc:
                st.error(str(exc))

    with col_right:
        st.subheader("Assignació d'adults")
        available_adults = [
            adult
            for adult in adults.values()
            if not schedule.is_adult_assigned(adult.identifier, timeslot=selected_timeslot)
            or adult.identifier in selected_assignment.adults
        ]
        adult_names = {adult.identifier: format_adult_option(adult) for adult in available_adults}
        selected_adults = st.multiselect(
            "Selecciona adults",
            options=list(adult_names.keys()),
            format_func=adult_names.get,
        )
        if st.button("Afegeix adults", use_container_width=True):
            try:
                for adult_id in selected_adults:
                    schedule.assign_adult(
                        adults[adult_id],
                        timeslot=selected_timeslot,
                        workshop_id=selected_workshop_id,
                    )
                st.success("Adults assignats correctament.")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Resum de la franja")
    current_assignments = schedule.assignments_for_timeslot(selected_timeslot)
    summary_rows = []
    for workshop_id, assignment in current_assignments.items():
        summary_rows.append(
            {
                "Espai": schedule.workshops[workshop_id].space,
                "Taller": schedule.workshops[workshop_id].name,
                "Alumnes": ", ".join(
                    f"{students[s_id].name} ({students[s_id].stage.capitalize()})"
                    if students[s_id].stage
                    else students[s_id].name
                    for s_id in sorted(assignment.students)
                    if s_id in students
                ),
                "Adults": ", ".join(
                    adults[a_id].name for a_id in sorted(assignment.adults) if a_id in adults
                ),
            }
        )
    summary_columns = ["Espai", "Taller", "Alumnes", "Adults"]
    st.markdown(
        build_table_html(summary_rows, summary_columns),
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Vista completa de la setmana")
    space_order = derive_space_order(schedule, timeslot_options)
    grid_html = build_schedule_grid_html(
        schedule,
        students=students,
        adults=adults,
        timeslots=timeslot_options,
        spaces=space_order,
    )
    st.markdown(grid_html, unsafe_allow_html=True)

    full_rows = schedule.as_rows(students=students, adults=adults)
    full_columns = ["Franja", "Espai", "Taller", "Alumnes", "Adults", "Notes"]
    st.download_button(
        "Descarrega en CSV",
        data=rows_to_csv(full_rows, full_columns),
        file_name="horaris_ls.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
