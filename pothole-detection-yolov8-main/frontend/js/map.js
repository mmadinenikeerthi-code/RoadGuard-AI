/* ==========================================================
   ROADGUARD AI
   LIVE POTHOLE MAP SYSTEM

   Features:
   - OpenStreetMap
   - Live GPS tracking
   - Complete road path drawing
   - Distance calculation
   - Pothole markers
   - Backend pothole loading
   - Automatic updates
========================================================== */


/* ==========================================================
   GLOBAL VARIABLES
========================================================== */

let map = null;

let userMarker = null;

let accuracyCircle = null;

let watchId = null;

let routeCoordinates = [];

let routeLine = null;

let potholeLayer = null;

let currentLatitude = null;

let currentLongitude = null;

let totalDistance = 0;

let lastPosition = null;

let autoRefreshInterval = null;


/* ==========================================================
   API CONFIGURATION
========================================================== */


/*
   Make sure config.js defines API_BASE_URL.

   Example:

   const API_BASE_URL = "http://127.0.0.1:8000";
*/

const MAP_API_BASE =
    typeof API_BASE_URL !== "undefined"
        ? API_BASE_URL
        : "http://127.0.0.1:8000";


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


    if (!mapElement) {

        console.error(
            "Map element with id='map' was not found"
        );

        return;

    }


    /* ======================================================
       CREATE MAP
    ====================================================== */

    map = L.map("map").setView(
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
       CREATE POTHOLE LAYER
    ====================================================== */

    potholeLayer =
        L.layerGroup().addTo(map);


    /* ======================================================
       CREATE ROUTE LINE
    ====================================================== */

    routeLine = L.polyline(

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
       LOAD POTHOLES
    ====================================================== */

    loadPotholeLocations();


    /* ======================================================
       AUTO REFRESH POTHOLES
    ====================================================== */

    startAutomaticRefresh();


    /* ======================================================
       STATUS
    ====================================================== */

    updateStatus(
        "🗺️ OpenStreetMap loaded successfully"
    );


}


/* ==========================================================
   START AUTOMATIC REFRESH
========================================================== */

function startAutomaticRefresh() {


    if (autoRefreshInterval) {

        clearInterval(
            autoRefreshInterval
        );

    }


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
            "❌ Geolocation is not supported by this browser"
        );


        return;

    }


    /* ======================================================
       PREVENT MULTIPLE GPS WATCHES
    ====================================================== */

    if (watchId !== null) {

        updateStatus(
            "🟢 GPS tracking is already active"
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
        "📡 Starting live GPS tracking..."
    );


    /* ======================================================
       WATCH LOCATION
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


}


/* ==========================================================
   UPDATE LIVE LOCATION
========================================================== */

function updateLiveLocation(position) {


    const latitude =
        position.coords.latitude;


    const longitude =
        position.coords.longitude;


    const accuracy =
        position.coords.accuracy;


    currentLatitude =
        latitude;


    currentLongitude =
        longitude;


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

        Math.round(accuracy) + " m"

    );


    /* ======================================================
       UPDATE USER MARKER
    ====================================================== */

    if (!userMarker) {


        userMarker =
            L.marker(

                [latitude, longitude]

            )

                .addTo(map)

                .bindPopup(
                    "<b>📍 Current RoadGuard Location</b>"
                );


    }

    else {


        userMarker.setLatLng(
            [latitude, longitude]
        );


    }


    /* ======================================================
       ACCURACY CIRCLE
    ====================================================== */

    if (!accuracyCircle) {


        accuracyCircle =
            L.circle(

                [latitude, longitude],

                {

                    radius: accuracy,

                    weight: 1,

                    fillOpacity: 0.08

                }

            ).addTo(map);


    }

    else {


        accuracyCircle.setLatLng(
            [latitude, longitude]
        );


        accuracyCircle.setRadius(
            accuracy
        );


    }


    /* ======================================================
       ADD ROUTE POINT
    ====================================================== */

    addRoutePoint(
        latitude,
        longitude
    );


    /* ======================================================
       UPDATE MAP
    ====================================================== */

    map.setView(

        [latitude, longitude],

        17

    );


    updateStatus(
        "🟢 Live GPS tracking active"
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
        [latitude, longitude];


    /* ======================================================
       PREVENT DUPLICATE POINTS
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
           Ignore very small GPS movement/noise
        */

        if (distance < 3) {

            return;

        }


        totalDistance += distance;

    }


    /* ======================================================
       ADD NEW POINT
    ====================================================== */

    routeCoordinates.push(
        newPoint
    );


    lastPosition =
        newPoint;


    /* ======================================================
       UPDATE ROUTE LINE
    ====================================================== */

    routeLine.setLatLngs(
        routeCoordinates
    );


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


    if (distanceElement) {


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
        )

        *

        Math.cos(
            degreesToRadians(lat2)
        )

        *

        Math.sin(
            longitudeDifference / 2
        )

        *

        Math.sin(
            longitudeDifference / 2
        );


    const angle =
        2 *

        Math.atan2(

            Math.sqrt(calculation),

            Math.sqrt(1 - calculation)

        );


    return earthRadius * angle;


}


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
        "🔴 Live GPS tracking stopped"
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
            "⚠️ Start live tracking first"
        );


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


    if (routeCoordinates.length === 0) {


        updateStatus(
            "⚠️ No route has been recorded yet"
        );


        return;

    }


    map.fitBounds(

        routeLine.getBounds(),

        {

            padding: [50, 50]

        }

    );


}


/* ==========================================================
   LOAD POTHOLE LOCATIONS
========================================================== */

async function loadPotholeLocations() {


    try {


        console.log(
            "Loading pothole locations..."
        );


        const response =
            await fetch(

                `${MAP_API_BASE}/api/map/locations`

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
           CLEAR OLD MARKERS
        ================================================== */

        potholeLayer.clearLayers();


        /* ==================================================
           NORMALIZE RESPONSE
        ================================================== */

        const locations =

            Array.isArray(data)

                ? data

                :

                (

                    data.locations ||

                    data.data ||

                    []

                );


        let validLocations =
            0;


        /* ==================================================
           ADD POTHOLE MARKERS
        ================================================== */

        locations.forEach(

            location => {


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


                if (

                    !Number.isFinite(latitude) ||

                    !Number.isFinite(longitude)

                ) {


                    console.warn(
                        "Invalid location:",
                        location
                    );


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


                /* ==========================================
                   GET MARKER STYLE
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
                            ⚠️ Pothole Detected
                        </h3>

                        <p>
                            <b>Severity:</b>
                            ${severity}
                        </p>

                        <p>
                            <b>Confidence:</b>
                            ${confidence}
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


                marker.addTo(
                    potholeLayer
                );


            }

        );


        updateText(

            "potholeCount",

            validLocations

        );


        console.log(

            `${validLocations} pothole locations loaded`

        );


    }


    catch (error) {


        console.error(
            "Map loading error:",
            error
        );


        updateStatus(
            "⚠️ Unable to load pothole locations"
        );


    }


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


    let style = {


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
        "❌ Unable to access location";


    switch (
        error.code
    ) {


        case error.PERMISSION_DENIED:


            message =
                "❌ Location permission denied";


            break;


        case error.POSITION_UNAVAILABLE:


            message =
                "❌ Location information unavailable";


            break;


        case error.TIMEOUT:


            message =
                "❌ Location request timed out";


            break;


    }


    updateStatus(
        message
    );


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
   CLEANUP
========================================================== */

window.addEventListener(

    "beforeunload",

    () => {


        if (watchId !== null) {


            navigator.geolocation.clearWatch(
                watchId
            );


        }


        if (autoRefreshInterval) {


            clearInterval(
                autoRefreshInterval
            );


        }


    }

);