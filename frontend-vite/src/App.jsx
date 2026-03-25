import React, { useState, useEffect, useRef } from 'react';
import { Send, Calendar, Clock, MapPin, User, Trash2, RefreshCw, MessageSquare } from 'lucide-react';

const API_URL = 'http://localhost:8000';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [events, setEvents] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchEvents();
    // Auto-refresh events every 30 seconds
    const interval = setInterval(fetchEvents, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchEvents = async () => {
    try {
      const response = await fetch(`${API_URL}/events`);
      const data = await response.json();
      setEvents(data);
    } catch (error) {
      console.error('Error fetching events:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMsg = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputMessage,
          conversation_id: conversationId
        })
      });

      const data = await response.json();

      // Update conversation ID
      if (!conversationId) {
        setConversationId(data.conversation_id);
      }

      // Add assistant message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.assistant_message.content,
        timestamp: data.assistant_message.timestamp
      }]);

      // Refresh events if any were created
      if (data.events && data.events.length > 0) {
        fetchEvents();
      }

    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const deleteEvent = async (eventId) => {
    try {
      await fetch(`${API_URL}/events/${eventId}`, { method: 'DELETE' });
      fetchEvents();
    } catch (error) {
      console.error('Error deleting event:', error);
    }
  };

  const syncCalendar = async () => {
    try {
      const response = await fetch(`${API_URL}/sync-calendar`, { method: 'POST' });
      const data = await response.json();
      alert(data.message);
      fetchEvents();
    } catch (error) {
      console.error('Error syncing calendar:', error);
    }
  };

  const newConversation = () => {
    setMessages([]);
    setConversationId(null);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const isToday = (dateString) => {
    const date = new Date(dateString);
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  const isTomorrow = (dateString) => {
    const date = new Date(dateString);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return date.toDateString() === tomorrow.toDateString();
  };

  const getEventDateLabel = (dateString) => {
    if (isToday(dateString)) return 'Today';
    if (isTomorrow(dateString)) return 'Tomorrow';
    return formatDate(dateString);
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-800">AI Calendar Assistant</h1>
              <p className="text-sm text-gray-500">Chat naturally to schedule events</p>
            </div>
          </div>
          <button
            onClick={newConversation}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
          >
            <MessageSquare className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <Calendar className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h2 className="text-2xl font-semibold text-gray-700 mb-2">
                Welcome to your AI Calendar Assistant!
              </h2>
              <p className="text-gray-500 mb-6">
                Chat naturally to schedule events, check your calendar, and more.
              </p>
              <div className="max-w-2xl mx-auto text-left bg-white rounded-lg p-6 shadow-sm">
                <p className="font-semibold text-gray-700 mb-3">Try saying:</p>
                <ul className="space-y-2 text-gray-600">
                  <li>• "Schedule a team meeting tomorrow at 2pm"</li>
                  <li>• "Remind me to call mom next Monday at 10am"</li>
                  <li>• "What do I have on my calendar today?"</li>
                  <li>• "Book a dentist appointment for next week"</li>
                </ul>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xl px-4 py-3 rounded-2xl ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-800 shadow-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    msg.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                  }`}
                >
                  {formatTime(msg.timestamp)}
                </p>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-white px-4 py-3 rounded-2xl shadow-sm">
                <div className="flex gap-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t px-6 py-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Type your message..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !inputMessage.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
              Send
            </button>
          </div>
        </div>
      </div>

      {/* Calendar Sidebar */}
      <div className="w-96 bg-white border-l flex flex-col">
        {/* Sidebar Header */}
        <div className="px-6 py-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              Your Calendar
            </h2>
            <button
              onClick={syncCalendar}
              className="p-2 hover:bg-gray-100 rounded-lg transition"
              title="Sync with Google Calendar"
            >
              <RefreshCw className="w-4 h-4 text-gray-600" />
            </button>
          </div>
          <p className="text-sm text-gray-500">
            {events.length} upcoming event{events.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Events List */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {events.length === 0 ? (
            <div className="text-center py-8">
              <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">No upcoming events</p>
              <p className="text-gray-400 text-xs mt-1">
                Start chatting to schedule something!
              </p>
            </div>
          ) : (
            events.map((event) => (
              <div
                key={event.id}
                className="bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-800 flex-1">
                    {event.title}
                  </h3>
                  <button
                    onClick={() => deleteEvent(event.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition"
                    title="Delete event"
                  >
                    <Trash2 className="w-4 h-4 text-red-600" />
                  </button>
                </div>

                {event.description && (
                  <p className="text-sm text-gray-600 mb-2">
                    {event.description}
                  </p>
                )}

                <div className="space-y-1 text-sm text-gray-500">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    <span>{getEventDateLabel(event.start_time)}</span>
                  </div>
                  <div className="flex items-center gap-2 ml-6">
                    <span>{formatTime(event.start_time)}</span>
                    {event.end_time && (
                      <>
                        <span>-</span>
                        <span>{formatTime(event.end_time)}</span>
                      </>
                    )}
                  </div>
                  {event.location && (
                    <div className="flex items-center gap-2">
                      <MapPin className="w-4 h-4" />
                      <span>{event.location}</span>
                    </div>
                  )}
                </div>

                {event.calendar_event_id && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-green-600">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    Synced with Google Calendar
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}