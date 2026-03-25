// Get elements
const summarizeBtn = document.getElementById("summarizeBtn");
const videoLinkInput = document.getElementById("videoLink");
const lengthSelect = document.getElementById("lengthSelect");
const bulletModeCheckbox = document.getElementById("bulletMode");
const summaryText = document.getElementById("summaryText");
const copyBtn = document.getElementById("copyBtn");
const videoMeta = document.getElementById("videoMeta");
const videoThumbnail = document.getElementById("videoThumbnail");
const videoTitle = document.getElementById("videoTitle");
const inputError = document.getElementById("inputError");
const loadingSpinner = document.getElementById("loadingSpinner");
// Handle summarize button click
summarizeBtn.addEventListener("click", async () => {
    const videoUrl = videoLinkInput.value.trim();
    const length = lengthSelect.dataset.value||"medium";
    const bullet = bulletModeCheckbox.checked;

    if (!videoUrl) {
    inputError.innerText = "⚠️ Please enter a YouTube URL";
    inputError.classList.remove("hidden");
    return;
    }
    
    inputError.classList.add("hidden");
    summaryText.innerText = ""; // clear old text
    loadingSpinner.classList.remove("hidden");
    videoMeta.classList.add("hidden");
//  Disable button
    summarizeBtn.disabled = true;
    summarizeBtn.classList.add("opacity-50", "cursor-not-allowed");
    summarizeBtn.innerText = "Processing...";
    copyBtn.disabled = true;
    copyBtn.classList.add("opacity-50", "cursor-not-allowed");
    try {
        const response = await fetch("/summarize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url: videoUrl,
                length: length,
                bullet: bullet
            })
        });
        
        const data = await response.json();

        if (data.error) {
            loadingSpinner.classList.add("hidden");
            summaryText.innerText = "⚠️ " + data.error;
   
            //  Make it red
            summaryText.classList.remove("text-gray-800");
            summaryText.classList.add("text-red-500");
            videoMeta.classList.add("hidden");
        } else {
            loadingSpinner.classList.add("hidden");
            // Show title + thumbnail
            videoMeta.classList.remove("hidden");
            videoThumbnail.src = data.thumbnail;
            videoTitle.innerText = data.title;

            // Reset to normal color
            summaryText.classList.remove("text-red-500");
            summaryText.classList.add("text-gray-800");

            summaryText.innerText = data.summary;
            copyBtn.disabled = false;
            copyBtn.classList.remove("opacity-50", "cursor-not-allowed");
        }

    } catch (err) {
        summaryText.innerText = "⚠️ Something went wrong!";

// make it red
        summaryText.classList.remove("text-gray-800");
        summaryText.classList.add("text-red-500");
        videoMeta.classList.add("hidden");
        console.error(err);
    }
    // Re-enable button
summarizeBtn.innerText = "Summarize →";
summarizeBtn.disabled = false;
summarizeBtn.classList.remove("opacity-50", "cursor-not-allowed");
});

// Handle copy button
copyBtn.addEventListener("click", () => {
    const text = summaryText.innerText;

    if (text && text !== "Your summary will appear here...") {
        navigator.clipboard.writeText(text);

        // Change button text
        copyBtn.innerText = "✓ Copied";
        copyBtn.classList.add("bg-green-200");

        // Reset after 2 seconds
        setTimeout(() => {
            copyBtn.innerText = "Copy";
            copyBtn.classList.remove("bg-green-200");
        }, 2000);
    }
});


const selectBtn = document.getElementById("lengthSelect");
    const optionsList = document.getElementById("lengthOptions");
    const selectedText = document.getElementById("selectedOption");
    selectBtn.dataset.value = "medium";
    // Toggle dropdown
    selectBtn.addEventListener("click", () => {
        optionsList.classList.toggle("hidden");
    });

    // Select option
    optionsList.querySelectorAll("li").forEach(option => {
        option.addEventListener("click", () => {
            selectedText.textContent = option.textContent;
            selectBtn.dataset.value = option.dataset.value; // store selected value
            optionsList.classList.add("hidden");
        });
    });
// Close if clicked outside
    document.addEventListener("click", (e) => {
        if (!selectBtn.contains(e.target) && !optionsList.contains(e.target)) {
            optionsList.classList.add("hidden");
        }
    });

videoLinkInput.addEventListener("input", () => {
    inputError.classList.add("hidden");
});