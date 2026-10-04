// ==========================================================
// ROADGUARD AI
// FRONTEND CONFIGURATION
// ==========================================================

// The FastAPI app serves this frontend, so relative URLs work
// in local development, Replit Preview, and deployment.
const API_BASE_URL = "";


// ==========================================================
// API ENDPOINTS
// ==========================================================

const API_ENDPOINTS = {

    // ------------------------------------------------------
    // BASE
    // ------------------------------------------------------

    // Used by modules that build their own URLs.
    // Example:
    // `${API_ENDPOINTS.base}/3d/scene`

    base:
        API_BASE_URL,


    // ------------------------------------------------------
    // DETECTION
    // ------------------------------------------------------

    detectionUpload:
        `${API_BASE_URL}/api/detection/upload`,

    detectionProcess:
        `${API_BASE_URL}/api/detection/process`,

    detectionStatus:
        `${API_BASE_URL}/api/detection`,


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
    // PHOTOGRAMMETRY / REAL 3D RECONSTRUCTION
    // ------------------------------------------------------

    // Check which reconstruction engine is available.
    //
    // Example:
    // /api/photogrammetry/engine
    //
    // Expected response can contain:
    // {
    //     "configured_engine": "opencv",
    //     "active_engine": "opencv",
    //     "colmap_available": true
    // }

    photogrammetryEngine:
        `${API_BASE_URL}/api/photogrammetry/engine`,


    // Check reconstruction status for a report.
    //
    // Example:
    // /api/photogrammetry/status/12

    photogrammetryStatus:
        `${API_BASE_URL}/api/photogrammetry/status`,


    // Get reconstruction metadata.
    //
    // Example:
    // /api/photogrammetry/metadata/12

    photogrammetryMetadata:
        `${API_BASE_URL}/api/photogrammetry/metadata`,


    // Get reconstructed PLY mesh information.
    //
    // Example:
    // /api/photogrammetry/mesh/12

    photogrammetryMesh:
        `${API_BASE_URL}/api/photogrammetry/mesh`,


    // Start reconstruction.
    //
    // This endpoint will be used by the
    // "Build 3D Model" button once the backend
    // reconstruction implementation is connected.

    photogrammetryReconstruct:
        `${API_BASE_URL}/api/photogrammetry/reconstruct`,


    // Basic photogrammetry API test.

    photogrammetryTest:
        `${API_BASE_URL}/api/photogrammetry/test`

};


// ==========================================================
// HELPER FUNCTIONS
// ==========================================================

/**
 * Build a report-specific 3D road-view URL.
 *
 * Example:
 * getThreeRoadViewUrl(12)
 * -> /3d/road-view/12
 */
function getThreeRoadViewUrl(reportId) {

    return `${API_ENDPOINTS.threeRoadView}/${reportId}`;

}


/**
 * Build a report-specific photogrammetry status URL.
 *
 * Example:
 * getPhotogrammetryStatusUrl(12)
 * -> /api/photogrammetry/status/12
 */
function getPhotogrammetryStatusUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryStatus}/${reportId}`;

}


/**
 * Build a report-specific photogrammetry metadata URL.
 *
 * Example:
 * getPhotogrammetryMetadataUrl(12)
 * -> /api/photogrammetry/metadata/12
 */
function getPhotogrammetryMetadataUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryMetadata}/${reportId}`;

}


/**
 * Build a report-specific photogrammetry mesh URL.
 *
 * Example:
 * getPhotogrammetryMeshUrl(12)
 * -> /api/photogrammetry/mesh/12
 */
function getPhotogrammetryMeshUrl(reportId) {

    return `${API_ENDPOINTS.photogrammetryMesh}/${reportId}`;

}


/**
 * Build a report-specific 3D scene URL.
 *
 * Example:
 * getThreeSceneUrl(12)
 * -> /3d/scene/12
 */
function getThreeSceneUrl(reportId) {

    return `${API_ENDPOINTS.threeScene}/${reportId}`;

}