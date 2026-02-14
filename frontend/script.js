const audioPlayer = document.getElementById("audioPlayer");
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusText = document.getElementById("status");
const answerBox = document.getElementById("answerBox");

let stream = null;
let recognition = null;

/* ---------------- BASE64 → AUDIO ---------------- */
function base64ToBlob(base64, mimeType) {
  const bytes = atob(base64);
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    buffer[i] = bytes.charCodeAt(i);
  }
  return new Blob([buffer], { type: mimeType });
}

/* ✅ Unlock audio (important for autoplay policies) */
function unlockAudio() {
  audioPlayer.play().catch(() => {});
  audioPlayer.pause();
}

/* ---------------- PLAY AI AUDIO ---------------- */
function playAudio(base64Audio) {
  if (!base64Audio) {
    console.error("No audio received");
    statusText.innerText = "⚠️ No audio received from backend";
    return;
  }

  const blob = base64ToBlob(base64Audio, "audio/mp3");
  const url = URL.createObjectURL(blob);

  audioPlayer.src = url;
  statusText.innerText = "🤖 AI is speaking...";

  audioPlayer.play()
    .then(() => console.log("AI speaking"))
    .catch(err => {
      console.error("Audio blocked:", err);
      statusText.innerText = "🔇 Audio blocked. Click play on audio player.";
    });
}

/* ---------------- START CAMERA ---------------- */
async function startCamera() {
  try {
    if (stream) return; // already running

    stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false
    });

    video.srcObject = stream;
    await video.play();

    console.log("✅ Webcam started");
  } catch (err) {
    console.error("Camera error:", err);
    alert("❌ Camera permission denied or webcam not found.");
  }
}

/* ---------------- CAPTURE IMAGE BASE64 ---------------- */
function captureImageBase64() {
  const ctx = canvas.getContext("2d");
  canvas.width = video.videoWidth || 320;
  canvas.height = video.videoHeight || 240;

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg"); // includes "data:image/jpeg;base64,..."
}

/* ---------------- START INTERVIEW ---------------- */
async function startInterview() {
  unlockAudio();
  await startCamera();

  statusText.innerText = "⏳ Starting interview...";

  fetch("http://127.0.0.1:5000/interview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reset: true })
  })
    .then(res => res.json())
    .then(data => {
      console.log("✅ Interview started");
      playAudio(data.audio);
      statusText.innerText = "✅ Interview started. Now answer!";
    })
    .catch(err => {
      console.error("Backend error:", err);
      statusText.innerText = "❌ Backend not reachable. Is Flask running?";
    });
}

/* ---------------- START VOICE RECOGNITION ---------------- */
function startListening() {
  unlockAudio();

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    alert("❌ Speech Recognition not supported. Use Google Chrome.");
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = "en-IN"; // ✅ better for India users
  recognition.interimResults = false;
  recognition.continuous = false;

  statusText.innerText = "🎙️ Listening... Speak now";

  recognition.onstart = () => {
    console.log("✅ Mic listening started");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    console.log("✅ Transcript:", transcript);

    answerBox.value = transcript;   // ✅ THIS should fill your textbox
    statusText.innerText = "✅ Voice captured! Now click Submit Answer.";
  };

  recognition.onerror = (event) => {
    console.error("❌ Speech recognition error:", event.error);
    statusText.innerText = `❌ Mic error: ${event.error}. Type answer instead.`;
  };

  recognition.onend = () => {
    console.log("🎤 Mic stopped");
    if (!answerBox.value.trim()) {
      statusText.innerText = "⚠️ No voice detected. Please speak louder or type.";
    }
  };

  recognition.start();
}

/* ---------------- SUBMIT ANSWER ---------------- */
async function submitAnswer() {
const answer = answerBox.value.trim();
console.log("📌 Answer being submitted:", answer);

  if (!answer) {
    alert("⚠️ Please speak or type an answer first.");
    return;
  }

  await startCamera();
  const image_b64 = captureImageBase64();

  statusText.innerText = "⏳ Sending answer to AI...";

  fetch("http://127.0.0.1:5000/interview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      answer: answer,
      image: image_b64
    })
  })
    .then(res => res.json())
    .then(data => {
      if (data.interview_complete) {
        statusText.innerText = `✅ Interview complete! Score: ${data.average_score} (${data.performance})`;
      } else {
        statusText.innerText = `✅ Next Question Incoming... Score: ${data.current_score}`;
      }

      playAudio(data.audio);
      answerBox.value = ""; // clear for next question
    })
    .catch(err => {
      console.error("Backend error:", err);
      statusText.innerText = "❌ Backend error while submitting answer";
    });
}
