from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .services import calculate_optimal_route
import json

class RouteOptimizationView(APIView):
    def get(self, request):
        start = request.query_params.get('start')
        finish = request.query_params.get('finish')
        
        if not start or not finish:
            return Response({"error": "Please provide 'start' and 'finish' locations in the query parameters."}, status=status.HTTP_400_BAD_REQUEST)
            
        result = calculate_optimal_route(start, finish)
        
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(result, status=status.HTTP_200_OK)

class RouteMapView(APIView):
    def get(self, request):
        start = request.query_params.get('start')
        finish = request.query_params.get('finish')
        
        if not start or not finish:
            return HttpResponse("Please provide 'start' and 'finish' locations.", status=400)
            
        result = calculate_optimal_route(start, finish)
        
        if "error" in result:
            return HttpResponse(result["error"], status=400)
            
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Route Map</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                #map {{ height: 100vh; width: 100%; }}
                body {{ margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var map = L.map('map').setView([39.8283, -98.5795], 4);
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '© OpenStreetMap'
                }}).addTo(map);

                var routeGeoJSON = {json.dumps(result['route_geojson'])};
                var fuelStops = {json.dumps(result['fuel_stops'])};

                var routeLayer = L.geoJSON(routeGeoJSON, {{
                    style: function (feature) {{
                        return {{color: "#3388ff", weight: 5}};
                    }}
                }}).addTo(map);
                
                map.fitBounds(routeLayer.getBounds());

                fuelStops.forEach(function(stop) {{
                    var marker = L.marker([stop.lat, stop.lon]).addTo(map);
                    marker.bindPopup("<b>" + stop.name + "</b><br>Price: $" + stop.price_per_gallon + "<br>Gallons: " + stop.gallons_purchased);
                }});
            </script>
        </body>
        </html>
        """
        return HttpResponse(html)
