from django.apps import AppConfig
import pandas as pd
import numpy as np
import os
from django.conf import settings

class RoutingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'routing'
    
    stations_df = None
    stations_tree = None

    def ready(self):
        # Load geocoded stations into memory and build KDTree
        # We only load it once at startup
        csv_path = os.path.join(settings.BASE_DIR, 'data', 'stations_geocoded.csv')
        if os.path.exists(csv_path):
            try:
                import scipy.spatial
                df = pd.read_csv(csv_path)
                
                # Convert lat/lon to radians for cKDTree
                coords_rad = np.radians(df[['latitude', 'longitude']].values)
                tree = scipy.spatial.cKDTree(coords_rad)
                
                RoutingConfig.stations_df = df
                RoutingConfig.stations_tree = tree
                print(f"Loaded {len(df)} stations into spatial index.")
            except Exception as e:
                print(f"Failed to load stations spatial index: {e}")
