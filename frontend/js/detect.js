// ==========================================================
// ROADGUARD AI
// DETECTION CONTROLLER
//
// REAL MEDIA + REAL GPS + REAL YOLO LIVE DETECTION
//
// Features:
// - Image upload detection
// - Video upload detection
// - Camera capture
// - Camera recording
// - Real browser GPS tracking
// - GPS attached to detection uploads
// - Live YOLO WebSocket detection
// - Leaflet live-map integration
// - No fake GPS
// - No fake detection
// - No custom routing
// ==========================================================


// ==========================================================
// STATE
// ==========================================================

let selectedImageFile = null;

let selectedVideoFile = null;

let cameraStream = null;

let mediaRecorder = null;

let recordedChunks = [];

let recordedVideoBlob = null;

let capturedImages = [];


// ==========================================================
// REAL GPS STATE
// ==========================================================

let latestGPS = {
    latitude: null,
    longitude: null,
    accuracy: null
};

let gpsWatchId = null;


// ==========================================================
// LIVE DETECTION STATE
// ==========================================================

let liveDetectionSocket = null;

let liveDetectionActive = false;

let liveDetectionInterval = null;

let liveDetectionCanvas = null;

let liveDetectionContext = null;

let lastLiveFrameSent = 0;

let liveSocketReconnectTimer = null;

let liveFrameEncoding = false;


// Approximately 2 frames per second.
const LIVE_DETECTION_INTERVAL_MS = 500;


// ==========================================================
// DOM READY
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        initializeDetectionPage();

    }
);


// ==========================================================
// INITIALIZE PAGE
// ==========================================================

function initializeDetectionPage() {

    initializeModeTabs();

    initializeImageUpload();

    initializeVideoUpload();

    initializeCamera();

    initializeClearButton();

    startGPSTracking();

}


// ==========================================================
// GPS TRACKING
// ==========================================================

function startGPSTracking() {

    if (!navigator.geolocation) {

        console.warn(
            "Geolocation is not supported by this browser."
        );

        updateGPSStatus(
            "GPS: Browser location is unavailable"
        );

        return;
    }


    if (gpsWatchId !== null) {

        return;

    }


    updateGPSStatus(
        "GPS: Requesting location..."
    );


    gpsWatchId =
        navigator.geolocation.watchPosition(

            position => {

                if (
                    !position ||
                    !position.coords
                ) {

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


                // --------------------------------------------------
                // VALIDATE REAL GPS
                // --------------------------------------------------

                if (
                    !Number.isFinite(latitude) ||
                    !Number.isFinite(longitude) ||
                    latitude < -90 ||
                    latitude > 90 ||
                    longitude < -180 ||
                    longitude > 180 ||
                    (
                        latitude === 0 &&
                        longitude === 0
                    )
                ) {

                    console.warn(
                        "Invalid GPS position received."
                    );

                    updateGPSStatus(
                        "GPS: Invalid location"
                    );

                    return;

                }


                // --------------------------------------------------
                // SAVE REAL GPS
                // --------------------------------------------------

                latestGPS = {

                    latitude:
                        latitude,

                    longitude:
                        longitude,

                    accuracy:
                        Number.isFinite(accuracy)
                            ? accuracy
                            : null

                };


                console.log(
                    "Real GPS updated:",
                    latestGPS
                );


                // --------------------------------------------------
                // MAKE GPS AVAILABLE GLOBALLY
                // map.js can use this if required.
                // --------------------------------------------------

                window.latestGPS = {
                    ...latestGPS
                };


                updateGPSUI();

            },


            error => {

                console.warn(
                    "GPS error:",
                    error
                );


                let message =
                    "GPS: Location unavailable";


                if (error && error.code === 1) {

                    message =
                        "GPS: Location permission denied";

                }

                else if (error && error.code === 2) {

                    message =
                        "GPS: Unable to determine location";

                }

                else if (error && error.code === 3) {

                    message =
                        "GPS: Location request timed out";

                }


                updateGPSStatus(
                    message
                );

            },


            {

                enableHighAccuracy:
                    true,

                maximumAge:
                    1000,

                timeout:
                    10000

            }

        );

}


// ==========================================================
// UPDATE GPS UI
// ==========================================================

function updateGPSUI() {

    const latitudeElement =
        document.getElementById(
            "latitude"
        );


    const longitudeElement =
        document.getElementById(
            "longitude"
        );


    const accuracyElement =
        document.getElementById(
            "accuracy"
        );


    if (latitudeElement) {

        latitudeElement.textContent =
            latestGPS.latitude !== null
                ? latestGPS.latitude.toFixed(6)
                : "N/A";

    }


    if (longitudeElement) {

        longitudeElement.textContent =
            latestGPS.longitude !== null
                ? latestGPS.longitude.toFixed(6)
                : "N/A";

    }


    if (accuracyElement) {

        accuracyElement.textContent =
            latestGPS.accuracy !== null
                ? Math.round(
                    latestGPS.accuracy
                ) + " m"
                : "N/A";

    }


    updateGPSStatus(
        hasValidGPS()
            ? `GPS: ${latestGPS.latitude.toFixed(6)}, ${latestGPS.longitude.toFixed(6)}`
            : "GPS: Waiting for location..."
    );

}


// ==========================================================
// UPDATE LIVE GPS STATUS
// ==========================================================

function updateGPSStatus(message) {

    const element =
        document.getElementById(
            "liveGPSStatus"
        );


    if (element) {

        element.textContent =
            message;

    }

}


// ==========================================================
// UPDATE LIVE DETECTION STATUS
// ==========================================================

function updateLiveDetectionStatus(message) {

    const element =
        document.getElementById(
            "liveDetectionStatus"
        );


    if (element) {

        element.textContent =
            message;

    }


    // Also update the normal recording status
    // when it exists.

    updateRecordingStatus(
        message
    );

}


// ==========================================================
// CHECK GPS
// ==========================================================

function hasValidGPS() {

    return (

        Number.isFinite(
            latestGPS.latitude
        )

        &&

        Number.isFinite(
            latestGPS.longitude
        )

        &&

        latestGPS.latitude >= -90

        &&

        latestGPS.latitude <= 90

        &&

        latestGPS.longitude >= -180

        &&

        latestGPS.longitude <= 180

        &&

        !(
            latestGPS.latitude === 0 &&
            latestGPS.longitude === 0
        )

    );

}


// ==========================================================
// MODE TABS
// ==========================================================

function initializeModeTabs() {

    const buttons =
        document.querySelectorAll(
            ".mode-btn"
        );


    buttons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    const mode =
                        button.dataset.mode;


                    document
                        .querySelectorAll(
                            ".mode-btn"
                        )
                        .forEach(
                            btn => {

                                btn.classList.remove(
                                    "active"
                                );

                            }
                        );


                    button.classList.add(
                        "active"
                    );


                    document
                        .querySelectorAll(
                            ".detection-panel"
                        )
                        .forEach(
                            panel => {

                                panel.classList.add(
                                    "hidden"
                                );

                            }
                        );


                    const selectedPanel =
                        document.getElementById(
                            `${mode}Mode`
                        );


                    if (selectedPanel) {

                        selectedPanel.classList.remove(
                            "hidden"
                        );

                    }


                    // Camera mode is the only mode
                    // that needs live YOLO.

                    if (mode !== "camera") {

                        stopLiveDetection();

                        stopCamera();

                    }

                }
            );

        }
    );

}


// ==========================================================
// IMAGE UPLOAD
// ==========================================================

function initializeImageUpload() {

    const input =
        document.getElementById(
            "imageInput"
        );


    const selectButton =
        document.getElementById(
            "selectImageBtn"
        );


    const detectButton =
        document.getElementById(
            "detectImageBtn"
        );


    if (
        !input ||
        !selectButton ||
        !detectButton
    ) {

        return;

    }


    selectButton.addEventListener(
        "click",
        () => input.click()
    );


    input.addEventListener(
        "change",
        event => {

            const file =
                event.target.files[0];


            if (!file) {

                return;

            }


            selectedImageFile =
                file;


            showImagePreview(
                file
            );


            detectButton.disabled =
                false;

        }
    );


    detectButton.addEventListener(
        "click",
        async () => {

            if (!selectedImageFile) {

                alert(
                    "Please select an image first."
                );

                return;

            }


            await uploadAndProcess(
                selectedImageFile
            );

        }
    );

}


// ==========================================================
// IMAGE PREVIEW
// ==========================================================

function showImagePreview(
    file
) {

    const container =
        document.getElementById(
            "imagePreviewContainer"
        );


    const preview =
        document.getElementById(
            "imagePreview"
        );


    if (
        !container ||
        !preview
    ) {

        return;

    }


    preview.src =
        URL.createObjectURL(
            file
        );


    container.classList.remove(
        "hidden"
    );

}


// ==========================================================
// VIDEO UPLOAD
// ==========================================================

function initializeVideoUpload() {

    const input =
        document.getElementById(
            "videoInput"
        );


    const selectButton =
        document.getElementById(
            "selectVideoBtn"
        );


    const detectButton =
        document.getElementById(
            "detectVideoBtn"
        );


    if (
        !input ||
        !selectButton ||
        !detectButton
    ) {

        return;

    }


    selectButton.addEventListener(
        "click",
        () => input.click()
    );


    input.addEventListener(
        "change",
        event => {

            const file =
                event.target.files[0];


            if (!file) {

                return;

            }


            selectedVideoFile =
                file;


            showVideoPreview(
                file
            );


            detectButton.disabled =
                false;

        }
    );


    detectButton.addEventListener(
        "click",
        async () => {

            if (!selectedVideoFile) {

                alert(
                    "Please select a video first."
                );

                return;

            }


            await uploadAndProcess(
                selectedVideoFile
            );

        }
    );

}


// ==========================================================
// VIDEO PREVIEW
// ==========================================================

function showVideoPreview(
    file
) {

    const container =
        document.getElementById(
            "videoPreviewContainer"
        );


    const preview =
        document.getElementById(
            "videoPreview"
        );


    if (
        !container ||
        !preview
    ) {

        return;

    }


    preview.src =
        URL.createObjectURL(
            file
        );


    container.classList.remove(
        "hidden"
    );

}


// ==========================================================
// CAMERA INITIALIZATION
// ==========================================================

function initializeCamera() {

    const startButton =
        document.getElementById(
            "startCameraBtn"
        );


    const captureButton =
        document.getElementById(
            "captureImageBtn"
        );


    const startRecordingButton =
        document.getElementById(
            "startRecordingBtn"
        );


    const stopRecordingButton =
        document.getElementById(
            "stopRecordingBtn"
        );


    const stopCameraButton =
        document.getElementById(
            "stopCameraBtn"
        );


    const processVideoButton =
        document.getElementById(
            "processRecordedVideoBtn"
        );


    if (startButton) {

        startButton.addEventListener(
            "click",
            startCamera
        );

    }


    if (captureButton) {

        captureButton.addEventListener(
            "click",
            captureCameraImage
        );

    }


    if (startRecordingButton) {

        startRecordingButton.addEventListener(
            "click",
            startRecording
        );

    }


    if (stopRecordingButton) {

        stopRecordingButton.addEventListener(
            "click",
            stopRecording
        );

    }


    if (stopCameraButton) {

        stopCameraButton.addEventListener(
            "click",
            stopCamera
        );

    }


    if (processVideoButton) {

        processVideoButton.addEventListener(
            "click",
            async () => {

                if (!recordedVideoBlob) {

                    alert(
                        "No recorded video available."
                    );

                    return;

                }


                const videoFile =
                    new File(
                        [
                            recordedVideoBlob
                        ],
                        `roadguard_recording_${Date.now()}.webm`,
                        {
                            type:
                                recordedVideoBlob.type ||
                                "video/webm"
                        }
                    );


                await uploadAndProcess(
                    videoFile
                );

            }
        );

    }

}


// ==========================================================
// START CAMERA
// ==========================================================

async function startCamera() {

    try {

        if (
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia
        ) {

            throw new Error(
                "Camera API is unavailable."
            );

        }


        // Stop any previous stream first.

        if (cameraStream) {

            stopCamera();

        }


        cameraStream =
            await navigator
                .mediaDevices
                .getUserMedia({

                    video: {

                        facingMode: {
                            ideal: "environment"
                        },

                        width: {
                            ideal: 1280
                        },

                        height: {
                            ideal: 720
                        }

                    },

                    audio: false

                });


        const video =
            document.getElementById(
                "cameraVideo"
            );


        if (video) {

            video.srcObject =
                cameraStream;


            await video
                .play()
                .catch(
                    () => { }
                );

        }


        const placeholder =
            document.getElementById(
                "cameraPlaceholder"
            );


        if (placeholder) {

            placeholder.style.display =
                "none";

        }


        const captureButton =
            document.getElementById(
                "captureImageBtn"
            );


        const recordingButton =
            document.getElementById(
                "startRecordingBtn"
            );


        const stopButton =
            document.getElementById(
                "stopCameraBtn"
            );


        if (captureButton) {

            captureButton.disabled =
                false;

        }


        if (recordingButton) {

            recordingButton.disabled =
                false;

        }


        if (stopButton) {

            stopButton.disabled =
                false;

        }


        updateRecordingStatus(
            "Camera is active"
        );


        updateLiveDetectionStatus(
            "Connecting to live YOLO..."
        );


        // Start real-time YOLO.

        startLiveDetection();

    }


    catch (error) {

        console.error(
            "Camera error:",
            error
        );


        updateRecordingStatus(
            "Camera permission denied or camera unavailable"
        );


        updateLiveDetectionStatus(
            "Live YOLO unavailable"
        );

    }

}


// ==========================================================
// CAPTURE IMAGE
// ==========================================================

function captureCameraImage() {

    if (!cameraStream) {

        return;

    }


    const video =
        document.getElementById(
            "cameraVideo"
        );


    const canvas =
        document.getElementById(
            "cameraCanvas"
        );


    if (
        !video ||
        !canvas
    ) {

        return;

    }


    if (
        video.videoWidth === 0 ||
        video.videoHeight === 0
    ) {

        return;

    }


    canvas.width =
        video.videoWidth;


    canvas.height =
        video.videoHeight;


    const context =
        canvas.getContext(
            "2d"
        );


    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );


    canvas.toBlob(
        blob => {

            if (!blob) {

                return;

            }


            const file =
                new File(
                    [blob],
                    `road_capture_${Date.now()}.jpg`,
                    {
                        type:
                            "image/jpeg"
                    }
                );


            capturedImages.push(
                file
            );


            displayCapturedImage(
                blob,
                file
            );

        },
        "image/jpeg",
        0.95
    );

}


// ==========================================================
// DISPLAY CAPTURED IMAGE
// ==========================================================

function displayCapturedImage(
    blob,
    file
) {

    const section =
        document.getElementById(
            "capturedImagesSection"
        );


    const gallery =
        document.getElementById(
            "capturedImages"
        );


    if (
        !section ||
        !gallery
    ) {

        return;

    }


    section.classList.remove(
        "hidden"
    );


    const card =
        document.createElement(
            "div"
        );


    card.className =
        "captured-image-card";


    const image =
        document.createElement(
            "img"
        );


    image.src =
        URL.createObjectURL(
            blob
        );


    const button =
        document.createElement(
            "button"
        );


    button.className =
        "primary-btn";


    button.textContent =
        "Detect";


    button.addEventListener(
        "click",
        async () => {

            await uploadAndProcess(
                file
            );

        }
    );


    card.appendChild(
        image
    );


    card.appendChild(
        button
    );


    gallery.appendChild(
        card
    );

}


// ==========================================================
// START RECORDING
// ==========================================================

function startRecording() {

    if (!cameraStream) {

        return;

    }


    if (!window.MediaRecorder) {

        updateRecordingStatus(
            "MediaRecorder is not supported."
        );

        return;

    }


    recordedChunks = [];


    try {

        mediaRecorder =
            new MediaRecorder(
                cameraStream
            );

    }

    catch (error) {

        console.error(
            error
        );


        updateRecordingStatus(
            "Unable to start recording."
        );

        return;

    }


    mediaRecorder.addEventListener(
        "dataavailable",
        event => {

            if (
                event.data &&
                event.data.size > 0
            ) {

                recordedChunks.push(
                    event.data
                );

            }

        }
    );


    mediaRecorder.addEventListener(
        "stop",
        createRecordedVideo
    );


    mediaRecorder.start();


    const startButton =
        document.getElementById(
            "startRecordingBtn"
        );


    const stopButton =
        document.getElementById(
            "stopRecordingBtn"
        );


    if (startButton) {

        startButton.disabled =
            true;

    }


    if (stopButton) {

        stopButton.disabled =
            false;

    }


    updateRecordingStatus(
        "Recording in progress..."
    );

}


// ==========================================================
// STOP RECORDING
// ==========================================================

function stopRecording() {

    if (
        mediaRecorder &&
        mediaRecorder.state !== "inactive"
    ) {

        mediaRecorder.stop();

    }

}


// ==========================================================
// CREATE RECORDED VIDEO
// ==========================================================

function createRecordedVideo() {

    if (!mediaRecorder) {

        return;

    }


    recordedVideoBlob =
        new Blob(
            recordedChunks,
            {
                type:
                    mediaRecorder.mimeType ||
                    "video/webm"
            }
        );


    const video =
        document.getElementById(
            "recordedVideo"
        );


    if (video) {

        video.src =
            URL.createObjectURL(
                recordedVideoBlob
            );

    }


    const section =
        document.getElementById(
            "recordedVideoSection"
        );


    if (section) {

        section.classList.remove(
            "hidden"
        );

    }


    const startButton =
        document.getElementById(
            "startRecordingBtn"
        );


    const stopButton =
        document.getElementById(
            "stopRecordingBtn"
        );


    if (startButton) {

        startButton.disabled =
            false;

    }


    if (stopButton) {

        stopButton.disabled =
            true;

    }


    updateRecordingStatus(
        "Recording completed"
    );

}


// ==========================================================
// STOP CAMERA
// ==========================================================

function stopCamera() {

    stopLiveDetection();


    if (mediaRecorder) {

        if (
            mediaRecorder.state !==
            "inactive"
        ) {

            try {

                mediaRecorder.stop();

            }

            catch (error) {

                console.warn(
                    "Recorder stop error:",
                    error
                );

            }

        }

    }


    if (cameraStream) {

        cameraStream
            .getTracks()
            .forEach(
                track => {

                    track.stop();

                }
            );

    }


    cameraStream =
        null;


    const video =
        document.getElementById(
            "cameraVideo"
        );


    if (video) {

        video.srcObject =
            null;

    }


    const placeholder =
        document.getElementById(
            "cameraPlaceholder"
        );


    if (placeholder) {

        placeholder.style.display =
            "flex";

    }


    const captureButton =
        document.getElementById(
            "captureImageBtn"
        );


    const recordingButton =
        document.getElementById(
            "startRecordingBtn"
        );


    const stopRecordingButton =
        document.getElementById(
            "stopRecordingBtn"
        );


    const stopCameraButton =
        document.getElementById(
            "stopCameraBtn"
        );


    if (captureButton) {

        captureButton.disabled =
            true;

    }


    if (recordingButton) {

        recordingButton.disabled =
            true;

    }


    if (stopRecordingButton) {

        stopRecordingButton.disabled =
            true;

    }


    if (stopCameraButton) {

        stopCameraButton.disabled =
            true;

    }


    updateRecordingStatus(
        "Camera stopped"
    );


    updateLiveDetectionStatus(
        "Live AI detection is not active"
    );

}


// ==========================================================
// START LIVE DETECTION
//
// Camera
//    ↓
// Canvas
//    ↓
// JPEG
//    ↓
// WebSocket
//    ↓
// FastAPI
//    ↓
// YOLO
//    ↓
// Detection result
//    ↓
// Map
// ==========================================================

function startLiveDetection() {

    if (liveDetectionActive) {

        return;

    }


    const video =
        document.getElementById(
            "cameraVideo"
        );


    if (!video) {

        console.warn(
            "Camera video element not found."
        );

        return;

    }


    liveDetectionActive =
        true;


    liveDetectionCanvas =
        document.createElement(
            "canvas"
        );


    liveDetectionContext =
        liveDetectionCanvas.getContext(
            "2d"
        );


    lastLiveFrameSent =
        0;


    updateLiveDetectionStatus(
        "Connecting to live YOLO..."
    );


    connectLiveDetectionSocket();

}


// ==========================================================
// BUILD WEBSOCKET URL
// ==========================================================

function buildLiveWebSocketURL() {

    const baseUrl =
        getAPIBaseURL();


    try {

        const parsed =
            new URL(
                baseUrl,
                window.location.origin
            );


        const protocol =
            parsed.protocol === "https:"
                ? "wss:"
                : "ws:";


        return (
            `${protocol}//${parsed.host}` +
            `/api/live/detect`
        );

    }

    catch (error) {

        console.error(
            "Unable to build WebSocket URL:",
            error
        );


        return null;

    }

}


// ==========================================================
// CONNECT LIVE WEBSOCKET
// ==========================================================

function connectLiveDetectionSocket() {

    if (!liveDetectionActive) {

        return;

    }


    if (
        liveDetectionSocket &&
        (
            liveDetectionSocket.readyState ===
            WebSocket.OPEN
        )
    ) {

        startLiveFrameLoop();

        return;

    }


    const websocketUrl =
        buildLiveWebSocketURL();


    if (!websocketUrl) {

        updateLiveDetectionStatus(
            "Unable to connect to live YOLO"
        );

        return;

    }


    console.log(
        "Connecting to live detection:",
        websocketUrl
    );


    try {

        liveDetectionSocket =
            new WebSocket(
                websocketUrl
            );

    }

    catch (error) {

        console.error(
            "WebSocket creation error:",
            error
        );


        scheduleLiveSocketReconnect();

        return;

    }


    liveDetectionSocket.onopen =
        () => {

            console.log(
                "Live YOLO WebSocket connected."
            );


            updateLiveDetectionStatus(
                "Live YOLO detection active"
            );


            startLiveFrameLoop();

        };


    liveDetectionSocket.onmessage =
        event => {

            try {

                const result =
                    JSON.parse(
                        event.data
                    );


                console.log(
                    "Live detection result:",
                    result
                );


                handleLiveDetectionResult(
                    result
                );

            }

            catch (error) {

                console.error(
                    "Invalid live detection response:",
                    error
                );

            }

        };


    liveDetectionSocket.onerror =
        error => {

            console.error(
                "Live detection WebSocket error:",
                error
            );


            updateLiveDetectionStatus(
                "Live YOLO connection error"
            );

        };


    liveDetectionSocket.onclose =
        event => {

            console.log(
                "Live YOLO WebSocket closed:",
                event.code,
                event.reason
            );


            stopLiveFrameLoop();


            liveDetectionSocket =
                null;


            if (liveDetectionActive) {

                updateLiveDetectionStatus(
                    "Live YOLO reconnecting..."
                );


                scheduleLiveSocketReconnect();

            }

        };

}


// ==========================================================
// RECONNECT WEBSOCKET
// ==========================================================

function scheduleLiveSocketReconnect() {

    if (!liveDetectionActive) {

        return;

    }


    if (liveSocketReconnectTimer !== null) {

        return;

    }


    liveSocketReconnectTimer =
        setTimeout(
            () => {

                liveSocketReconnectTimer =
                    null;


                if (
                    liveDetectionActive &&
                    cameraStream
                ) {

                    connectLiveDetectionSocket();

                }

            },
            2000
        );

}


// ==========================================================
// START LIVE FRAME LOOP
// ==========================================================

function startLiveFrameLoop() {

    stopLiveFrameLoop();


    liveDetectionInterval =
        setInterval(
            sendLiveFrame,
            LIVE_DETECTION_INTERVAL_MS
        );

}


// ==========================================================
// STOP LIVE FRAME LOOP
// ==========================================================

function stopLiveFrameLoop() {

    if (
        liveDetectionInterval !== null
    ) {

        clearInterval(
            liveDetectionInterval
        );


        liveDetectionInterval =
            null;

    }

}


// ==========================================================
// SEND LIVE CAMERA FRAME
// ==========================================================

function sendLiveFrame() {

    if (!liveDetectionActive) {

        return;

    }


    if (
        !liveDetectionSocket ||
        liveDetectionSocket.readyState !==
        WebSocket.OPEN
    ) {

        return;

    }


    if (liveFrameEncoding) {

        return;

    }


    const video =
        document.getElementById(
            "cameraVideo"
        );


    if (!video) {

        return;

    }


    if (
        video.readyState <
        HTMLMediaElement.HAVE_CURRENT_DATA
    ) {

        return;

    }


    if (
        video.videoWidth <= 0 ||
        video.videoHeight <= 0
    ) {

        return;

    }


    const now =
        Date.now();


    if (
        now - lastLiveFrameSent <
        LIVE_DETECTION_INTERVAL_MS
    ) {

        return;

    }


    lastLiveFrameSent =
        now;


    liveFrameEncoding =
        true;


    // ------------------------------------------------------
    // RESIZE FRAME
    // ------------------------------------------------------

    const maxWidth =
        960;


    const scale =
        Math.min(
            1,
            maxWidth /
            video.videoWidth
        );


    liveDetectionCanvas.width =
        Math.round(
            video.videoWidth *
            scale
        );


    liveDetectionCanvas.height =
        Math.round(
            video.videoHeight *
            scale
        );


    liveDetectionContext.drawImage(
        video,
        0,
        0,
        liveDetectionCanvas.width,
        liveDetectionCanvas.height
    );


    // ------------------------------------------------------
    // JPEG ENCODE
    // ------------------------------------------------------

    liveDetectionCanvas.toBlob(
        blob => {

            if (!blob) {

                liveFrameEncoding =
                    false;

                return;

            }


            if (
                !liveDetectionSocket ||
                liveDetectionSocket.readyState !==
                WebSocket.OPEN
            ) {

                liveFrameEncoding =
                    false;

                return;

            }


            const reader =
                new FileReader();


            reader.onloadend =
                () => {

                    try {

                        if (
                            !liveDetectionSocket ||
                            liveDetectionSocket.readyState !==
                            WebSocket.OPEN
                        ) {

                            return;

                        }


                        const dataUrl =
                            String(
                                reader.result
                            );


                        const parts =
                            dataUrl.split(
                                ","
                            );


                        const base64 =
                            parts.length > 1
                                ? parts[1]
                                : null;


                        if (!base64) {

                            return;

                        }


                        // --------------------------------------------------
                        // LIVE YOLO PAYLOAD
                        //
                        // Real frame
                        // Real GPS
                        // No fake location
                        // --------------------------------------------------

                        const payload = {

                            type:
                                "frame",

                            frame:
                                base64,

                            latitude:
                                hasValidGPS()
                                    ? latestGPS.latitude
                                    : null,

                            longitude:
                                hasValidGPS()
                                    ? latestGPS.longitude
                                    : null,

                            accuracy:
                                hasValidGPS()
                                    ? latestGPS.accuracy
                                    : null,

                            conf:
                                0.35

                        };


                        liveDetectionSocket.send(
                            JSON.stringify(
                                payload
                            )
                        );


                    }

                    catch (error) {

                        console.error(
                            "Live frame send error:",
                            error
                        );

                    }

                    finally {

                        liveFrameEncoding =
                            false;

                    }

                };


            reader.onerror =
                () => {

                    liveFrameEncoding =
                        false;

                };


            reader.readAsDataURL(
                blob
            );

        },
        "image/jpeg",
        0.75
    );

}


// ==========================================================
// HANDLE LIVE DETECTION RESULT
// ==========================================================

function handleLiveDetectionResult(
    result
) {

    if (!result) {

        return;

    }


    // ------------------------------------------------------
    // UPDATE GPS STATUS FROM BACKEND
    // ------------------------------------------------------

    if (
        result.location &&
        result.location.valid === true
    ) {

        const backendLatitude =
            Number(
                result.location.latitude
            );


        const backendLongitude =
            Number(
                result.location.longitude
            );


        if (
            Number.isFinite(
                backendLatitude
            ) &&
            Number.isFinite(
                backendLongitude
            )
        ) {

            updateGPSStatus(
                `GPS: ${backendLatitude.toFixed(6)}, ${backendLongitude.toFixed(6)}`
            );

        }

    }


    // ------------------------------------------------------
    // SEND RESULT TO LEAFLET MAP
    // ------------------------------------------------------

    if (
        typeof window.updateLiveMap ===
        "function"
    ) {

        window.updateLiveMap(
            result
        );

    }


    // ------------------------------------------------------
    // CUSTOM EVENT
    //
    // Allows another frontend component to
    // receive the real detection result.
    // ------------------------------------------------------

    try {

        window.dispatchEvent(
            new CustomEvent(
                "roadguard:live-detection",
                {
                    detail:
                        result
                }
            )
        );

    }

    catch (error) {

        console.warn(
            "Unable to dispatch live detection event:",
            error
        );

    }


    // ------------------------------------------------------
    // UPDATE STATUS
    // ------------------------------------------------------

    if (
        result.success === true
    ) {

        const count =
            Number(
                result.pothole_count || 0
            );


        if (count > 0) {

            updateLiveDetectionStatus(
                `Live YOLO: ${count} pothole(s) detected`
            );

        }

        else {

            updateLiveDetectionStatus(
                "Live YOLO scanning road..."
            );

        }

    }

    else {

        updateLiveDetectionStatus(
            "Live YOLO is processing..."
        );

    }

}


// ==========================================================
// STOP LIVE DETECTION
// ==========================================================

function stopLiveDetection() {

    liveDetectionActive =
        false;


    stopLiveFrameLoop();


    lastLiveFrameSent =
        0;


    liveFrameEncoding =
        false;


    if (liveSocketReconnectTimer !== null) {

        clearTimeout(
            liveSocketReconnectTimer
        );


        liveSocketReconnectTimer =
            null;

    }


    if (liveDetectionSocket) {

        try {

            liveDetectionSocket.close();

        }

        catch (error) {

            console.warn(
                "WebSocket close error:",
                error
            );

        }

    }


    liveDetectionSocket =
        null;


    updateLiveDetectionStatus(
        "Live AI detection is not active"
    );

}


// ==========================================================
// GET API BASE URL
// ==========================================================

function getAPIBaseURL() {

    if (
        typeof API_BASE_URL !==
        "undefined" &&
        API_BASE_URL
    ) {

        return API_BASE_URL;

    }


    return window.location.origin;

}


// ==========================================================
// GET DETECTION UPLOAD ENDPOINT
// ==========================================================

function getDetectionUploadEndpoint() {

    if (
        typeof API_ENDPOINTS !==
        "undefined" &&
        API_ENDPOINTS &&
        API_ENDPOINTS.detectionUpload
    ) {

        return API_ENDPOINTS.detectionUpload;

    }


    return (
        `${getAPIBaseURL()}` +
        `/api/detection/upload`
    );

}


// ==========================================================
// GET DETECTION PROCESS ENDPOINT
// ==========================================================

function getDetectionProcessEndpoint(
    reportId
) {

    if (
        typeof API_ENDPOINTS !==
        "undefined" &&
        API_ENDPOINTS &&
        API_ENDPOINTS.detectionProcess
    ) {

        return (
            `${API_ENDPOINTS.detectionProcess}` +
            `/${encodeURIComponent(reportId)}`
        );

    }


    return (
        `${getAPIBaseURL()}` +
        `/api/detection/process/` +
        `${encodeURIComponent(reportId)}`
    );

}


// ==========================================================
// UPLOAD AND PROCESS
// ==========================================================

async function uploadAndProcess(
    file
) {

    if (!file) {

        return;

    }


    showProcessing(
        "Uploading media to RoadGuard AI..."
    );


    try {

        const formData =
            new FormData();


        // --------------------------------------------------
        // MEDIA
        // --------------------------------------------------

        formData.append(
            "file",
            file
        );


        // --------------------------------------------------
        // REAL GPS
        // --------------------------------------------------

        if (hasValidGPS()) {

            formData.append(
                "latitude",
                latestGPS.latitude
            );


            formData.append(
                "longitude",
                latestGPS.longitude
            );


            if (
                latestGPS.accuracy !== null
            ) {

                formData.append(
                    "accuracy",
                    latestGPS.accuracy
                );

            }

        }

        else if (
            navigator.geolocation
        ) {

            // --------------------------------------------------
            // Request one real GPS position if the watcher
            // has not produced a valid position yet.
            // --------------------------------------------------

            try {

                const position =
                    await new Promise(
                        (
                            resolve,
                            reject
                        ) => {

                            navigator
                                .geolocation
                                .getCurrentPosition(
                                    resolve,
                                    reject,
                                    {

                                        enableHighAccuracy:
                                            true,

                                        timeout:
                                            5000,

                                        maximumAge:
                                            10000

                                    }
                                );

                        }
                    );


                if (
                    position &&
                    position.coords
                ) {

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


                    if (
                        Number.isFinite(
                            latitude
                        ) &&
                        Number.isFinite(
                            longitude
                        ) &&
                        !(
                            latitude === 0 &&
                            longitude === 0
                        )
                    ) {

                        formData.append(
                            "latitude",
                            latitude
                        );


                        formData.append(
                            "longitude",
                            longitude
                        );


                        if (
                            Number.isFinite(
                                accuracy
                            )
                        ) {

                            formData.append(
                                "accuracy",
                                accuracy
                            );

                        }


                        // Keep the real GPS state
                        // synchronized.

                        latestGPS = {

                            latitude:
                                latitude,

                            longitude:
                                longitude,

                            accuracy:
                                Number.isFinite(
                                    accuracy
                                )
                                    ? accuracy
                                    : null

                        };


                        window.latestGPS = {
                            ...latestGPS
                        };


                        updateGPSUI();

                    }

                }

            }

            catch (geoError) {

                console.info(
                    "Real GPS unavailable for upload. Uploading without GPS."
                );

            }

        }


        // --------------------------------------------------
        // UPLOAD
        // --------------------------------------------------

        const uploadEndpoint =
            getDetectionUploadEndpoint();


        console.log(
            "Detection upload endpoint:",
            uploadEndpoint
        );


        const uploadResponse =
            await fetch(
                uploadEndpoint,
                {
                    method:
                        "POST",

                    body:
                        formData
                }
            );


        const uploadData =
            await parseResponse(
                uploadResponse
            );


        if (!uploadResponse.ok) {

            throw new Error(

                uploadData.detail ||
                uploadData.message ||
                "Upload failed"

            );

        }


        console.log(
            "Upload Response:",
            uploadData
        );


        // --------------------------------------------------
        // REPORT ID
        // --------------------------------------------------

        const reportId =

            uploadData.report_id ||

            uploadData.id ||

            uploadData.report?.id ||

            uploadData.data?.report_id ||

            uploadData.data?.id;


        // --------------------------------------------------
        // BACKEND ALREADY RETURNED FINAL RESULT
        // --------------------------------------------------

        if (!reportId) {

            hideProcessing();


            displayResult(
                uploadData
            );


            return;

        }


        // --------------------------------------------------
        // PROCESS REPORT
        // --------------------------------------------------

        showProcessing(
            "AI is analyzing potholes..."
        );


        const processEndpoint =
            getDetectionProcessEndpoint(
                reportId
            );


        console.log(
            "Detection process endpoint:",
            processEndpoint
        );


        const processResponse =
            await fetch(
                processEndpoint,
                {
                    method:
                        "POST"
                }
            );


        const processData =
            await parseResponse(
                processResponse
            );


        if (!processResponse.ok) {

            throw new Error(

                processData.detail ||
                processData.message ||
                "Detection processing failed"

            );

        }


        hideProcessing();


        displayResult(
            processData
        );


        console.log(
            "Detection Result:",
            processData
        );

    }


    catch (error) {

        console.error(
            "Detection Error:",
            error
        );


        hideProcessing();


        displayError(
            error.message ||
            "Unknown detection error"
        );

    }

}


// ==========================================================
// PARSE RESPONSE
// ==========================================================

async function parseResponse(
    response
) {

    const text =
        await response.text();


    try {

        return JSON.parse(
            text
        );

    }

    catch {

        return {
            detail:
                text
        };

    }

}


// ==========================================================
// PROCESSING UI
// ==========================================================

function showProcessing(
    message
) {

    const section =
        document.getElementById(
            "processingSection"
        );


    const messageElement =
        document.getElementById(
            "processingMessage"
        );


    if (section) {

        section.classList.remove(
            "hidden"
        );

    }


    if (messageElement) {

        messageElement.textContent =
            message;

    }

}


// ==========================================================
// HIDE PROCESSING
// ==========================================================

function hideProcessing() {

    const section =
        document.getElementById(
            "processingSection"
        );


    if (section) {

        section.classList.add(
            "hidden"
        );

    }

}


// ==========================================================
// DISPLAY RESULT
// ==========================================================

function displayResult(
    data
) {

    const result =
        document.getElementById(
            "detectionResult"
        );


    if (!result) {

        return;

    }


    result.classList.remove(
        "empty-result"
    );


    result.innerHTML = `

        <div class="result-success">

            <h3>
                Detection Completed Successfully
            </h3>

            <p>
                RoadGuard AI has completed
                the analysis.
            </p>

        </div>

        <pre class="result-json">${escapeHtml(
        JSON.stringify(
            data,
            null,
            2
        )
    )}</pre>

    `;

}


// ==========================================================
// DISPLAY ERROR
// ==========================================================

function displayError(
    message
) {

    const result =
        document.getElementById(
            "detectionResult"
        );


    if (!result) {

        return;

    }


    result.innerHTML = `

        <div class="result-error">

            <h3>
                Detection Failed
            </h3>

            <p>
                ${escapeHtml(
        message
    )}
            </p>

        </div>

    `;

}


// ==========================================================
// CLEAR RESULTS
// ==========================================================

function initializeClearButton() {

    const button =
        document.getElementById(
            "clearResultsBtn"
        );


    if (!button) {

        return;

    }


    button.addEventListener(
        "click",
        () => {

            const result =
                document.getElementById(
                    "detectionResult"
                );


            if (!result) {

                return;

            }


            result.className =
                "result-card empty-result";


            result.innerHTML = `

                <div class="empty-icon">
                    🔍
                </div>

                <h3>
                    No Detection Yet
                </h3>

                <p>
                    Upload media to begin detection.
                </p>

            `;

        }
    );

}


// ==========================================================
// RECORDING STATUS
// ==========================================================

function updateRecordingStatus(
    message
) {

    const element =
        document.getElementById(
            "recordingStatus"
        );


    if (element) {

        element.textContent =
            message;

    }

}


// ==========================================================
// ESCAPE HTML
// ==========================================================

function escapeHtml(
    text
) {

    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        String(text);


    return div.innerHTML;

}


// ==========================================================
// CLEANUP
// ==========================================================

window.addEventListener(
    "beforeunload",
    () => {

        stopLiveDetection();


        if (
            gpsWatchId !== null
        ) {

            navigator
                .geolocation
                .clearWatch(
                    gpsWatchId
                );


            gpsWatchId =
                null;

        }


        if (cameraStream) {

            cameraStream
                .getTracks()
                .forEach(
                    track => {

                        track.stop();

                    }
                );


            cameraStream =
                null;

        }


        if (mediaRecorder) {

            try {

                if (
                    mediaRecorder.state !==
                    "inactive"
                ) {

                    mediaRecorder.stop();

                }

            }

            catch (error) {

                console.warn(
                    "Recorder cleanup error:",
                    error
                );

            }

        }

    }
);