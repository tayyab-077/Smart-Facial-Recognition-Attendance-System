const video = document.getElementById("video");
const startBtn = document.getElementById("start");
const nameInput = document.getElementById("name");
const status = document.getElementById("status");

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user', width:{ideal:640}, height:{ideal:480}}});
    video.srcObject = stream;
    video.onloadedmetadata = () => video.play();
  } catch (e) {
    alert("Camera error: " + e.message);
  }
}

startCamera();

startBtn.onclick = async () => {
  const name = nameInput.value.trim();
  if (!name) { alert("Enter name"); return; }

  startBtn.disabled = true;
  status.innerText = "Capturing images...";

  const canvas = document.createElement("canvas");
  canvas.width = 480; canvas.height = 360;
  const ctx = canvas.getContext("2d");

  const images = [];
  for (let i = 0; i < 15; i++) {
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    images.push(canvas.toDataURL("image/jpeg", 0.8));
    await new Promise(r=>setTimeout(r, 250));
  }

  status.innerText = "Uploading, please wait...";

  try {
    const res = await fetch("/api/enroll", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name,images})});
    const data = await res.json();
    status.innerText = data.status==="pending"?"Enrollment submitted (waiting for admin approval)":"Error: "+JSON.stringify(data);
  } catch (e) {
    status.innerText = "❌ Network error. Server not reachable";
  }

  startBtn.disabled = false;
};
