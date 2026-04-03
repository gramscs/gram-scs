document.addEventListener("DOMContentLoaded", function () {
    var mapElement = document.getElementById("map");

    // Exit when the tracking result/map is not present on the page.
    if (!mapElement) {
        return;
    }

    // Leaflet must be loaded globally by the base layout.
    if (typeof L === "undefined") {
        console.error("Leaflet is not loaded. Unable to render tracking map.");
        return;
    }

    var pickupLat = parseFloat(mapElement.dataset.pickupLat);
    var pickupLng = parseFloat(mapElement.dataset.pickupLng);
    var dropLat = parseFloat(mapElement.dataset.dropLat);
    var dropLng = parseFloat(mapElement.dataset.dropLng);

    if (
        Number.isNaN(pickupLat) ||
        Number.isNaN(pickupLng) ||
        Number.isNaN(dropLat) ||
        Number.isNaN(dropLng)
    ) {
        console.error("Invalid coordinates found in tracking map data attributes.");
        return;
    }

    var pickup = [pickupLat, pickupLng];
    var drop = [dropLat, dropLng];

    var map = L.map("map").setView(pickup, 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    L.marker(pickup).addTo(map).bindPopup("Pickup Location").openPopup();
    L.marker(drop).addTo(map).bindPopup("Drop Location");

    var routeLine = L.polyline([pickup, drop], { color: "red" }).addTo(map);
    map.fitBounds(routeLine.getBounds());
});
