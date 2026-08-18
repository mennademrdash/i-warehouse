document.addEventListener("DOMContentLoaded", () => {

    const faceToggle = document.getElementById("faceToggle");
    const faceContent = document.getElementById("faceContent");
    const cameraPreview = document.getElementById("cameraPreview");
    const captureFaceBtn = document.getElementById("captureFaceBtn");
    const faceStatus = document.getElementById("faceStatus");

    let stream = null;

    function showFaceContent() {
        if (faceToggle.checked) {
            faceContent.style.display = "block";
        } else {
            faceContent.style.display = "none";
            stopCamera();
        }
    }

    async function startCamera() {

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            faceStatus.textContent = "Camera is not supported.";
            return;
        }

        try {

            stream = await navigator.mediaDevices.getUserMedia({
                video: true
            });

            cameraPreview.srcObject = stream;

            faceStatus.textContent = "";

        } catch (error) {

            if (
                error.name === "NotAllowedError" ||
                error.name === "PermissionDeniedError"
            ) {
                faceStatus.textContent =
                    "Camera permission not allowed.";
            } else if (error.name === "NotFoundError") {
                faceStatus.textContent =
                    "No camera found on this device.";
            } else {
                faceStatus.textContent =
                    "Could not open the camera.";
            }
        }
    }

    function stopCamera() {

        if (stream) {

            stream.getTracks().forEach(track => {
                track.stop();
            });

            stream = null;
        }

        cameraPreview.srcObject = null;
    }

    faceToggle.addEventListener("change", async () => {

        showFaceContent();

        if (faceToggle.checked) {
            await startCamera();
        }

    });

    captureFaceBtn.addEventListener("click", async () => {

        if (!stream) {
            await startCamera();
            return;
        }

        const canvas = document.getElementById("cameraCanvas");

        canvas.width = cameraPreview.videoWidth;
        canvas.height = cameraPreview.videoHeight;

        const ctx = canvas.getContext("2d");

        ctx.drawImage(
            cameraPreview,
            0,
            0,
            canvas.width,
            canvas.height
        );

        const image = canvas.toDataURL("image/jpeg", 0.9);

        faceStatus.textContent = "Verifying face...";

        try {

            const response = await fetch("/api/settings/face", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    image: image
                })
            });

            const data = await response.json();

            if (data.success) {

                faceStatus.textContent =
                    "Face captured successfully.";

                stopCamera();

            } else {

                faceStatus.textContent =
                    data.message || "Face capture failed.";

            }

        } catch (error) {

            console.error(error);

            faceStatus.textContent =
                "Something went wrong. Try again.";
        }
    });

    showFaceContent();

});