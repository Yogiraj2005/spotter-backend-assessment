import csv
from django.core.management.base import BaseCommand
from routing.models import FuelStation

class Command(BaseCommand):
    help = 'Loads fuel stations from CSV'

    def handle(self, *args, **kwargs):
        file_path = 'fuel-prices-for-be-assessment.csv'
        with open(file_path, mode='r') as file:
            reader = csv.DictReader(file)
            count = 0
            for row in reader:
                try:
                    FuelStation.objects.update_or_create(
                        opis_truckstop_id=row['OPIS Truckstop ID'],
                        defaults={
                            'name': row['Truckstop Name'],
                            'address': row['Address'],
                            'city': row['City'],
                            'state': row['State'],
                            'rack_id': row['Rack ID'],
                            'retail_price': row['Retail Price']
                        }
                    )
                    count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error on row {row}: {e}"))
            self.stdout.write(self.style.SUCCESS(f'Successfully loaded {count} stations.'))
