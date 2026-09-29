from django.test import TestCase
import json
import os
from unittest.mock import patch
from routing.services import calculate_optimal_route
from django.conf import settings

class RouteOptimizationTestCase(TestCase):
    def setUp(self):
        # We need mock route data
        mock_data_path = os.path.join(settings.BASE_DIR, 'routing', 'mock_route_data.json')
        if os.path.exists(mock_data_path):
            with open(mock_data_path, 'r') as f:
                self.mock_data = json.load(f)
        else:
            self.mock_data = None

    @patch('routing.services.geocode_address')
    @patch('routing.services.get_route')
    def test_chicago_denver_fuel_calculation(self, mock_get_route, mock_geocode):
        if not self.mock_data:
            self.skipTest("No mock data found")
            
        def mock_geocode_side_effect(address):
            if "Chicago" in address:
                return self.mock_data['start']
            elif "Denver" in address:
                return self.mock_data['finish']
            return None
            
        mock_geocode.side_effect = mock_geocode_side_effect
        mock_get_route.return_value = self.mock_data['route']
        
        response = calculate_optimal_route("Chicago,IL", "Denver,CO")
        
        self.assertNotIn("error", response)
        
        # Check initial tank exists
        self.assertIn("initial_tank", response)
        
        initial_tank_gallons = response["initial_tank"]["gallons"]
        self.assertLessEqual(initial_tank_gallons, 50.0)
        
        total_calculated_gallons = initial_tank_gallons
        total_calculated_cost = response["initial_tank"]["cost"]
        
        for stop in response["fuel_stops"]:
            self.assertLessEqual(stop["gallons_purchased"], 50.0)
            total_calculated_gallons += stop["gallons_purchased"]
            total_calculated_cost += stop["cost"]
            
        # Allow small floating point drift
        self.assertAlmostEqual(total_calculated_gallons, response["total_gallons"], places=1)
        self.assertAlmostEqual(total_calculated_cost, response["total_fuel_cost"], places=1)
