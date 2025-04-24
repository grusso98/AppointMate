import json
import os
import smtplib
from datetime import date, datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import dateparser
from dotenv import load_dotenv
from ics import Attendee, Calendar, Event
from langchain.tools import tool

from database import (APPOINTMENT_DURATION_MINUTES, add_appointment,
                      delete_appointment_from_db, find_available_slots,
                      is_slot_already_booked, is_slot_within_working_hours,
                      list_appointments, update_appointment_in_db)

load_dotenv()

PROFESSIONAL_EMAIL = os.getenv("PROFESSIONAL_EMAIL")
PROFESSIONAL_NAME = os.getenv("PROFESSIONAL_NAME")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

@tool
def get_datetime():
    """
    Checks the current date and time, use it whenever it is useful to know what date is today, 
    e.g to schedule appointments or to reschedule them and also at startup before handling the client's requests.
    """
    return str(datetime.today())

@tool
def cancel_appointment(parsed_datetime: str, client_name: str):
    """
    Cancel an appoint previously boooked, use it whenever the user asks to cancel an appointment:
    e.g 'I would like to cancel my appointment/booking'.
    You need to collect the datetime of the booking and the client name before calling this tool.
    The date and time needs to be provided to the tool in this format: YYYY-MM-DD HH:MM. If the user provides it
    in a different format transform it in the above format before calling the tool.
    """
    print(f"Tool: Cancel Appointment for query: {parsed_datetime}")

    try:
        appointment_dt = datetime.strptime(parsed_datetime, '%Y-%m-%d %H:%M')
        formatted_datetime = appointment_dt.strftime('%Y-%m-%d %H:%M')

    except ValueError:
        return f"Error: Invalid datetime format '{parsed_datetime}'. Please use 'YYYY-MM-DD HH:MM' format."

    result = delete_appointment_from_db(formatted_datetime, client_name)
    if result:
        return "Appointment has been successfully deleted!"
    return "There was an error in the appointment cancellation, please try again."

@tool
def check_availability(date_query: str) -> str:
    """
    Use it only when you need to book a new appointment or to edit an exsisting one.
    Checks the professional's calendar for available appointment slots on a specific date
    or based on a natural language query like 'today', 'tomorrow', 'next Friday', or 'July 10th'.
    Do not use relative times like 'afternoon' or 'morning', ask the user for a specific date.
    Returns a list of available slots in 'YYYY-MM-DD HH:MM' format or a message indicating unavailability.
    """
    print(f"Tool: Checking availability for query: {date_query}")
    parsed_date = dateparser.parse(date_query,
                                   settings={
                                       'PREFER_DATES_FROM': 'future',
                                       'STRICT_PARSING': False
                                   })

    if not parsed_date:
        return f"Sorry, I couldn't understand the date '{date_query}'. Please provide a specific date like 'tomorrow', 'next Monday', or 'YYYY-MM-DD'."

    target_date = parsed_date.date()
    print(f"Tool: Parsed date query '{date_query}' to: {target_date}")

    # Ensure we don't check for dates too far in the past unless specified explicitly
    if target_date < date.today() and parsed_date.strftime(
            '%Y%m%d') == datetime.now().strftime('%Y%m%d'):
        # If dateparser defaults to today for a time-only query, fine.
        pass
    elif target_date < date.today():
        return "Sorry, I can only check availability for today or future dates."

    available_slots = find_available_slots(parsed_date)

    if not available_slots:
        return f"Sorry, no available slots found for {target_date.strftime('%A, %B %d, %Y')}. Please try another date."
    else:
        # Limit the number of slots shown?
        slots_str = "\n".join(available_slots)
        return f"Available slots for {target_date.strftime('%A, %B %d, %Y')}:\n{slots_str}\nPlease specify the exact slot you want to book (e.g., 'Book 2025-04-28 14:00')."


@tool
def book_appointment(datetime_str: str, client_name: str, client_email: str) -> str:
    """
    Books an appointment for the client at the specified date and time.
    Requires the exact datetime string in 'YYYY-MM-DD HH:MM' format (as provided by check_availability)
    and the client's name. Confirms the booking and triggers a notification email.
    """
    print(f"Tool: Attempting to book appointment for '{client_name}' at '{datetime_str}'")
    if not client_name or client_name.strip() == "":
        return "Error: Client name is required to book an appointment."
    try:
        # Validate and parse the datetime string
        appointment_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')

        # Prevent booking past slots
        if appointment_dt < datetime.now():
            return f"Error: Cannot book an appointment in the past ({datetime_str}). Please check availability for a future time."

    except ValueError:
        return f"Error: Invalid datetime format '{datetime_str}'. Please use 'YYYY-MM-DD HH:MM' format as shown in availability."

    # Attempt to add to database (includes conflict check)
    success = add_appointment(client_name, appointment_dt, client_email)

    if success:
        # Prepare details for email (even if sending fails or is skipped)
        appointment_details = {
            "client_name": client_name,
            "datetime": appointment_dt.isoformat(), # Use ISO for internal consistency
            "datetime_readable": appointment_dt.strftime('%A, %B %d, %Y at %I:%M %p'),
            "duration": APPOINTMENT_DURATION_MINUTES,
            "client_email": client_email
        }
        # Trigger email sending (can be done here or as a separate step by the agent)
        email_status = send_confirmation_email_internal(appointment_details)

        return f"Success! Appointment confirmed for {client_name} on {appointment_details['datetime_readable']}. {email_status}"
    else:
        # The add_appointment function already prints conflict/error messages
        return f"Error: Could not book appointment for {client_name} at {datetime_str}. The slot might have been taken, or another error occurred. Please try checking availability again."

@tool
def list_client_appointments(client_name: str):
    """
    Retrieves the current appointment a client has already booked. Requires the 
    client name to perform the sql query.
    """
    print(f"Tool: Attempting to list appointment for '{client_name}'")
    if not client_name or client_name.strip() == "":
        return "Error: Client name is required to book an appointment."
    success = list_appointments(client_name)
    if success:
        return f"Here are your booked appointments: \n{success}"
    else:
        return f"Error: no booked appointments with the following name: {client_name}"

@tool
def get_professional_info() -> str:
    """
    Provides detailed information about the professional (Dr. Demo), including specialty,
    contact details, services offered, prices, and payment information. Use this tool
    when the user asks questions about services, costs, what Dr. Demo does,
    or general practice information. Do not use for checking appointment availability.
    """
    print("Tool: Attempting to retrieve professional info.")
    try:
        with open("professional_info.json", 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Format the data into a readable string for the LLM/user
        info_parts = [
            f"--- Information about {data.get('professional_name', 'the professional')} ---",
            f"Specialty: {data.get('specialty', 'N/A')}",
            f"Location: {data.get('location', 'N/A')}",
            f"Contact (non-booking): {data.get('contact_info', 'N/A')}",
        ]
        if 'services' in data and data['services']:
            info_parts.append("\nServices Offered:")
            for service in data['services']:
                name = service.get('name', 'Unnamed Service')
                price = f" - Price: {service.get('price', 'N/A')}"
                duration = f" - Duration: approx. {service.get('duration_minutes', 'N/A')} min" if service.get('duration_minutes') else ""
                desc = f" - Desc: {service.get('description', '')}" if service.get('description') else ""
                info_parts.append(f"  - {name}\n    {price}{duration}\n    {desc}") # Indented formatting

        info_parts.append(f"\nPayment Info: {data.get('payment_info', 'Please inquire.')}")
        info_parts.append("\nNote: For exact appointment times, please use the availability checking tool.")

        return "\n".join(info_parts)
    except FileNotFoundError:
        print("Error: professional_info.json not found.")
        return "Sorry, I couldn't find the detailed service information file."
    except Exception as e:
        print(f"Error reading professional_info.json: {e}")
        return "Sorry, I encountered an error while retrieving service information."

@tool
def edit_appointment(client_name: str, current_datetime_str: str, new_datetime_str: str) -> str:
    """
    Changes the date or time of an existing appointment for a client.
    **Requires THREE arguments:**
    1. client_name: The name of the client whose appointment is being changed.
    2. current_datetime_str: The CURRENT date and time of the appointment being changed (MUST be in 'YYYY-MM-DD HH:MM' format).
    3. new_datetime_str: The NEW desired date and time for the appointment (MUST be in 'YYYY-MM-DD HH:MM' format).
    Checks if the new slot is available before attempting the update.
    **Do NOT call this tool unless you have gathered ALL THREE arguments from the user.**
    """
    print(f"Tool: Attempting to edit appointment for '{client_name}' from '{current_datetime_str}' to '{new_datetime_str}'")

    if not client_name or not isinstance(client_name, str) or client_name.strip() == "":
        return "Error: Client name is required to edit an appointment."
    if not current_datetime_str or not new_datetime_str:
        return "Error: Both the current and new appointment date/time are required."

    try:
        dt_format = '%Y-%m-%d %H:%M'
        old_dt_obj = datetime.strptime(current_datetime_str.strip(), dt_format)
        new_dt_obj = datetime.strptime(new_datetime_str.strip(), dt_format)

        old_dt_iso = old_dt_obj.isoformat()
        new_dt_iso = new_dt_obj.isoformat()

        if new_dt_obj < datetime.now():
            return f"Error: Cannot reschedule appointment to the past ({new_datetime_str}). Please choose a future time."

    except ValueError:
        return f"Error: Invalid datetime format. Please use 'YYYY-MM-DD HH:MM' format for both current and new times."

    # --- Check Availability and Validity of NEW Slot ---
    if not is_slot_within_working_hours(new_dt_obj):
        return f"Error: The requested new time ({new_datetime_str}) is outside of working hours."
    if is_slot_already_booked(new_dt_iso):
        return f"Error: The requested new time slot ({new_datetime_str}) is already booked. Please choose a different time."
    try:
        update_successful = update_appointment_in_db(client_name.strip(), old_dt_iso, new_dt_iso)
    except Exception as e:
        print(f"Error calling database function update_appointment_in_db: {e}")
        return f"Error: Could not reschedule appointment for {client_name.strip()} due to an internal error."
    if update_successful:
        return f"Success! Appointment for {client_name.strip()} rescheduled from {current_datetime_str} to {new_datetime_str}."
    else:
        return f"Error: Could not reschedule appointment for {client_name.strip()}. Please ensure the original appointment time ({current_datetime_str}) is correct for this name, and that the new slot is available."

# Internal function for email sending, not exposed as a tool directly to the LLM
# but called by book_appointment. This prevents LLM from trying to call email arbitrary things.
def send_confirmation_email_internal(appointment_details: dict) -> str:
    """Sends a confirmation email to the professional with appointment details and a calendar invite."""
    print(f"Internal: Preparing confirmation email for: {appointment_details}")

    # Check if SMTP is configured
    if not all([PROFESSIONAL_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        msg = f"Email notification skipped: SMTP details not fully configured in .env file."
        print(msg)
        return msg # Return status message

    client_name = appointment_details.get("client_name", "Unknown Client")
    datetime_iso = appointment_details.get("datetime")
    datetime_readable = appointment_details.get("datetime_readable", datetime_iso) # Fallback
    duration = appointment_details.get("duration", APPOINTMENT_DURATION_MINUTES)
    client_email = appointment_details.get("client_email", "No email")
    recipients = []

    if not datetime_iso:
        return "Error: Missing appointment datetime for email."

    try:
        dt_start = datetime.fromisoformat(datetime_iso)
        dt_end = dt_start + timedelta(minutes=duration)

        # --- Create Email ---
        msg = MIMEMultipart('related') # Use related for inline calendar data? Alternative is better.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"New Appointment Booking: {client_name} on {dt_start.strftime('%Y-%m-%d %H:%M')}"
        msg['From'] = SMTP_USER
        recipients.append(PROFESSIONAL_EMAIL)
        if client_email != "No email":
            recipients.append(client_email)
            msg['To'] = ", ".join(recipients)
        else:
            msg['To'] = PROFESSIONAL_EMAIL

        # --- Email Body ---
        body = f"""
        Hi,

        A new appointment has been booked via the booking agent:

        Client: {client_name}
        Date & Time: {datetime_readable}
        Duration: {duration} minutes

        This appointment has been added to the database. Please find the calendar invite attached (.ics file).

        Best regards,
        AppointMate.
        """
        msg.attach(MIMEText(body, 'plain'))

        # --- Create ICS File ---
        cal = Calendar()
        event = Event()
        event.name = f"Appointment: {client_name}"
        event.begin = dt_start
        event.end = dt_end
        event.description = f"Appointment with {client_name} booked via automated agent."
        # event.location = "Optional: Add location"
        professional_attendee = Attendee(f"mailto:{PROFESSIONAL_EMAIL}")
        event.attendees.add(professional_attendee)
        client_attendee = Attendee(f"mailto:{client_email}")
        event.attendees.add(client_attendee)
        cal.events.add(event)

        # --- Attach ICS file ---
        # Use MIMEBase for generic binary data (text/calendar can sometimes be mishandled)
        ics_filename = f"appointment_{client_name}_{dt_start.strftime('%Y%m%d_%H%M')}.ics"
        part = MIMEBase('application', "octet-stream") # Or 'text', 'calendar; method=REQUEST'
        part.set_payload(str(cal).encode('utf-8'))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{ics_filename}"')
        msg.attach(part)


        # --- Send Email to Professional---
        print(f"Internal: Sending email to {PROFESSIONAL_EMAIL} via {SMTP_SERVER}:{SMTP_PORT}")
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.ehlo() # Identify client to ESMTP server
            server.starttls() # Encrypt connection
            server.ehlo() # Re-identify client over encrypted connection
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(from_addr=SMTP_USER, to_addrs=recipients, msg=msg.as_string()) if client_email != "No email" else server.sendmail(from_addr=SMTP_USER, to_addrs=PROFESSIONAL_EMAIL, msg=msg.as_string())
            print("Internal: Email sent successfully.")

        return f"Confirmation email sent to {PROFESSIONAL_EMAIL}."

    except smtplib.SMTPAuthenticationError:
        err_msg = "Email Error: SMTP Authentication failed. Check SMTP_USER/SMTP_PASSWORD."
        print(err_msg)
        return err_msg
    except Exception as e:
        err_msg = f"Email Error: Failed to send confirmation email: {e}"
        print(err_msg)
        return err_msg

# List of tools for the agent (only expose tools safe for LLM calls)
tools = [check_availability,
         book_appointment,
         list_client_appointments,
         get_professional_info,
         edit_appointment,
         get_datetime,
         cancel_appointment]
