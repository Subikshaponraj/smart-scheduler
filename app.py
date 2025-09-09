import streamlit as st
import openai
import os
import json
import dateparser
from dotenv import load_dotenv
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Auth
@st.cache_resource
def authenticate_google_calendar():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

# Extract event from OpenAI
def parse_schedule_input(user_input):
    prompt = f"""Extract event details as raw JSON with these exact keys: "title", "date", "time", "participants".

Return ONLY valid JSON, no labels, no formatting. Example:
{{
  "title": "Project sync",
  "date": "July 3rd",
  "time": "10:00 AM",
  "participants": "alice@example.com"
}}

Input: "{user_input}"
"""

    response = openai.Completion.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=200,
    )

    raw = response.choices[0].text.strip()

    # Remove "Output:" or other junk before JSON
    if raw.lower().startswith("output:"):
        raw = raw[len("output:"):].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"❌ Failed to parse JSON: {e}")
        st.text("Raw response:")
        st.code(response.choices[0].text)
        return None


# Calendar event creation
def create_event(service, details):
    raw_datetime = f"{details['date']} {details['time']}"
    parsed_datetime = dateparser.parse(raw_datetime)

    if not parsed_datetime:
        return None, None

    start = parsed_datetime.isoformat()
    end = (parsed_datetime + timedelta(hours=1)).isoformat()

    event = {
        'summary': details['title'],
        'start': {'dateTime': start, 'timeZone': 'America/New_York'},
        'end': {'dateTime': end, 'timeZone': 'America/New_York'},
        'attendees': [{'email': p.strip()} for p in details['participants'].split(',')],
        'conferenceData': {
            'createRequest': {
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                'requestId': f"meet-{int(datetime.now().timestamp())}"
            }
        }
    }

    created = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1
    ).execute()

    return created.get('htmlLink'), created.get('hangoutLink', None)

# UI
st.title("📆 Agentic AI Calendar Assistant")
user_input = st.text_input("What would you like to schedule?", placeholder="e.g., Schedule a call with Alice on Friday at 2 PM")

if st.button("Parse and Schedule"):
    if not user_input:
        st.warning("Please enter a command.")
    else:
        try:
            details = parse_schedule_input(user_input)
            st.subheader("🧠 Parsed Details")
            st.json(details)

            with st.spinner("Authenticating with Google Calendar..."):
                service = authenticate_google_calendar()

            with st.spinner("Creating event..."):
                link, meet = create_event(service, details)

            if link:
                st.success("✅ Event Created!")
                st.markdown(f"📅 [Open Calendar Event]({link})")
                if meet:
                    st.markdown(f"🎥 [Google Meet Link]({meet})")
            else:
                st.error("❌ Failed to parse time or create event.")
        except Exception as e:
            st.error(f"❌ Error: {e}")