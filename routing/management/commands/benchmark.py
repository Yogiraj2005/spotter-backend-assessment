from django.core.management.base import BaseCommand
from routing.services import calculate_optimal_route
import time

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        self.stdout.write("--- FIRST RUN (COLD) ---")
        calculate_optimal_route('Chicago,IL', 'Denver,CO')
        
        self.stdout.write("\n--- SECOND RUN (CACHED) ---")
        calculate_optimal_route('Chicago,IL', 'Denver,CO')
        
        self.stdout.write("Success")
