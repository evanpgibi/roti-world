const state = {
  imageUrl: "",
  isAnalyzing: false,
};

const countryProfiles = [
  { name: "Italy", flag: "🇮🇹", baseScore: 92 },
  { name: "Greece", flag: "🇬🇷", baseScore: 88 },
  { name: "Brazil", flag: "🇧🇷", baseScore: 86 },
  { name: "India", flag: "🇮🇳", baseScore: 84 },
  { name: "Japan", flag: "🇯🇵", baseScore: 83 },
  { name: "Argentina", flag: "🇦🇷", baseScore: 81 },
  { name: "Mexico", flag: "🇲🇽", baseScore: 80 },
  { name: "France", flag: "🇫🇷", baseScore: 79 },
];

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

function setButtonState() {
  analyzeBtn.disabled = !state.imageUrl || state.isAnalyzing;
}

function updatePreview(file) {
  const objectUrl = URL.createObjectURL(file);
  state.imageUrl = objectUrl;
  previewImg.src = objectUrl;
  previewPanel.classList.remove("hidden");
  setButtonState();
}

function clearPreview() {
  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }

  state.imageUrl = "";
  previewImg.src = "";
  previewPanel.classList.add("hidden");
  fileInput.value = "";
  setButtonState();
}

function handleFiles(files) {
  const file = files && files[0];
  if (!file || !file.type.startsWith("image/")) {
    return;
  }

  if (state.imageUrl) {
    URL.revokeObjectURL(state.imageUrl);
  }

  updatePreview(file);
}

function openFilePicker(captureMode = false) {
  if (captureMode) {
    fileInput.setAttribute("capture", "environment");
  } else {
    fileInput.removeAttribute("capture");
  }

  fileInput.click();
}

function calculateProfile(seed) {
  const safeSeed = (seed || "chapati").toLowerCase();
  const base = Array.from(safeSeed).reduce((total, char) => total + char.charCodeAt(0), 0);

  return countryProfiles
    .map((country, index) => {
      const variance = ((base + index * 13) % 17) - 8;
      return {
        ...country,
        score: Math.max(61, Math.min(98, country.baseScore + variance)),
      };
    })
    .sort((a, b) => b.score - a.score);
}

function renderRunnerUps(items) {
  runnerUpList.innerHTML = items
    .map(
      (country) => `
        <li>
          <div class="runner-left">
            <span class="chip">${country.flag}</span>
            <span>${country.name}</span>
          </div>
          <span class="runner-score">${Math.round(country.score)}%</span>
        </li>
      `,
    )
    .join("");
}

function renderResult() {
  const ranked = calculateProfile(state.imageUrl || "chapati");
  const winner = ranked[0];
  const runnerUps = ranked.slice(1, 4);

  resultFlag.textContent = winner.flag;
  resultCountry.textContent = winner.name;
  resultScore.textContent = `${Math.round(winner.score)}%`;
  resultMessage.textContent = `Your chapati is giving ${winner.name}.`;
  resultPreview.src = state.imageUrl;

  renderRunnerUps(runnerUps);
  resultSection.classList.remove("hidden");
  window.scrollTo({
    top: resultSection.offsetTop - 24,
    behavior: "smooth",
  });
}

function simulateAnalysis() {
  if (!state.imageUrl || state.isAnalyzing) {
    return;
  }

  state.isAnalyzing = true;
  analyzeBtn.textContent = "Scanning the dough...";
  analyzeBtn.disabled = true;

  window.setTimeout(() => {
    renderResult();
    state.isAnalyzing = false;
    analyzeBtn.textContent = "Analyze My Chapati";
    setButtonState();
  }, 900);
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
analyzeBtn.addEventListener("click", simulateAnalysis);
tryAnotherBtn.addEventListener("click", () => {
  resultSection.classList.add("hidden");
  clearPreview();
  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
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
