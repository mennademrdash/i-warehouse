
let videoStream = null;
let handScrollStream = null;

function isCameraSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

function getCameraErrorMessage(err) {
    if (!window.isSecureContext) {
        return "Camera needs a secure page. Open http://localhost:5000 or use HTTPS in Chrome/Edge.";
    }
    if (err && (err.name === "NotAllowedError" || err.name === "PermissionDeniedError")) {
        return "Camera permission was blocked. Allow camera access for this site in Chrome/Edge settings.";
    }
    if (err && err.name === "NotFoundError") {
        return "No camera was found on this device.";
    }
    if (err && err.name === "NotReadableError") {
        return "Camera is already in use by another app or browser tab.";
    }
    return "Could not open the camera. Check permissions and try again.";
}

async function getCameraStream(options = { video: true }) {
    if (!isCameraSupported()) {
        throw new Error("UNSUPPORTED");
    }

    const attempts = [
        options,
        { video: { facingMode: "user" } },
        { video: true },
    ];

    let lastError = null;
    for (const constraints of attempts) {
        try {
            return await navigator.mediaDevices.getUserMedia(constraints);
        } catch (err) {
            lastError = err;
        }
    }

    throw lastError || new Error("Camera unavailable");
}

async function attachStreamToVideo(video, stream) {
    video.muted = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.srcObject = stream;

    await new Promise((resolve, reject) => {
        const onReady = () => {
            video.removeEventListener("loadedmetadata", onReady);
            resolve();
        };
        const onError = () => {
            video.removeEventListener("error", onError);
            reject(new Error("Video failed to load camera stream"));
        };

        if (video.readyState >= 1 && video.videoWidth > 0) {
            resolve();
            return;
        }

        video.addEventListener("loadedmetadata", onReady, { once: true });
        video.addEventListener("error", onError, { once: true });
    });

    try {
        await video.play();
    } catch (err) {
        // Chrome/Edge may block autoplay until the user interacts once.
        await new Promise((resolve, reject) => {
            const resume = async () => {
                document.removeEventListener("click", resume);
                document.removeEventListener("keydown", resume);
                try {
                    await video.play();
                    resolve();
                } catch (playErr) {
                    reject(playErr);
                }
            };
            document.addEventListener("click", resume, { once: true });
            document.addEventListener("keydown", resume, { once: true });
        });
    }
}

async function openCamera(videoElementId) {
    const video = document.getElementById(videoElementId);
    if (!video) return;

    try {
        videoStream = await getCameraStream({ video: true });
        await attachStreamToVideo(video, videoStream);
    } catch (err) {
        console.error("Camera error:", err);
        alert(getCameraErrorMessage(err));
    }
}

function closeCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    if (handScrollStream) {
        handScrollStream.getTracks().forEach(track => track.stop());
        handScrollStream = null;
    }
}

function captureFrame(videoElementId, canvasElementId) {
    const video = document.getElementById(videoElementId);
    const canvas = document.getElementById(canvasElementId);

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return canvas.toDataURL("image/jpeg", 0.9);
}




function setupRegisterFaceCapture() {
    const captureBtn = document.getElementById("captureFace");
    const statusText = document.getElementById("faceStatus");
    const hiddenInput = document.getElementById("face_encoding");

    if (!captureBtn) return;

    let cameraOpen = false;

    captureBtn.addEventListener("click", async () => {

        if (!cameraOpen) {
            await openCamera("registerVideo");
            cameraOpen = true;
            captureBtn.textContent = "📸 Capture now";
            return;
        }

        const imageData = captureFrame("registerVideo", "registerCanvas");

        statusText.textContent = "⏳Verifying the face...";

        try {
            const response = await fetch("/api/detect-face", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: imageData })
            });

            const data = await response.json();

            if (data.success) {
                hiddenInput.value = JSON.stringify(data.encoding);
                statusText.textContent = "✅ Face captured successfully";
                closeCamera();
                cameraOpen = false;
                captureBtn.textContent = "📷 Capture Face";
            } else {
                statusText.textContent = "❌ " + data.message;
            }
        } catch (err) {
            statusText.textContent = "try again";
            console.error(err);
        }
    });
}



function setupFaceLogin() {
    const loginFaceBtn = document.getElementById("faceLoginBtn");
    const statusText = document.getElementById("faceLoginStatus");

    if (!loginFaceBtn) return;

    let cameraOpen = false;

    loginFaceBtn.addEventListener("click", async () => {

        if (!cameraOpen) {
            await openCamera("loginVideo");
            cameraOpen = true;
            loginFaceBtn.textContent = "📸 login now";
            return;
        }

        const imageData = captureFrame("loginVideo", "loginCanvas");

        statusText.textContent = "⏳ checking the face...";

        try {
            const response = await fetch("/api/face-login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: imageData })
            });

            const data = await response.json();

            if (data.success) {
                statusText.textContent = "✅ You have been identified; logging in...";
                closeCamera();
                window.location.href = data.redirect;
            } else {
                statusText.textContent = "❌ " + data.message;
            }
        } catch (err) {
            statusText.textContent = "❌try again";
            console.error(err);
        }
    });
}



function setupLoginTabs() {
    const manualTab = document.getElementById("manualTab");
    const faceTab = document.getElementById("faceTab");
    const manualForm = document.getElementById("manualLoginForm");
    const faceForm = document.getElementById("faceLoginForm");

    if (!manualTab || !faceTab) return;

    manualTab.addEventListener("click", () => {
        manualTab.classList.add("active");
        faceTab.classList.remove("active");
        manualForm.style.display = "block";
        faceForm.style.display = "none";
        closeCamera();
    });

    faceTab.addEventListener("click", () => {
        faceTab.classList.add("active");
        manualTab.classList.remove("active");
        faceForm.style.display = "block";
        manualForm.style.display = "none";
    });
}




async function setupHandScroll() {
    const video = document.getElementById("handVideo");
    const canvas = document.getElementById("handCanvas");
    const gestureBadge = document.getElementById("gestureBadge");
    const SCROLL_DISTANCE = Math.round(window.innerHeight * 0.5);
    const POLL_MS = 300;
    const MAX_FRAME_WIDTH =240;

    if (!video || !canvas) return;

    let busy = false;
    let polling = false;

    async function startHandScrollCamera() {
        if (handScrollStream) return true;

        if (!isCameraSupported()) {
            console.warn("[hand-scroll]", getCameraErrorMessage({ name: "Unsupported" }));
            if (gestureBadge) gestureBadge.textContent = "⚠️ Camera unsupported";
            return false;
        }

        try {
            handScrollStream = await getCameraStream({
                video: {
                    facingMode: "user",
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    frameRate: { ideal: 30 },
                },
            });
            await attachStreamToVideo(video, handScrollStream);
            if (gestureBadge) gestureBadge.textContent = "✋ Gesture Control Active";
            return true;
        } catch (err) {
            console.error("[hand-scroll] Camera error:", err);
            if (gestureBadge) gestureBadge.textContent = "⚠️ Camera offline";
            return false;
        }
    }

    function startPolling() {
        if (polling) return;
        polling = true;

        setInterval(async () => {
            if (busy || !video.videoWidth || !video.videoHeight) {
                return;
            }

            busy = true;

            const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth);
            canvas.width = Math.round(video.videoWidth * scale);
            canvas.height = Math.round(video.videoHeight * scale);

            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imageData = canvas.toDataURL("image/jpeg", 0.34);

            try {
                const response = await fetch("/api/hand-command", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ image: imageData }),
                    credentials: "same-origin",
                });

                if (!response.ok) {
                    return;
                }

                const data = await response.json();

                if (gestureBadge) {
                    if (data.gesture && data.gesture !== "No Hand" && data.gesture !== "Unknown") {
                        gestureBadge.textContent = `${data.gesture} (${data.command})`;
                        gestureBadge.classList.add("active");
                    } else {
                       //gestureBadge.textContent = "✋ Gesture Control Active";
                        gestureBadge.classList.remove("active");
                    }
                }

                if (data.command === "SCROLL_UP") {
                    window.scrollBy({ top: -SCROLL_DISTANCE, left: 0, behavior: "smooth" });
                } else if (data.command === "SCROLL_DOWN") {
                    window.scrollBy({ top: SCROLL_DISTANCE, left: 0, behavior: "smooth" });
                }
            } catch (err) {
                console.error("[hand-scroll] Hand command error:", err);
            } finally {
                busy = false;
            }
        }, POLL_MS);
    }

    const ready = await startHandScrollCamera();
    if (ready) {
        startPolling();
        return;
    }

    // Chrome/Edge sometimes need one click on the page before camera autoplay works.
    const enableOnInteraction = async () => {
        document.removeEventListener("click", enableOnInteraction);
        document.removeEventListener("keydown", enableOnInteraction);

        if (await startHandScrollCamera()) {
            startPolling();
        }
    };

    document.addEventListener("click", enableOnInteraction, { once: true });
    document.addEventListener("keydown", enableOnInteraction, { once: true });
}


document.addEventListener("DOMContentLoaded", () => {
    setupRegisterFaceCapture();
    setupFaceLogin();
    setupLoginTabs();
    setupHandScroll();   
});