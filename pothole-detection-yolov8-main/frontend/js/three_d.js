// ==========================================================
// ROADGUARD AI
// 3D VISUALIZATION
// FILE: frontend/js/three_d.js
// ==========================================================


// ==========================================================
// THREE.JS IMPORTS
// ==========================================================

// Using ESM CDN versions to avoid browser module errors

import * as THREE from
    "https://esm.sh/three@0.160.0";


import {
    OrbitControls
} from
    "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";


// ==========================================================
// GLOBALS
// ==========================================================

let scene;

let camera;

let renderer;

let controls;

let potholeGroup;

let animationId;


// ==========================================================
// INITIALIZE
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    initializeThreeViewer
);


async function initializeThreeViewer() {

    console.log(
        "🚀 Initializing RoadGuard AI 3D Visualization..."
    );


    try {

        createThreeScene();

        initializeControls();

        animate();

        await loadThreeData();

    }

    catch (error) {

        console.error(
            "❌ 3D initialization error:",
            error
        );


        updateThreeStatus(
            `❌ Failed to initialize: ${error.message}`
        );

    }

}


// ==========================================================
// CREATE THREE.JS SCENE
// ==========================================================

function createThreeScene() {

    const container =
        document.getElementById(
            "threeContainer"
        );


    if (!container) {

        throw new Error(
            "threeContainer not found in three_d.html"
        );

    }


    // Clear previous canvas

    container.innerHTML = "";


    // ======================================================
    // SCENE
    // ======================================================

    scene =
        new THREE.Scene();


    scene.background =
        new THREE.Color(
            0x0f172a
        );


    // ======================================================
    // CAMERA
    // ======================================================

    const width =
        container.clientWidth || 800;


    const height =
        container.clientHeight || 500;


    camera =
        new THREE.PerspectiveCamera(

            60,

            width / height,

            0.1,

            1000

        );


    camera.position.set(

        10,

        10,

        15

    );


    // ======================================================
    // RENDERER
    // ======================================================

    renderer =
        new THREE.WebGLRenderer({

            antialias: true

        });


    renderer.setSize(

        width,

        height

    );


    renderer.setPixelRatio(

        Math.min(
            window.devicePixelRatio,
            2
        )

    );


    renderer.shadowMap.enabled =
        true;


    container.appendChild(
        renderer.domElement
    );


    // ======================================================
    // ORBIT CONTROLS
    // ======================================================

    controls =
        new OrbitControls(

            camera,

            renderer.domElement

        );


    controls.enableDamping =
        true;


    controls.dampingFactor =
        0.05;


    controls.target.set(

        0,

        0,

        0

    );


    // ======================================================
    // CREATE SCENE ELEMENTS
    // ======================================================

    createLighting();

    createRoadSurface();

    createGrid();

    createAxes();

    createPotholeGroup();


    // ======================================================
    // RESIZE
    // ======================================================

    window.addEventListener(

        "resize",

        resizeThreeViewer

    );


    console.log(
        "✅ Three.js scene created successfully"
    );

}


// ==========================================================
// CREATE LIGHTING
// ==========================================================

function createLighting() {


    // Ambient Light

    const ambient =
        new THREE.AmbientLight(

            0xffffff,

            1.8

        );


    scene.add(
        ambient
    );


    // Directional Light

    const directional =
        new THREE.DirectionalLight(

            0xffffff,

            2.5

        );


    directional.position.set(

        10,

        20,

        10

    );


    directional.castShadow =
        true;


    scene.add(
        directional
    );


    // Additional light

    const directionalTwo =
        new THREE.DirectionalLight(

            0xffffff,

            1.2

        );


    directionalTwo.position.set(

        -10,

        10,

        -10

    );


    scene.add(
        directionalTwo
    );

}


// ==========================================================
// CREATE ROAD SURFACE
// ==========================================================

function createRoadSurface() {


    const geometry =
        new THREE.PlaneGeometry(

            40,

            40

        );


    const material =
        new THREE.MeshStandardMaterial({

            color: 0x374151,

            roughness: 0.9,

            metalness: 0.05

        });


    const road =
        new THREE.Mesh(

            geometry,

            material

        );


    road.rotation.x =
        -Math.PI / 2;


    road.receiveShadow =
        true;


    scene.add(
        road
    );

}


// ==========================================================
// CREATE GRID
// ==========================================================

function createGrid() {


    const grid =
        new THREE.GridHelper(

            40,

            40,

            0x64748b,

            0x475569

        );


    grid.position.y =
        0.02;


    scene.add(
        grid
    );

}


// ==========================================================
// CREATE AXES
// ==========================================================

function createAxes() {


    const axes =
        new THREE.AxesHelper(
            5
        );


    scene.add(
        axes
    );

}


// ==========================================================
// CREATE POTHOLE GROUP
// ==========================================================

function createPotholeGroup() {


    potholeGroup =
        new THREE.Group();


    scene.add(
        potholeGroup
    );

}


// ==========================================================
// LOAD BACKEND DATA
// ==========================================================

async function loadThreeData() {


    updateThreeStatus(
        "⏳ Loading 3D scene..."
    );


    try {


        console.log(
            "📡 Loading:",
            API_ENDPOINTS.threeScene
        );


        const response =
            await fetch(
                API_ENDPOINTS.threeScene
            );


        if (!response.ok) {

            throw new Error(
                `Server error: ${response.status}`
            );

        }


        const data =
            await response.json();


        console.log(
            "📦 3D Scene Data:",
            data
        );


        const objects =
            extractSceneObjects(
                data
            );


        renderThreeObjects(
            objects
        );


        await loadThreeSummary();


        if (objects.length === 0) {

            updateThreeStatus(
                "⚠️ No pothole data available"
            );

        }

        else {

            updateThreeStatus(
                `✅ 3D visualization loaded — ${objects.length} locations`
            );

        }


        console.log(
            "✅ 3D objects rendered:",
            objects.length
        );

    }


    catch (error) {


        console.error(
            "❌ Error loading 3D data:",
            error
        );


        updateThreeStatus(
            `❌ ${error.message}`
        );

    }

}


// ==========================================================
// EXTRACT OBJECTS
// ==========================================================

function extractSceneObjects(data) {


    if (Array.isArray(data)) {

        return data;

    }


    if (
        data &&
        Array.isArray(data.objects)
    ) {

        return data.objects;

    }


    if (
        data &&
        Array.isArray(data.scene)
    ) {

        return data.scene;

    }


    if (
        data &&
        Array.isArray(data.data)
    ) {

        return data.data;

    }


    return [];

}


// ==========================================================
// CLEAR POTHOLES
// ==========================================================

function clearPotholes() {


    while (
        potholeGroup.children.length > 0
    ) {


        const object =
            potholeGroup.children[0];


        potholeGroup.remove(
            object
        );


        if (object.geometry) {

            object.geometry.dispose();

        }


        if (object.material) {

            object.material.dispose();

        }

    }

}


// ==========================================================
// RENDER 3D OBJECTS
// ==========================================================

function renderThreeObjects(objects) {


    clearPotholes();


    objects.forEach(

        (
            object,
            index
        ) => {


            // ==================================================
            // GET POSITION
            // ==================================================

            let x =
                Number(
                    object.x
                );


            let z =
                Number(
                    object.z
                );


            // Fallback if x/z don't exist

            if (Number.isNaN(x)) {

                x =
                    (index - objects.length / 2) * 3;

            }


            if (Number.isNaN(z)) {

                z =
                    0;

            }


            // ==================================================
            // GET DATA
            // ==================================================

            const severity =
                String(
                    object.severity || "LOW"
                ).toUpperCase();


            const potholeCount =
                Number(
                    object.pothole_count || 0
                );


            const size =
                getPotholeSize(
                    severity
                );


            // ==================================================
            // CREATE POTHOLE
            // ==================================================

            const geometry =
                new THREE.SphereGeometry(

                    size,

                    32,

                    20

                );


            const material =
                new THREE.MeshStandardMaterial({

                    color:
                        getThreeColor(
                            severity
                        ),

                    roughness: 0.7,

                    metalness: 0.15

                });


            const pothole =
                new THREE.Mesh(

                    geometry,

                    material

                );


            pothole.position.set(

                x,

                0.15,

                z

            );


            // Flatten sphere to look like a pothole

            pothole.scale.y =
                0.25;


            pothole.castShadow =
                true;


            pothole.receiveShadow =
                true;


            // ==================================================
            // STORE DATA
            // ==================================================

            pothole.userData =
                object;


            // ==================================================
            // ADD TO SCENE
            // ==================================================

            potholeGroup.add(
                pothole
            );


            // ==================================================
            // ADD MARKER RING
            // ==================================================

            addPotholeRing(

                x,

                z,

                severity,

                size

            );


            console.log(

                `🕳️ Pothole ${index + 1}:`,

                {

                    x,

                    z,

                    severity,

                    potholeCount

                }

            );

        }

    );


    // ======================================================
    // UPDATE TOTAL OBJECTS
    // ======================================================

    const totalObjects =
        document.getElementById(
            "totalObjects"
        );


    if (totalObjects) {

        totalObjects.textContent =
            objects.length;

    }


    // ======================================================
    // CENTER CAMERA
    // ======================================================

    if (objects.length > 0) {

        controls.target.set(

            0,

            0,

            0

        );


        controls.update();

    }

}


// ==========================================================
// ADD POTHOLE RING
// ==========================================================

function addPotholeRing(

    x,

    z,

    severity,

    size

) {


    const geometry =
        new THREE.RingGeometry(

            size * 1.2,

            size * 1.5,

            32

        );


    const material =
        new THREE.MeshBasicMaterial({

            color:
                getThreeColor(
                    severity
                ),

            side:
                THREE.DoubleSide

        });


    const ring =
        new THREE.Mesh(

            geometry,

            material

        );


    ring.rotation.x =
        -Math.PI / 2;


    ring.position.set(

        x,

        0.03,

        z

    );


    potholeGroup.add(
        ring
    );

}


// ==========================================================
// GET THREE COLOR
// ==========================================================

function getThreeColor(severity) {


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

        colors[severity] ||

        0x64748b

    );

}


// ==========================================================
// GET POTHOLE SIZE
// ==========================================================

function getPotholeSize(severity) {


    const sizes = {

        LOW:
            0.5,

        MODERATE:
            0.7,

        HIGH:
            0.9,

        CRITICAL:
            1.2

    };


    return (

        sizes[severity] ||

        0.5

    );

}


// ==========================================================
// LOAD SUMMARY
// ==========================================================

async function loadThreeSummary() {


    try {


        const response =
            await fetch(
                API_ENDPOINTS.threeSummary
            );


        if (!response.ok) {

            throw new Error(
                "Unable to load summary"
            );

        }


        const data =
            await response.json();


        console.log(
            "📊 3D Summary:",
            data
        );


        const totalPotholes =
            document.getElementById(
                "total3DPotholes"
            );


        if (totalPotholes) {

            totalPotholes.textContent =

                data.total_potholes ??

                "--";

        }


        const criticalAreas =
            document.getElementById(
                "critical3D"
            );


        if (criticalAreas) {

            criticalAreas.textContent =

                data.critical_hotspots ??

                data.critical ??

                "--";

        }

    }


    catch (error) {

        console.warn(

            "⚠️ Summary unavailable:",

            error

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
// RESET CAMERA
// ==========================================================

function resetCamera() {


    camera.position.set(

        10,

        10,

        15

    );


    controls.target.set(

        0,

        0,

        0

    );


    controls.update();


    updateThreeStatus(
        "🎯 Camera reset"
    );

}


// ==========================================================
// INITIALIZE BUTTON CONTROLS
// ==========================================================

function initializeControls() {


    const reloadButton =
        document.getElementById(
            "reloadSceneBtn"
        );


    if (reloadButton) {

        reloadButton.addEventListener(

            "click",

            loadThreeData

        );

    }


    const resetButton =
        document.getElementById(
            "resetCameraBtn"
        );


    if (resetButton) {

        resetButton.addEventListener(

            "click",

            resetCamera

        );

    }

}


// ==========================================================
// RESIZE
// ==========================================================

function resizeThreeViewer() {


    const container =
        document.getElementById(
            "threeContainer"
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
        width === 0 ||
        height === 0
    ) {

        return;

    }


    camera.aspect =
        width / height;


    camera.updateProjectionMatrix();


    renderer.setSize(

        width,

        height

    );

}


// ==========================================================
// UPDATE STATUS
// ==========================================================

function updateThreeStatus(message) {


    const status =
        document.getElementById(
            "threeStatus"
        );


    if (status) {

        status.textContent =
            message;

    }


    console.log(
        "3D Status:",
        message
    );

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

    }

);