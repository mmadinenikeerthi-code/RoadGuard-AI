/* ==========================================================
   ROADGUARD AI
   LIVE POTHOLE MAP SYSTEM

   REAL DATA ONLY
   ----------------------------------------------------------
   Features:
   - OpenStreetMap
   - Browser GPS
   - Live GPS tracking
   - Complete road path drawing
   - Distance calculation
   - Current GPS marker
   - GPS accuracy circle
   - Backend pothole loading
   - Live YOLO pothole markers
   - Automatic backend refresh
   - Shared GPS state for detect.js
   - No fake coordinates
   - No hard-coded port
========================================================== */

"use strict";


/* ==========================================================
   GLOBAL VARIABLES
========================================================== */

let map = null;

let userMarker = null;

let accuracyCircle = null;

let livePotholeMarker = null;

let watchId = null;

let routeCoordinates = [];

let routeLine = null;

let potholeLayer = null;

let currentLatitude = null;

let currentLongitude = null;

let currentAccuracy = null;

let totalDistance = 0;

let lastPosition = null;

let autoRefreshInterval = null;

let mapInitialized = false;


/* ==========================================================
   API CONFIGURATION
========================================================== */

/*
   config.js is loaded before map.js.

   API_BASE_URL should remain:

       ""

   because FastAPI serves the frontend itself.

   Example:

       http://127.0.0.1:8001

   automatically becomes:

       /api/map/locations

   There must NOT be a fallback to port 8000.
*/

const MAP_API_BASE =
    typeof API_BASE_URL !== "undefined"
        ? API_BASE_URL
        : "";


/* ==========================================================
   INITIALIZE MAP
========================================================== */

document.addEventListener(
    "DOMContentLoaded",
    initializeMap
);


function initializeMap() {

    /* ======================================================
       CHECK MAP ELEMENT
    ====================================================== */

    const mapElement =
        document.getElementById("map");


    /*
       map.js is shared by multiple pages.

       If the current page does not contain a map,
       simply do nothing.

       This prevents detect.html from producing an error
       when map.js is loaded there.
    */

    if (!mapElement) {

        console.log(
            "RoadGuard Map: no #map element on this page."
        );

        return;
    }


    /* ======================================================
       PREVENT DOUBLE INITIALIZATION
    ====================================================== */

    if (mapInitialized) {

        return;
    }


    /* ======================================================
       CHECK LEAFLET
    ====================================================== */

    if (typeof L === "undefined") {

        console.error(
            "RoadGuard Map: Leaflet is not loaded."
        );

        return;
    }


    /* ======================================================
       CREATE MAP
    ====================================================== */

    map = L.map(
        "map",
        {
            zoomControl: true
        }
    ).setView(
        [20.5937, 78.9629],
        5
    );


    /* ======================================================
       OPENSTREETMAP TILE LAYER
    ====================================================== */

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                "&copy; OpenStreetMap contributors"
        }
    ).addTo(map);


    /* ======================================================
       CREATE BACKEND POTHOLE LAYER
    ====================================================== */

    potholeLayer =
        L.layerGroup().addTo(map);


    /* ======================================================
       CREATE ROUTE LINE
    ====================================================== */

    routeLine =
        L.polyline(
            [],
            {
                weight: 6,
                opacity: 0.9,
                smoothFactor: 1
            }
        ).addTo(map);


    /* ======================================================
       BUTTON EVENTS
    ====================================================== */

    const startButton =
        document.getElementById(
            "startTrackingBtn"
        );


    if (startButton) {

        startButton.addEventListener(
            "click",
            startLiveTracking
        );

    }


    const stopButton =
        document.getElementById(
            "stopTrackingBtn"
        );


    if (stopButton) {

        stopButton.addEventListener(
            "click",
            stopLiveTracking
        );

        stopButton.disabled = true;

    }


    const loadButton =
        document.getElementById(
            "loadLocationsBtn"
        );


    if (loadButton) {

        loadButton.addEventListener(
            "click",
            loadPotholeLocations
        );

    }


    const centerButton =
        document.getElementById(
            "centerMapBtn"
        );


    if (centerButton) {

        centerButton.addEventListener(
            "click",
            centerOnUser
        );

    }


    /* ======================================================
       LOAD EXISTING POTHOLES
    ====================================================== */

    loadPotholeLocations();


    /* ======================================================
       AUTOMATIC REFRESH
    ====================================================== */

    startAutomaticRefresh();


    /* ======================================================
       STATUS
    ====================================================== */

    updateStatus(
        "OpenStreetMap loaded successfully"
    );


    mapInitialized = true;


    console.log(
        "RoadGuard Map initialized."
    );
}


/* ==========================================================
   START AUTOMATIC BACKEND REFRESH
========================================================== */

function startAutomaticRefresh() {

    if (autoRefreshInterval) {

        clearInterval(
            autoRefreshInterval
        );

    }


    /*
       Refresh backend pothole locations every 10 seconds.

       This means newly saved detections can appear on
       the map without manually refreshing the page.
    */

    autoRefreshInterval =
        setInterval(
            loadPotholeLocations,
            10000
        );
}


/* ==========================================================
   START LIVE GPS TRACKING
========================================================== */

function startLiveTracking() {

    if (!navigator.geolocation) {

        updateStatus(
            "Browser GPS is not available"
        );

        return;
    }


    /* ======================================================
       PREVENT MULTIPLE GPS WATCHES
    ====================================================== */

    if (watchId !== null) {

        updateStatus(
            "GPS tracking is already active"
        );

        return;
    }


    /* ======================================================
       BUTTON STATE
    ====================================================== */

    const startButton =
        document.getElementById(
            "startTrackingBtn"
        );


    const stopButton =
        document.getElementById(
            "stopTrackingBtn"
        );


    if (startButton) {

        startButton.disabled = true;

    }


    if (stopButton) {

        stopButton.disabled = false;

    }


    updateStatus(
        "Starting live GPS tracking..."
    );


    /* ======================================================
       WATCH REAL BROWSER GPS
    ====================================================== */

    watchId =
        navigator.geolocation.watchPosition(

            updateLiveLocation,

            handleLocationError,

            {
                enableHighAccuracy: true,

                maximumAge: 1000,

                timeout: 15000
            }
        );


    /*
       Make the latest GPS available to detect.js.

       detect.js can read:

       window.latestGPS.latitude
       window.latestGPS.longitude
       window.latestGPS.accuracy
    */

    window.gpsTrackingActive = true;
}


/* ==========================================================
   UPDATE LIVE LOCATION
========================================================== */

function updateLiveLocation(position) {

    if (!position || !position.coords) {

        updateStatus(
            "Location unavailable"
        );

        return;
    }


    const latitude =
        Number(
            position.coords.latitude
        );


    const longitude =
        Number(
            position.coords.longitude
        );


    const accuracy =
        Number(
            position.coords.accuracy
        );


    /* ======================================================
       VALIDATE GPS
    ====================================================== */

    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        (latitude === 0 && longitude === 0) ||
        latitude < -90 ||
        latitude > 90 ||
        longitude < -180 ||
        longitude > 180
    ) {

        updateStatus(
            "Invalid GPS location received"
        );

        return;
    }


    /* ======================================================
       SAVE CURRENT GPS
    ====================================================== */

    currentLatitude =
        latitude;


    currentLongitude =
        longitude;


    currentAccuracy =
        Number.isFinite(accuracy)
            ? accuracy
            : null;


    /* ======================================================
       SHARED GPS STATE
    ====================================================== */

    window.latestGPS = {

        latitude:
            currentLatitude,

        longitude:
            currentLongitude,

        accuracy:
            currentAccuracy,

        timestamp:
            Date.now()
    };


    window.dispatchEvent(
        new CustomEvent(
            "roadguard:gps-update",
            {
                detail:
                    window.latestGPS
            }
        )
    );


    /* ======================================================
       UPDATE UI
    ====================================================== */

    updateText(
        "latitude",
        latitude.toFixed(6)
    );


    updateText(
        "longitude",
        longitude.toFixed(6)
    );


    updateText(
        "accuracy",
        Number.isFinite(accuracy)
            ? Math.round(accuracy) + " m"
            : "N/A"
    );


    /* ======================================================
       UPDATE USER MARKER
    ====================================================== */

    if (!userMarker) {

        userMarker =
            L.marker(
                [
                    latitude,
                    longitude
                ]
            )
                .addTo(map)
                .bindPopup(
                    "<b>Current RoadGuard Location</b>"
                );

    }

    else {

        userMarker.setLatLng(
            [
                latitude,
                longitude
            ]
        );

    }


    /* ======================================================
       UPDATE GPS ACCURACY CIRCLE
    ====================================================== */

    if (Number.isFinite(accuracy)) {

        if (!accuracyCircle) {

            accuracyCircle =
                L.circle(
                    [
                        latitude,
                        longitude
                    ],
                    {
                        radius:
                            accuracy,

                        weight:
                            1,

                        fillOpacity:
                            0.08
                    }
                ).addTo(map);

        }

        else {

            accuracyCircle.setLatLng(
                [
                    latitude,
                    longitude
                ]
            );

            accuracyCircle.setRadius(
                accuracy
            );

        }

    }


    /* ======================================================
       ADD ROUTE POINT
    ====================================================== */

    addRoutePoint(
        latitude,
        longitude
    );


    /* ======================================================
       CENTER MAP
    ====================================================== */

    if (map) {

        map.setView(
            [
                latitude,
                longitude
            ],
            17
        );

    }


    updateStatus(
        "Live GPS tracking active"
    );
}


/* ==========================================================
   ADD ROUTE POINT
========================================================== */

function addRoutePoint(
    latitude,
    longitude
) {

    const newPoint =
        [
            latitude,
            longitude
        ];


    /* ======================================================
       PREVENT DUPLICATE / GPS NOISE
    ====================================================== */

    if (routeCoordinates.length > 0) {

        const previousPoint =
            routeCoordinates[
            routeCoordinates.length - 1
            ];


        const distance =
            calculateDistance(
                previousPoint[0],
                previousPoint[1],
                latitude,
                longitude
            );


        /*
           Ignore GPS movement smaller than 3 metres.

           This prevents tiny GPS fluctuations from
           creating thousands of route points.
        */

        if (distance < 3) {

            return;
        }


        totalDistance +=
            distance;
    }


    /* ======================================================
       ADD POINT
    ====================================================== */

    routeCoordinates.push(
        newPoint
    );


    lastPosition =
        newPoint;


    /* ======================================================
       UPDATE ROUTE LINE
    ====================================================== */

    if (routeLine) {

        routeLine.setLatLngs(
            routeCoordinates
        );

    }


    /* ======================================================
       UPDATE ROUTE COUNTER
    ====================================================== */

    updateText(
        "routePoints",
        routeCoordinates.length
    );


    /* ======================================================
       UPDATE DISTANCE
    ====================================================== */

    const distanceElement =
        document.getElementById(
            "distance"
        );


    if (!distanceElement) {

        return;
    }


    if (totalDistance >= 1000) {

        distanceElement.textContent =
            (
                totalDistance / 1000
            ).toFixed(2)
            + " km";

    }

    else {

        distanceElement.textContent =
            Math.round(totalDistance)
            + " m";

    }
}


/* ==========================================================
   CALCULATE DISTANCE
========================================================== */

function calculateDistance(
    lat1,
    lon1,
    lat2,
    lon2
) {

    const earthRadius =
        6371000;


    const latitudeDifference =
        degreesToRadians(
            lat2 - lat1
        );


    const longitudeDifference =
        degreesToRadians(
            lon2 - lon1
        );


    const calculation =
        Math.sin(
            latitudeDifference / 2
        ) *
        Math.sin(
            latitudeDifference / 2
        )
        +
        Math.cos(
            degreesToRadians(lat1)
        ) *
        Math.cos(
            degreesToRadians(lat2)
        ) *
        Math.sin(
            longitudeDifference / 2
        ) *
        Math.sin(
            longitudeDifference / 2
        );


    const safeCalculation =
        Math.min(
            1,
            Math.max(
                0,
                calculation
            )
        );


    const angle =
        2 *
        Math.atan2(
            Math.sqrt(
                safeCalculation
            ),
            Math.sqrt(
                1 - safeCalculation
            )
        );


    return earthRadius * angle;
}


/* ==========================================================
   DEGREES TO RADIANS
========================================================== */

function degreesToRadians(
    degrees
) {

    return degrees *
        (
            Math.PI / 180
        );
}


/* ==========================================================
   STOP LIVE TRACKING
========================================================== */

function stopLiveTracking() {

    if (watchId !== null) {

        navigator.geolocation.clearWatch(
            watchId
        );

        watchId = null;
    }


    window.gpsTrackingActive =
        false;


    const startButton =
        document.getElementById(
            "startTrackingBtn"
        );


    const stopButton =
        document.getElementById(
            "stopTrackingBtn"
        );


    if (startButton) {

        startButton.disabled = false;

    }


    if (stopButton) {

        stopButton.disabled = true;

    }


    updateStatus(
        "Live GPS tracking stopped"
    );
}


/* ==========================================================
   CENTER MAP ON USER
========================================================== */

function centerOnUser() {

    if (
        currentLatitude === null ||
        currentLongitude === null
    ) {

        updateStatus(
            "Location unavailable"
        );

        return;
    }


    if (!map) {

        return;
    }


    map.setView(
        [
            currentLatitude,
            currentLongitude
        ],
        17
    );
}


/* ==========================================================
   SHOW COMPLETE ROUTE
========================================================== */

function showCompleteRoute() {

    if (
        !routeCoordinates.length ||
        !routeLine
    ) {

        updateStatus(
            "No route has been recorded yet"
        );

        return;
    }


    const bounds =
        routeLine.getBounds();


    if (bounds.isValid()) {

        map.fitBounds(
            bounds,
            {
                padding: [
                    50,
                    50
                ]
            }
        );

    }
}


/* ==========================================================
   LOAD POTHOLE LOCATIONS FROM BACKEND
========================================================== */

async function loadPotholeLocations() {

    if (!map || !potholeLayer) {

        return;
    }


    try {

        console.log(
            "Loading pothole locations..."
        );


        const response =
            await fetch(
                `${MAP_API_BASE}/api/map/locations`,
                {
                    method: "GET",

                    headers: {
                        "Accept":
                            "application/json"
                    },

                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        console.log(
            "Pothole Map Response:",
            data
        );


        /* ==================================================
           CLEAR OLD BACKEND MARKERS
        ================================================== */

        potholeLayer.clearLayers();


        /* ==================================================
           NORMALIZE BACKEND RESPONSE
        ================================================== */

        const locations =
            Array.isArray(data)
                ? data
                : (
                    data.locations ||
                    data.data ||
                    []
                );


        let validLocations = 0;


        /* ==================================================
           ADD BACKEND POTHOLE MARKERS
        ================================================== */

        locations.forEach(
            location => {

                if (!location) {

                    return;
                }


                const latitude =
                    Number(
                        location.latitude ??
                        location.lat
                    );


                const longitude =
                    Number(
                        location.longitude ??
                        location.lng ??
                        location.lon
                    );


                /* ==========================================
                   VALIDATE COORDINATES
                ========================================== */

                if (
                    !Number.isFinite(latitude) ||
                    !Number.isFinite(longitude) ||
                    (latitude === 0 && longitude === 0) ||
                    latitude < -90 ||
                    latitude > 90 ||
                    longitude < -180 ||
                    longitude > 180
                ) {

                    return;
                }


                validLocations++;


                const severity =
                    location.severity ||
                    "Unknown";


                const confidence =
                    location.confidence ??
                    location.score ??
                    "N/A";


                const locationName =
                    location.location_name ||
                    location.locationName ||
                    "Unknown Location";


                const reportId =
                    location.id ??
                    location.report_id ??
                    location.reportId ??
                    null;


                /* ==========================================
                   MARKER STYLE
                ========================================== */

                const markerStyle =
                    getSeverityStyle(
                        severity
                    );


                /* ==========================================
                   CREATE MARKER
                ========================================== */

                const marker =
                    L.circleMarker(
                        [
                            latitude,
                            longitude
                        ],
                        markerStyle
                    );


                /* ==========================================
                   POPUP
                ========================================== */

                marker.bindPopup(
                    `
                    <div class="map-popup">

                        <h3>
                            Pothole Detected
                        </h3>

                        <p>
                            <b>Severity:</b>
                            ${escapeHTML(severity)}
                        </p>

                        <p>
                            <b>Confidence:</b>
                            ${escapeHTML(confidence)}
                        </p>

                        <p>
                            <b>Location:</b>
                            ${escapeHTML(locationName)}
                        </p>

                        <p>
                            <b>Latitude:</b>
                            ${latitude.toFixed(6)}
                        </p>

                        <p>
                            <b>Longitude:</b>
                            ${longitude.toFixed(6)}
                        </p>

                        ${reportId !== null
                        ? `
                                <p>
                                    <b>Report ID:</b>
                                    ${escapeHTML(reportId)}
                                </p>
                                `
                        : ""
                    }

                    </div>
                    `
                );


                marker.addTo(
                    potholeLayer
                );

            }
        );


        /* ==================================================
           UPDATE COUNT
        ================================================== */

        updateText(
            "potholeCount",
            validLocations
        );


        console.log(
            `${validLocations} pothole locations loaded`
        );


        updateStatus(
            `${validLocations} pothole location(s) loaded`
        );

    }


    catch (error) {

        console.error(
            "Map loading error:",
            error
        );


        updateStatus(
            "Unable to load pothole locations"
        );
    }
}


/* ==========================================================
   LIVE POTHOLE MARKER
   CALLED BY LIVE YOLO DETECTION

   Expected result:

   {
       success: true,

       pothole_count: 1,

       detections: [...],

       location: {
           valid: true,
           latitude: ...,
           longitude: ...,
           accuracy: ...
       }
   }
========================================================== */

function updateLiveMap(result) {

    /* ======================================================
       VALIDATE RESULT
    ====================================================== */

    if (
        !result ||
        result.success !== true
    ) {

        return;
    }


    /* ======================================================
       READ GPS
    ====================================================== */

    const location =
        result.location;


    if (
        !location ||
        location.valid !== true ||
        location.latitude == null ||
        location.longitude == null
    ) {

        return;
    }


    /* ======================================================
       VALIDATE COORDINATES
    ====================================================== */

    const latitude =
        Number(
            location.latitude
        );


    const longitude =
        Number(
            location.longitude
        );


    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        (latitude === 0 && longitude === 0) ||
        latitude < -90 ||
        latitude > 90 ||
        longitude < -180 ||
        longitude > 180
    ) {

        return;
    }


    /* ======================================================
       CHECK POTHOLE COUNT
    ====================================================== */

    const potholeCount =
        Number(
            result.pothole_count
        );


    if (
        !Number.isFinite(potholeCount) ||
        potholeCount <= 0
    ) {

        /*
           No pothole in this frame.
           Do not create a map marker.
        */

        return;
    }


    /* ======================================================
       CONFIDENCE
    ====================================================== */

    const confidence =
        result.confidence ??
        result.average_confidence ??
        "N/A";


    /* ======================================================
       GPS ACCURACY
    ====================================================== */

    const accuracy =
        location.accuracy;


    /* ======================================================
       CREATE OR UPDATE LIVE MARKER
    ====================================================== */

    if (!livePotholeMarker) {

        livePotholeMarker =
            L.circleMarker(
                [
                    latitude,
                    longitude
                ],
                {
                    radius: 8,

                    weight: 2,

                    opacity: 1,

                    fillOpacity: 0.85,

                    color: "#dc2626",

                    fillColor: "#ef4444"
                }
            ).addTo(map);

    }

    else {

        livePotholeMarker.setLatLng(
            [
                latitude,
                longitude
            ]
        );

    }


    /* ======================================================
       LIVE POPUP
    ====================================================== */

    livePotholeMarker.bindPopup(
        `
        <div class="map-popup">

            <h3>
                Live Pothole Detection
            </h3>

            <p>
                <b>Potholes:</b>
                ${potholeCount}
            </p>

            <p>
                <b>Confidence:</b>
                ${escapeHTML(confidence)}
            </p>

            <p>
                <b>GPS Accuracy:</b>
                ${accuracy != null &&
            Number.isFinite(
                Number(accuracy)
            )
            ? Number(accuracy).toFixed(1) + " m"
            : "N/A"
        }
            </p>

            <p>
                <b>Latitude:</b>
                ${latitude.toFixed(6)}
            </p>

            <p>
                <b>Longitude:</b>
                ${longitude.toFixed(6)}
            </p>

        </div>
        `
    );


    /* ======================================================
       CENTER ON LIVE DETECTION
    ====================================================== */

    if (map) {

        map.setView(
            [
                latitude,
                longitude
            ],
            17
        );

    }


    /* ======================================================
       UPDATE STATUS
    ====================================================== */

    updateStatus(
        `Live detection: ${potholeCount} pothole(s) detected`
    );


    /*
       IMPORTANT:

       Do NOT increment the backend pothole count here.

       The same video frame can be processed repeatedly.
       Incrementing the counter on every frame would create
       an incorrect number.

       The authoritative count comes from the backend after
       the detection/report is saved.
    */
}


/* ==========================================================
   REMOVE LIVE POTHOLE MARKER
========================================================== */

function clearLivePotholeMarker() {

    if (
        livePotholeMarker &&
        map
    ) {

        map.removeLayer(
            livePotholeMarker
        );

    }


    livePotholeMarker =
        null;
}


/* ==========================================================
   GET MARKER STYLE BY SEVERITY
========================================================== */

function getSeverityStyle(
    severity
) {

    const level =
        String(severity)
            .toLowerCase();


    const style = {

        radius: 10,

        weight: 2,

        opacity: 1,

        fillOpacity: 0.8

    };


    if (
        level.includes("critical")
    ) {

        style.color =
            "#991b1b";

        style.fillColor =
            "#dc2626";

    }

    else if (
        level.includes("high")
    ) {

        style.color =
            "#c2410c";

        style.fillColor =
            "#f97316";

    }

    else if (
        level.includes("moderate") ||
        level.includes("medium")
    ) {

        style.color =
            "#a16207";

        style.fillColor =
            "#f59e0b";

    }

    else {

        style.color =
            "#15803d";

        style.fillColor =
            "#22c55e";
    }


    return style;
}


/* ==========================================================
   LOCATION ERROR
========================================================== */

function handleLocationError(
    error
) {

    console.error(
        "GPS Error:",
        error
    );


    let message =
        "Location unavailable";


    if (error) {

        if (error.code === 1) {

            message =
                "Location permission denied";

        }

        else if (error.code === 2) {

            message =
                "Unable to determine location";

        }

        else if (error.code === 3) {

            message =
                "Location request timed out";
        }

    }


    updateStatus(
        message
    );


    /*
       Keep the GPS state explicit.
    */

    window.gpsTrackingActive =
        false;
}


/* ==========================================================
   UPDATE TEXT SAFELY
========================================================== */

function updateText(
    elementId,
    value
) {

    const element =
        document.getElementById(
            elementId
        );


    if (element) {

        element.textContent =
            value;

    }
}


/* ==========================================================
   STATUS UPDATE
========================================================== */

function updateStatus(
    message
) {

    const status =
        document.getElementById(
            "mapStatus"
        );


    if (status) {

        status.textContent =
            message;

    }
}


/* ==========================================================
   ESCAPE HTML
   Prevent backend text from being interpreted as HTML.
========================================================== */

function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "";
    }


    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}


/* ==========================================================
   PUBLIC GPS HELPERS
========================================================== */

/*
   Other frontend modules can call:

       getCurrentGPS()

   and receive the latest real browser GPS.
*/

function getCurrentGPS() {

    if (
        currentLatitude === null ||
        currentLongitude === null
    ) {

        return null;
    }


    return {

        latitude:
            currentLatitude,

        longitude:
            currentLongitude,

        accuracy:
            currentAccuracy,

        timestamp:
            Date.now()
    };
}


/* ==========================================================
   RESET ROUTE
========================================================== */

function resetRoute() {

    routeCoordinates = [];

    totalDistance = 0;

    lastPosition = null;


    if (routeLine) {

        routeLine.setLatLngs([]);

    }


    updateText(
        "routePoints",
        "0"
    );


    updateText(
        "distance",
        "0 m"
    );


    updateStatus(
        "Route cleared"
    );
}


/* ==========================================================
   CLEANUP
========================================================== */

window.addEventListener(
    "beforeunload",
    () => {

        if (watchId !== null) {

            navigator.geolocation.clearWatch(
                watchId
            );

            watchId = null;
        }


        if (autoRefreshInterval) {

            clearInterval(
                autoRefreshInterval
            );

            autoRefreshInterval = null;
        }


        window.gpsTrackingActive =
            false;
    }
);


/* ==========================================================
   GLOBAL EXPORTS
========================================================== */

window.initializeMap =
    initializeMap;

window.startLiveTracking =
    startLiveTracking;

window.stopLiveTracking =
    stopLiveTracking;

window.updateLiveLocation =
    updateLiveLocation;

window.centerOnUser =
    centerOnUser;

window.showCompleteRoute =
    showCompleteRoute;

window.loadPotholeLocations =
    loadPotholeLocations;

window.updateLiveMap =
    updateLiveMap;

window.clearLivePotholeMarker =
    clearLivePotholeMarker;

window.getCurrentGPS =
    getCurrentGPS;

window.resetRoute =
    resetRoute;

window.calculateDistance =
    calculateDistance;

window.getSeverityStyle =
    getSeverityStyle;


/* ==========================================================
   INITIAL STATE
========================================================== */

window.latestGPS =
    null;

window.gpsTrackingActive =
    false;


console.log(
    "RoadGuard AI map.js loaded successfully."
);