// Focus the answer field so desktop players can type straight away. On touch devices
// this would pop up the on-screen keyboard on every page load, so it is skipped there.
const desktopPointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const hasTouchScreen = navigator.maxTouchPoints > 0 || "ontouchstart" in window;

if (desktopPointer && !hasTouchScreen) {
  document.querySelector('input[name="guess"]')?.focus();
}

// Share the final score. Uses the system share sheet where it exists (phones), and the
// clipboard otherwise, so desktop browsers get a copyable message too.
const shareButton = document.querySelector(".share-button");

if (shareButton) {
  const status = document.querySelector(".share-status");
  const text = shareButton.dataset.shareText;
  const url = shareButton.dataset.shareUrl;

  shareButton.addEventListener("click", async () => {
    if (navigator.share) {
      try {
        await navigator.share({ text, url });
        return;
      } catch (error) {
        if (error.name === "AbortError") return; // player closed the share sheet
      }
    }
    try {
      await navigator.clipboard.writeText(`${text} ${url}`);
      status.textContent = "Copied! Paste it anywhere.";
    } catch {
      status.textContent = `${text} ${url}`; // last resort: leave it selectable on screen
    }
  });
}
