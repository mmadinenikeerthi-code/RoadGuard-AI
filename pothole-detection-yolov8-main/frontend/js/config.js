// ==========================================================
// ROADGUARD AI
// FRONTEND CONFIGURATION
// ==========================================================

// The FastAPI app serves this frontend, so relative URLs work in Replit
// Preview, local development, and a published deployment.
const API_BASE_URL = "";


// ==========================================================
// API ENDPOINTS
// ==========================================================

const API_ENDPOINTS = {

    // Detection
    detectionUpload:
        `${API_BASE_URL}/api/detection/upload`,

    detectionProcess:
        `${API_BASE_URL}/api/detection/process`,

    detectionStatus:
        `${API_BASE_URL}/api/detection`,


    // Reports
    reports:
        `${API_BASE_URL}/api/reports`,

    reportsSummary:
        `${API_BASE_URL}/api/reports/summary`,


    // Map
    mapLocations:
        `${API_BASE_URL}/api/map/locations`,


    // Hotspots
    hotspots:
        `${API_BASE_URL}/hotspots`,

    hotspotSummary:
        `${API_BASE_URL}/hotspots/summary`,


    // 3D Visualization
    threeHome:
        `${API_BASE_URL}/3d/`,

    threeScene:
        `${API_BASE_URL}/3d/scene`,

    threeSummary:
        `${API_BASE_URL}/3d/summary`

};