import requests
import math
import concurrent.futures
from django.conf import settings
from geopy.distance import geodesic
from .models import FuelStation

from django.core.cache import cache

def geocode_address(address_string):
    cache_key = f"geocode_{address_string.strip().lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
        
    url = "https://api.openrouteservice.org/geocode/search"
    params = {'api_key': settings.ORS_API_KEY, 'text': address_string, 'size': 1}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['features']:
                coords = data['features'][0]['geometry']['coordinates']
                res = coords[1], coords[0]
                cache.set(cache_key, res, timeout=86400) # cache for 24h
                return res
    except Exception:
        pass
    return None, None

def get_route(start_coords, finish_coords):
    cache_key = f"route_{start_coords[0]}_{start_coords[1]}_{finish_coords[0]}_{finish_coords[1]}"
    cached = cache.get(cache_key)
    if cached:
        return cached
        
    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {'Authorization': settings.ORS_API_KEY, 'Content-Type': 'application/json'}
    body = {
        "coordinates": [[start_coords[1], start_coords[0]], [finish_coords[1], finish_coords[0]]],
        "instructions": False
    }
    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        if response.status_code == 200:
            res = response.json()
            cache.set(cache_key, res, timeout=86400)
            return res
    except Exception:
        pass
    return None

def point_to_segment_distance(px, py, x1, y1, x2, y2):
    # approximate distance from point to segment in degrees
    l2 = (x1 - x2)**2 + (y1 - y2)**2
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)

def decode_polyline(polyline_str):
    # OpenRouteService uses Google's polyline algorithm with precision 5
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}
    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']: 
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if (result & 1):
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = (result >> 1)
        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates

import time

def calculate_optimal_route(start_address, finish_address):
    t_start = time.time()
    timings = {}
    
    # Run both geocoding API calls simultaneously (saves ~2 seconds)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_start = executor.submit(geocode_address, start_address)
        future_finish = executor.submit(geocode_address, finish_address)
        start_coords = future_start.result()
        finish_coords = future_finish.result()
        
    timings['geocoding'] = time.time() - t_start
    t_route_start = time.time()
    
    if not start_coords or not finish_coords:
        return {"error": "Could not geocode start or finish address."}
        
    route_data = get_route(start_coords, finish_coords)
    if not route_data or 'routes' not in route_data:
        return {"error": "Could not find a route."}
        
    route = route_data['routes'][0]
    total_distance_miles = route['summary']['distance'] * 0.000621371 # meters to miles
    geometry = route['geometry']
    
    timings['routing_api'] = time.time() - t_route_start
    t_decode_start = time.time()
    
    # decode polyline
    path = decode_polyline(geometry)
    
    timings['polyline_decode'] = time.time() - t_decode_start
    t_station_match_start = time.time()
    
    from routing.apps import RoutingConfig
    import numpy as np
    
    # Downsample route: keep roughly one point every 5 miles
    sampled_path = []
    sampled_distances = []
    
    if len(path) > 0:
        sampled_path.append(path[0])
        sampled_distances.append(0.0)
        
        cum_dist = 0.0
        last_sampled_dist = 0.0
        
        for i in range(1, len(path)):
            dist = geodesic(path[i-1], path[i]).miles
            cum_dist += dist
            if cum_dist - last_sampled_dist >= 5.0 or i == len(path) - 1:
                sampled_path.append(path[i])
                sampled_distances.append(cum_dist)
                last_sampled_dist = cum_dist
                
    stations_along_route = []
    if RoutingConfig.stations_tree is not None and RoutingConfig.stations_df is not None:
        # Search radius in radians (5 miles approx)
        EARTH_RADIUS_MILES = 3958.8
        radius_rad = 5.0 / EARTH_RADIUS_MILES
        
        # Convert sampled path to radians for KDTree query
        path_rad = np.radians(sampled_path)
        
        # Query the KDTree for all points at once
        # Returns list of lists of indices
        indices_list = RoutingConfig.stations_tree.query_ball_point(path_rad, radius_rad)
        
        seen_station_ids = set()
        
        for i, indices in enumerate(indices_list):
            dist_along = sampled_distances[i]
            for idx in indices:
                station_row = RoutingConfig.stations_df.iloc[idx]
                station_id = station_row['opis_truckstop_id']
                if station_id not in seen_station_ids:
                    seen_station_ids.add(station_id)
                    stations_along_route.append({
                        'station_name': station_row['name'],
                        'address': station_row['address'],
                        'city': station_row['city'],
                        'state': station_row['state'],
                        'price': station_row['retail_price'],
                        'distance_along_route': dist_along,
                        'location': {'lat': station_row['latitude'], 'lng': station_row['longitude']}
                    })
            
            
    # Sort stations by distance from start
    stations_along_route.sort(key=lambda x: x['distance_along_route'])
    
    timings['station_matching'] = time.time() - t_station_match_start
    t_greedy_start = time.time()
    
    # FUEL OPTIMIZATION (Simplified Greedy Algorithm)
    # Range = 500 miles. MPG = 10.
    MAX_RANGE = 500.0
    MPG = 10.0
    
    stops = []
    total_cost = 0.0
    current_pos = 0.0
    
    while current_pos + MAX_RANGE < total_distance_miles:
        # Find all reachable stations from current_pos
        reachable = [s for s in stations_along_route if current_pos < s['distance_along_route'] <= current_pos + MAX_RANGE]
        
        if not reachable:
            return {"error": "Not enough fuel stations along the route to complete the journey."}
            
        # Find cheapest station in range
        cheapest = min(reachable, key=lambda x: x['price'])
        
        # Calculate fuel needed to get from current_pos to this cheapest station
        dist_driven = cheapest['distance_along_route'] - current_pos
        gallons_needed = dist_driven / MPG
        
        stops.append({
            "name": cheapest['station_name'],
            "address": cheapest['address'],
            "city": cheapest['city'],
            "state": cheapest['state'],
            "lat": cheapest['location']['lat'],
            "lon": cheapest['location']['lng'],
            "price_per_gallon": cheapest['price'],
            "miles_from_start": round(cheapest['distance_along_route'], 2)
        })
        
        current_pos = cheapest['distance_along_route']
        
    total_gallons = total_distance_miles / MPG
    initial_tank = None

    # Calculate costs based on the stops we picked.
    if not stops and stations_along_route:
        cheapest = min(stations_along_route, key=lambda x: x['price'])
        dist = total_distance_miles
        gallons = dist / MPG
        cost = gallons * cheapest['price']
        
        initial_tank = {
            "miles": round(dist, 2),
            "gallons": round(gallons, 2),
            "price_per_gallon": cheapest['price'],
            "cost": round(cost, 2)
        }
        total_cost = cost
    elif not stops:
        # Route < 500 miles and NO stations found. 
        total_cost = 0.0 # Free ride
    else:
        # initial_tank covers start to stops[0]
        dist_initial = stops[0]['miles_from_start']
        gal_initial = dist_initial / MPG
        cost_initial = gal_initial * stops[0]['price_per_gallon']
        
        initial_tank = {
            "miles": round(dist_initial, 2),
            "gallons": round(gal_initial, 2),
            "price_per_gallon": stops[0]['price_per_gallon'],
            "cost": round(cost_initial, 2)
        }
        
        total_cost = cost_initial
        
        for i, stop in enumerate(stops):
            if i < len(stops) - 1:
                dist = stops[i+1]['miles_from_start'] - stop['miles_from_start']
            else:
                dist = total_distance_miles - stop['miles_from_start']
            
            gallons = dist / MPG
            cost = gallons * stop['price_per_gallon']
            
            stop['gallons_purchased'] = round(gallons, 2)
            stop['cost'] = round(cost, 2)
            
            total_cost += cost

    timings['greedy_optimization'] = time.time() - t_greedy_start
    timings['total'] = time.time() - t_start
    
    print("--- TIMINGS ---")
    for k, v in timings.items():
        print(f"{k}: {v:.4f}s")
    print("---------------")

    # Downsample route_geojson to max 500 points
    if len(path) > 500:
        step = len(path) / 500.0
        path = [path[int(i * step)] for i in range(500)]

    path_lng_lat = [[p[1], p[0]] for p in path]

    response = {
        "total_distance_miles": round(total_distance_miles, 2),
        "total_gallons": round(total_gallons, 2),
        "total_fuel_cost": round(total_cost, 2)
    }
    
    if initial_tank:
        response["initial_tank"] = initial_tank
        
    response["fuel_stops"] = stops
    response["meta"] = {
        "processing_time_seconds": round(timings['total'], 4),
        "assumption": "Initial tank is priced at the first stop's price per gallon."
    }
    response["route_geojson"] = {
        "type": "LineString",
        "coordinates": path_lng_lat
    }
    return response
