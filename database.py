# database.py
import sqlite3
from datetime import datetime, timedelta, time
import os

DATABASE_FILE = "appointments.db"
APPOINTMENT_DURATION_MINUTES = int(os.getenv("APPOINTMENT_DURATION_MINUTES", 60))

# Define standard working hours (example: Mon-Fri, 9 AM to 5 PM)
WORKING_HOURS = {
    0: (time(9, 0), time(17, 0)),  # Monday
    1: (time(9, 0), time(17, 0)),  # Tuesday
    2: (time(9, 0), time(17, 0)),  # Wednesday
    3: (time(9, 0), time(17, 0)),  # Thursday
    4: (time(9, 0), time(17, 0)),  # Friday
    # 5: None, # Saturday - Off
    # 6: None, # Sunday - Off
}

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

def initialize_database():
    """Creates the appointments table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            appointment_datetime TEXT NOT NULL UNIQUE, -- ISO format YYYY-MM-DDTHH:MM:SS
            duration_minutes INTEGER NOT NULL,
            booked_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("Database initialized.")

def get_booked_slots(start_date: datetime, end_date: datetime) -> set:
    """Retrieves booked appointment datetimes within a given range."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query appointments that *start* within the range
    cursor.execute("""
        SELECT appointment_datetime FROM appointments
        WHERE appointment_datetime >= ? AND appointment_datetime < ?
    """, (start_date.isoformat(), end_date.isoformat()))
    booked_slots = {row['appointment_datetime'] for row in cursor.fetchall()}
    conn.close()
    return booked_slots

def find_available_slots(target_date: datetime) -> list[str]:
    """Finds available slots for a specific date based on working hours and booked slots."""
    available_slots = []
    day_of_week = target_date.weekday()

    if day_of_week not in WORKING_HOURS:
        return [] # Not a working day

    start_time, end_time = WORKING_HOURS[day_of_week]
    slot_duration = timedelta(minutes=APPOINTMENT_DURATION_MINUTES)

    # Get booked slots for the entire target day
    day_start = datetime.combine(target_date.date(), time(0, 0))
    day_end = day_start + timedelta(days=1)
    booked_slots_iso = get_booked_slots(day_start, day_end)
    booked_slot_datetimes = {datetime.fromisoformat(s) for s in booked_slots_iso}

    current_slot_start_dt = datetime.combine(target_date.date(), start_time)
    end_of_work_dt = datetime.combine(target_date.date(), end_time)

    while current_slot_start_dt + slot_duration <= end_of_work_dt:
        # Check if this potential slot is already booked
        if current_slot_start_dt not in booked_slot_datetimes:
            # Basic check, doesn't account for appointments overlapping the start time
            # A more robust check would consider the duration of booked slots as well
            available_slots.append(current_slot_start_dt.isoformat(sep=' ', timespec='minutes')) # Format YYYY-MM-DD HH:MM

        current_slot_start_dt += slot_duration

    return available_slots


def add_appointment(client_name: str, appointment_dt: datetime) -> bool:
    """Adds a new appointment to the database after checking for conflicts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    appointment_iso = appointment_dt.isoformat()
    duration = APPOINTMENT_DURATION_MINUTES
    booked_at_iso = datetime.now().isoformat()

    try:
        # Check for conflict again just before inserting
        cursor.execute("SELECT id FROM appointments WHERE appointment_datetime = ?", (appointment_iso,))
        if cursor.fetchone():
            print(f"Conflict detected for {appointment_iso} during add operation.")
            conn.close()
            return False # Slot is already booked

        cursor.execute("""
            INSERT INTO appointments (client_name, appointment_datetime, duration_minutes, booked_at)
            VALUES (?, ?, ?, ?)
        """, (client_name, appointment_iso, duration, booked_at_iso))
        conn.commit()
        conn.close()
        print(f"Appointment added for {client_name} at {appointment_iso}")
        return True
    except sqlite3.IntegrityError:
        # Handles the UNIQUE constraint violation, though the check above should prevent it
        print(f"IntegrityError: Slot {appointment_iso} likely already exists.")
        conn.close()
        return False
    except Exception as e:
        print(f"Error adding appointment: {e}")
        conn.rollback() # Rollback any changes if an error occurs
        conn.close()
        return False

# Initialize the database when this module is loaded
initialize_database()