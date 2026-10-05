// ==========================================================
// ROADGUARD AI
// FRONTEND CONFIGURATION
// ==========================================================
//
// Central configuration for:
// - FastAPI backend
// - YOLO detection
// - Live camera detection
// - GPS / Map
// - Hotspots
// - Three.js 3D viewer
// - COLMAP photogrammetry
//
// IMPORTANT:
// Keep API_BASE_URL empty when the frontend is served by FastAPI.
// This allows the app to work on localhost, port 8001, deployment,
// and other environments without hard-coding a port.
// ==========================================================


"use strict";


// ==========================================================
// BASE API URL
// ==========================================================
//
// When opening:
//
// http://127.0.0.1:8001/detect
//
// API_BASE_URL = ""
//
// The browser automatically uses:
//
// http://127.0.0.1:8001
//
// Do NOT put :8000 or :8001 here unless you are intentionally
// serving the frontend from a different server.
//

const API_BASE_URL = "";


// ==========================================================
// API ENDPOINTS
// ==========================================================

const API_ENDPOINTS = {

    // ------------------------------------------------------
    // BASE
    // ------------------------------------------------------

    base: API_BASE_URL,


    // ------------------------------------------------------
    // DETECTION
    // ------------------------------------------------------

    detectionUpload:
        `${API_BASE_URL}/api/detection/upload`,

    detectionProcess:
        `${API_BASE_URL}/api/detection/process`,

    detectionStatus:
        `${API_BASE_URL}/api/detection`,

    // Single detection/report
    detectionById:
        `${API_BASE_URL}/api/detection`,


    // ------------------------------------------------------
    // LIVE YOLO DETECTION
    // ------------------------------------------------------
    //
    // WebSocket endpoint used by the live camera.
    //
    // Browser automatically converts:
    //
    // http:// -> ws://
    // https:// -> wss://
    //

    liveDetection:
        `${API_BASE_URL}/api/live/detect`,


    // ------------------------------------------------------
    // REPORTS
    // ------------------------------------------------------

    reports:
        `${API_BASE_URL}/api/reports`,

    reportsSummary:
        `${API_BASE_URL}/api/reports/summary`,


    // ------------------------------------------------------
    // MAP
    // ------------------------------------------------------

    mapLocations:
        `${API_BASE_URL}/api/map/locations`,


    // ------------------------------------------------------
    // HOTSPOTS
    // ------------------------------------------------------

    hotspots:
        `${API_BASE_URL}/hotspots`,

    hotspotSummary:
        `${API_BASE_URL}/hotspots/summary`,


    // ------------------------------------------------------
    // 3D VISUALIZATION
    // ------------------------------------------------------

    threeHome:
        `${API_BASE_URL}/3d/`,

    threeScene:
        `${API_BASE_URL}/3d/scene`,

    threeLatestScene:
        `${API_BASE_URL}/3d/scene/latest`,

    threeSceneByReport:
        `${API_BASE_URL}/3d/scene`,

    threeSummary:
        `${API_BASE_URL}/3d/summary`,

    threeRoadView:
        `${API_BASE_URL}/3d/road-view`,

    threeReports:
        `${API_BASE_URL}/3d/reports-list`,


    // ------------------------------------------------------
    // PHOTOGRAMMETRY / COLMAP
    // ------------------------------------------------------
    //
    // These endpoints are for REAL reconstruction only.
    //
    // No procedural road.
    // No fake 3D.
    // No generated fallback geometry.
    //
    // Expected pipeline:
    //
    // Images
    //    ↓
    // COLMAP feature extraction
    //    ↓
    // Feature matching
    //    ↓
    // Sparse reconstruction
    //    ↓
    // Dense reconstruction
    //    ↓
    // Point cloud / mesh
    //    ↓
    // Three.js
    //


    // Check COLMAP / reconstruction engine availability
    photogrammetryEngine:
        `${API_BASE_URL}/api/photogrammetry/engine`,


    // Check reconstruction status
    photogrammetryStatus:
        `${API_BASE_URL}/api/photogrammetry/status`,


    // Get reconstruction metadata
    photogrammetryMetadata:
        `${API_BASE_URL}/api/photogrammetry/metadata`,


    // Get real reconstructed mesh / point-cloud information
    photogrammetryMesh:
        `${API_BASE_URL}/api/photogrammetry/mesh`,


    // Start real reconstruction
    photogrammetryReconstruct:
        `${API_BASE_URL}/api/photogrammetry/reconstruct`,


    // Basic photogrammetry API test
    photogrammetryTest:
        `${API_BASE_URL}/api/photogrammetry/test`


};


// ==========================================================
// WEBSOCKET HELPERS
// ==========================================================

/**
 * Convert the current page protocol into a WebSocket protocol.
 *
 * http  -> ws
 * https -> wss
 */
function getWebSocketBaseURL() {

    if (window.location.protocol === "https:") {
        return "wss:";
    }

    return "ws:";
}


/**
 * Build the live detection WebSocket URL.
 *
 * Example:
 *
 * http://127.0.0.1:8001
 *
 * becomes:
 *
 * ws://127.0.0.1:8001/api/live/detect
 */
function getLiveDetectionWebSocketURL() {

    const protocol = getWebSocketBaseURL();

    const host = window.location.host;

    return `${protocol}//${host}/api/live/detect`;
}


// ==========================================================
// REPORT-SPECIFIC URL HELPERS
// ==========================================================


/**
 * Build a report-specific 3D road-view URL.
 *
 * Example:
 *
 * getThreeRoadViewUrl(21)
 *
 * -> /3d/road-view/21
 */
function getThreeRoadViewUrl(reportId) {

    return `${API_ENDPOINTS.threeRoadView}/${encodeURIComponent(reportId)}`;

}


/**
 * Build a report-specific 3D scene URL.
 *
 * Example:
 *
 * getThreeSceneUrl(21)
 *
 * -> /3d/scene/21
 */
function getThreeSceneUrl(reportId) {

    return `${API_ENDPOINTS.threeScene}/${encodeURIComponent(reportId)}`;

}


/**
 * Build a report-specific photogrammetry status URL.
 *
 * Example:
 *
 * getPhotogrammetryStatusUrl(21)
 *
 * -> /api/photogrammetry/status/21
 */
function getPhotogrammetryStatusUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryStatus}/${encodeURIComponent(reportId)}`;

}


/**
 * Build a report-specific photogrammetry metadata URL.
 *
 * Example:
 *
 * getPhotogrammetryMetadataUrl(21)
 *
 * -> /api/photogrammetry/metadata/21
 */
function getPhotogrammetryMetadataUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryMetadata}/${encodeURIComponent(reportId)}`;

}


/**
 * Build a report-specific photogrammetry mesh URL.
 *
 * Example:
 *
 * getPhotogrammetryMeshUrl(21)
 *
 * -> /api/photogrammetry/mesh/21
 */
function getPhotogrammetryMeshUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryMesh}/${encodeURIComponent(reportId)}`;

}


/**
 * Build a report-specific reconstruction URL.
 *
 * Example:
 *
 * getPhotogrammetryReconstructUrl(21)
 *
 * -> /api/photogrammetry/reconstruct/21
 *
 * NOTE:
 * This helper is provided for compatibility.
 * The backend must actually expose this route before using it.
 */
function getPhotogrammetryReconstructUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryReconstruct}/${encodeURIComponent(reportId)}`;

}


// ==========================================================
// STATIC / REAL 3D ASSET HELPERS
// ==========================================================
//
// These helpers allow the Three.js viewer to work with real
// reconstruction files returned by the backend.
//
// The backend should provide the actual file URL.
//
// DO NOT generate fake geometry in the frontend.
//

/**
 * Convert a backend asset path into a usable URL.
 *
 * Examples:
 *
 * /results/report_21/model.ply
 *
 * or
 *
 * /frontend/assets/model.ply
 */
function getAssetURL(assetPath) {

    if (!assetPath) {
        return "";
    }

    // Already an absolute URL
    if (
        assetPath.startsWith("http://") ||
        assetPath.startsWith("https://") ||
        assetPath.startsWith("blob:")
    ) {
        return assetPath;
    }

    // Already starts with /
    if (assetPath.startsWith("/")) {
        return assetPath;
    }

    return `${API_BASE_URL}/${assetPath}`;
}


// ==========================================================
// API FETCH HELPER
// ==========================================================
//
// Centralized fetch function.
// Keeps API error handling consistent across the frontend.
//

async function apiFetch(url, options = {}) {

    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.headers || {})
        }
    });

    if (!response.ok) {

        let errorMessage =
            `API request failed: ${response.status} ${response.statusText}`;

        try {

            const errorData = await response.json();

            if (errorData?.detail) {
                errorMessage = errorData.detail;
            } else if (errorData?.error) {
                errorMessage = errorData.error;
            }

        } catch (_) {
            // Response was not JSON.
        }

        throw new Error(errorMessage);
    }

    return response;

}


// ==========================================================
// JSON API HELPER
// ==========================================================

async function apiFetchJSON(url, options = {}) {

    const response = await apiFetch(url, options);

    return await response.json();

}


// ==========================================================
// API HEALTH CHECK
// ==========================================================
//
// Useful for Dashboard / debugging.
//

async function checkAPIHealth() {

    try {

        const response = await fetch("/");

        return response.ok;

    } catch (error) {

        console.error(
            "RoadGuard API health check failed:",
            error
        );

        return false;
    }

}


// ==========================================================
// PHOTOGRAMMETRY STATUS HELPERS
// ==========================================================
//
// Expected real reconstruction states:
//
// NOT_STARTED
// FAILED
// SPARSE_ONLY
// DENSE_POINT_CLOUD
// MESH_AVAILABLE
//
// The frontend must never treat SPARSE_ONLY as a finished
// 3D mesh.
//

const PHOTOGRAMMETRY_STATUS = {

    NOT_STARTED: "NOT_STARTED",

    FAILED: "FAILED",

    SPARSE_ONLY: "SPARSE_ONLY",

    DENSE_POINT_CLOUD: "DENSE_POINT_CLOUD",

    MESH_AVAILABLE: "MESH_AVAILABLE"

};


// ==========================================================
// CHECK IF A REAL 3D MESH IS AVAILABLE
// ==========================================================

function isRealMeshAvailable(status) {

    return status === PHOTOGRAMMETRY_STATUS.MESH_AVAILABLE;

}


// ==========================================================
// CHECK IF A REAL POINT CLOUD IS AVAILABLE
// ==========================================================

function isRealPointCloudAvailable(status) {

    return (
        status === PHOTOGRAMMETRY_STATUS.DENSE_POINT_CLOUD ||
        status === PHOTOGRAMMETRY_STATUS.MESH_AVAILABLE
    );

}


// ==========================================================
// SAFE REPORT ID
// ==========================================================

function normalizeReportId(reportId) {

    if (
        reportId === null ||
        reportId === undefined ||
        reportId === ""
    ) {
        return null;
    }

    const value = Number(reportId);

    if (!Number.isFinite(value)) {
        return null;
    }

    return value;

}


// ==========================================================
// DEBUG INFORMATION
// ==========================================================
//
// Open browser console and run:
//
// RoadGuardConfigDebug()
//
// This should show the current URLs.
//

function RoadGuardConfigDebug() {

    const debugInfo = {

        API_BASE_URL,

        currentPage:
            window.location.href,

        liveDetectionWebSocket:
            getLiveDetectionWebSocketURL(),

        detectionUpload:
            API_ENDPOINTS.detectionUpload,

        reports:
            API_ENDPOINTS.reports,

        mapLocations:
            API_ENDPOINTS.mapLocations,

        hotspots:
            API_ENDPOINTS.hotspots,

        threeRoadView:
            API_ENDPOINTS.threeRoadView,

        photogrammetryEngine:
            API_ENDPOINTS.photogrammetryEngine,

        photogrammetryStatus:
            API_ENDPOINTS.photogrammetryStatus,

        photogrammetryMesh:
            API_ENDPOINTS.photogrammetryMesh

    };

    console.table(debugInfo);

    return debugInfo;

}


// ==========================================================
// OPTIONAL GLOBAL EXPORT
// ==========================================================
//
// Makes helper functions available to detect.js,
// map.js and roadguard-3d.js even if they are loaded
// in different script scopes.
//

window.API_BASE_URL = API_BASE_URL;
window.API_ENDPOINTS = API_ENDPOINTS;

window.getLiveDetectionWebSocketURL =
    getLiveDetectionWebSocketURL;

window.getThreeRoadViewUrl =
    getThreeRoadViewUrl;

window.getThreeSceneUrl =
    getThreeSceneUrl;

window.getPhotogrammetryStatusUrl =
    getPhotogrammetryStatusUrl;

window.getPhotogrammetryMetadataUrl =
    getPhotogrammetryMetadataUrl;

window.getPhotogrammetryMeshUrl =
    getPhotogrammetryMeshUrl;

window.getPhotogrammetryReconstructUrl =
    getPhotogrammetryReconstructUrl;

window.getAssetURL =
    getAssetURL;

window.apiFetch =
    apiFetch;

window.apiFetchJSON =
    apiFetchJSON;

window.checkAPIHealth =
    checkAPIHealth;

window.PHOTOGRAMMETRY_STATUS =
    PHOTOGRAMMETRY_STATUS;

window.isRealMeshAvailable =
    isRealMeshAvailable;

window.isRealPointCloudAvailable =
    isRealPointCloudAvailable;

window.normalizeReportId =
    normalizeReportId;

window.RoadGuardConfigDebug =
    RoadGuardConfigDebug;


// ==========================================================
// CONFIGURATION LOADED
// ==========================================================

console.log(
    "RoadGuard AI configuration loaded.",
    {
        apiBase: API_BASE_URL || "(current FastAPI origin)",
        liveDetection: getLiveDetectionWebSocketURL(),
        photogrammetry:
            API_ENDPOINTS.photogrammetryEngine
    }
);