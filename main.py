from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import os
import json
import base64
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import get_db, init_db, Conversation, Message, Event
from models import (
    MessageCreate, MessageResponse, ConversationResponse, 
    EventCreate, EventResponse, ChatRequest, ChatResponse
)
from task_extractor import (
    extract_events_from_conversation, 
    generate_calendar_summary,
    transcribe_audio,
    generate_smart_reminder,
    analyze_user_patterns
)
from calendar_sync import (
    create_calendar_event, update_calendar_event, 
    delete_calendar_event, fetch_upcoming_events
)

load_dotenv()

app = FastAPI(title="AI Calendar Chat Assistant")

# CORS - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background scheduler for agentic reminders
scheduler = BackgroundScheduler()

def check_upcoming_events():
    """
    Agentic AI checks for upcoming events and sends smart reminders
    """
    db = next(get_db())
    now = datetime.utcnow()
    
    # Find events in next 30 minutes
    upcoming = db.query(Event).filter(
        Event.start_time > now,
        Event.start_time <= now + timedelta(minutes=30),
        Event.status == "confirmed"
    ).all()
    
    for event in upcoming:
        # Get user's event history for context
        user_events = db.query(Event).filter(
            Event.user_id == event.user_id
        ).limit(20).all()
        
        # Generate smart reminder using Claude
        reminder = generate_smart_reminder(event, user_events)
        
        print(f"\n🔔 SMART REMINDER:")
        print(f"Event: {event.title}")
        print(f"Message: {reminder}")
        print(f"Time: {event.start_time}")
        
        # You can send this via email, SMS, or push notification
        # For now, we'll just log it
    
    db.close()

def analyze_user_behavior():
    """
    Agentic AI analyzes user patterns and provides insights
    """
    db = next(get_db())
    
    # Get all events from last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    events = db.query(Event).filter(
        Event.created_at >= thirty_days_ago
    ).all()
    
    if events:
        insights = analyze_user_patterns(events)
        print(f"\n📊 USER BEHAVIOR INSIGHTS:")
        print(json.dumps(insights, indent=2))
    
    db.close()

@app.on_event("startup")
def startup_event():
    init_db()
    
    # Start agentic monitoring
    scheduler.add_job(
        check_upcoming_events,
        trigger=IntervalTrigger(minutes=5),
        id="event_reminders",
        replace_existing=True
    )
    
    scheduler.add_job(
        analyze_user_behavior,
        trigger=IntervalTrigger(hours=24),
        id="behavior_analysis",
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Agentic AI monitoring started!")

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Backend is running!"}

# Chat Endpoints

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint - processes user message and extracts events
    """
    print(f"\n📨 Received message: {request.message}")
    
    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation()
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Get conversation history for context
    messages = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.timestamp.asc()).all()
    
    message_history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
    
    # Extract events and generate response using Claude
    result = extract_events_from_conversation(message_history)
    
    # Save assistant response
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["response"]
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    # Process extracted events
    created_events = []
    for event_data in result.get("events", []):
        # Create event in database
        event = Event(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            title=event_data["title"],
            description=event_data.get("description"),
            start_time=event_data["start_time"],
            end_time=event_data.get("end_time"),
            location=event_data.get("location"),
            attendees=json.dumps(event_data.get("attendees", []))
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        # Sync to Google Calendar
        try:
            calendar_event_id = create_calendar_event(
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                description=event.description,
                location=event.location,
                attendees=event_data.get("attendees")
            )
            
            if calendar_event_id:
                event.calendar_event_id = calendar_event_id
                event.synced_at = datetime.utcnow()
                db.commit()
                print(f"✅ Event synced to Google Calendar: {event.title}")
        except Exception as e:
            print(f"⚠️ Google Calendar sync failed: {e}")
        
        created_events.append(event)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    db.commit()
    
    print(f"✅ Created {len(created_events)} events")
    
    return ChatResponse(
        message=user_message,
        assistant_message=assistant_message,
        events=created_events,
        conversation_id=conversation.id
    )

@app.post("/chat/voice")
async def chat_voice(audio: UploadFile = File(...), conversation_id: int = None, db: Session = Depends(get_db)):
    """
    Voice chat endpoint - transcribes audio and processes as chat
    """
    print(f"\n🎤 Received voice message")
    
    # Read audio file
    audio_data = await audio.read()
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    
    # Transcribe using Whisper
    transcript = transcribe_audio(audio_base64)
    print(f"📝 Transcribed: {transcript}")
    
    if not transcript:
        raise HTTPException(status_code=400, detail="Could not transcribe audio")
    
    # Process as regular chat
    request = ChatRequest(message=transcript, conversation_id=conversation_id)
    return chat(request, db)

@app.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(db: Session = Depends(get_db)):
    """
    Get all conversations
    """
    conversations = db.query(Conversation).order_by(
        Conversation.updated_at.desc()
    ).all()
    return conversations

@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Get a specific conversation with all messages
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """
    Delete a conversation and its messages
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted"}

# Event Endpoints

@app.get("/events", response_model=List[EventResponse])
def get_events(db: Session = Depends(get_db)):
    """
    Get all upcoming events
    """
    events = db.query(Event).filter(
        Event.start_time >= datetime.utcnow()
    ).order_by(Event.start_time.asc()).all()
    
    return events

@app.get("/events/insights")
def get_event_insights(db: Session = Depends(get_db)):
    """
    Get AI-powered insights about user's scheduling patterns
    """
    # Get events from last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    events = db.query(Event).filter(
        Event.created_at >= thirty_days_ago
    ).all()
    
    if not events:
        return {"insights": [], "suggestions": []}
    
    insights = analyze_user_patterns(events)
    return insights

@app.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    """
    Get a specific event
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event

@app.put("/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, event_data: EventCreate, db: Session = Depends(get_db)):
    """
    Update an event
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.title = event_data.title
    event.description = event_data.description
    event.start_time = event_data.start_time
    event.end_time = event_data.end_time
    event.location = event_data.location
    event.attendees = json.dumps(event_data.attendees or [])
    event.updated_at = datetime.utcnow()
    
    # Update in Google Calendar
    if event.calendar_event_id:
        try:
            update_calendar_event(
                event.calendar_event_id,
                event.title,
                event.start_time,
                event.end_time,
                event.description,
                event.location,
                event_data.attendees
            )
            event.synced_at = datetime.utcnow()
        except Exception as e:
            print(f"⚠️ Calendar update failed: {e}")
    
    db.commit()
    db.refresh(event)
    
    return event

@app.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """
    Delete an event
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete from Google Calendar
    if event.calendar_event_id:
        try:
            delete_calendar_event(event.calendar_event_id)
        except Exception as e:
            print(f"⚠️ Calendar deletion failed: {e}")
    
    db.delete(event)
    db.commit()
    
    return {"message": "Event deleted"}

@app.post("/sync-calendar")
def sync_calendar(db: Session = Depends(get_db)):
    """
    Sync events from Google Calendar
    """
    try:
        google_events = fetch_upcoming_events()
        
        synced_count = 0
        for g_event in google_events:
            # Check if event already exists
            existing = db.query(Event).filter(
                Event.calendar_event_id == g_event['id']
            ).first()
            
            if not existing:
                # Create new event from Google Calendar
                event = Event(
                    title=g_event['title'],
                    description=g_event.get('description'),
                    start_time=datetime.fromisoformat(g_event['start_time'].replace('Z', '+00:00')),
                    end_time=datetime.fromisoformat(g_event['end_time'].replace('Z', '+00:00')) if g_event.get('end_time') else None,
                    location=g_event.get('location'),
                    status=g_event.get('status', 'confirmed'),
                    calendar_event_id=g_event['id'],
                    synced_at=datetime.utcnow()
                )
                db.add(event)
                synced_count += 1
        
        db.commit()
        
        return {"message": f"Synced {synced_count} events from Google Calendar", "count": synced_count}
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")
        return {"message": "Sync failed - Google Calendar not configured", "count": 0}

@app.get("/")
def root():
    return {
        "status": "running",
        "message": "AI Calendar Chat Assistant API",
        "version": "2.0",
        "features": ["chat", "voice", "agentic_reminders", "pattern_analysis"],
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "voice": "/chat/voice",
            "events": "/events",
            "insights": "/events/insights",
            "conversations": "/conversations",
            "sync": "/sync-calendar"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AI Calendar Assistant Backend...")
    print("📍 Backend will be available at: http://localhost:8000")
    print("📚 API docs available at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")