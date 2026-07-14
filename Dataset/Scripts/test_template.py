from config import EVENT_FILE
from utils import load_events
from template_manager import maintenance_template

events = load_events(EVENT_FILE)

event = events.iloc[0]

temp = maintenance_template(event)

for k, v in temp.items():

    print("=" * 40)

    print(k.upper())

    print(v)