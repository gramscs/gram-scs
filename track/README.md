# Standalone Track Your Shipment package

This folder packages the public tracking UI from this project into a portable, backend-adaptable widget. Copy the whole `track/` folder into another website and wire its two API endpoints to that site's backend instead of reading Supabase directly in the browser.

## Files

- `index.html` – standalone demo page and the exact DOM hooks used by the widget.
- `track.css` – copied tracking page styling plus a few standalone page helpers.
- `track.js` – vanilla JavaScript that submits a consignment number, calls your backend API, normalizes the response, renders the same shipment summary/progress cards, and downloads POD files.
- `supabase-proxy-example.js` – optional Node/Express backend proxy pattern for projects currently reading Supabase directly from the frontend.
- `backend/flask_adapter.py` – reusable Flask blueprint factory for the same two backend endpoints.
- `backend/supabase-flask-example.py` – optional Flask/Supabase implementation sketch using server-side credentials.
- `api-contract.json` – machine-readable endpoint/payload contract for another team or backend to implement.

## Expected backend flow

The widget intentionally calls your backend, not Supabase directly:

1. User submits a consignment number in the browser.
2. Browser calls `GET /api/track/{number}`.
3. Your backend validates the number, queries Supabase or any other data source with server-side credentials, and returns JSON.
4. If POD is available, the browser calls `GET /api/track/{number}/pod` to stream/download it through your backend.

This is similar to the Flask project flow here, where `routes/track.py` renders the page and asks `services/dashboard_api.py` for data from an internal dashboard API.

## API contract

### `GET /api/track/{number}`

Return either a plain object or `{ "success": true, "data": { ... } }`.

The widget understands both snake_case and camelCase variants:

```json
{
  "success": true,
  "data": {
    "consignment_number": "ABC123",
    "status": "In Transit",
    "pickup_pincode": "110001",
    "pickup_address": "Delhi warehouse",
    "pickup_tag": "Delhi",
    "pickup_date": "2026-06-18",
    "drop_pincode": "400001",
    "drop_address": "Mumbai customer address",
    "drop_tag": "Mumbai",
    "drop_date": null,
    "eta": "2026-06-21",
    "pod_image": true
  }
}
```

Supported aliases include `consignmentNumber`, `tracking_number`, `pickupAddress`, `dropAddress`, `expectedDelivery`, `podUrl`, and `hasPod`.

### `GET /api/track/{number}/pod`

Return the POD bytes with a useful `Content-Type` and optional `Content-Disposition` header. Return `404` when no POD exists.

## Frontend configuration

Edit `window.TRACK_WIDGET_CONFIG` before loading `track.js`, or use data attributes on `.track-shell`.

```html
<script>
window.TRACK_WIDGET_CONFIG = {
  apiBase: 'https://your-domain.com',
  lookupPath: '/api/track/{number}',
  podPath: '/api/track/{number}/pod',
  homeHref: '/'
};
</script>
<script src="/track/track.js"></script>
```

If this folder is embedded inside an existing app, keep the `.track-shell` block from `index.html`, link `track.css`, and load `track.js`.

## CORS notes

Best option: serve the tracking page and `/api/track/*` from the same origin so no browser CORS configuration is needed.

If the API is on another origin, configure the backend to allow only your production website origin, allow `GET`, and expose `Content-Disposition` so POD filenames can be read by the browser.

## Supabase migration note

Do not put Supabase service-role keys or privileged table access in this frontend folder. Use `supabase-proxy-example.js` or `backend/supabase-flask-example.py` as the pattern: the browser calls your server, and your server calls Supabase.


## What to copy

Copy the entire `track/` directory. If your destination project already has a layout, you can embed just the `.track-shell` section from `index.html`, but keep `track.css`, `track.js`, and one backend adapter/API implementation.

## Backend adapter choice

- Node/Express projects: start from `supabase-proxy-example.js`.
- Flask projects: register the blueprint from `backend/flask_adapter.py` and implement the two callables, or adapt `backend/supabase-flask-example.py`.
- Other stacks: implement the endpoints exactly as described in `api-contract.json`.
