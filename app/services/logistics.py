import re
import time
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


CONSIGNMENT_NUMBER_REGEX = re.compile(r"^[A-Za-z0-9]{1,16}$")
INDIAN_PINCODE_REGEX = re.compile(r"^[1-9][0-9]{5}$")
ALLOWED_STATUSES = {
	"Pickup Scheduled",
	"In Transit",
	"Out for Delivery",
	"Delivered",
}


def normalize_consignment_number(raw_value):
	value = (raw_value or "").strip().upper()
	if not CONSIGNMENT_NUMBER_REGEX.fullmatch(value):
		raise ValueError(f"Invalid consignment number: {value or '(empty)'}")
	return value


def normalize_status(raw_value):
	value = (raw_value or "").strip()
	if value not in ALLOWED_STATUSES:
		raise ValueError("Invalid status value.")
	return value


def normalize_indian_pincode(raw_value, field_name):
	value = (raw_value or "").strip()
	if not INDIAN_PINCODE_REGEX.fullmatch(value):
		raise ValueError(f"{field_name} must be a valid 6-digit Indian pincode.")
	return value


def validate_and_round_coordinate(raw_value, field_name):
	try:
		decimal_value = Decimal(str(raw_value))
	except (InvalidOperation, TypeError, ValueError):
		raise ValueError(f"{field_name} must be a valid number.")

	exponent = decimal_value.as_tuple().exponent
	decimal_places = -exponent if exponent < 0 else 0
	if decimal_places > 5:
		raise ValueError(f"{field_name} can have at most 5 decimal places.")

	numeric = float(decimal_value)
	return round(numeric, 5)


# Route duration cache (simple in-memory cache with TTL)
_route_cache = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour

# Pincode geocode cache
_pincode_cache = {}
_PINCODE_CACHE_TTL_SECONDS = 86400  # 24 hours

TRUCK_ETA_MULTIPLIER = 1.7
TRUCK_ETA_BUFFER_HOURS = 6.0


def _get_cache_key(pickup_lat, pickup_lng, drop_lat, drop_lng):
	"""Generate a deterministic cache key for route lookup."""
	coord_string = f"{pickup_lat:.5f},{pickup_lng:.5f}|{drop_lat:.5f},{drop_lng:.5f}"
	return hashlib.md5(coord_string.encode()).hexdigest()


def _is_cache_valid(cache_entry):
	"""Check if cache entry is still valid based on TTL."""
	if not cache_entry:
		return False
	return time.time() - cache_entry["timestamp"] < _CACHE_TTL_SECONDS


def _is_pincode_cache_valid(cache_entry):
	if not cache_entry:
		return False
	return time.time() - cache_entry["timestamp"] < _PINCODE_CACHE_TTL_SECONDS


def truck_eta(osrm_time: float) -> float:
	"""Return adjusted truck ETA hours using business rule formula."""
	return (float(osrm_time) * TRUCK_ETA_MULTIPLIER) + TRUCK_ETA_BUFFER_HOURS


def geocode_indian_pincode_with_retry(
	pincode: str,
	max_retries: int = 3,
	timeout: int = 10
) -> Optional[dict]:
	"""
	Resolve an Indian pincode to latitude/longitude.

	Returns:
		Dict with lat/lng metadata, or None when lookup fails.
	"""
	if pincode in _pincode_cache and _is_pincode_cache_valid(_pincode_cache[pincode]):
		cached = _pincode_cache[pincode]
		return {
			"lat": cached["lat"],
			"lng": cached["lng"],
			"display_name": cached.get("display_name", ""),
			"source": "cache",
		}

	url = "https://nominatim.openstreetmap.org/search"
	params = {
		"postalcode": pincode,
		"country": "India",
		"countrycodes": "in",
		"format": "json",
		"limit": 1,
	}
	headers = {
		"User-Agent": "GRAM-SCS-ETA/1.0 (+logistics-geocoding)",
	}

	last_error = None
	for attempt in range(max_retries):
		try:
			response = requests.get(url, params=params, headers=headers, timeout=timeout)
			response.raise_for_status()
			data = response.json()

			if not data:
				return None

			first = data[0]
			lat = float(first["lat"])
			lng = float(first["lon"])
			display_name = first.get("display_name", "")

			_pincode_cache[pincode] = {
				"lat": lat,
				"lng": lng,
				"display_name": display_name,
				"timestamp": time.time(),
			}

			return {
				"lat": lat,
				"lng": lng,
				"display_name": display_name,
				"source": "nominatim",
			}
		except (requests.RequestException, ValueError, KeyError) as e:
			last_error = e
			logger.warning("Pincode geocoding attempt %s/%s failed for %s: %s", attempt + 1, max_retries, pincode, e)
			if attempt < max_retries - 1:
				time.sleep(1)

	logger.error("Failed to geocode pincode %s after %s attempts. Last error: %s", pincode, max_retries, last_error)
	return None


def reverse_geocode_pincode_with_retry(
	lat: float,
	lng: float,
	max_retries: int = 3,
	timeout: int = 10
) -> Optional[str]:
	"""Resolve a postal code from latitude/longitude using Nominatim reverse geocoding."""
	headers = {
		"User-Agent": "GRAM-SCS-ETA/1.0 (+logistics-geocoding)",
	}
	url = "https://nominatim.openstreetmap.org/reverse"
	params = {
		"lat": lat,
		"lon": lng,
		"format": "json",
		"addressdetails": 1,
		"zoom": 18,
	}

	last_error = None
	for attempt in range(max_retries):
		try:
			response = requests.get(url, params=params, headers=headers, timeout=timeout)
			response.raise_for_status()
			data = response.json()
			address = data.get("address", {})
			postcode = (address.get("postcode") or "").strip()

			match = re.search(r"\b[1-9][0-9]{5}\b", postcode)
			if match:
				return match.group(0)

			if INDIAN_PINCODE_REGEX.fullmatch(postcode):
				return postcode

			return None
		except (requests.RequestException, ValueError, KeyError) as e:
			last_error = e
			logger.warning("Reverse geocode attempt %s/%s failed for (%s, %s): %s", attempt + 1, max_retries, lat, lng, e)
			if attempt < max_retries - 1:
				time.sleep(1)

	logger.error("Failed reverse geocoding for (%s, %s) after %s attempts. Last error: %s", lat, lng, max_retries, last_error)
	return None


def _get_route_metrics_with_retry(
	pickup_lat: float,
	pickup_lng: float,
	drop_lat: float,
	drop_lng: float,
	max_retries: int = 3,
	timeout: int = 10
) -> Optional[dict]:
	cache_key = _get_cache_key(pickup_lat, pickup_lng, drop_lat, drop_lng)

	if cache_key in _route_cache and _is_cache_valid(_route_cache[cache_key]):
		cached = _route_cache[cache_key]
		return {
			"duration_seconds": cached["duration"],
			"distance_meters": cached.get("distance"),
			"source": "cache",
		}

	url = f"https://router.project-osrm.org/route/v1/driving/{pickup_lng},{pickup_lat};{drop_lng},{drop_lat}?overview=false"
	last_error = None

	for attempt in range(max_retries):
		try:
			response = requests.get(url, timeout=timeout)
			response.raise_for_status()
			data = response.json()

			if not data.get("routes") or len(data["routes"]) == 0:
				continue

			route = data["routes"][0]
			duration_seconds = route.get("duration")
			distance_meters = route.get("distance")

			if duration_seconds:
				_route_cache[cache_key] = {
					"duration": duration_seconds,
					"distance": distance_meters,
					"timestamp": time.time(),
				}
				logger.info("Successfully calculated route metrics via OSRM: duration=%ss distance=%sm", duration_seconds, distance_meters)
				return {
					"duration_seconds": duration_seconds,
					"distance_meters": distance_meters,
					"source": "osrm",
				}
		except (requests.RequestException, ValueError, KeyError) as e:
			last_error = e
			logger.warning("OSRM route attempt %s/%s failed: %s", attempt + 1, max_retries, e)
			if attempt < max_retries - 1:
				time.sleep(1)

	logger.error("OSRM route lookup failed after %s attempts. Last error: %s", max_retries, last_error)
	return None


def calculate_eta_breakdown_with_retry(
	pickup_lat: float,
	pickup_lng: float,
	drop_lat: float,
	drop_lng: float,
	max_retries: int = 3,
	timeout: int = 10
) -> Optional[dict]:
	"""Calculate ETA and return a transparent breakdown used for UI/debugging."""
	route_metrics = _get_route_metrics_with_retry(
		pickup_lat,
		pickup_lng,
		drop_lat,
		drop_lng,
		max_retries=max_retries,
		timeout=timeout,
	)

	if not route_metrics:
		return None

	osrm_duration_seconds = float(route_metrics["duration_seconds"])
	osrm_base_hours = osrm_duration_seconds / 3600.0
	adjusted_truck_hours = truck_eta(osrm_base_hours)
	adjusted_duration_seconds = adjusted_truck_hours * 3600.0

	calculated_at = datetime.now()
	eta_timestamp = calculated_at + timedelta(seconds=adjusted_duration_seconds)
	distance_meters = route_metrics.get("distance_meters")

	return {
		"eta": eta_timestamp.strftime("%Y-%m-%d %H:%M"),
		"duration_seconds": round(adjusted_duration_seconds, 2),
		"duration_hours": round(adjusted_truck_hours, 2),
		"osrm_base_hours": round(osrm_base_hours, 2),
		"truck_multiplier": TRUCK_ETA_MULTIPLIER,
		"truck_buffer_hours": TRUCK_ETA_BUFFER_HOURS,
		"adjusted_truck_hours": round(adjusted_truck_hours, 2),
		"distance_km": round((distance_meters or 0) / 1000.0, 2) if distance_meters is not None else None,
		"calculated_at": calculated_at.strftime("%Y-%m-%d %H:%M"),
		"route_source": route_metrics.get("source", "unknown"),
		"formula": "Adjusted_Truck_ETA = OSRM_base_time * 1.7 + 6",
	}


def calculate_eta_with_retry(
	pickup_lat: float,
	pickup_lng: float,
	drop_lat: float,
	drop_lng: float,
	max_retries: int = 3,
	timeout: int = 10
) -> Optional[str]:
	"""
	Calculate ETA for a route using OSRM API with retry logic and caching.
	
	Args:
		pickup_lat: Pickup latitude
		pickup_lng: Pickup longitude
		drop_lat: Drop latitude
		drop_lng: Drop longitude
		max_retries: Maximum number of retry attempts
		timeout: Request timeout in seconds
	
	Returns:
		Formatted ETA string (YYYY-MM-DD HH:MM) or None if calculation fails
	"""
	breakdown = calculate_eta_breakdown_with_retry(
		pickup_lat,
		pickup_lng,
		drop_lat,
		drop_lng,
		max_retries=max_retries,
		timeout=timeout,
	)
	if not breakdown:
		return None
	return breakdown["eta"]


def get_fallback_eta() -> str:
	"""Generate a fallback ETA (current timestamp) when route calculation fails."""
	return datetime.now().strftime("%Y-%m-%d %H:%M")
