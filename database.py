import os
import sqlite3
from datetime import datetime, time, timedelta

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
            booked_at TEXT NOT NULL,
            email TEXT
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


def add_appointment(client_name: str, appointment_dt: datetime, client_email: str) -> bool:
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
            INSERT INTO appointments (client_name, appointment_datetime, duration_minutes, booked_at, email)
            VALUES (?, ?, ?, ?, ?)
        """, (client_name, appointment_iso, duration, booked_at_iso, client_email))
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

def list_appointments(client_name: str):
    """
    Performs a query to retrieve a client's appointments.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query appointments that *start* within the range
    cursor.execute("""
        SELECT client_name, appointment_datetime 
        FROM appointments
        WHERE client_name = ?
        """, [client_name])
    booked_slots = {row['appointment_datetime'] for row in cursor.fetchall()}
    conn.close()
    return booked_slots

def update_appointment_in_db(client_name: str, old_datetime_iso: str, new_datetime_iso: str) -> bool:
    """
    Updates an existing appointment to a new datetime in the database.

    Checks:
    1. If an appointment exists for the client at the old datetime.
    2. If the new datetime slot is already booked by ANYONE.

    Args:
        client_name: The name of the client whose appointment is being changed.
        old_datetime_iso: The ISO timestamp string of the current appointment.
        new_datetime_iso: The ISO timestamp string for the desired new appointment time.

    Returns:
        True if the update was successful, False otherwise.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    updated = False
    print(f"DB: Attempting to update appointment for '{client_name}' from '{old_datetime_iso}' to '{new_datetime_iso}'")

    try:
        # 1. Check if the *new* slot is already taken (by anyone)
        cursor.execute("SELECT id FROM appointments WHERE appointment_datetime = ?", (new_datetime_iso,))
        existing_at_new_time = cursor.fetchone()
        if existing_at_new_time:
            print(f"DB Error: Cannot update. The new slot {new_datetime_iso} is already booked.")
            return False # New slot is already booked

        # 2. Find the original appointment ID for the specific client and time
        cursor.execute("""
            SELECT id FROM appointments
            WHERE client_name = ? AND appointment_datetime = ?
            """, (client_name, old_datetime_iso))
        original_appointment = cursor.fetchone()

        if original_appointment:
            original_id = original_appointment['id']
            print(f"DB: Found original appointment ID: {original_id}. Proceeding with update.")
            # 3. Perform the update
            cursor.execute("""
                UPDATE appointments
                SET appointment_datetime = ?
                WHERE id = ?
            """, (new_datetime_iso, original_id))
            conn.commit()

            # Verify update (optional but good)
            if cursor.rowcount > 0:
                print(f"DB: Successfully updated appointment ID {original_id} to {new_datetime_iso}")
                updated = True
            else:
                 print(f"DB Warning: Update command affected 0 rows for ID {original_id}.") # Should not happen if found previously

        else:
            print(f"DB Error: Original appointment for '{client_name}' at '{old_datetime_iso}' not found.")
            updated = False

    except sqlite3.Error as e:
        print(f"DB Error during update process: {e}")
        conn.rollback() # Rollback changes on error
        updated = False
    except Exception as e:
        print(f"General Error during update process: {e}")
        conn.rollback()
        updated = False
    finally:
        conn.close()

    return updated


def is_slot_within_working_hours(dt_obj: datetime) -> bool:
    """Checks if a datetime object falls within defined working hours."""
    day_of_week = dt_obj.weekday()
    slot_time = dt_obj.time()

    if day_of_week not in WORKING_HOURS:
        return False # Not a working day

    start_time, end_time = WORKING_HOURS[day_of_week]
    # Ensure the slot *starts* within hours and doesn't overlap closing time
    # Assumes APPOINTMENT_DURATION_MINUTES is defined globally or passed
    slot_duration = timedelta(minutes=APPOINTMENT_DURATION_MINUTES)
    slot_end_time = (dt_obj + slot_duration).time()

    # Check if start time is within range and end time does not exceed end_time
    # Handle edge case where end_time is midnight (00:00) -> compare as 24:00
    effective_end_time = time(23, 59, 59, 999999) if end_time == time(0, 0) else end_time

    return start_time <= slot_time and slot_end_time <= effective_end_time

def is_slot_already_booked(dt_iso: str) -> bool:
    """Checks if a specific ISO datetime string is already booked."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM appointments WHERE appointment_datetime = ?", (dt_iso,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

initialize_database()