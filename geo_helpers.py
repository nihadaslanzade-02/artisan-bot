# geo_helpers.py

import math
import logging
from typing import List, Tuple, Dict, Any, Optional, Union
import psycopg2.extras
import json
import aiohttp
import asyncio
from config import GOOGLE_MAPS_API_KEY  # Google API key for reverse geocoding
from db import get_nearby_artisans

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# DISTANCE CALCULATION FUNCTIONS
# -------------------------

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.
    
    Args:
        lat1 (float): Latitude of the first point in degrees
        lon1 (float): Longitude of the first point in degrees
        lat2 (float): Latitude of the second point in degrees
        lon2 (float): Longitude of the second point in degrees
        
    Returns:
        float: Distance between the points in kilometers
    """
    # Check for missing coordinates - return large distance if data is missing
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        logger.warning("Calculating distance with missing coordinates - returning maximum distance")
        return float('inf')
        
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Earth radius in kilometers
    R = 6371.0
    
    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return distance

def format_distance(distance: float) -> str:
    """
    Format a distance value for user-friendly display.
    
    Args:
        distance (float): Distance in kilometers
        
    Returns:
        str: Formatted distance string (e.g., "750 m", "3.5 km", "12 km")
    """
    if distance == float('inf') or distance is None:
        return "Naməlum məsafə"
    
    if distance < 1:
        # Convert to meters for distances less than 1 km
        meters = int(distance * 1000)
        return f"{meters} m"
    elif distance < 10:
        # Show one decimal place for distances under 10 km
        return f"{distance:.1f} km"
    else:
        # Round to nearest kilometer for larger distances
        return f"{int(round(distance))} km"

# -------------------------
# REVERSE GEOCODING FUNCTIONS
# -------------------------

# Fallback data for Azerbaijan locations (simplified version for when API is not available)
AZERBAIJAN_REGIONS = {
    # Format: (latitude_range, longitude_range): "Location Name"
    # Central Baku
    ((40.3500, 40.4200), (49.8000, 49.9000)): "Bakı, Mərkəz",
    # Greater Baku districts
    ((40.3000, 40.5000), (49.7500, 50.0000)): "Bakı",
    # Specific Baku districts
    ((40.3700, 40.4100), (49.8300, 49.8700)): "Bakı, Nərimanov",
    ((40.3600, 40.4000), (49.8000, 49.8400)): "Bakı, Nəsimi",
    ((40.3700, 40.4000), (49.7700, 49.8200)): "Bakı, Yasamal",
    ((40.4200, 40.4600), (49.8200, 49.8700)): "Bakı, Binəqədi",
    ((40.3600, 40.4000), (49.8500, 49.9000)): "Bakı, Xətai",
    ((40.3300, 40.3800), (49.7800, 49.8300)): "Bakı, Səbail",
    ((40.4000, 40.5000), (49.9000, 50.0500)): "Bakı, Sabunçu",
    ((40.4500, 40.5500), (49.7500, 49.8500)): "Bakı, Xırdalan",
    # Other major cities
    ((40.5500, 40.7000), (49.5500, 49.7500)): "Sumqayıt",
    ((40.1500, 40.2500), (47.1500, 47.2500)): "Gəncə",
    ((39.8000, 39.8500), (47.7000, 47.8000)): "Mingəçevir",
    ((40.5800, 40.6500), (50.1000, 50.2000)): "Xızı",
    ((41.5700, 41.6200), (48.6000, 48.6500)): "Quba",
    ((38.7500, 39.0000), (48.8000, 49.0000)): "Lənkəran"
}

def fallback_get_location_name(latitude: float, longitude: float) -> Optional[str]:
    """
    Get location name based on coordinates using local data when API is unavailable.
    
    Args:
        latitude (float): Latitude in degrees
        longitude (float): Longitude in degrees
        
    Returns:
        Optional[str]: Location name or None if location cannot be determined
    """
    if latitude is None or longitude is None:
        return None
        
    # Check each region to see if the coordinates fall within it
    for (lat_range, lon_range), location_name in AZERBAIJAN_REGIONS.items():
        lat_min, lat_max = lat_range
        lon_min, lon_max = lon_range
        
        if lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max:
            return location_name
    
    # Return a default if no specific region is found but within Azerbaijan general borders
    if 38.5 <= latitude <= 42.0 and 44.5 <= longitude <= 51.0:
        return "Azərbaycan"
        
    return None

async def get_location_name(latitude: float, longitude: float) -> Optional[str]:
    """
    Get location name based on coordinates using Google Maps Reverse Geocoding API.
    If API fails, falls back to local data.
    
    Args:
        latitude (float): Latitude in degrees
        longitude (float): Longitude in degrees
        
    Returns:
        Optional[str]: Location name or None if location cannot be determined
    """
    if latitude is None or longitude is None:
        logger.warning("Cannot get location name - coordinates missing")
        return None
    
    # Try with Google Maps API if key is available
    if GOOGLE_MAPS_API_KEY:
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={GOOGLE_MAPS_API_KEY}&language=az"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['status'] == 'OK':
                            # Process results to extract the most relevant location info
                            result = data['results'][0]
                            
                            # Look for locality (city) and administrative_area_level_1 (state/province)
                            locality = None
                            admin_area = None
                            neighborhood = None
                            
                            for component in result['address_components']:
                                if 'locality' in component['types']:
                                    locality = component['long_name']
                                elif 'administrative_area_level_1' in component['types']:
                                    admin_area = component['long_name']
                                elif 'neighborhood' in component['types']:
                                    neighborhood = component['long_name']
                            
                            # Determine the best location name format
                            if locality and neighborhood:
                                return f"{locality}, {neighborhood}"
                            elif locality:
                                return locality
                            elif admin_area:
                                return admin_area
                            else:
                                return result['formatted_address'].split(',')[0]
        except Exception as e:
            logger.error(f"Error with Google Maps API: {e}")
    
    # Fall back to local data if API fails or is unavailable
    return fallback_get_location_name(latitude, longitude)

# -------------------------
# ARTISAN SEARCH FUNCTIONS
# -------------------------

def find_nearby_artisans(
    conn, 
    latitude: float, 
    longitude: float, 
    radius: float = 10.0, 
    service: str = None, 
    subservice: str = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find artisans near a specific location, with optional filtering by service type.
    
    This function uses a bounding box approach for initial DB filtering,
    then applies the more accurate Haversine formula for precise distance calculation.
    
    Args:
        conn: Database connection
        latitude (float): Customer's latitude
        longitude (float): Customer's longitude
        radius (float): Search radius in kilometers (default: 10km)
        service (str, optional): Filter by service type
        subservice (str, optional): Filter by specific subservice
        limit (int): Maximum number of results to return (default: 20)
        
    Returns:
        List[Dict[str, Any]]: List of nearby artisans with distance information
    """
    # Input validation
    if latitude is None or longitude is None:
        logger.warning("Cannot find nearby artisans - coordinates missing")
        return []
    
    try:
        # Approximate 1 degree of latitude/longitude in kilometers (varies by latitude)
        km_per_degree_lat = 111.0
        km_per_degree_lon = 111.0 * math.cos(math.radians(latitude))
        
        # Calculate the bounding box with a slightly larger area for better results
        # (We'll filter exact distances later with Haversine)
        lat_delta = (radius * 1.2) / km_per_degree_lat
        lon_delta = (radius * 1.2) / km_per_degree_lon
        
        lat_min = latitude - lat_delta
        lat_max = latitude + lat_delta
        lon_min = longitude - lon_delta
        lon_max = longitude + lon_delta
        
        # Build the SQL query with proper filtering
        query = """
            SELECT a.id, a.name, a.phone, a.service, a.location, 
                   a.latitude, a.longitude, a.rating
            FROM artisans a
            WHERE a.active = TRUE 
              AND a.latitude BETWEEN %s AND %s
              AND a.longitude BETWEEN %s AND %s
        """
        
        params = [lat_min, lat_max, lon_min, lon_max]
        
        # Add service filter if provided
        if service:
            query += " AND a.service = %s"
            params.append(service)
        
        # Add subservice filter if provided
        if subservice:
            query += """
                AND EXISTS (
                    SELECT 1 FROM artisan_price_ranges apr
                    JOIN subservices s ON apr.subservice_id = s.id
                    WHERE apr.artisan_id = a.id 
                      AND s.name = %s 
                      AND apr.is_active = TRUE
                )
            """
            params.append(subservice)
        
        # Execute the query
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
        
        # Calculate actual distances using the Haversine formula
        artisans_with_distance = []
        for row in results:
            artisan_lat = row['latitude']
            artisan_lon = row['longitude']
            
            # Skip if no location data
            if artisan_lat is None or artisan_lon is None:
                continue
            
            # Calculate precise distance
            distance = calculate_distance(latitude, longitude, artisan_lat, artisan_lon)
            
            # Only include artisans within the actual radius
            if distance <= radius:
                # Convert to regular dict and add distance
                artisan_data = dict(row)
                artisan_data['distance'] = round(distance, 2)
                artisan_data['distance_text'] = format_distance(distance)
                artisans_with_distance.append(artisan_data)
        
        # Sort by distance (ascending)
        artisans_with_distance.sort(key=lambda x: x['distance'])
        
        # Apply limit
        return artisans_with_distance[:limit]
        
    except Exception as e:
        logger.error(f"Error finding nearby artisans: {e}")
        return []

def find_available_artisans_by_service(
    conn,
    service: str,
    subservice: str = None,
    latitude: float = None, 
    longitude: float = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Find available artisans by service type, optionally sorted by distance if coordinates provided.
    
    Args:
        conn: Database connection
        service (str): Type of service required
        subservice (str, optional): Specific subservice required
        latitude (float, optional): Customer's latitude for distance calculation
        longitude (float, optional): Customer's longitude for distance calculation
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: List of matching artisans
    """
    try:
        # Build query to get artisans by service
        query = """
            SELECT a.id, a.name, a.phone, a.service, a.location, 
                   a.latitude, a.longitude, a.rating
            FROM artisans a
            WHERE a.active = TRUE AND a.service = %s
        """
        
        params = [service]
        
        # Add subservice filter if provided
        if subservice:
            query += """
                AND EXISTS (
                    SELECT 1 FROM artisan_price_ranges apr
                    JOIN subservices s ON apr.subservice_id = s.id
                    WHERE apr.artisan_id = a.id 
                      AND s.name = %s 
                      AND apr.is_active = TRUE
                )
            """
            params.append(subservice)
        
        # Execute the query
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
        
        artisans_list = []
        
        # Process results and calculate distance if coordinates provided
        for row in results:
            artisan_data = dict(row)
            
            # Calculate distance if coordinates provided
            if latitude is not None and longitude is not None:
                artisan_lat = row['latitude']
                artisan_lon = row['longitude']
                
                if artisan_lat is not None and artisan_lon is not None:
                    distance = calculate_distance(latitude, longitude, artisan_lat, artisan_lon)
                    artisan_data['distance'] = round(distance, 2)
                    artisan_data['distance_text'] = format_distance(distance)
                else:
                    artisan_data['distance'] = None
                    artisan_data['distance_text'] = "Naməlum məsafə"
            
            artisans_list.append(artisan_data)
        
        # Sort by distance if available, otherwise by rating
        if latitude is not None and longitude is not None:
            artisans_list.sort(key=lambda x: x.get('distance', float('inf')))
        else:
            artisans_list.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        return artisans_list[:limit]
        
    except Exception as e:
        logger.error(f"Error finding artisans by service: {e}")
        return []
    

