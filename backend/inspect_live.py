"""Print non-sensitive coverage diagnostics for the configured OpenAQ account."""
import httpx
from app.config import get_settings
from app.catalog import CITIES

with httpx.Client(timeout=30, headers={"X-API-Key":get_settings().openaq_api_key}) as client:
    for city in [CITIES['delhi'], CITIES['mumbai']]:
        response = client.get('https://api.openaq.org/v3/locations', params={'coordinates':f'{city.latitude},{city.longitude}','radius':25000,'limit':100})
        print(city.city, response.status_code)
        for loc in response.json().get('results', []):
            print(loc['id'], loc['name'], loc.get('datetimeLast'), [(s['id'],s.get('parameter')) for s in loc.get('sensors',[])])
