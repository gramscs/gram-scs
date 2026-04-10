# Tracking Module

This repository now treats shipment tracking as a dedicated module behind the public `/track` URL.

## What The Module Does

- Accepts a consignment number from the user.
- Looks up the shipment record.
- Refreshes pickup and drop pincodes and coordinates when available.
- Recomputes ETA using the logistics helper service.
- Shows shipment status, route overview, and delivery progress to the visitor.

## Code Layout

- [app/track/routes.py](app/track/routes.py) contains the `/track` blueprint and request flow.
- [app/track/templates/track/track.html](app/track/templates/track/track.html) contains the tracking UI.
- [app/services/logistics.py](app/services/logistics.py) contains geocoding and ETA calculations.

## Logging Strategy

The track module logs:

- empty or invalid consignment submissions
- shipment lookups that return no result
- database failures while resolving shipments
- successful refreshes after ETA recalculation

## Test Coverage

- Backend route tests live in [tests/test_track_routes.py](tests/test_track_routes.py).
- UI smoke coverage still checks the public `/track` page in [tests/ui/smoke.spec.js](tests/ui/smoke.spec.js).

## Current Boundary

The module now has its own ORM boundary in [app/track/models.py](app/track/models.py).
It still maps to the same physical database table for now, which keeps the current site stable while making it easier to move tracking into a separate database later.

## Run The Tests

```bash
python -m unittest tests.test_track_routes
```