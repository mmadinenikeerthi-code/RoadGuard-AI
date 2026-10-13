let liveSocket = null;
let liveStream = null;
let liveTimer = null;

const video = document.getElementById("liveVideo");
const canvas = document.createElement("canvas");

async function startLiveDetection() {
    liveStream = await navigator.mediaDevices.getUserMedia({
        video: {
            facingMode: "environment",
            width: { ideal: 1280 },
            height: { ideal: 720 }
        },
        audio: false
    });

    video.srcObject = liveStream;

    liveSocket = new WebSocket(
        `ws://${window.location.host}/api/live/detect`
    );

    liveSocket.onopen = () => {
        console.log("Live detection connected");

        liveTimer = setInterval(sendFrame, 500);
    };

    liveSocket.onmessage = event => {
        const result = JSON.parse(event.data);

        if (!result.success) {
            console.error(result.error);
            return;
        }

        updateLiveDetectionUI(result);
        updateLiveMap(result);
    };

    liveSocket.onerror = error => {
        console.error("Live detection error", error);
    };
}

async function sendFrame() {
    if (!video.videoWidth || !liveSocket) {
        return;
    }

    if (liveSocket.readyState !== WebSocket.OPEN) {
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    ctx.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    const frame = canvas.toDataURL(
        "image/jpeg",
        0.65
    );

    const location = await getCurrentLocation();

    liveSocket.send(JSON.stringify({
        frame,
        latitude: location?.latitude ?? null,
        longitude: location?.longitude ?? null
    }));
}

function updateLiveDetectionUI(result) {
    const countElement =
        document.getElementById("livePotholeCount");

    if (countElement) {
        countElement.textContent =
            result.pothole_count;
    }
}

function stopLiveDetection() {
    if (liveTimer) {
        clearInterval(liveTimer);
        liveTimer = null;
    }

    if (liveSocket) {
        liveSocket.close();
        liveSocket = null;
    }

    if (liveStream) {
        liveStream.getTracks().forEach(
            track => track.stop()
        );

        liveStream = null;
    }
}