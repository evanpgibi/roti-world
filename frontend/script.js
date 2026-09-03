const API_BASE_URL = (window.__APP_CONFIG__ && window.__APP_CONFIG__.apiBaseUrl) || "https://roti-world.onrender.com";

const state = {
  imageUrl: "",
  imageFile: null,
  isAnalyzing: false,
  analysisResult: null,
  selectedContour: null,
};

const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const previewPanel = document.getElementById("previewPanel");
const previewImg = document.getElementById("previewImg");
const analyzeBtn = document.getElementById("analyzeBtn");
const browseBtn = document.getElementById("browseBtn");
const cameraBtn = document.getElementById("cameraBtn");
const clearBtn = document.getElementById("clearBtn");
const resultSection = document.getElementById("resultSection");
const resultPreview = document.getElementById("resultPreview");
const resultFlag = document.getElementById("resultFlag");
const resultCountry = document.getElementById("resultCountry");
const resultScore = document.getElementById("resultScore");
const resultMessage = document.getElementById("resultMessage");
const runnerUpList = document.getElementById("runnerUpList");
const tryAnotherBtn = document.getElementById("tryAnotherBtn");
const errorBanner = document.getElementById("errorBanner");
const confirmPanel = document.getElementById("confirmPanel");
const confirmImg = document.getElementById("confirmImg");
const confirmBtn = document.getElementById("confirmBtn");
const retryConfirmBtn = document.getElementById("retryConfirmBtn");
const candidatePicker = document.getElementById("candidatePicker");
const candidateList = document.getElementById("candidateList");

function clearError() {
  if (errorBanner) {
    errorBanner.textContent = "";
    errorBanner.classList.add("hidden");
  }
}

function showError(message) {
  if (errorBanner) {
    errorBanner.textContent = message;
    errorBanner.classList.remove("hidden");
  }
  resultSection.classList.add("hidden");
  if (confirmPanel) confirmPanel.classList.add("hidden");
}

function setButtonState() {
  analyzeBtn.disabled = !state.imageUrl || state.isAnalyzing;
}

function updatePreview(file) {
  const objectUrl = URL.createObjectURL(file);
  state.imageFile = file;
  state.imageUrl = objectUrl;
  previewImg.src = objectUrl;
  previewPanel.classList.remove("hidden");
  clearError();
  setButtonState();
}

function clearPreview() {
  if (state.imageUrl && state.imageUrl.startsWith("blob:")) {
    URL.revokeObjectURL(state.imageUrl);
  }

  state.imageFile = null;
  state.imageUrl = "";
  state.analysisResult = null;
  state.selectedContour = null;
  previewImg.src = "";
  previewPanel.classList.add("hidden");
  if (confirmPanel) confirmPanel.classList.add("hidden");
  if (candidatePicker) candidatePicker.classList.add("hidden");
  fileInput.value = "";
  clearError();
  setButtonState();
}

function handleFiles(files) {
  const file = files && files[0];
  if (!file || !file.type.startsWith("image/")) {
    return;
  }

  if (state.imageUrl && state.imageUrl.startsWith("blob:")) {
    URL.revokeObjectURL(state.imageUrl);
  }

  updatePreview(file);
}

function openFilePicker(captureMode = false) {
  fileInput.setAttribute("capture", captureMode ? "environment" : "");
  fileInput.click();
}

function renderRunnerUps(items) {
  runnerUpList.innerHTML = items
    .map((country) => `
      <li>
        <div class="runner-left">
          <span class="chip">${country.flag || "🌍"}</span>
          <span>${country.country || country.name}</span>
        </div>
        <span class="runner-score">${Math.round(country.score)}%</span>
      </li>
    `)
    .join("");
}

function renderResultFromApi(matchData, previewImageSrc) {
  const winner = matchData.best_match;
  const runnerUps = (matchData.leaderboard || []).slice(1, 4).map((country) => ({
    country: country.country,
    score: country.score,
    flag: "🌍",
  }));

  resultFlag.textContent = "🌍";
  resultCountry.textContent = winner.country;
  resultScore.textContent = `${Math.round(winner.score)}%`;
  resultMessage.textContent = matchData.playful_copy || `Your chapati is giving ${winner.country}.`;
  resultPreview.src = previewImageSrc || state.imageUrl || "";

  renderRunnerUps(runnerUps);
  resultSection.classList.remove("hidden");
  if (confirmPanel) confirmPanel.classList.add("hidden");
  window.scrollTo({
    top: resultSection.offsetTop - 24,
    behavior: "smooth",
  });
}

async function fetchWithRetry(url, options = {}, retries = 2) {
  let attempt = 0;
  while (attempt <= retries) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const message = payload?.detail?.message || payload?.detail || "Request failed.";
        if (response.status === 503 || response.status === 504 || attempt < retries) {
          throw new Error(message);
        }
        throw new Error(message);
      }
      return response;
    } catch (error) {
      if (attempt >= retries) {
        throw error;
      }
      attempt += 1;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
  throw new Error("Request failed.");
}

async function analyzeChapati(file) {
  const formData = new FormData();
  formData.append("image", file);

  const response = await fetchWithRetry(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    body: formData,
  });

  return response.json();
}

async function matchContour(contour) {
  const response = await fetchWithRetry(`${API_BASE_URL}/api/match`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ contour }),
  });

  return response.json();
}

function renderCandidatePicker(result) {
  if (!candidatePicker || !result || !result.multiple_candidates || !result.candidate_contours?.length) {
    candidatePicker.classList.add("hidden");
    return;
  }

  candidateList.innerHTML = result.candidate_contours
    .map((candidate, index) => `
      <button class="candidate-option" data-index="${index}" type="button">
        Candidate ${index + 1}
      </button>
    `)
    .join("");

  candidatePicker.classList.remove("hidden");
  candidateList.querySelectorAll(".candidate-option").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedContour = result.candidate_contours[Number(button.dataset.index)];
      candidateList.querySelectorAll(".candidate-option").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
    });
  });

  state.selectedContour = result.detected_contour || result.candidate_contours[0];
}

function showConfirmStep(result, overlayImage) {
  state.analysisResult = result;
  state.selectedContour = result.detected_contour || result.candidate_contours?.[0] || [];
  confirmImg.src = overlayImage || state.imageUrl || "";
  confirmPanel.classList.remove("hidden");
  renderCandidatePicker(result);
}

async function runRealAnalysis() {
  if (!state.imageFile || state.isAnalyzing) {
    return;
  }

  state.isAnalyzing = true;
  analyzeBtn.textContent = "Scanning the dough...";
  analyzeBtn.disabled = true;

  try {
    clearError();
    const analyzeResult = await analyzeChapati(state.imageFile);
    const overlayImage = analyzeResult.overlay_image_b64
      ? `data:image/png;base64,${analyzeResult.overlay_image_b64}`
      : state.imageUrl;

    previewImg.src = overlayImage;

    if (!analyzeResult.detected_contour || !analyzeResult.detected_contour.length) {
      throw new Error("No contour was detected in the uploaded chapati image.");
    }

    state.analysisResult = analyzeResult;
    showConfirmStep(analyzeResult, overlayImage);
  } catch (error) {
    const message = error?.message || "Something went wrong while analyzing your chapati.";
    console.error("Chapati analysis failed:", error);
    showError(message);
  } finally {
    state.isAnalyzing = false;
    analyzeBtn.textContent = "Analyze My Chapati";
    setButtonState();
  }
}

async function confirmCurrentContour() {
  if (!state.selectedContour || !state.selectedContour.length) {
    showError("Please select a valid chapati contour before matching.");
    return;
  }

  try {
    clearError();
    const matchResult = await matchContour(state.selectedContour);
    renderResultFromApi(matchResult, confirmImg.src || state.imageUrl || "");
  } catch (error) {
    showError(error?.message || "Could not match the selected chapati contour.");
  }
}

browseBtn.addEventListener("click", (event) => {
  event.stopPropagation();
  openFilePicker(false);
});

cameraBtn.addEventListener("click", (event) => {
  event.stopPropagation();
  openFilePicker(true);
});

clearBtn.addEventListener("click", clearPreview);
fileInput.addEventListener("change", (event) => handleFiles(event.target.files));
analyzeBtn.addEventListener("click", runRealAnalysis);
confirmBtn.addEventListener("click", confirmCurrentContour);
retryConfirmBtn.addEventListener("click", () => {
  if (confirmPanel) confirmPanel.classList.add("hidden");
  previewPanel.classList.remove("hidden");
  clearError();
});
tryAnotherBtn.addEventListener("click", () => {
  resultSection.classList.add("hidden");
  clearError();
  clearPreview();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("drag-active");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("drag-active");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("drag-active");
  handleFiles(event.dataTransfer.files);
});

dropzone.addEventListener("click", (event) => {
  if (event.target.closest("button")) {
    return;
  }
  openFilePicker(false);
});

setButtonState();
resultSection.classList.add("hidden");
if (confirmPanel) confirmPanel.classList.add("hidden");
if (candidatePicker) candidatePicker.classList.add("hidden");
