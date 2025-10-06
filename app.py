"""Streamlit front-end for the LS timetable scheduler."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pandas as pd
import streamlit as st

from scheduler import data_loader
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


@cache
def load_students() -> dict[str, Student]:
    students = data_loader.load_students(DATA_DIR / "students.csv")
    return {student.identifier: student for student in students}


@cache
def load_adults() -> dict[str, Adult]:
    adults = data_loader.load_adults(DATA_DIR / "adults.csv")
    return {adult.identifier: adult for adult in adults}


def load_schedule() -> Schedule:
    workshops = data_loader.load_workshops(DATA_DIR / "workshops.csv", valid_timeslots=DEFAULT_TIMESLOTS)
    return Schedule(workshops)


def main() -> None:
    st.set_page_config(
        page_title="Planificador de Tallers LS",
        layout="wide",
    )

    st.title("Planificador de Tallers de La Serra")
    st.caption("Assigna alumnes i adults a cada franja horària i espai.")

    students = load_students()
    adults = load_adults()
    if "schedule" not in st.session_state:
        st.session_state.schedule = load_schedule()
    schedule: Schedule = st.session_state.schedule

    with st.sidebar:
        st.header("Filtres")
        selected_timeslot = st.selectbox("Franja horària", DEFAULT_TIMESLOTS)
        workshops_in_slot = {
            workshop_id: workshop
            for workshop_id, workshop in schedule.workshops.items()
            if workshop.timeslot == selected_timeslot
        }
        selected_workshop_id = st.selectbox(
            "Espai / Taller",
            options=list(workshops_in_slot.keys()),
            format_func=lambda key: f"{workshops_in_slot[key].space} — {workshops_in_slot[key].name}",
        )

    selected_assignment = schedule.get_assignment(selected_timeslot, selected_workshop_id)

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Assignació d'alumnes")
        available_students = [
            student for student in students.values()
            if not schedule.is_student_assigned(student.identifier, timeslot=selected_timeslot)
            or student.identifier in selected_assignment.students
        ]
        student_names = {student.identifier: student.name for student in available_students}
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
            adult for adult in adults.values()
            if not schedule.is_adult_assigned(adult.identifier, timeslot=selected_timeslot)
            or adult.identifier in selected_assignment.adults
        ]
        adult_names = {adult.identifier: adult.name for adult in available_adults}
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
                "Alumnes": ", ".join(students[s_id].name for s_id in sorted(assignment.students)),
                "Adults": ", ".join(adults[a_id].name for a_id in sorted(assignment.adults)),
            }
        )
    df = pd.DataFrame(summary_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Vista completa de la setmana")
    full_rows = schedule.as_rows(students=students, adults=adults)
    full_df = pd.DataFrame(full_rows)
    st.dataframe(full_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Descarrega en CSV",
        data=full_df.to_csv(index=False).encode("utf-8"),
        file_name="horaris_ls.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
