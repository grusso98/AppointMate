import streamlit as st
import pandas as pd
from datetime import datetime

try:
    from database import get_appointments_for_date
except ImportError as e:
    st.error(f"Fatal Error: Could not import database functions from database.py. Ensure it's in the correct path. Details: {e}")
    st.stop()

# --- Page Configuration (Optional but Recommended) ---
st.set_page_config(
    layout="wide",
    page_title="Appointment Admin",
    page_icon="📅"
)

# --- Sidebar (for future actions) ---
st.sidebar.title("Admin Actions")
st.sidebar.info("Currently view-only. Future actions like blocking time will be added here.")

# --- Main Page Content ---
st.title("📅 Appointment Schedule Viewer")
st.markdown("Select a date to view the scheduled appointments.")

# --- Date Selector ---
selected_date = st.date_input("Select Date", value=datetime.now().date())

# --- Display Schedule for Selected Date ---
if selected_date:
    st.subheader(f"Schedule for: {selected_date.strftime('%A, %B %d, %Y')}")

    try:
        # Fetch data using the new database function
        appointments_list = get_appointments_for_date(selected_date)

        if not appointments_list:
            st.info("No appointments scheduled for this date.")
        else:
            df = pd.DataFrame(appointments_list)

            # --- Data Processing for Display ---
            # 1. Convert ISO string datetime to actual datetime objects
            #    Handle potential errors if data is malformed
            try:
                df['appointment_datetime_obj'] = pd.to_datetime(df['appointment_datetime'])
            except Exception as e:
                st.error(f"Error processing appointment times: {e}. Displaying raw data.")
                st.dataframe(df) # Show raw data if conversion fails
                st.stop()

            # 2. Create columns for display (Time, Client, Duration)
            df_display = pd.DataFrame({
                'Time': df['appointment_datetime_obj'].dt.strftime('%H:%M'), # Format time
                'Client Name': df['client_name'],
                'Duration (min)': df['duration_minutes'],
                'Client Email': df['email']
            })

            # 3. Sort by time just to be sure
            df_display = df_display.sort_values(by='Time').reset_index(drop=True)

            st.dataframe(
                df_display,
                use_container_width=True, # Use full width
                hide_index=True # Don't show pandas index
            )

    except Exception as e:
        st.error("An error occurred while trying to load the schedule.")
        st.exception(e)

else:
    st.warning("Please select a date.")