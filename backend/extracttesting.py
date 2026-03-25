from task_extractor import extract_events_from_conversation
messages = [{"role":"user","content":"Schedule a team meeting tomorrow at 2pm."}]
print(extract_events_from_conversation(messages))
