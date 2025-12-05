import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """
    Authenticate and return Google Calendar service
    """
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("WARNING: credentials.json not found. Google Calendar sync disabled.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(
    title: str, 
    start_time: datetime, 
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None
) -> Optional[str]:
    """
    Create an event in Google Calendar and return event ID
    """
    try:
        service = get_calendar_service()
        if not service:
            return None
        
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        event_body = {
            'summary': title,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        
        if description:
            event_body['description'] = description
        
        if location:
            event_body['location'] = location
        
        if attendees:
            event_body['attendees'] = [{'email': email} for email in attendees]
        
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return event.get('id')
        
    except Exception as e:
        print(f"Error creating calendar event: {e}")
        return None

def update_calendar_event(
    event_id: str,
    title: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[List[str]] = None
) -> bool:
    """
    Update an existing calendar event
    """
    try:
        service = get_calendar_service()
        if not service:
            return False
        
        if not end_time:
            end_time = start_time + timedelta(hours=1)
        
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        event['summary'] = title
        event['start'] = {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        }
        event['end'] = {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        }
        
        if description:
            event['description'] = description
        
        if location:
            event['location'] = location
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return True
        
    except Exception as e:
        print(f"Error updating calendar event: {e}")
        return False

def delete_calendar_event(event_id: str) -> bool:
    """
    Delete a calendar event
    """
    try:
        service = get_calendar_service()
        if not service:
            return False
        
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True
        
    except Exception as e:
        print(f"Error deleting calendar event: {e}")
        return False

def fetch_upcoming_events(max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch upcoming events from Google Calendar
    """
    try:
        service = get_calendar_service()
        if not service:
            return []
        
        now = datetime.utcnow().isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        parsed_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            parsed_events.append({
                'id': event['id'],
                'title': event.get('summary', 'Untitled'),
                'description': event.get('description'),
                'start_time': start,
                'end_time': end,
                'location': event.get('location'),
                'status': event.get('status', 'confirmed')
            })
        
        return parsed_events
        
    except Exception as e:
        print(f"Error fetching calendar events: {e}")
        return []