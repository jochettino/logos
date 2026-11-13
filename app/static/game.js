// Focus the answer field so desktop players can type straight away. On touch devices
// this would pop up the on-screen keyboard on every page load, so it is skipped there.
const desktopPointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const hasTouchScreen = navigator.maxTouchPoints > 0 || "ontouchstart" in window;

function focusGuess() {
  if (!desktopPointer || hasTouchScreen) return;
  document.querySelector('input[name="guess"]')?.focus();
}

// Share the final score. Uses the system share sheet where it exists (phones), and the
// clipboard otherwise, so desktop browsers get a copyable message too.
function bindShareButton() {
  const shareButton = document.querySelector(".share-button");
  if (!shareButton) return;

  const status = document.querySelector(".share-status");
  const text = shareButton.dataset.shareText;
  const url = shareButton.dataset.shareUrl;

  // iOS Safari drops the text when both `text` and `url` are passed to the share sheet,
  // sharing only the link. Passing the message alone, link included, works everywhere.
  const message = `${text} ${url}`;

  shareButton.addEventListener("click", async () => {
    if (navigator.share) {
      try {
        await navigator.share({ text: message });
        return;
      } catch (error) {
        if (error.name === "AbortError") return; // player closed the share sheet
      }
    }
    try {
      await navigator.clipboard.writeText(message);
      status.textContent = "Copied! Paste it anywhere.";
    } catch {
      status.textContent = message; // last resort: leave it selectable on screen
    }
  });
}

// Replace the parts of the page a guess changes, so the header, footer and styles stay put
// and the next image repaints without a full reload. The server renders these as HTML, so
// the markup lives in one place (the Jinja templates) rather than being rebuilt here.
function swapIn(html) {
  const next = new DOMParser().parseFromString(html, "text/html");
  const play = next.getElementById("play");
  if (!play) return false; // unexpected page: let the caller fall back to a normal load
  for (const id of ["pills", "play"]) {
    const current = document.getElementById(id);
    const replacement = next.getElementById(id);
    if (current && replacement) current.replaceWith(replacement);
  }
  // The result screens recolour the background through a body class.
  document.body.className = play.dataset.bodyClass || "";
  focusGuess();
  bindShareButton();
  return true;
}

// Guesses go out with fetch() and land as a fragment; anything unexpected (no JS support,
// no network, a stale session) falls back to the plain form POST that always worked.
function enableSwap() {
  const form = document.querySelector("form.guess");
  if (!form || !window.fetch || !window.DOMParser) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.busy) return; // ignore double taps
    form.dataset.busy = "1";

    let response;
    try {
      response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Logos-Swap": "1" },
      });
    } catch {
      form.submit(); // network failure: submit for real, the browser deals with it
      return;
    }

    const swapped = response.ok && swapIn(await response.text());
    if (!swapped) window.location.href = "/game";
  });
}

focusGuess();
bindShareButton();
enableSwap();
