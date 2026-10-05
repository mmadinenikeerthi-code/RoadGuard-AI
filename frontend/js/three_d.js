// ==========================================================
// ROADGUARD AI — 3D ROAD VISUALIZATION
// frontend/js/three_d.js
//
// MAIN VIEW:
//   Three.js road visualization + report pothole detections
//
// SEPARATE VIEW:
//   Actual COLMAP / PLY reconstruction can be opened through
//   the "Open 3D Reconstruction" button.
//
// IMPORTANT:
//   The road in this main viewer is a visualization layer.
//   It is NOT falsely presented as measured COLMAP geometry.
// ==========================================================


import * as THREE from "three";

import {
    OrbitControls
} from "three/addons/controls/OrbitControls.js";

import {
    PLYLoader
} from "three/addons/loaders/PLYLoader.js";

import {
    OBJLoader
} from "three/addons/loaders/OBJLoader.js";

import {
    GLTFLoader
} from "three/addons/loaders/GLTFLoader.js";


// ==========================================================
// GLOBAL STATE
// ==========================================================

let scene;
let camera;
let renderer;
let controls;

let roadGroup;
let potholeGroup;
let reconstructionGroup;

let raycaster;
let mouse;

let currentReportId = null;
let currentSceneData = null;

let animationId = null;

let roadWidth = 18;
let roadLength = 60;


// ==========================================================
// INITIALIZATION
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    initializeThreeViewer
);


async function initializeThreeViewer() {

    try {

        createThreeScene();

        initializeControls();

        animate();

        await loadReportList();

    } catch (error) {

        console.error(
            "3D initialization error:",
            error
        );

        showError(
            `Failed to initialize 3D viewer: ${error.message}`
        );
    }
}


// ==========================================================
// API HELPERS
// ==========================================================

function getApiBase() {

    if (
        window.API_ENDPOINTS &&
        typeof window.API_ENDPOINTS.base === "string"
    ) {

        return window.API_ENDPOINTS.base;
    }

    return "";
}


function getPhotogrammetryEndpoint() {

    if (
        window.API_ENDPOINTS &&
        window.API_ENDPOINTS.photogrammetryReconstruct
    ) {

        return window.API_ENDPOINTS.photogrammetryReconstruct;
    }

    return "/api/photogrammetry/reconstruct";
}


// ==========================================================
// THREE.JS SCENE
// ==========================================================

function createThreeScene() {

    const container =
        document.getElementById(
            "three-container"
        );

    if (!container) {

        throw new Error(
            "3D viewer container #three-container was not found."
        );
    }


    scene =
        new THREE.Scene();

    scene.background =
        new THREE.Color(
            0x07111f
        );


    const width =
        container.clientWidth || 1000;

    const height =
        container.clientHeight || 620;


    camera =
        new THREE.PerspectiveCamera(
            55,
            width / height,
            0.1,
            2000
        );


    camera.position.set(
        0,
        8,
        20
    );


    renderer =
        new THREE.WebGLRenderer({
            antialias: true,
            alpha: false
        });


    renderer.setSize(
        width,
        height
    );


    renderer.setPixelRatio(
        Math.min(
            window.devicePixelRatio || 1,
            2
        )
    );


    renderer.shadowMap.enabled = true;

    renderer.shadowMap.type =
        THREE.PCFSoftShadowMap;


    renderer.outputColorSpace =
        THREE.SRGBColorSpace;


    container.appendChild(
        renderer.domElement
    );


    // ------------------------------------------------------
    // CAMERA CONTROLS
    // ------------------------------------------------------

    controls =
        new OrbitControls(
            camera,
            renderer.domElement
        );


    controls.enableDamping = true;

    controls.dampingFactor = 0.08;

    controls.enablePan = true;

    controls.minDistance = 4;

    controls.maxDistance = 100;


    controls.target.set(
        0,
        0,
        -12
    );


    // ------------------------------------------------------
    // GROUPS
    // ------------------------------------------------------

    roadGroup =
        new THREE.Group();

    roadGroup.name =
        "roadVisualization";

    scene.add(
        roadGroup
    );


    potholeGroup =
        new THREE.Group();

    potholeGroup.name =
        "potholeMarkers";

    scene.add(
        potholeGroup
    );


    reconstructionGroup =
        new THREE.Group();

    reconstructionGroup.name =
        "colmapReconstruction";

    reconstructionGroup.visible =
        false;

    scene.add(
        reconstructionGroup
    );


    // ------------------------------------------------------
    // LIGHTS
    // ------------------------------------------------------

    createLighting();


    // ------------------------------------------------------
    // RAYCASTING
    // ------------------------------------------------------

    raycaster =
        new THREE.Raycaster();

    mouse =
        new THREE.Vector2();


    renderer.domElement.addEventListener(
        "click",
        onSceneClick
    );


    renderer.domElement.addEventListener(
        "mousemove",
        onSceneMouseMove
    );


    window.addEventListener(
        "resize",
        resizeThreeViewer
    );
}


// ==========================================================
// LIGHTING
// ==========================================================

function createLighting() {

    const hemisphere =
        new THREE.HemisphereLight(
            0xffffff,
            0x182233,
            2.0
        );

    hemisphere.name =
        "roadHemisphereLight";

    scene.add(
        hemisphere
    );


    const directional =
        new THREE.DirectionalLight(
            0xffffff,
            2.8
        );

    directional.name =
        "roadDirectionalLight";


    directional.position.set(
        8,
        18,
        12
    );


    directional.castShadow =
        true;


    directional.shadow.mapSize.width =
        2048;

    directional.shadow.mapSize.height =
        2048;


    directional.shadow.camera.left =
        -30;

    directional.shadow.camera.right =
        30;

    directional.shadow.camera.top =
        30;

    directional.shadow.camera.bottom =
        -30;


    scene.add(
        directional
    );


    const fill =
        new THREE.DirectionalLight(
            0x8fb8ff,
            0.8
        );


    fill.position.set(
        -12,
        8,
        -20
    );


    scene.add(
        fill
    );
}


// ==========================================================
// REPORT LIST
// ==========================================================

async function loadReportList() {

    const selector =
        document.getElementById(
            "reportSelector"
        );


    try {

        const response =
            await fetch(
                `${getApiBase()}/3d/reports-list`
            );


        if (!response.ok) {

            throw new Error(
                `Server returned HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        if (!selector) {

            throw new Error(
                "Report selector not found."
            );
        }


        selector.innerHTML = "";


        const reports =
            data.reports || [];


        reports.forEach(
            report => {

                const option =
                    document.createElement(
                        "option"
                    );


                option.value =
                    report.id;


                option.textContent =
                    `#${report.id} — `
                    + `${report.media_type || "media"} — `
                    + `${report.pothole_count || 0} potholes`;


                selector.appendChild(
                    option
                );
            }
        );


        if (!reports.length) {

            updateThreeStatus(
                "No road inspection reports available."
            );

            return;
        }


        selector.addEventListener(
            "change",
            () => {

                loadRoadView(
                    selector.value
                );
            }
        );


        const requestedId =
            new URLSearchParams(
                window.location.search
            ).get(
                "report_id"
            );


        const requestedReport =
            requestedId
                ? reports.find(
                    report =>
                        String(report.id) ===
                        String(requestedId)
                )
                : null;


        const target =
            requestedReport ||
            reports[0];


        selector.value =
            target.id;


        await loadRoadView(
            target.id
        );


    } catch (error) {

        console.error(
            "Report list error:",
            error
        );


        showError(
            `Could not load reports: ${error.message}`
        );
    }
}


// ==========================================================
// LOAD SELECTED REPORT
// ==========================================================

async function loadRoadView(
    reportId
) {

    if (
        reportId === undefined ||
        reportId === null ||
        reportId === ""
    ) {

        showError(
            "No report selected."
        );

        return;
    }


    currentReportId =
        reportId;


    showLoadingOverlay(
        true
    );


    updateThreeStatus(
        `Loading report #${reportId}...`
    );


    try {

        const response =
            await fetch(
                `${getApiBase()}/3d/road-view/${reportId}`
            );


        const rawBody =
            await response.text();


        let data = null;


        if (rawBody) {

            try {

                data =
                    JSON.parse(
                        rawBody
                    );

            } catch (error) {

                throw new Error(
                    `Invalid JSON from /3d/road-view/${reportId}`
                );
            }
        }


        if (!response.ok) {

            const detail =
                data &&
                (
                    data.detail ||
                    data.message
                );


            throw new Error(
                detail
                    ? `HTTP ${response.status}: ${detail}`
                    : `HTTP ${response.status}`
            );
        }


        if (!data) {

            throw new Error(
                "The backend returned an empty response."
            );
        }


        currentSceneData =
            data;


        // --------------------------------------------------
        // CLEAR PREVIOUS VISUALIZATION
        // --------------------------------------------------

        clearWorld();


        // --------------------------------------------------
        // BUILD MAIN ROAD
        // --------------------------------------------------

        buildRoadScene();


        // --------------------------------------------------
        // UPDATE REPORT INFORMATION
        // --------------------------------------------------

        updateSummary(
            data
        );


        updateReportHeader(
            data
        );


        // --------------------------------------------------
        // PLACE ACTUAL REPORT DETECTIONS
        // --------------------------------------------------

        const potholes =
            data.potholes || [];


        renderPotholeMarkers(
            potholes
        );


        // --------------------------------------------------
        // STATUS
        // --------------------------------------------------

        updateModeBadge(
            "3D ROAD VISUALIZATION",
            true
        );


        reportLoadOutcome(
            data
        );


        // --------------------------------------------------
        // CAMERA
        // --------------------------------------------------

        frameRoadScene();


    } catch (error) {

        console.error(
            "3D road view error:",
            error
        );


        showError(
            `Could not load report #${reportId}: ${error.message}`
        );


    } finally {

        showLoadingOverlay(
            false
        );
    }
}


// ==========================================================
// BUILD MAIN 3D ROAD
// ==========================================================

function buildRoadScene() {

    clearRoad();


    // ------------------------------------------------------
    // ROAD SURFACE
    // ------------------------------------------------------

    const roadGeometry =
        new THREE.PlaneGeometry(
            roadWidth,
            roadLength,
            1,
            1
        );


    const roadMaterial =
        new THREE.MeshStandardMaterial({
            color: 0x343a46,
            roughness: 0.96,
            metalness: 0.0,
            side: THREE.DoubleSide
        });


    const road =
        new THREE.Mesh(
            roadGeometry,
            roadMaterial
        );


    road.rotation.x =
        -Math.PI / 2;


    road.position.set(
        0,
        0,
        -10
    );


    road.receiveShadow =
        true;


    road.name =
        "roadSurface";


    roadGroup.add(
        road
    );


    // ------------------------------------------------------
    // LEFT SHOULDER
    // ------------------------------------------------------

    const shoulderMaterial =
        new THREE.MeshStandardMaterial({
            color: 0x59616d,
            roughness: 1.0
        });


    const leftShoulder =
        new THREE.Mesh(
            new THREE.BoxGeometry(
                3.0,
                0.12,
                roadLength
            ),
            shoulderMaterial
        );


    leftShoulder.position.set(
        -10.5,
        -0.04,
        -10
    );


    leftShoulder.receiveShadow =
        true;


    roadGroup.add(
        leftShoulder
    );


    // ------------------------------------------------------
    // RIGHT SHOULDER
    // ------------------------------------------------------

    const rightShoulder =
        new THREE.Mesh(
            new THREE.BoxGeometry(
                3.0,
                0.12,
                roadLength
            ),
            shoulderMaterial
        );


    rightShoulder.position.set(
        10.5,
        -0.04,
        -10
    );


    rightShoulder.receiveShadow =
        true;


    roadGroup.add(
        rightShoulder
    );


    // ------------------------------------------------------
    // ROAD EDGE LINES
    // ------------------------------------------------------

    const edgeMaterial =
        new THREE.MeshStandardMaterial({
            color: 0xf1f5f9,
            roughness: 0.8
        });


    createRoadStripe(
        -8.35,
        0.06,
        0,
        roadLength,
        0.10,
        edgeMaterial,
        "leftEdge"
    );


    createRoadStripe(
        8.35,
        0.06,
        0,
        roadLength,
        0.10,
        edgeMaterial,
        "rightEdge"
    );


    // ------------------------------------------------------
    // CENTER LANE MARKING
    // ------------------------------------------------------

    const laneMaterial =
        new THREE.MeshStandardMaterial({
            color: 0xf8fafc,
            roughness: 0.75
        });


    const stripeLength =
        3.0;

    const stripeGap =
        2.0;


    for (
        let z = 14;
        z > -43;
        z -= stripeLength + stripeGap
    ) {

        createRoadStripe(
            0,
            0.07,
            z,
            stripeLength,
            0.12,
            laneMaterial,
            "centerLane"
        );
    }


    // ------------------------------------------------------
    // SIDE ROAD MARKINGS
    // ------------------------------------------------------

    createSideRoadMarkings();


    // ------------------------------------------------------
    // ROAD GRID / GUIDE LINES
    // ------------------------------------------------------

    createRoadGuideLines();
}


// ==========================================================
// ROAD STRIPE
// ==========================================================

function createRoadStripe(
    x,
    y,
    z,
    length,
    width,
    material,
    name
) {

    const stripe =
        new THREE.Mesh(
            new THREE.BoxGeometry(
                width,
                0.025,
                length
            ),
            material
        );


    stripe.position.set(
        x,
        y,
        z
    );


    stripe.name =
        name;


    roadGroup.add(
        stripe
    );
}


// ==========================================================
// SIDE ROAD MARKINGS
// ==========================================================

function createSideRoadMarkings() {

    const markingMaterial =
        new THREE.MeshStandardMaterial({
            color: 0xcbd5e1,
            roughness: 0.85
        });


    for (
        let z = 14;
        z > -43;
        z -= 5
    ) {

        const left =
            new THREE.Mesh(
                new THREE.BoxGeometry(
                    0.65,
                    0.025,
                    0.12
                ),
                markingMaterial
            );


        left.position.set(
            -6.2,
            0.07,
            z
        );


        roadGroup.add(
            left
        );


        const right =
            new THREE.Mesh(
                new THREE.BoxGeometry(
                    0.65,
                    0.025,
                    0.12
                ),
                markingMaterial
            );


        right.position.set(
            6.2,
            0.07,
            z
        );


        roadGroup.add(
            right
        );
    }
}


// ==========================================================
// ROAD GUIDE LINES
// ==========================================================

function createRoadGuideLines() {

    const guideMaterial =
        new THREE.LineBasicMaterial({
            color: 0x46505f,
            transparent: true,
            opacity: 0.55
        });


    const positions = [];


    for (
        let z = 18;
        z >= -48;
        z -= 6
    ) {

        positions.push(
            -8.0, 0.012, z,
            8.0, 0.012, z
        );
    }


    const geometry =
        new THREE.BufferGeometry();


    geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(
            positions,
            3
        )
    );


    const lines =
        new THREE.LineSegments(
            geometry,
            guideMaterial
        );


    lines.name =
        "roadGuideLines";


    roadGroup.add(
        lines
    );
}


// ==========================================================
// POTHOLE MARKERS
// ==========================================================

function renderPotholeMarkers(
    markers
) {

    clearPotholes();


    if (!markers.length) {

        return;
    }


    markers.forEach(
        (
            marker,
            index
        ) => {

            const position =
                mapPotholeToRoad(
                    marker,
                    index,
                    markers
                );


            createPotholeMarker(
                marker,
                position,
                index
            );
        }
    );
}


// ==========================================================
// MAP DETECTION TO ROAD
// ==========================================================

function mapPotholeToRoad(
    marker,
    index,
    allMarkers
) {

    // ------------------------------------------------------
    // CASE 1:
    // Backend already supplies a 3D position.
    // ------------------------------------------------------

    const real3D =
        marker.position_3d ||
        marker.position3d;


    if (
        real3D &&
        Number.isFinite(
            Number(real3D.x)
        ) &&
        Number.isFinite(
            Number(real3D.y)
        ) &&
        Number.isFinite(
            Number(real3D.z)
        )
    ) {

        return new THREE.Vector3(
            Number(real3D.x),
            Math.max(
                0.15,
                Number(real3D.y)
            ),
            Number(real3D.z)
        );
    }


    // ------------------------------------------------------
    // Get image coordinates.
    // ------------------------------------------------------

    let x =
        Number(
            marker.center_x ??
            marker.x ??
            0
        );


    let y =
        Number(
            marker.center_y ??
            marker.y ??
            0
        );


    if (
        !Number.isFinite(x)
    ) {

        x = 0;
    }


    if (
        !Number.isFinite(y)
    ) {

        y = 0;
    }


    // ------------------------------------------------------
    // Try to find image dimensions supplied by backend.
    // ------------------------------------------------------

    const imageWidth =
        Number(
            marker.image_width ??
            marker.width_image ??
            marker.frame_width ??
            currentSceneData?.metadata?.image_width ??
            currentSceneData?.metadata?.frame_width ??
            0
        );


    const imageHeight =
        Number(
            marker.image_height ??
            marker.height_image ??
            marker.frame_height ??
            currentSceneData?.metadata?.image_height ??
            currentSceneData?.metadata?.frame_height ??
            0
        );


    // ------------------------------------------------------
    // Convert coordinates to 0..1.
    // ------------------------------------------------------

    let normalizedX;
    let normalizedY;


    if (
        imageWidth > 0 &&
        imageHeight > 0
    ) {

        normalizedX =
            x / imageWidth;

        normalizedY =
            y / imageHeight;

    } else if (
        x >= 0 &&
        x <= 1 &&
        y >= 0 &&
        y <= 1
    ) {

        normalizedX =
            x;

        normalizedY =
            y;

    } else if (
        x >= 0 &&
        x <= 1000 &&
        y >= 0 &&
        y <= 1000
    ) {

        /*
         * Some report formats store normalized detection
         * coordinates on a 0..1000 scale.
         */
        normalizedX =
            x / 1000;

        normalizedY =
            y / 1000;

    } else {

        /*
         * Last-resort visualization mapping.
         *
         * This keeps the marker visible when the backend only
         * supplies raw coordinates without image dimensions.
         */
        const xs =
            allMarkers.map(
                item =>
                    Number(
                        item.center_x ??
                        item.x ??
                        0
                    )
            );


        const ys =
            allMarkers.map(
                item =>
                    Number(
                        item.center_y ??
                        item.y ??
                        0
                    )
            );


        const minX =
            Math.min(
                ...xs
            );

        const maxX =
            Math.max(
                ...xs
            );

        const minY =
            Math.min(
                ...ys
            );

        const maxY =
            Math.max(
                ...ys
            );


        const rangeX =
            Math.max(
                maxX - minX,
                1
            );


        const rangeY =
            Math.max(
                maxY - minY,
                1
            );


        normalizedX =
            (x - minX) /
            rangeX;


        normalizedY =
            (y - minY) /
            rangeY;
    }


    normalizedX =
        THREE.MathUtils.clamp(
            normalizedX,
            0,
            1
        );


    normalizedY =
        THREE.MathUtils.clamp(
            normalizedY,
            0,
            1
        );


    // ------------------------------------------------------
    // Convert image position to road position.
    //
    // X:
    // image left  -> road left
    // image right -> road right
    //
    // Y:
    // image top    -> farther road
    // image bottom -> closer road
    // ------------------------------------------------------

    const roadX =
        (
            normalizedX - 0.5
        ) * 15.0;


    const roadZ =
        10 -
        normalizedY * 50;


    return new THREE.Vector3(
        roadX,
        0.25,
        roadZ
    );
}


// ==========================================================
// CREATE POTHOLE MARKER
// ==========================================================

function createPotholeMarker(
    marker,
    position,
    index
) {

    const severityColor =
        getThreeColor(
            marker.severity
        );


    // ------------------------------------------------------
    // POTHOLE CRATER
    // ------------------------------------------------------

    const crater =
        createPotholeCrater(
            severityColor
        );


    crater.position.copy(
        position
    );


    crater.position.y =
        0.08;


    crater.userData =
        marker;


    crater.userData.markerIndex =
        index;


    crater.name =
        `pothole-${marker.pothole_id ?? index + 1}`;


    potholeGroup.add(
        crater
    );


    // ------------------------------------------------------
    // MARKER SPHERE
    // ------------------------------------------------------

    const markerGeometry =
        new THREE.SphereGeometry(
            0.24,
            24,
            18
        );


    const markerMaterial =
        new THREE.MeshStandardMaterial({
            color: severityColor,
            roughness: 0.35,
            metalness: 0.05,
            emissive: severityColor,
            emissiveIntensity: 0.35
        });


    const markerMesh =
        new THREE.Mesh(
            markerGeometry,
            markerMaterial
        );


    markerMesh.position.copy(
        position
    );


    markerMesh.position.y =
        0.65;


    markerMesh.castShadow =
        true;


    markerMesh.userData =
        marker;


    markerMesh.userData.markerIndex =
        index;


    markerMesh.name =
        `potholeMarker-${marker.pothole_id ?? index + 1}`;


    potholeGroup.add(
        markerMesh
    );


    // ------------------------------------------------------
    // VERTICAL PIN
    // ------------------------------------------------------

    const pinMaterial =
        new THREE.MeshBasicMaterial({
            color: severityColor
        });


    const pin =
        new THREE.Mesh(
            new THREE.CylinderGeometry(
                0.025,
                0.025,
                0.8,
                8
            ),
            pinMaterial
        );


    pin.position.copy(
        position
    );


    pin.position.y =
        0.42;


    pin.userData =
        marker;


    potholeGroup.add(
        pin
    );


    // ------------------------------------------------------
    // GLOW RING
    // ------------------------------------------------------

    const ringGeometry =
        new THREE.RingGeometry(
            0.34,
            0.43,
            32
        );


    const ringMaterial =
        new THREE.MeshBasicMaterial({
            color: severityColor,
            transparent: true,
            opacity: 0.55,
            side: THREE.DoubleSide
        });


    const ring =
        new THREE.Mesh(
            ringGeometry,
            ringMaterial
        );


    ring.rotation.x =
        -Math.PI / 2;


    ring.position.copy(
        position
    );


    ring.position.y =
        0.095;


    ring.userData =
        marker;


    potholeGroup.add(
        ring
    );
}


// ==========================================================
// POTHOLE CRATER
// ==========================================================

function createPotholeCrater(
    color
) {

    const geometry =
        new THREE.CircleGeometry(
            0.48,
            24
        );


    const material =
        new THREE.MeshStandardMaterial({
            color: 0x111827,
            roughness: 1.0,
            metalness: 0.0,
            side: THREE.DoubleSide
        });


    const crater =
        new THREE.Mesh(
            geometry,
            material
        );


    crater.rotation.x =
        -Math.PI / 2;


    crater.receiveShadow =
        true;


    return crater;
}


// ==========================================================
// REPORT OUTCOME
// ==========================================================

function reportLoadOutcome(
    data
) {

    const markers =
        data.potholes || [];


    const recorded =
        Number(
            data.report?.pothole_count ??
            data.total_potholes ??
            markers.length
        );


    let message =
        `${markers.length} pothole marker(s) displayed`;


    if (
        recorded !== markers.length
    ) {

        message +=
            ` — report count: ${recorded}`;
    }


    setStatusBar(
        message,
        false
    );


    console.log(
        "RoadGuard 3D report:",
        data
    );
}


// ==========================================================
// SUMMARY
// ==========================================================

function updateSummary(
    data
) {

    const total =
        document.getElementById(
            "totalObjects"
        );


    const format =
        document.getElementById(
            "mediaFormat"
        );


    if (total) {

        total.textContent =
            data.total_potholes ??
            data.report?.pothole_count ??
            0;
    }


    if (format) {

        format.textContent =
            data.report?.media_type ||
            "--";
    }
}


// ==========================================================
// REPORT HEADER / STATS
// ==========================================================

function updateReportHeader(
    data
) {

    const reportId =
        document.getElementById(
            "reportId"
        );


    const reconstructionState =
        document.getElementById(
            "reconstructionState"
        );


    const pointCount =
        document.getElementById(
            "pointCount"
        );


    const meshStatus =
        document.getElementById(
            "meshStatus"
        );


    if (reportId) {

        reportId.textContent =
            data.report?.id ??
            currentReportId;
    }


    if (reconstructionState) {

        reconstructionState.textContent =
            "ROAD VISUALIZATION";
    }


    if (pointCount) {

        pointCount.textContent =
            (data.potholes || []).length;
    }


    if (meshStatus) {

        meshStatus.textContent =
            "VISUALIZATION";
    }
}


// ==========================================================
// MODE BADGE
// ==========================================================

function updateModeBadge(
    label,
    isActive
) {

    const badge =
        document.getElementById(
            "viewModeBadge"
        );


    if (!badge) {

        return;
    }


    badge.textContent =
        label;


    badge.className =
        "view-mode-badge " +
        (
            isActive
                ? "true-360"
                : "reconstruction"
        );
}


// ==========================================================
// SEVERITY COLORS
// ==========================================================

function getThreeColor(
    severity
) {

    const colors = {

        LOW:
            0x22c55e,

        MODERATE:
            0xf59e0b,

        HIGH:
            0xf97316,

        CRITICAL:
            0xef4444
    };


    return (
        colors[
        String(
            severity || "LOW"
        ).toUpperCase()
        ] ||
        0x64748b
    );
}


// ==========================================================
// CAMERA
// ==========================================================

function frameRoadScene() {

    const target =
        new THREE.Vector3(
            0,
            0,
            -12
        );


    camera.position.set(
        0,
        8,
        19
    );


    controls.target.copy(
        target
    );


    controls.minDistance =
        4;


    controls.maxDistance =
        100;


    controls.update();
}


// ==========================================================
// RESET CAMERA
// ==========================================================

function resetCamera() {

    frameRoadScene();


    updateThreeStatus(
        "Camera reset."
    );
}


// ==========================================================
// TOP VIEW
// ==========================================================

function topRoadView() {

    camera.position.set(
        0,
        34,
        -10
    );


    controls.target.set(
        0,
        0,
        -10
    );


    controls.update();


    updateThreeStatus(
        "Top road view."
    );
}


// ==========================================================
// FOCUS ALL POTHOLES
// ==========================================================

function focusAllPotholes() {

    if (
        !potholeGroup.children.length
    ) {

        frameRoadScene();

        return;
    }


    const box =
        new THREE.Box3()
            .setFromObject(
                potholeGroup
            );


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const maxSize =
        Math.max(
            size.x,
            size.y,
            size.z,
            5
        );


    camera.position.set(
        center.x,
        center.y + maxSize * 0.8,
        center.z + maxSize * 1.2
    );


    controls.target.copy(
        center
    );


    controls.update();


    updateThreeStatus(
        "Focused on detected potholes."
    );
}


// ==========================================================
// CLICK DETECTION
// ==========================================================

function onSceneClick(
    event
) {

    const rect =
        renderer.domElement
            .getBoundingClientRect();


    mouse.x =
        (
            (
                event.clientX -
                rect.left
            ) /
            rect.width
        ) * 2 - 1;


    mouse.y =
        -(
            (
                event.clientY -
                rect.top
            ) /
            rect.height
        ) * 2 + 1;


    raycaster.setFromCamera(
        mouse,
        camera
    );


    const clickable =
        potholeGroup.children.filter(
            object =>
                object.userData &&
                object.userData.pothole_id !== undefined
        );


    const intersections =
        raycaster.intersectObjects(
            clickable,
            false
        );


    if (
        intersections.length
    ) {

        const marker =
            intersections[0]
                .object
                .userData;


        showPotholeInfo(
            marker
        );
    }
}


// ==========================================================
// HOVER
// ==========================================================

function onSceneMouseMove(
    event
) {

    const rect =
        renderer.domElement
            .getBoundingClientRect();


    mouse.x =
        (
            (
                event.clientX -
                rect.left
            ) /
            rect.width
        ) * 2 - 1;


    mouse.y =
        -(
            (
                event.clientY -
                rect.top
            ) /
            rect.height
        ) * 2 + 1;


    raycaster.setFromCamera(
        mouse,
        camera
    );


    const clickable =
        potholeGroup.children.filter(
            object =>
                object.userData &&
                object.userData.pothole_id !== undefined
        );


    const intersections =
        raycaster.intersectObjects(
            clickable,
            false
        );


    renderer.domElement.style.cursor =
        intersections.length
            ? "pointer"
            : "default";
}


// ==========================================================
// POTHOLE INFO PANEL
// ==========================================================

function showPotholeInfo(
    marker
) {

    const panel =
        document.getElementById(
            "potholeInfoPanel"
        );


    if (!panel) {

        return;
    }


    const location =
        marker.location;


    let locationText =
        "Location unavailable";


    if (
        location &&
        location.latitude !== undefined &&
        location.longitude !== undefined
    ) {

        locationText =
            `${Number(location.latitude).toFixed(6)}, `
            + `${Number(location.longitude).toFixed(6)}`;
    }


    const confidence =
        (
            Number(
                marker.confidence || 0
            ) * 100
        ).toFixed(0);


    panel.innerHTML = `
        <div class="pothole-info-card">

            <h4>
                Pothole #${marker.pothole_id ?? "--"}
            </h4>

            <p>
                <strong>Severity:</strong>
                ${marker.severity || "UNKNOWN"}
            </p>

            <p>
                <strong>Confidence:</strong>
                ${confidence}%
            </p>

            <p>
                <strong>Location:</strong>
                ${locationText}
            </p>

        </div>
    `;
}


// ==========================================================
// CLEAR ROAD
// ==========================================================

function clearRoad() {

    if (!roadGroup) {

        return;
    }


    while (
        roadGroup.children.length
    ) {

        const object =
            roadGroup.children[0];


        roadGroup.remove(
            object
        );


        disposeObject(
            object
        );
    }
}


// ==========================================================
// CLEAR POTHOLES
// ==========================================================

function clearPotholes() {

    if (!potholeGroup) {

        return;
    }


    while (
        potholeGroup.children.length
    ) {

        const object =
            potholeGroup.children[0];


        potholeGroup.remove(
            object
        );


        disposeObject(
            object
        );
    }
}


// ==========================================================
// CLEAR RECONSTRUCTION
// ==========================================================

function clearReconstruction() {

    if (!reconstructionGroup) {

        return;
    }


    while (
        reconstructionGroup.children.length
    ) {

        const object =
            reconstructionGroup.children[0];


        reconstructionGroup.remove(
            object
        );


        disposeObject(
            object
        );
    }
}


// ==========================================================
// CLEAR WORLD
// ==========================================================

function clearWorld() {

    clearRoad();

    clearPotholes();

    clearReconstruction();


    reconstructionGroup.visible =
        false;
}


// ==========================================================
// DISPOSE OBJECT RECURSIVELY
// ==========================================================

function disposeObject(
    object
) {

    if (!object) {

        return;
    }


    object.traverse(
        child => {

            if (
                child.geometry
            ) {

                child.geometry.dispose();
            }


            if (
                child.material
            ) {

                if (
                    Array.isArray(
                        child.material
                    )
                ) {

                    child.material.forEach(
                        material =>
                            disposeMaterial(
                                material
                            )
                    );

                } else {

                    disposeMaterial(
                        child.material
                    );
                }
            }
        }
    );
}


// ==========================================================
// MATERIAL DISPOSAL
// ==========================================================

function disposeMaterial(
    material
) {

    if (!material) {

        return;
    }


    if (
        material.map
    ) {

        material.map.dispose();
    }


    if (
        material.normalMap
    ) {

        material.normalMap.dispose();
    }


    if (
        material.roughnessMap
    ) {

        material.roughnessMap.dispose();
    }


    if (
        material.metalnessMap
    ) {

        material.metalnessMap.dispose();
    }


    material.dispose();
}


// ==========================================================
// OPTIONAL REAL COLMAP RECONSTRUCTION
// ==========================================================

async function loadReconstructionGeometry(
    url
) {

    const lower =
        url.toLowerCase();


    if (
        lower.endsWith(
            ".obj"
        )
    ) {

        const loader =
            new OBJLoader();


        return await loader.loadAsync(
            url
        );
    }


    if (
        lower.endsWith(".gltf") ||
        lower.endsWith(".glb")
    ) {

        const loader =
            new GLTFLoader();


        const gltf =
            await loader.loadAsync(
                url
            );


        return gltf.scene;
    }


    const loader =
        new PLYLoader();


    const geometry =
        await loader.loadAsync(
            url
        );


    if (
        !geometry ||
        !geometry.attributes.position ||
        geometry.attributes.position.count === 0
    ) {

        throw new Error(
            "PLY contains no vertex positions."
        );
    }


    const hasFaces =
        geometry.index &&
        geometry.index.count >= 3;


    if (hasFaces) {

        geometry.computeVertexNormals();


        const material =
            new THREE.MeshStandardMaterial({
                vertexColors:
                    geometry.hasAttribute(
                        "color"
                    ),
                color:
                    geometry.hasAttribute(
                        "color"
                    )
                        ? 0xffffff
                        : 0x64748b,
                roughness: 0.9,
                metalness: 0.02,
                side: THREE.DoubleSide
            });


        return new THREE.Mesh(
            geometry,
            material
        );
    }


    const material =
        new THREE.PointsMaterial({
            size: 0.12,
            sizeAttenuation: true,
            vertexColors:
                geometry.hasAttribute(
                    "color"
                ),
            color:
                geometry.hasAttribute(
                    "color"
                )
                    ? 0xffffff
                    : 0x93c5fd
        });


    return new THREE.Points(
        geometry,
        material
    );
}


// ==========================================================
// OPEN REAL RECONSTRUCTION
// ==========================================================

async function openRealReconstruction() {

    if (!currentSceneData) {

        showError(
            "Load a report first."
        );

        return;
    }


    const reconstruction =
        currentSceneData.reconstruction;


    const meshURL =
        reconstruction?.mesh_url;


    const pointURL =
        reconstruction?.pointcloud_url;


    const candidates =
        [
            meshURL,
            pointURL
        ].filter(Boolean);


    if (!candidates.length) {

        showError(
            "No COLMAP reconstruction file is available for this report."
        );

        return;
    }


    showLoadingOverlay(
        true
    );


    try {

        clearReconstruction();


        for (
            const url of candidates
        ) {

            try {

                updateThreeStatus(
                    "Loading real COLMAP reconstruction..."
                );


                const object =
                    await loadReconstructionGeometry(
                        url
                    );


                normalizeObject(
                    object
                );


                object.name =
                    "realCOLMAPReconstruction";


                reconstructionGroup.add(
                    object
                );


                reconstructionGroup.visible =
                    true;


                roadGroup.visible =
                    false;


                potholeGroup.visible =
                    false;


                fitCameraToObject(
                    object
                );


                updateModeBadge(
                    "COLMAP RECONSTRUCTION",
                    true
                );


                updateThreeStatus(
                    "Real COLMAP reconstruction loaded."
                );


                return;

            } catch (error) {

                console.warn(
                    "Reconstruction failed:",
                    url,
                    error
                );
            }
        }


        throw new Error(
            "Available reconstruction files could not be loaded."
        );


    } catch (error) {

        showError(
            error.message
        );


    } finally {

        showLoadingOverlay(
            false
        );
    }
}


// ==========================================================
// RETURN TO ROAD VIEW
// ==========================================================

function returnToRoadView() {

    reconstructionGroup.visible =
        false;


    roadGroup.visible =
        true;


    potholeGroup.visible =
        true;


    updateModeBadge(
        "3D ROAD VISUALIZATION",
        true
    );


    frameRoadScene();


    updateThreeStatus(
        "3D road visualization active."
    );
}


// ==========================================================
// NORMALIZE RECONSTRUCTION
// ==========================================================

function normalizeObject(
    object
) {

    const box =
        new THREE.Box3()
            .setFromObject(
                object
            );


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const maxDimension =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    if (
        !Number.isFinite(
            maxDimension
        ) ||
        maxDimension <= 0
    ) {

        return;
    }


    const scale =
        20 /
        maxDimension;


    object.scale.setScalar(
        scale
    );


    object.position.sub(
        center.multiplyScalar(
            scale
        )
    );
}


// ==========================================================
// FIT RECONSTRUCTION CAMERA
// ==========================================================

function fitCameraToObject(
    object
) {

    const box =
        new THREE.Box3()
            .setFromObject(
                object
            );


    const center =
        box.getCenter(
            new THREE.Vector3()
        );


    const size =
        box.getSize(
            new THREE.Vector3()
        );


    const maxSize =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    const distance =
        Math.max(
            maxSize * 1.5,
            8
        );


    camera.position.set(
        center.x,
        center.y +
        distance * 0.55,
        center.z +
        distance
    );


    controls.target.copy(
        center
    );


    controls.minDistance =
        Math.max(
            1,
            maxSize * 0.05
        );


    controls.maxDistance =
        Math.max(
            50,
            maxSize * 5
        );


    controls.update();
}


// ==========================================================
// PHOTOGRAMMETRY BUTTON
// ==========================================================

async function runPhotogrammetryReconstruction() {

    if (!currentReportId) {

        showError(
            "Select a report first."
        );

        return;
    }


    const confirmed =
        window.confirm(
            `Run photogrammetry reconstruction for report #${currentReportId}?\n\n`
            +
            "This can take several minutes."
        );


    if (!confirmed) {

        return;
    }


    showLoadingOverlay(
        true
    );


    try {

        const endpoint =
            `${getPhotogrammetryEndpoint()}/${currentReportId}`;


        updateThreeStatus(
            `Running photogrammetry for report #${currentReportId}...`
        );


        const response =
            await fetch(
                endpoint,
                {
                    method: "POST"
                }
            );


        const raw =
            await response.text();


        let data = null;


        if (raw) {

            try {

                data =
                    JSON.parse(
                        raw
                    );

            } catch (error) {

                data = null;
            }
        }


        if (!response.ok) {

            throw new Error(
                data?.detail ||
                data?.message ||
                `HTTP ${response.status}`
            );
        }


        updateThreeStatus(
            "Photogrammetry completed. Reloading report..."
        );


        await loadRoadView(
            currentReportId
        );


    } catch (error) {

        showError(
            `Photogrammetry failed: ${error.message}`
        );


    } finally {

        showLoadingOverlay(
            false
        );
    }
}


// ==========================================================
// CONTROLS
// ==========================================================

function initializeControls() {

    const reload =
        document.getElementById(
            "reloadSceneBtn"
        );


    if (reload) {

        reload.addEventListener(
            "click",
            () => {

                if (currentReportId) {

                    loadRoadView(
                        currentReportId
                    );
                }
            }
        );
    }


    const reset =
        document.getElementById(
            "resetCameraBtn"
        );


    if (reset) {

        reset.addEventListener(
            "click",
            resetCamera
        );
    }


    const topView =
        document.getElementById(
            "topViewBtn"
        );


    if (topView) {

        topView.addEventListener(
            "click",
            topRoadView
        );
    }


    const focus =
        document.getElementById(
            "focusPotholesBtn"
        );


    if (focus) {

        focus.addEventListener(
            "click",
            focusAllPotholes
        );
    }


    const build =
        document.getElementById(
            "runReconstructionBtn"
        );


    if (build) {

        build.addEventListener(
            "click",
            runPhotogrammetryReconstruction
        );
    }


    const open =
        document.getElementById(
            "openPlyViewerBtn"
        );


    if (open) {

        open.addEventListener(
            "click",
            openRealReconstruction
        );
    }


    const roadView =
        document.getElementById(
            "roadViewBtn"
        );


    if (roadView) {

        roadView.addEventListener(
            "click",
            returnToRoadView
        );
    }


    const retry =
        document.getElementById(
            "retryBtn"
        );


    if (retry) {

        retry.addEventListener(
            "click",
            () => {

                if (currentReportId) {

                    loadRoadView(
                        currentReportId
                    );
                }
            }
        );
    }
}


// ==========================================================
// ANIMATION
// ==========================================================

function animate() {

    animationId =
        requestAnimationFrame(
            animate
        );


    if (controls) {

        controls.update();
    }


    if (
        renderer &&
        scene &&
        camera
    ) {

        renderer.render(
            scene,
            camera
        );
    }
}


// ==========================================================
// RESIZE
// ==========================================================

function resizeThreeViewer() {

    const container =
        document.getElementById(
            "three-container"
        );


    if (
        !container ||
        !camera ||
        !renderer
    ) {

        return;
    }


    const width =
        container.clientWidth;


    const height =
        container.clientHeight;


    if (
        width <= 0 ||
        height <= 0
    ) {

        return;
    }


    camera.aspect =
        width /
        height;


    camera.updateProjectionMatrix();


    renderer.setSize(
        width,
        height
    );
}


// ==========================================================
// LOADING UI
// ==========================================================

function showLoadingOverlay(
    visible
) {

    const loading =
        document.getElementById(
            "loading"
        );


    if (!loading) {

        return;
    }


    loading.style.display =
        visible
            ? "flex"
            : "none";
}


// ==========================================================
// STATUS
// ==========================================================

function updateThreeStatus(
    message
) {

    const status =
        document.getElementById(
            "threeStatus"
        );


    if (status) {

        status.textContent =
            message;
    }


    const reconstructionStatus =
        document.getElementById(
            "reconstructionStatus"
        );


    if (reconstructionStatus) {

        reconstructionStatus.textContent =
            message;
    }


    setStatusBar(
        message,
        false
    );


    console.log(
        "RoadGuard 3D:",
        message
    );
}


// ==========================================================
// STATUS BAR
// ==========================================================

function setStatusBar(
    message,
    isError
) {

    const bar =
        document.getElementById(
            "threeStatusBar"
        );


    if (!bar) {

        return;
    }


    bar.textContent =
        message;


    bar.classList.toggle(
        "error",
        Boolean(isError)
    );
}


// ==========================================================
// ERROR
// ==========================================================

function showError(
    message
) {

    console.error(
        "RoadGuard 3D:",
        message
    );


    showLoadingOverlay(
        false
    );


    setStatusBar(
        message,
        true
    );


    const errorMessage =
        document.getElementById(
            "errorMessage"
        );


    const errorDetail =
        document.getElementById(
            "errorDetail"
        );


    if (errorDetail) {

        errorDetail.textContent =
            message;
    }


    if (errorMessage) {

        errorMessage.style.display =
            "flex";
    }
}


// ==========================================================
// CLEANUP
// ==========================================================

window.addEventListener(
    "beforeunload",
    () => {

        if (animationId) {

            cancelAnimationFrame(
                animationId
            );
        }


        if (renderer) {

            renderer.dispose();
        }
    }
);