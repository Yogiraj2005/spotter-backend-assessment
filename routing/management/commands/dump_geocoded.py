import csv
import os
from django.core.management.base import BaseCommand
from routing.models import FuelStation

class Command(BaseCommand):
    help = 'Dumps geocoded stations to a CSV file'

    def handle(self, *args, **kwargs):
        stations = FuelStation.objects.exclude(latitude__isnull=True)
        os.makedirs('data', exist_ok=True)
        with open('data/stations_geocoded.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['opis_truckstop_id', 'name', 'address', 'city', 'state', 'rack_id', 'retail_price', 'latitude', 'longitude'])
            count = 0
            for s in stations:
                writer.writerow([s.opis_truckstop_id, s.name, s.address, s.city, s.state, s.rack_id, s.retail_price, s.latitude, s.longitude])
                count += 1
        self.stdout.write(f"Dumped {count} stations to data/stations_geocoded.csv")
