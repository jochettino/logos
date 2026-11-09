// Focus the answer field so desktop players can type straight away. On touch devices
// this would pop up the on-screen keyboard on every page load, so it is skipped there.
const desktopPointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
const hasTouchScreen = navigator.maxTouchPoints > 0 || "ontouchstart" in window;

if (desktopPointer && !hasTouchScreen) {
  document.querySelector('input[name="guess"]')?.focus();
}
