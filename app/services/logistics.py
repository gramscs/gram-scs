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


def _get_cache_key(pickup_lat, pickup_lng, drop_lat, drop_lng):
	"""Generate a deterministic cache key for route lookup."""
	coord_string = f"{pickup_lat:.5f},{pickup_lng:.5f}|{drop_lat:.5f},{drop_lng:.5f}"
	return hashlib.md5(coord_string.encode()).hexdigest()


def _is_cache_valid(cache_entry):
	"""Check if cache entry is still valid based on TTL."""
	if not cache_entry:
		return False
	return time.time() - cache_entry["timestamp"] < _CACHE_TTL_SECONDS


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
	cache_key = _get_cache_key(pickup_lat, pickup_lng, drop_lat, drop_lng)
	
	# Check cache first
	if cache_key in _route_cache and _is_cache_valid(_route_cache[cache_key]):
		logger.debug(f"Using cached route duration for {cache_key}")
		duration_seconds = _route_cache[cache_key]["duration"]
	else:
		# Fetch from OSRM with retry logic
		url = f"https://router.project-osrm.org/route/v1/driving/{pickup_lng},{pickup_lat};{drop_lng},{drop_lat}?overview=false"
		
		duration_seconds = None
		last_error = None
		
		for attempt in range(max_retries):
			try:
				response = requests.get(url, timeout=timeout)
				response.raise_for_status()
				data = response.json()
				
				if data.get("routes") and len(data["routes"]) > 0:
					duration_seconds = data["routes"][0].get("duration")
					if duration_seconds:
						# Cache the result
						_route_cache[cache_key] = {
							"duration": duration_seconds,
							"timestamp": time.time()
						}
						logger.info(f"Successfully calculated route duration: {duration_seconds}s")
						break
			except (requests.RequestException, ValueError, KeyError) as e:
				last_error = e
				logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
				if attempt < max_retries - 1:
					time.sleep(1)  # Brief pause before retry
				continue
		
		if duration_seconds is None:
			# All retries failed, return None to trigger fallback
			logger.error(f"Failed to calculate ETA after {max_retries} attempts. Last error: {last_error}")
			return None
	
	# Calculate ETA from current time + duration
	eta_timestamp = datetime.now() + timedelta(seconds=duration_seconds)
	return eta_timestamp.strftime("%Y-%m-%d %H:%M")


def get_fallback_eta() -> str:
	"""Generate a fallback ETA (current timestamp) when route calculation fails."""
	return datetime.now().strftime("%Y-%m-%d %H:%M")
