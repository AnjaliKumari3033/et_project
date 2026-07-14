from config import EVENT_FILE
from utils import *

events = load_events(EVENT_FILE)

log("Excel Loaded Successfully")

print(events.head())

print()

print(get_event(events, "EVT-001"))

print()

print(linked_documents(events.iloc[0]))