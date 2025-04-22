import os
from dotenv import load_dotenv
from langchain.tools import tool
import dateparser # Using dateparser for flexible date input
from datetime import datetime, timedelta, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from ics import Calendar, Event

# Import database functions
from database import find_available_slots, add_appointment, APPOINTMENT_DURATION_MINUTES

load_dotenv()

PROFESSIONAL_EMAIL = os.getenv("PROFESSIONAL_EMAIL")
PROFESSIONAL_NAME = os.getenv("PROFESSIONAL_NAME")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


@tool
def check_availability(date_query: str) -> str:
    """
    Checks the professional's calendar for available appointment slots on a specific date
    or based on a natural language query like 'today', 'tomorrow', 'next Friday', or 'July 10th'.
    Do not use relative times like 'afternoon' or 'morning', ask the user for a specific date.
    Returns a list of available slots in 'YYYY-MM-DD HH:MM' format or a message indicating unavailability.
    """
    print(f"Tool: Checking availability for query: {date_query}")
    parsed_date = dateparser.parse(date_query, settings={'PREFER_DATES_FROM': 'future', 'STRICT_PARSING': False})

    if not parsed_date:
        return f"Sorry, I couldn't understand the date '{date_query}'. Please provide a specific date like 'tomorrow', 'next Monday', or 'YYYY-MM-DD'."

    target_date = parsed_date.date()
    print(f"Tool: Parsed date query '{date_query}' to: {target_date}")

    # Ensure we don't check for dates too far in the past unless specified explicitly
    if target_date < date.today() and parsed_date.strftime('%Y%m%d') == datetime.now().strftime('%Y%m%d'):
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
def book_appointment(datetime_str: str, client_name: str) -> str:
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
    success = add_appointment(client_name, appointment_dt)

    if success:
        # Prepare details for email (even if sending fails or is skipped)
        appointment_details = {
            "client_name": client_name,
            "datetime": appointment_dt.isoformat(), # Use ISO for internal consistency
            "datetime_readable": appointment_dt.strftime('%A, %B %d, %Y at %I:%M %p'),
            "duration": APPOINTMENT_DURATION_MINUTES
        }
        # Trigger email sending (can be done here or as a separate step by the agent)
        email_status = send_confirmation_email_internal(appointment_details)

        return f"Success! Appointment confirmed for {client_name} on {appointment_details['datetime_readable']}. {email_status}"
    else:
        # The add_appointment function already prints conflict/error messages
        return f"Error: Could not book appointment for {client_name} at {datetime_str}. The slot might have been taken, or another error occurred. Please try checking availability again."


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
        msg['To'] = PROFESSIONAL_EMAIL
        # msg['To'] = ", ".join([PROFESSIONAL_EMAIL, client_email]) # Also send to client? Add client_email param

        # --- Email Body ---
        body = f"""
        Hi {PROFESSIONAL_NAME},

        A new appointment has been booked via the booking agent:

        Client: {client_name}
        Date & Time: {datetime_readable}
        Duration: {duration} minutes

        This appointment has been added to the database. Please find the calendar invite attached (.ics file).

        Best regards,
        Your Booking Bot
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
        # event.organizer = f"MAILTO:{SMTP_USER}" # Optional: Set organizer
        # event.add('attendee', f'MAILTO:{PROFESSIONAL_EMAIL}') # Optional
        # event.add('attendee', f'MAILTO:{client_email}') # Optional
        cal.events.add(event)

        # --- Attach ICS file ---
        # Use MIMEBase for generic binary data (text/calendar can sometimes be mishandled)
        ics_filename = f"appointment_{client_name}_{dt_start.strftime('%Y%m%d_%H%M')}.ics"
        part = MIMEBase('application', "octet-stream") # Or 'text', 'calendar; method=REQUEST'
        part.set_payload(str(cal).encode('utf-8'))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{ics_filename}"')
        msg.attach(part)


        # --- Send Email ---
        print(f"Internal: Sending email to {PROFESSIONAL_EMAIL} via {SMTP_SERVER}:{SMTP_PORT}")
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.ehlo() # Identify client to ESMTP server
            server.starttls() # Encrypt connection
            server.ehlo() # Re-identify client over encrypted connection
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, PROFESSIONAL_EMAIL, msg.as_string())
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
tools = [check_availability, book_appointment]