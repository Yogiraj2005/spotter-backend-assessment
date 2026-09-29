import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
from routing.services import geocode_address, get_route
import json

start = geocode_address("Chicago,IL")
finish = geocode_address("Denver,CO")
route = get_route(start, finish)

with open("routing/mock_route_data.json", "w") as f:
    json.dump({
        "start": start,
        "finish": finish,
        "route": route
    }, f)
print("Data saved.")
