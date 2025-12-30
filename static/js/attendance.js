const video = document.getElementById("video");
const markBtn = document.getElementById("markBtn");

const resultBox = document.getElementById("resultBox");
const resultTitle = document.getElementById("resultTitle");
const resultDetails = document.getElementById("resultDetails");
const resultIcon = document.getElementById("resultIcon");

/* -------------------------
   CAMERA SETUP
------------------------- */
async function startCamera() {
    try {
        const constraints = {
            video: {
                facingMode: { ideal: "user" },
                width: { ideal: 640 },
                height: { ideal: 480 }
            }
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = stream;
        video.onloadedmetadata = () => video.play();
    } catch (err) {
        alert("Camera error: " + err.message);
    }
}

startCamera();

/* -------------------------
   CAPTURE FRAME
------------------------- */
function captureFrame() {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 480;
    canvas.height = video.videoHeight || 360;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return canvas.toDataURL("image/jpeg", 0.9);
}

/* -------------------------
   MARK ATTENDANCE
------------------------- */
markBtn.onclick = async () => {
    markBtn.disabled = true;
    markBtn.innerText = "Processing...";
    resultBox.classList.add("hidden");

    try {
        const image = captureFrame();

        const res = await fetch("/api/recognize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                image,
                device: "camera"   // matches backend
            })
        });

        const data = await res.json();

        resultBox.classList.remove("hidden", "success", "error");

        /* -------------------------
           NOT RECOGNIZED
        ------------------------- */
        if (!data.recognized) {
            resultBox.classList.add("error");

            resultTitle.innerHTML = `<span class="error-text">Face Not Recognized</span>`;

            let msg = data.reason || data.error || "Recognition failed";
            if (typeof data.score === "number") {
                msg += ` (Score: ${data.score.toFixed(2)})`;
            }

            if (data.borderline) {
                msg += " ⚠️ Borderline similarity — please retry with better lighting.";
            }

            resultDetails.innerText = msg;
            resultIcon.innerHTML = "❌";
            resultIcon.style.color = "red";
        }

        /* -------------------------
           RECOGNIZED
        ------------------------- */
        else {
            const scoreText = `Score: ${data.score.toFixed(2)}`;
            const attendance = data.attendance || { success: false };

            if (attendance.success) {
                resultBox.classList.add("success");

                resultTitle.innerHTML =
                    `Name: <span class="success-text">${data.name}</span>`;

                let msg = `Attendance marked successfully! (${scoreText})`;

                if (data.borderline) {
                    msg += " ⚠️ Borderline match — verify manually.";
                }

                resultDetails.innerText = msg;
                resultIcon.innerHTML = "✔️";
                resultIcon.style.color = "green";
            } else {
                resultBox.classList.add("error");

                resultTitle.innerHTML =
                    `Name: <span class="success-text">${data.name}</span>`;

                resultDetails.innerText =
                    `Attendance NOT marked: ${attendance.reason || "Unknown reason"} (${scoreText})`;

                resultIcon.innerHTML = "⚠️";
                resultIcon.style.color = "orange";
            }
        }

    } catch (err) {
        console.error(err);

        resultBox.classList.remove("hidden", "success");
        resultBox.classList.add("error");
        resultTitle.innerText = "Network Error";
        resultDetails.innerText = "Server not reachable";
        resultIcon.innerHTML = "⚠️";
        resultIcon.style.color = "red";
    }

    markBtn.disabled = false;
    markBtn.innerText = "Mark Attendance";
};
