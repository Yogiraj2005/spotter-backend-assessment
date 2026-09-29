import requests
import csv
import io
from django.core.management.base import BaseCommand
from routing.models import FuelStation

class Command(BaseCommand):
    help = 'Batch geocodes fuel stations using US Census API'

    def handle(self, *args, **kwargs):
        stations = FuelStation.objects.filter(latitude__isnull=True)
        total = stations.count()
        self.stdout.write(f"Found {total} stations to geocode.")
        
        if total == 0:
            return

        # US Census batch geocoder accepts max 10,000 records. We have ~8000, so we can do it in one go.
        # Format: Unique ID, Street address, City, State, ZIP
        
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        
        for station in stations:
            writer.writerow([station.opis_truckstop_id, station.address, station.city, station.state, ''])
            
        csv_buffer.seek(0)
        
        self.stdout.write("Sending batch request to US Census API (this might take a few minutes)...")
        
        url = 'https://geocoding.geo.census.gov/geocoder/locations/addressbatch'
        payload = {'benchmark': 'Public_AR_Current'}
        files = {'addressFile': ('addresses.csv', csv_buffer.getvalue())}
        
        response = requests.post(url, data=payload, files=files)
        
        if response.status_code == 200:
            self.stdout.write(self.style.SUCCESS("Received response from Census API, parsing..."))
            results_csv = response.text.splitlines()
            reader = csv.reader(results_csv)
            
            updated_count = 0
            for row in reader:
                if len(row) >= 6 and row[2] == 'Match':
                    try:
                        station_id = int(row[0])
                        # Coordinates are in row[5] as "Longitude,Latitude"
                        lon_str, lat_str = row[5].split(',')
                        
                        FuelStation.objects.filter(opis_truckstop_id=station_id).update(
                            latitude=float(lat_str),
                            longitude=float(lon_str)
                        )
                        updated_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error parsing row {row}: {e}"))
            
            self.stdout.write(self.style.SUCCESS(f"Successfully geocoded {updated_count} stations!"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to geocode. Status code: {response.status_code}"))
            self.stdout.write(response.text)
