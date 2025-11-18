import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time
import plotly.express as px
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io

# Page config
st.set_page_config(page_title="MediReminder - Medication & Health Tracker", layout="centered")
st.title("🩺 MediReminder")
st.markdown("### Your Personal Medication Reminder & Health Logging App")

# Database setup
conn = sqlite3.connect("health_log.db", check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''
CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    start_date TEXT,
    end_date TEXT,
    times_per_day TEXT,
    reminder_times TEXT
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    symptom TEXT,
    severity INTEGER,
    notes TEXT,
    taken_medications TEXT
)
''')

conn.commit()

# Sidebar Navigation
page = st.sidebar.selectbox("Navigate", ["🏠 Dashboard", "💊 Add Medication", "📊 Health Log", "📈 Reports", "🩺 Generate PDF Report"])

# Helper function to parse time strings
def parse_times(time_str):
    if not time_str:
        return []
    return [t.strip() for t in time_str.split(",")]

# ==================== DASHBOARD ====================
if page == "🏠 Dashboard":
    st.header("Today's Reminder Dashboard")
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")

    c.execute("SELECT * FROM medications WHERE ? BETWEEN start_date AND COALESCE(end_date, ?) ", (today, today))
    meds = c.fetchall()

    if not meds:
        st.info("No medications scheduled for today. Enjoy your day! 😊")
    else:
        st.success(f"📅 Today: {datetime.now().strftime('%A, %B %d, %Y')}")
        
        for med in meds:
            med_id, name, dosage, freq, start, end, times_per_day, reminder_times_str = med
            reminder_times = parse_times(reminder_times_str)

            with st.expander(f"💊 {name} - {dosage}", expanded=True):
                cols = st.columns([2, 1, 1])
                cols[0].write(f"**Frequency:** {freq}")
                cols[1].write(f"**Times/day:** {times_per_day}")

                pending = []
                taken = []
                for t in reminder_times:
                    if t < current_time:
                        # Check if logged today
                        c.execute("SELECT taken_medications FROM health_log WHERE date = ?", (today,))
                        log = c.fetchone()
                        med_taken = log[0].split(";") if log and log[0] else []
                        if name in med_taken:
                            taken.append(t)
                        else:
                            pending.append(t)
                    else:
                        pending.append(t)

                if pending:
                    st.warning(f"⏰ Pending: {', '.join(pending)}")
                if taken:
                    st.success(f"✅ Taken: {', '.join(taken)}")

                if st.button(f"Mark {name} as Taken Now", key=f"take_{med_id}"):
                    c.execute("SELECT taken_medications FROM health_log WHERE date = ?", (today,))
                    row = c.fetchone()
                    taken_list = row[0].split(";") if row and row[0] else []
                    if name not in taken_list:
                        taken_list.append(name)
                        taken_str = ";".join(taken_list)
                        if row:
                            c.execute("UPDATE health_log SET taken_medications = ? WHERE date = ?", (taken_str, today))
                        else:
                            c.execute("INSERT INTO health_log (date, taken_medications) VALUES (?, ?)", (today, name))
                        conn.commit()
                        st.success(f"✅ {name} marked as taken!")
                        st.experimental_rerun()

# ==================== ADD MEDICATION ====================
elif page == "💊 Add Medication":
    st.header("Add New Medication")

    with st.form("med_form"):
        name = st.text_input("Medication Name*", placeholder="e.g., Amlodipine")
        dosage = st.text_input("Dosage*", placeholder="e.g., 5mg")
        frequency = st.selectbox("Frequency*", ["Daily", "Every other day", "Weekly", "As needed"])
        times_per_day = st.number_input("How many times per day?", min_value=1, max_value=10, value=2)
        
        reminder_input = st.text_input(f"Reminder Times (24-hour format, comma separated)*", 
                                       placeholder="08:00, 20:00")
        
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start Date", value=datetime.today())
        end_date = col2.date_input("End Date (optional)", value=None)

        submitted = st.form_submit_button("💾 Save Medication")
        if submitted:
            if not name or not dosage or not reminder_input:
                st.error("Please fill all required fields.")
            else:
                c.execute('''
                INSERT INTO medications (name, dosage, frequency, start_date, end_date, times_per_day, reminder_times)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, dosage, frequency, str(start_date), 
                      str(end_date) if end_date else None, times_per_day, reminder_input))
                conn.commit()
                st.success(f"Medication '{name}' added successfully!")
                st.balloons()

# ==================== HEALTH LOG ====================
elif page == "📊 Health Log":
    st.header("Log Symptoms & Health Status")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    with st.form("log_form"):
        symptom = st.text_input("Symptom (e.g., Headache, Fatigue)")
        severity = st.slider("Severity", 1, 10, 5)
        notes = st.text_area("Additional Notes")
        
        submitted = st.form_submit_button("Save Health Entry")
        if submitted:
            c.execute('''
            INSERT INTO health_log (date, symptom, severity, notes)
            VALUES (?, ?, ?, ?)
            ''', (today, symptom, severity, notes))
            conn.commit()
            st.success("Health entry saved!")

    # Show recent logs
    st.subheader("Recent Health Entries")
    c.execute("SELECT date, symptom, severity, notes FROM health_log ORDER BY date DESC LIMIT 10")
    logs = c.fetchall()
    if logs:
        df = pd.DataFrame(logs, columns=["Date", "Symptom", "Severity", "Notes"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No health logs yet.")

# ==================== REPORTS ====================
elif page == "📈 Reports":
    st.header("Health & Medication Reports")

    c.execute("SELECT date, symptom, severity FROM health_log")
    data = c.fetchall()
    
    if data:
        df = pd.DataFrame(data, columns=["Date", "Symptom", "Severity"])
        df["Date"] = pd.to_datetime(df["Date"])

        fig = px.line(df, x="Date", y="Severity", color="Symptom", title="Symptom Severity Over Time")
        st.plotly_chart(fig, use_container_width=True)

        adherence_df = pd.read_sql("""
            SELECT date, taken_medications FROM health_log WHERE taken_medications != ''
        """, conn)
        if not adherence_df.empty:
            st.success(f"Medication Adherence: {len(adherence_df)} days logged")
    else:
        st.info("No data available for reports yet.")

# ==================== GENERATE PDF REPORT ====================
elif page == "🩺 Generate PDF Report":
    st.header("Generate PDF Health Report")

    start_date = st.date_input("From Date", value=datetime.today())
    end_date = st.date_input("To Date", value=datetime.today())

    if st.button("Generate PDF Report"):
        c.execute("SELECT * FROM health_log WHERE date BETWEEN ? AND ?", (str(start_date), str(end_date)))
        logs = c.fetchall()
        c.execute("SELECT name, dosage FROM medications")
        meds = c.fetchall()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("Health & Medication Report", styles['Title']))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # Medications
        elements.append(Paragraph("Active Medications", styles['Heading2']))
        med_data = [["Name", "Dosage"]]
        for m in meds:
            med_data.append([m[0], m[1]])
        t = Table(med_data)
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey),
                               ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                               ('GRID',(0,0),(-1,-1),0.5,colors.grey)]))
        elements.append(t)
        elements.append(Spacer(1, 20))

        # Health Log
        elements.append(Paragraph("Health Log Entries", styles['Heading2']))
        log_data = [["Date", "Symptom", "Severity", "Notes"]]
        for log in logs:
            log_data.append([log[1], log[2], log[3], log[4] or "-"])
        t2 = Table(log_data)
        t2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                                ('GRID',(0,0),(-1,-1),0.5,colors.black)]))
        elements.append(t2)

        doc.build(elements)
        buffer.seek(0)

        st.download_button(
            label="Download PDF Report",
            data=buffer,
            file_name=f"health_report_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
        st.success("PDF Report Ready!")

# Footer
st.markdown("---")
st.markdown("Made with ❤️ for better health management | Pakistan 🇵🇰")