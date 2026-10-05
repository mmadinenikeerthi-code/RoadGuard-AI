// ==========================================================
// ROADGUARD AI - CANONICAL 3D ROAD INSPECTION VIEWER
// frontend/js/roadguard-3d.js
//
// IMPORTANT ARCHITECTURE:
// REAL INPUT
//     ↓
// COLMAP reconstruction
//     ↓
// REAL PLY / OBJ / GLTF
//     ↓
// Three.js visualization
//
// NO procedural road.
// NO synthetic road.
// NO image-space fake 3D.
// NO generated fallback geometry.
// ==========================================================


// ==========================================================
// THREE.JS ES MODULE IMPORTS
// ==========================================================

import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js";

import {
    OrbitControls
} from "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/controls/OrbitControls.js";

import {
    PLYLoader
} from "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/loaders/PLYLoader.js";

import {
    OBJLoader
} from "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/loaders/OBJLoader.js";

import {
    GLTFLoader
} from "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/jsm/loaders/GLTFLoader.js";


// ==========================================================
// STATE
// ==========================================================

let scene = null;
let camera = null;
let renderer = null;
let controls = null;

let roadGroup = null;
let potholeGroup = null;

let raycaster = null;
let mouse = null;

let activeReportId = null;
let currentSceneData = null;
let selectedMarker = null;

let roadBoundingBox = null;
let currentRoadObject = null;

let resizeObserver = null;


// ==========================================================
// DOM ELEMENTS
// ==========================================================

const container =
    document.getElementById("three-container");

const loadingElement =
    document.getElementById("loading");

const loadingText =
    document.getElementById("loadingText");

const errorOverlay =
    document.getElementById("errorMessage");

const errorTitle =
    document.getElementById("errorTitle");

const errorDetail =
    document.getElementById("errorDetail");

const retryBtn =
    document.getElementById("retryBtn");

const reportSelector =
    document.getElementById("reportSelector");

const viewModeBadge =
    document.getElementById("viewModeBadge");


// ==========================================================
// SUMMARY ELEMENTS
// ==========================================================

const totalPotholesEl =
    document.getElementById("totalPotholes");

const selectedObjectEl =
    document.getElementById("selectedObject");

const confidenceEl =
    document.getElementById("confidence");

const roadConditionEl =
    document.getElementById("roadCondition");


// ==========================================================
// DETAIL ELEMENTS
// ==========================================================

const noSelectionEl =
    document.getElementById("noSelection");

const potholeDetailsEl =
    document.getElementById("potholeDetails");

const detailIdEl =
    document.getElementById("detailId");

const detailSeverityEl =
    document.getElementById("detailSeverity");

const detailConfidenceEl =
    document.getElementById("detailConfidence");

const detailWidthEl =
    document.getElementById("detailWidth");

const detailDepthEl =
    document.getElementById("detailDepth");

const detailPositionEl =
    document.getElementById("detailPosition");

const focusSelectedBtn =
    document.getElementById("focusSelectedBtn");


// ==========================================================
// OPTIONAL STATUS ELEMENTS
// ==========================================================

const reportIdEl =
    document.getElementById("reportId");

const reconstructionStateEl =
    document.getElementById("reconstructionState");

const pointCountEl =
    document.getElementById("pointCount");

const meshStatusEl =
    document.getElementById("meshStatus");


// ==========================================================
// CONTAINER VALIDATION
// ==========================================================

if (!container) {
    console.error(
        "[RoadGuard 3D] #three-container not found."
    );

    throw new Error(
        "3D container missing."
    );
}


// ==========================================================
// INITIALIZATION
// ==========================================================

initThreeScene();

initInteractions();

setupViewerButtons();

setupResizeObserver();

loadReportCatalogAndStart();

animate();


// ==========================================================
// THREE.JS SETUP
// ==========================================================

function initThreeScene() {

    scene =
        new THREE.Scene();

    scene.background =
        new THREE.Color(0x060b14);


    // ------------------------------------------------------
    // INITIAL DIMENSIONS
    // ------------------------------------------------------

    const width =
        Math.max(
            container.clientWidth,
            1
        );

    const height =
        Math.max(
            container.clientHeight,
            1
        );


    // ------------------------------------------------------
    // CAMERA
    // ------------------------------------------------------

    camera =
        new THREE.PerspectiveCamera(
            52,
            width / height,
            0.05,
            5000
        );

    camera.position.set(
        0,
        12,
        28
    );


    // ------------------------------------------------------
    // RENDERER
    // ------------------------------------------------------

    renderer =
        new THREE.WebGLRenderer({
            antialias: true,
            powerPreference: "high-performance",
            alpha: false
        });

    renderer.setPixelRatio(
        Math.min(
            window.devicePixelRatio || 1,
            2
        )
    );

    renderer.setSize(
        width,
        height,
        false
    );

    renderer.shadowMap.enabled = true;

    renderer.shadowMap.type =
        THREE.PCFSoftShadowMap;

    renderer.domElement.style.display =
        "block";

    renderer.domElement.style.width =
        "100%";

    renderer.domElement.style.height =
        "100%";

    container.appendChild(
        renderer.domElement
    );


    // ------------------------------------------------------
    // ORBIT CONTROLS
    // ------------------------------------------------------

    controls =
        new OrbitControls(
            camera,
            renderer.domElement
        );

    controls.enableDamping = true;

    controls.dampingFactor = 0.06;

    controls.screenSpacePanning = true;

    controls.minDistance = 0.5;

    controls.maxDistance = 500;

    controls.target.set(
        0,
        0,
        0
    );


    // ------------------------------------------------------
    // LIGHTING
    // ------------------------------------------------------

    const hemiLight =
        new THREE.HemisphereLight(
            0xffffff,
            0x1b2838,
            2.2
        );

    scene.add(
        hemiLight
    );


    const dirLight1 =
        new THREE.DirectionalLight(
            0xffffff,
            2.0
        );

    dirLight1.position.set(
        20,
        45,
        25
    );

    dirLight1.castShadow = true;

    scene.add(
        dirLight1
    );


    const dirLight2 =
        new THREE.DirectionalLight(
            0x60a5fa,
            1.2
        );

    dirLight2.position.set(
        -25,
        20,
        -20
    );

    scene.add(
        dirLight2
    );


    // ------------------------------------------------------
    // REAL MODEL GROUP
    // ------------------------------------------------------

    roadGroup =
        new THREE.Group();

    roadGroup.name =
        "real-colmap-reconstruction";

    scene.add(
        roadGroup
    );


    // ------------------------------------------------------
    // POTHOLE MARKER GROUP
    // ------------------------------------------------------

    potholeGroup =
        new THREE.Group();

    potholeGroup.name =
        "real-3d-pothole-markers";

    scene.add(
        potholeGroup
    );


    // ------------------------------------------------------
    // INTERACTION HELPERS
    // ------------------------------------------------------

    raycaster =
        new THREE.Raycaster();

    mouse =
        new THREE.Vector2();


    // ------------------------------------------------------
    // WINDOW RESIZE
    // ------------------------------------------------------

    window.addEventListener(
        "resize",
        onWindowResize
    );
}


// ==========================================================
// RESIZE OBSERVER
// ==========================================================

function setupResizeObserver() {

    if (
        !container ||
        typeof ResizeObserver === "undefined"
    ) {
        return;
    }

    resizeObserver =
        new ResizeObserver(
            () => {

                requestAnimationFrame(
                    () => {
                        resizeRendererToContainer();
                    }
                );
            }
        );

    resizeObserver.observe(
        container
    );
}


// ==========================================================
// RESIZE RENDERER
// ==========================================================

function resizeRendererToContainer() {

    if (
        !container ||
        !renderer ||
        !camera
    ) {
        return;
    }

    const rect =
        container.getBoundingClientRect();

    const width =
        Math.max(
            Math.floor(rect.width),
            1
        );

    const height =
        Math.max(
            Math.floor(rect.height),
            1
        );

    camera.aspect =
        width / height;

    camera.updateProjectionMatrix();

    renderer.setSize(
        width,
        height,
        false
    );
}


// ==========================================================
// WINDOW RESIZE
// ==========================================================

function onWindowResize() {

    resizeRendererToContainer();
}


// ==========================================================
// REPORT CATALOG
// ==========================================================

async function loadReportCatalogAndStart() {

    try {

        console.log(
            "[RoadGuard 3D] Starting report catalog load..."
        );


        // --------------------------------------------------
        // READ URL
        // --------------------------------------------------

        const params =
            new URLSearchParams(
                window.location.search
            );

        const requestedReportId =
            params.get(
                "report_id"
            );

        console.log(
            "[RoadGuard 3D] URL report_id:",
            requestedReportId
        );


        // --------------------------------------------------
        // FETCH REPORT CATALOG
        // --------------------------------------------------

        const response =
            await fetch(
                "/3d/reports-list",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {

            throw new Error(
                `Failed to load report catalog: HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        console.log(
            "[RoadGuard 3D] Report catalog:",
            data
        );


        if (
            !data ||
            !Array.isArray(data.reports)
        ) {

            throw new Error(
                "Invalid report catalog returned by backend."
            );
        }


        const reports =
            data.reports;


        if (
            reports.length === 0
        ) {

            throw new Error(
                "No reports are available."
            );
        }


        // ==================================================
        // PRIORITY 1:
        // EXPLICIT URL REPORT
        // ==================================================

        if (
            requestedReportId !== null
        ) {

            const requestedId =
                String(
                    requestedReportId
                );


            const requestedReport =
                reports.find(
                    report =>
                        String(
                            report.id ??
                            report.report_id
                        ) === requestedId
                );


            if (!requestedReport) {

                console.error(
                    "[RoadGuard 3D] Requested report was not found:",
                    requestedId
                );

                throw new Error(
                    `Requested report ${requestedId} was not found.`
                );
            }


            const actualId =
                requestedReport.id ??
                requestedReport.report_id;


            console.log(
                "[RoadGuard 3D] Explicit URL report selected:",
                actualId
            );


            populateReportSelector(
                reports,
                actualId
            );


            await loadReport(
                actualId
            );

            return;
        }


        // ==================================================
        // PRIORITY 2:
        // FIRST AVAILABLE REPORT
        // ==================================================

        const firstReport =
            reports[0];


        const firstId =
            firstReport.id ??
            firstReport.report_id;


        console.log(
            "[RoadGuard 3D] No URL report_id supplied.",
            "Using first available report:",
            firstId
        );


        populateReportSelector(
            reports,
            firstId
        );


        await loadReport(
            firstId
        );

    } catch (error) {

        console.error(
            "[RoadGuard 3D] Failed to initialize viewer:",
            error
        );

        showLoading(
            false
        );

        showError(
            "3D Reconstruction Unavailable",
            error?.message ||
            "Unable to load the reconstruction report."
        );
    }
}


// ==========================================================
// POPULATE REPORT SELECTOR
// ==========================================================

function populateReportSelector(
    reports,
    selectedId
) {

    if (!reportSelector) {
        return;
    }


    reportSelector.innerHTML = "";


    reports.forEach(
        report => {

            const id =
                report.id ??
                report.report_id;


            const option =
                document.createElement(
                    "option"
                );


            option.value =
                String(id);


            option.textContent =
                `Report #${id} ` +
                `(${(
                    report.media_type ||
                    "video"
                ).toUpperCase()} - ` +
                `${report.pothole_count || 0} defects)`;


            reportSelector.appendChild(
                option
            );
        }
    );


    reportSelector.value =
        String(selectedId);


    // Avoid duplicate listeners.
    reportSelector.onchange =
        () => {

            const targetId =
                reportSelector.value;


            if (!targetId) {
                return;
            }


            const url =
                new URL(
                    window.location.href
                );


            url.searchParams.set(
                "report_id",
                targetId
            );


            window.history.pushState(
                {},
                "",
                url
            );


            loadReport(
                targetId
            );
        };
}


// ==========================================================
// LOAD REPORT 3D SCENE
// ==========================================================

async function loadReport(
    reportId
) {

    if (
        reportId === null ||
        reportId === undefined ||
        String(reportId).trim() === ""
    ) {

        console.warn(
            "[RoadGuard 3D] loadReport called without report ID."
        );

        return;
    }


    activeReportId =
        String(reportId);


    // ------------------------------------------------------
    // UPDATE SELECTOR
    // ------------------------------------------------------

    if (reportSelector) {

        reportSelector.value =
            String(reportId);
    }


    // ------------------------------------------------------
    // LOADING STATE
    // ------------------------------------------------------

    showLoading(
        true,
        `Loading COLMAP 3D scene for Report #${reportId}...`
    );

    hideError();

    clearSelection();


    try {

        // ==================================================
        // FETCH BACKEND 3D INFORMATION
        // ==================================================

        const response =
            await fetch(
                `/3d/road-view/${encodeURIComponent(reportId)}`,
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                `Failed to load 3D scene data ` +
                `(HTTP ${response.status})`
            );
        }


        const data =
            await response.json();


        currentSceneData =
            data;


        console.info(
            "[RoadGuard 3D] Backend reconstruction:",
            data.reconstruction
        );


        // ==================================================
        // UPDATE UI INFORMATION
        // ==================================================

        updateSummaryPanels(
            data
        );

        updateReconstructionStatus(
            data
        );


        // ==================================================
        // CLEAR OLD MODEL
        // ==================================================

        clearGroup(
            roadGroup
        );

        clearGroup(
            potholeGroup
        );


        currentRoadObject =
            null;

        roadBoundingBox =
            null;


        // ==================================================
        // RECONSTRUCTION STATUS
        // ==================================================

        const isReconstruction =
            Boolean(
                data.viewer &&
                data.viewer.reconstruction_available
            );


        const reconstructionStatus =
            (
                data.viewer &&
                data.viewer.reconstruction_status
            ) ||
            (
                isReconstruction
                    ? "MESH_AVAILABLE"
                    : "NOT_STARTED"
            );


        // ==================================================
        // MODEL URLS
        // ==================================================

        const meshUrl =
            data.reconstruction &&
            data.reconstruction.mesh_url;


        const pointcloudUrl =
            data.reconstruction &&
            data.reconstruction.pointcloud_url;


        // ==================================================
        // VIEW MODE
        // ==================================================

        updateViewModeBadge(
            reconstructionStatus
        );


        // ==================================================
        // NO REAL RECONSTRUCTION
        // ==================================================

        if (!isReconstruction) {

            showLoading(
                false
            );


            const statusMessage =
                reconstructionStatus === "FAILED"
                    ? "COLMAP reconstruction failed for this report."
                    : "Real COLMAP reconstruction is unavailable for this report.";


            showError(
                "3D Reconstruction Unavailable",
                statusMessage
            );


            return;
        }


        // ==================================================
        // REAL MODEL URL
        // ==================================================

        let primaryModelUrl =
            meshUrl;


        // A point cloud is acceptable ONLY if
        // backend does not provide a mesh.
        if (!primaryModelUrl) {

            primaryModelUrl =
                pointcloudUrl;
        }


        // Backend should normally provide the URL.
        // This direct path is still a REAL file.
        if (!primaryModelUrl) {

            primaryModelUrl =
                `/results/photogrammetry/report_${reportId}/roadguard-road.ply`;
        }


        if (!primaryModelUrl) {

            throw new Error(
                "No real COLMAP reconstruction URL was provided."
            );
        }


        console.info(
            "[RoadGuard 3D] Loading real reconstruction:",
            primaryModelUrl
        );


        showLoading(
            true,
            "Loading real COLMAP 3D model..."
        );


        // ==================================================
        // LOAD REAL MODEL
        // ==================================================

        await loadModelGeometry(
            primaryModelUrl
        );


        // ==================================================
        // REAL 3D POTHOLE MARKERS ONLY
        // ==================================================

        renderPotholeMarkers(
            data.potholes || []
        );


        // ==================================================
        // FRAME CAMERA
        // ==================================================

        frameCameraOnScene();


        // Force correct dimensions after model/layout.
        resizeRendererToContainer();


        showLoading(
            false
        );


        console.info(
            "[RoadGuard 3D] REAL COLMAP MODEL LOADED",
            {
                reportId: String(reportId),

                url:
                    primaryModelUrl,

                vertices:
                    getCurrentVertexCount(),

                faces:
                    getCurrentFaceCount()
            }
        );

    } catch (error) {

        console.error(
            "[RoadGuard 3D] Reconstruction load error:",
            error
        );


        showLoading(
            false
        );


        showError(
            "3D Reconstruction Error",
            error?.message ||
            "Unable to load the real COLMAP reconstruction."
        );
    }
}


// ==========================================================
// MODEL STATISTICS
// ==========================================================

function getCurrentVertexCount() {

    if (
        !currentRoadObject ||
        !currentRoadObject.geometry ||
        !currentRoadObject.geometry.attributes ||
        !currentRoadObject.geometry.attributes.position
    ) {
        return null;
    }

    return currentRoadObject
        .geometry
        .attributes
        .position
        .count;
}


function getCurrentFaceCount() {

    if (
        !currentRoadObject ||
        !currentRoadObject.geometry
    ) {
        return null;
    }


    const geometry =
        currentRoadObject.geometry;


    if (
        geometry.index &&
        geometry.index.count >= 3
    ) {

        return (
            geometry.index.count / 3
        );
    }


    return 0;
}


// ==========================================================
// UPDATE RECONSTRUCTION STATUS UI
// ==========================================================

function updateReconstructionStatus(
    data
) {

    const report =
        data.report || {};

    const viewer =
        data.viewer || {};

    const reconstruction =
        data.reconstruction || {};


    if (reportIdEl) {

        const id =
            report.id ??
            activeReportId ??
            "--";

        reportIdEl.textContent =
            String(id);
    }


    if (reconstructionStateEl) {

        reconstructionStateEl.textContent =
            viewer.reconstruction_status ||
            reconstruction.status ||
            "--";
    }


    if (pointCountEl) {

        const count =
            reconstruction.vertex_count ??
            "--";

        pointCountEl.textContent =
            String(count);
    }


    if (meshStatusEl) {

        const available =
            Boolean(
                reconstruction.mesh_url ||
                viewer.mesh_available
            );

        meshStatusEl.textContent =
            available
                ? "AVAILABLE"
                : "NOT AVAILABLE";
    }
}


// ==========================================================
// VIEW MODE BADGE
// ==========================================================

function updateViewModeBadge(
    status
) {

    if (!viewModeBadge) {
        return;
    }


    if (
        status === "MESH_AVAILABLE"
    ) {

        viewModeBadge.textContent =
            "COLMAP RECONSTRUCTION";

        viewModeBadge.style.color =
            "#38bdf8";

        viewModeBadge.style.background =
            "rgba(56, 189, 248, 0.15)";

        viewModeBadge.style.borderColor =
            "rgba(56, 189, 248, 0.35)";


    } else if (
        status === "DENSE_POINT_CLOUD"
    ) {

        viewModeBadge.textContent =
            "DENSE POINT CLOUD";

        viewModeBadge.style.color =
            "#2dd4bf";

        viewModeBadge.style.background =
            "rgba(45, 212, 191, 0.15)";

        viewModeBadge.style.borderColor =
            "rgba(45, 212, 191, 0.35)";


    } else if (
        status === "SPARSE_ONLY"
    ) {

        viewModeBadge.textContent =
            "SPARSE ONLY";

        viewModeBadge.style.color =
            "#f59e0b";

        viewModeBadge.style.background =
            "rgba(245, 158, 11, 0.15)";

        viewModeBadge.style.borderColor =
            "rgba(245, 158, 11, 0.35)";


    } else if (
        status === "FAILED"
    ) {

        viewModeBadge.textContent =
            "RECONSTRUCTION FAILED";

        viewModeBadge.style.color =
            "#ef4444";

        viewModeBadge.style.background =
            "rgba(239, 68, 68, 0.15)";

        viewModeBadge.style.borderColor =
            "rgba(239, 68, 68, 0.35)";


    } else {

        viewModeBadge.textContent =
            "NOT AVAILABLE";

        viewModeBadge.style.color =
            "#94a3b8";

        viewModeBadge.style.background =
            "rgba(148, 163, 184, 0.15)";

        viewModeBadge.style.borderColor =
            "rgba(148, 163, 184, 0.35)";
    }
}


// ==========================================================
// REAL 3D RECONSTRUCTION LOADER
// PLY / OBJ / GLTF / GLB
// ==========================================================

async function loadModelGeometry(
    url
) {

    if (!url) {

        throw new Error(
            "Empty reconstruction URL."
        );
    }


    const lowerUrl =
        String(url)
            .split("?")[0]
            .toLowerCase();


    let object3D = null;


    // ======================================================
    // OBJ
    // ======================================================

    if (
        lowerUrl.endsWith(".obj")
    ) {

        const loader =
            new OBJLoader();


        object3D =
            await loader.loadAsync(
                url
            );


        normalizeLoadedObject(
            object3D
        );


        // ======================================================
        // GLTF / GLB
        // ======================================================

    } else if (
        lowerUrl.endsWith(".gltf") ||
        lowerUrl.endsWith(".glb")
    ) {

        const loader =
            new GLTFLoader();


        const gltf =
            await loader.loadAsync(
                url
            );


        object3D =
            gltf.scene;


        normalizeLoadedObject(
            object3D
        );


        // ======================================================
        // PLY
        // ======================================================

    } else {

        console.info(
            "[RoadGuard 3D] Loading PLY:",
            url
        );


        const loader =
            new PLYLoader();


        const geometry =
            await loader.loadAsync(
                url
            );


        // --------------------------------------------------
        // VALIDATION
        // --------------------------------------------------

        if (
            !geometry ||
            !geometry.attributes ||
            !geometry.attributes.position ||
            geometry.attributes.position.count === 0
        ) {

            throw new Error(
                "Loaded PLY contains no vertex positions."
            );
        }


        // --------------------------------------------------
        // BOUNDING BOX
        // --------------------------------------------------

        geometry.computeBoundingBox();


        const box =
            geometry.boundingBox;


        if (!box) {

            throw new Error(
                "PLY geometry has no bounding box."
            );
        }


        const center =
            new THREE.Vector3();


        const size =
            new THREE.Vector3();


        box.getCenter(
            center
        );


        box.getSize(
            size
        );


        const maxDim =
            Math.max(
                size.x,
                size.y,
                size.z
            );


        if (
            !Number.isFinite(maxDim) ||
            maxDim <= 0
        ) {

            throw new Error(
                "PLY geometry has invalid dimensions."
            );
        }


        // --------------------------------------------------
        // VIEW SCALE
        //
        // This changes only the viewer transform.
        // It does NOT modify the source COLMAP geometry.
        // --------------------------------------------------

        const targetSize =
            45.0;


        const scale =
            targetSize /
            maxDim;


        // --------------------------------------------------
        // CHECK REAL FACES
        // --------------------------------------------------

        const hasFaces =
            geometry.index !== null &&
            geometry.index !== undefined &&
            geometry.index.count >= 3;


        const hasColor =
            geometry.hasAttribute(
                "color"
            );


        console.info(
            "[RoadGuard 3D] PLY geometry:",
            {
                vertices:
                    geometry
                        .attributes
                        .position
                        .count,

                faces:
                    hasFaces
                        ? geometry.index.count / 3
                        : 0,

                hasColor:
                    hasColor,

                dimensions: {
                    x: size.x,
                    y: size.y,
                    z: size.z
                }
            }
        );


        // --------------------------------------------------
        // REAL MESH
        // --------------------------------------------------

        if (hasFaces) {

            geometry.computeVertexNormals();


            const material =
                new THREE.MeshStandardMaterial({
                    vertexColors:
                        hasColor,

                    color:
                        0xffffff,

                    roughness:
                        0.85,

                    metalness:
                        0.08,

                    side:
                        THREE.DoubleSide
                });


            object3D =
                new THREE.Mesh(
                    geometry,
                    material
                );


            object3D.castShadow = true;

            object3D.receiveShadow = true;


            // --------------------------------------------------
            // REAL POINT CLOUD
            // --------------------------------------------------

        } else {

            const pointMaterial =
                new THREE.PointsMaterial({

                    size:
                        0.65,

                    vertexColors:
                        hasColor,

                    color:
                        hasColor
                            ? 0xffffff
                            : 0x93c5fd,

                    sizeAttenuation:
                        true
                });


            object3D =
                new THREE.Points(
                    geometry,
                    pointMaterial
                );
        }


        // --------------------------------------------------
        // CENTER + SCALE REAL GEOMETRY
        // --------------------------------------------------

        object3D.scale.setScalar(
            scale
        );


        object3D.position.set(
            -center.x * scale,
            -center.y * scale,
            -center.z * scale
        );


        roadBoundingBox = {

            min:
                box.min.clone(),

            max:
                box.max.clone(),

            center:
                center.clone(),

            size:
                size.clone(),

            scale:
                scale,

            offset:
                object3D.position.clone()
        };
    }


    // ======================================================
    // VALIDATION
    // ======================================================

    if (!object3D) {

        throw new Error(
            "COLMAP reconstruction produced no renderable object."
        );
    }


    // ======================================================
    // ADD REAL OBJECT
    // ======================================================

    roadGroup.add(
        object3D
    );


    currentRoadObject =
        object3D;


    console.info(
        "[RoadGuard 3D] Loaded REAL COLMAP 3D model:",
        url
    );
}


// ==========================================================
// NORMALIZE OBJ / GLTF
// ==========================================================

function normalizeLoadedObject(
    object3D
) {

    const box =
        new THREE.Box3().setFromObject(
            object3D
        );


    const center =
        new THREE.Vector3();


    const size =
        new THREE.Vector3();


    box.getCenter(
        center
    );


    box.getSize(
        size
    );


    const maxDim =
        Math.max(
            size.x,
            size.y,
            size.z
        );


    if (
        !Number.isFinite(maxDim) ||
        maxDim <= 0
    ) {

        throw new Error(
            "Loaded reconstruction has invalid dimensions."
        );
    }


    const scale =
        45.0 /
        maxDim;


    object3D.scale.setScalar(
        scale
    );


    object3D.position.set(
        -center.x * scale,
        -center.y * scale,
        -center.z * scale
    );


    roadBoundingBox = {

        min:
            box.min.clone(),

        max:
            box.max.clone(),

        center:
            center.clone(),

        size:
            size.clone(),

        scale:
            scale,

        offset:
            object3D.position.clone()
    };
}


// ==========================================================
// POTHOLE MARKERS
//
// IMPORTANT:
// Markers are rendered ONLY when backend supplies
// a real position_3d.
//
// There is deliberately NO image-space fallback.
// ==========================================================

function getSeverityColorHex(
    severity
) {

    switch (
    String(
        severity || ""
    ).toUpperCase()
    ) {

        case "CRITICAL":
            return 0xef4444;

        case "HIGH":
            return 0xf97316;

        case "MODERATE":
            return 0xf59e0b;

        case "LOW":
        default:
            return 0x22c55e;
    }
}


// ==========================================================
// PARSE REAL 3D POSITION
// ==========================================================

function parseReal3DPosition(
    pothole
) {

    const pos3d =
        pothole &&
        pothole.position_3d;


    if (!pos3d) {
        return null;
    }


    let x;
    let y;
    let z;


    if (
        typeof pos3d.x === "number" &&
        typeof pos3d.y === "number" &&
        typeof pos3d.z === "number"
    ) {

        x = pos3d.x;
        y = pos3d.y;
        z = pos3d.z;


    } else if (
        Array.isArray(pos3d) &&
        pos3d.length >= 3 &&
        typeof pos3d[0] === "number" &&
        typeof pos3d[1] === "number" &&
        typeof pos3d[2] === "number"
    ) {

        x = pos3d[0];
        y = pos3d[1];
        z = pos3d[2];

    } else {

        return null;
    }


    if (
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        !Number.isFinite(z)
    ) {

        return null;
    }


    return {
        x,
        y,
        z
    };
}


// ==========================================================
// RENDER POTHOLE MARKERS
// ==========================================================

function renderPotholeMarkers(
    potholes
) {

    clearGroup(
        potholeGroup
    );


    if (
        !Array.isArray(potholes) ||
        potholes.length === 0
    ) {

        console.info(
            "[RoadGuard 3D] No pothole records returned."
        );

        return;
    }


    if (!roadBoundingBox) {

        console.warn(
            "[RoadGuard 3D] Cannot place 3D markers without model bounds."
        );

        return;
    }


    let real3DMarkerCount = 0;


    potholes.forEach(
        (pothole, index) => {

            const realPosition =
                parseReal3DPosition(
                    pothole
                );


            // ------------------------------------------------
            // NO FAKE FALLBACK
            // ------------------------------------------------

            if (!realPosition) {

                console.warn(
                    "[RoadGuard 3D] Skipping pothole without real position_3d:",
                    {
                        index,
                        pothole
                    }
                );

                return;
            }


            const posX =
                (
                    realPosition.x -
                    roadBoundingBox.center.x
                ) *
                roadBoundingBox.scale;


            const posY =
                (
                    realPosition.y -
                    roadBoundingBox.center.y
                ) *
                roadBoundingBox.scale +
                0.35;


            const posZ =
                (
                    realPosition.z -
                    roadBoundingBox.center.z
                ) *
                roadBoundingBox.scale;


            const colorHex =
                getSeverityColorHex(
                    pothole.severity
                );


            // ------------------------------------------------
            // MARKER
            // ------------------------------------------------

            const markerGeo =
                new THREE.SphereGeometry(
                    0.55,
                    20,
                    20
                );


            const markerMat =
                new THREE.MeshStandardMaterial({

                    color:
                        colorHex,

                    emissive:
                        colorHex,

                    emissiveIntensity:
                        0.45,

                    roughness:
                        0.3,

                    metalness:
                        0.2
                });


            const marker =
                new THREE.Mesh(
                    markerGeo,
                    markerMat
                );


            marker.position.set(
                posX,
                posY,
                posZ
            );


            marker.userData = {

                pothole:
                    pothole,

                index:
                    index,

                baseColor:
                    colorHex,

                worldPos:
                    new THREE.Vector3(
                        posX,
                        posY,
                        posZ
                    )
            };


            // ------------------------------------------------
            // PIN
            // ------------------------------------------------

            const pinPoints = [

                new THREE.Vector3(
                    posX,
                    posY - 0.5,
                    posZ
                ),

                new THREE.Vector3(
                    posX,
                    posY + 1.8,
                    posZ
                )
            ];


            const pinGeo =
                new THREE.BufferGeometry()
                    .setFromPoints(
                        pinPoints
                    );


            const pinMat =
                new THREE.LineBasicMaterial({
                    color:
                        colorHex,

                    transparent:
                        true,

                    opacity:
                        0.7
                });


            const pin =
                new THREE.Line(
                    pinGeo,
                    pinMat
                );


            potholeGroup.add(
                marker
            );

            potholeGroup.add(
                pin
            );


            real3DMarkerCount++;
        }
    );


    console.info(
        "[RoadGuard 3D] Real 3D pothole markers:",
        real3DMarkerCount,
        "/",
        potholes.length
    );
}


// ==========================================================
// INTERACTION
// ==========================================================

function initInteractions() {

    if (!renderer) {
        return;
    }


    renderer.domElement.addEventListener(
        "click",
        onCanvasClick
    );


    renderer.domElement.addEventListener(
        "pointermove",
        onCanvasPointerMove
    );


    if (retryBtn) {

        retryBtn.addEventListener(
            "click",
            () => {

                if (activeReportId) {

                    loadReport(
                        activeReportId
                    );
                }
            }
        );
    }


    if (focusSelectedBtn) {

        focusSelectedBtn.addEventListener(
            "click",
            () => {

                if (selectedMarker) {

                    focusOnMarker(
                        selectedMarker
                    );
                }
            }
        );
    }
}


// ==========================================================
// POINTER MOVE
// ==========================================================

function onCanvasPointerMove(
    event
) {

    if (
        !renderer ||
        !camera ||
        !raycaster
    ) {
        return;
    }


    const rect =
        renderer.domElement.getBoundingClientRect();


    if (
        rect.width <= 0 ||
        rect.height <= 0
    ) {

        return;
    }


    mouse.x =
        (
            (event.clientX - rect.left) /
            rect.width
        ) *
        2 -
        1;


    mouse.y =
        -(
            (event.clientY - rect.top) /
            rect.height
        ) *
        2 +
        1;


    raycaster.setFromCamera(
        mouse,
        camera
    );


    const meshes =
        potholeGroup.children.filter(
            child =>
                child.isMesh
        );


    const intersects =
        raycaster.intersectObjects(
            meshes,
            false
        );


    renderer.domElement.style.cursor =
        intersects.length > 0
            ? "pointer"
            : "default";
}


// ==========================================================
// CLICK
// ==========================================================

function onCanvasClick(
    event
) {

    if (
        !renderer ||
        !camera ||
        !raycaster
    ) {
        return;
    }


    const rect =
        renderer.domElement.getBoundingClientRect();


    if (
        rect.width <= 0 ||
        rect.height <= 0
    ) {

        return;
    }


    mouse.x =
        (
            (event.clientX - rect.left) /
            rect.width
        ) *
        2 -
        1;


    mouse.y =
        -(
            (event.clientY - rect.top) /
            rect.height
        ) *
        2 +
        1;


    raycaster.setFromCamera(
        mouse,
        camera
    );


    const meshes =
        potholeGroup.children.filter(
            child =>
                child.isMesh
        );


    const intersects =
        raycaster.intersectObjects(
            meshes,
            false
        );


    if (
        intersects.length > 0
    ) {

        selectMarker(
            intersects[0].object
        );
    }
}


// ==========================================================
// SELECT MARKER
// ==========================================================

function selectMarker(
    marker
) {

    if (
        selectedMarker &&
        selectedMarker.material
    ) {

        selectedMarker.scale.set(
            1,
            1,
            1
        );


        selectedMarker.material
            .emissiveIntensity =
            0.45;
    }


    selectedMarker =
        marker;


    if (!marker) {

        clearSelection();

        return;
    }


    marker.scale.set(
        1.4,
        1.4,
        1.4
    );


    if (marker.material) {

        marker.material
            .emissiveIntensity =
            0.95;
    }


    const pothole =
        marker.userData.pothole;


    const index =
        marker.userData.index;


    const potholeId =
        pothole.pothole_id ||
        pothole.id ||
        (index + 1);


    if (selectedObjectEl) {

        selectedObjectEl.textContent =
            `Pothole #${potholeId}`;
    }


    if (noSelectionEl) {

        noSelectionEl.style.display =
            "none";
    }


    if (potholeDetailsEl) {

        potholeDetailsEl.classList.remove(
            "hidden"
        );
    }


    if (detailIdEl) {

        detailIdEl.textContent =
            `P-${String(
                potholeId
            ).padStart(
                3,
                "0"
            )}`;
    }


    const severity =
        String(
            pothole.severity ||
            "LOW"
        ).toUpperCase();


    if (detailSeverityEl) {

        detailSeverityEl.textContent =
            severity;


        detailSeverityEl.className =
            "severity-badge";


        if (
            severity === "CRITICAL" ||
            severity === "HIGH"
        ) {

            detailSeverityEl.classList.add(
                "high"
            );

        } else if (
            severity === "MODERATE"
        ) {

            detailSeverityEl.classList.add(
                "medium"
            );

        } else {

            detailSeverityEl.classList.add(
                "low"
            );
        }
    }


    const confidence =
        Number(
            pothole.confidence || 0
        );


    if (detailConfidenceEl) {

        detailConfidenceEl.textContent =
            `${(
                confidence * 100
            ).toFixed(1)}%`;
    }


    const widthValue =
        pothole.width != null
            ? `${(
                Number(
                    pothole.width
                ) * 100
            ).toFixed(1)} cm`
            : "--";


    if (detailWidthEl) {

        detailWidthEl.textContent =
            widthValue;
    }


    const depthValue =
        pothole.depth_m != null
            ? `${(
                Number(
                    pothole.depth_m
                ) * 100
            ).toFixed(1)} cm`
            : "--";


    if (detailDepthEl) {

        detailDepthEl.textContent =
            depthValue;
    }


    if (detailPositionEl) {

        const position =
            marker.userData.worldPos;


        detailPositionEl.textContent =
            `X: ${position.x.toFixed(2)}, ` +
            `Y: ${position.y.toFixed(2)}, ` +
            `Z: ${position.z.toFixed(2)}`;
    }
}


// ==========================================================
// CLEAR SELECTION
// ==========================================================

function clearSelection() {

    selectedMarker =
        null;


    if (selectedObjectEl) {

        selectedObjectEl.textContent =
            "None";
    }


    if (noSelectionEl) {

        noSelectionEl.style.display =
            "block";
    }


    if (potholeDetailsEl) {

        potholeDetailsEl.classList.add(
            "hidden"
        );
    }
}


// ==========================================================
// FOCUS MARKER
// ==========================================================

function focusOnMarker(
    marker
) {

    if (
        !marker ||
        !controls ||
        !camera
    ) {
        return;
    }


    const position =
        marker.userData.worldPos;


    controls.target.copy(
        position
    );


    camera.position.set(
        position.x + 4,
        position.y + 4,
        position.z + 6
    );


    controls.update();
}


// ==========================================================
// FRAME CAMERA
// ==========================================================

function frameCameraOnScene() {

    if (
        !camera ||
        !controls
    ) {
        return;
    }


    const box =
        new THREE.Box3();


    let hasObjects =
        false;


    // ------------------------------------------------------
    // REAL COLMAP MODEL
    // ------------------------------------------------------

    if (
        roadGroup &&
        roadGroup.children.length > 0
    ) {

        box.expandByObject(
            roadGroup
        );

        hasObjects = true;
    }


    // ------------------------------------------------------
    // REAL 3D MARKERS
    // ------------------------------------------------------

    if (
        potholeGroup &&
        potholeGroup.children.length > 0
    ) {

        box.expandByObject(
            potholeGroup
        );

        hasObjects = true;
    }


    if (!hasObjects) {

        camera.position.set(
            0,
            12,
            28
        );


        controls.target.set(
            0,
            0,
            0
        );


        controls.update();

        return;
    }


    const center =
        new THREE.Vector3();


    const size =
        new THREE.Vector3();


    box.getCenter(
        center
    );


    box.getSize(
        size
    );


    const maxDim =
        Math.max(
            size.x,
            size.y,
            size.z,
            15
        );


    controls.target.copy(
        center
    );


    camera.position.set(
        center.x +
        maxDim * 0.8,

        center.y +
        maxDim * 0.7,

        center.z +
        maxDim * 1.0
    );


    camera.near =
        Math.max(
            0.01,
            maxDim / 1000
        );


    camera.far =
        Math.max(
            5000,
            maxDim * 100
        );


    camera.updateProjectionMatrix();


    controls.update();
}


// ==========================================================
// VIEWER BUTTONS
// ==========================================================

function setupViewerButtons() {

    const perspectiveBtn =
        document.getElementById(
            "perspectiveBtn"
        );


    const topBtn =
        document.getElementById(
            "topBtn"
        );


    const resetBtn =
        document.getElementById(
            "resetBtn"
        );


    const focusAllBtn =
        document.getElementById(
            "focusAllBtn"
        );


    if (perspectiveBtn) {

        perspectiveBtn.addEventListener(
            "click",
            () => {

                frameCameraOnScene();
            }
        );
    }


    if (topBtn) {

        topBtn.addEventListener(
            "click",
            () => {

                if (
                    !controls ||
                    !camera
                ) {
                    return;
                }


                const target =
                    controls.target.clone();


                camera.position.set(
                    target.x,
                    target.y + 40,
                    target.z + 0.001
                );


                controls.update();
            }
        );
    }


    if (resetBtn) {

        resetBtn.addEventListener(
            "click",
            () => {

                clearSelection();

                frameCameraOnScene();
            }
        );
    }


    if (focusAllBtn) {

        focusAllBtn.addEventListener(
            "click",
            () => {

                frameCameraOnScene();
            }
        );
    }
}


// ==========================================================
// SUMMARY PANELS
// ==========================================================

function updateSummaryPanels(
    data
) {

    const potholes =
        Array.isArray(
            data.potholes
        )
            ? data.potholes
            : [];


    const count =
        data.report &&
            data.report.pothole_count != null
            ? data.report.pothole_count
            : potholes.length;


    if (totalPotholesEl) {

        totalPotholesEl.textContent =
            String(count);
    }


    const confidence =
        data.report &&
            data.report.confidence != null
            ? Number(
                data.report.confidence
            )
            : 0;


    if (confidenceEl) {

        confidenceEl.textContent =
            confidence > 0
                ? `${(
                    confidence * 100
                ).toFixed(1)}%`
                : "--";
    }


    const severity =
        (
            data.report &&
            data.report.severity
        ) ||
        "LOW";


    if (roadConditionEl) {

        roadConditionEl.textContent =
            String(
                severity
            ).toUpperCase();


        const color =
            getSeverityColorHex(
                severity
            );


        if (
            color === 0xef4444
        ) {

            roadConditionEl.style.color =
                "#ef4444";

        } else if (
            color === 0xf97316
        ) {

            roadConditionEl.style.color =
                "#f97316";

        } else if (
            color === 0xf59e0b
        ) {

            roadConditionEl.style.color =
                "#f59e0b";

        } else {

            roadConditionEl.style.color =
                "#22c55e";
        }
    }
}


// ==========================================================
// LOADING
// ==========================================================

function showLoading(
    show,
    message
) {

    if (!loadingElement) {
        return;
    }


    if (show) {

        loadingElement.classList.remove(
            "hidden"
        );


        loadingElement.style.display =
            "flex";


        loadingElement.style.opacity =
            "1";


        if (loadingText) {

            loadingText.textContent =
                message ||
                "Loading 3D scene...";
        }


    } else {

        loadingElement.classList.add(
            "hidden"
        );


        setTimeout(
            () => {

                if (
                    loadingElement.classList.contains(
                        "hidden"
                    )
                ) {

                    loadingElement.style.display =
                        "none";
                }

            },
            400
        );
    }
}


// ==========================================================
// ERROR
// ==========================================================

function showError(
    title,
    detail
) {

    if (!errorOverlay) {
        return;
    }


    errorOverlay.classList.remove(
        "hidden"
    );


    errorOverlay.style.display =
        "flex";


    if (errorTitle) {

        errorTitle.textContent =
            title ||
            "Error";
    }


    if (errorDetail) {

        errorDetail.textContent =
            detail ||
            "Could not complete operation.";
    }
}


function hideError() {

    if (!errorOverlay) {
        return;
    }


    errorOverlay.classList.add(
        "hidden"
    );


    errorOverlay.style.display =
        "none";
}


// ==========================================================
// CLEAR THREE.JS GROUP
// ==========================================================

function clearGroup(
    group
) {

    if (!group) {
        return;
    }


    while (
        group.children.length > 0
    ) {

        const object =
            group.children[0];


        group.remove(
            object
        );


        if (
            object.geometry
        ) {

            object.geometry.dispose();
        }


        if (
            object.material
        ) {

            if (
                Array.isArray(
                    object.material
                )
            ) {

                object.material.forEach(
                    material => {

                        if (
                            material &&
                            material.dispose
                        ) {

                            material.dispose();
                        }
                    }
                );

            } else if (
                object.material.dispose
            ) {

                object.material.dispose();
            }
        }
    }
}


// ==========================================================
// ANIMATION LOOP
// ==========================================================

function animate() {

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
// DEBUG INFORMATION
// ==========================================================

console.info(
    "[RoadGuard 3D] Canonical viewer initialized."
);

console.info(
    "[RoadGuard 3D] Rendering source: REAL COLMAP reconstruction only."
);

console.info(
    "[RoadGuard 3D] Procedural/fallback road geometry: DISABLED."
);