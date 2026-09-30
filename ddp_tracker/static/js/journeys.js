// The user journeys prototype (ddp_tracker/journeys): [data-copy] buttons copy their value, for
// example the link to a shared shortlist or a citation, and say so for a moment (.is-copied).
document.addEventListener("click", async (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-copy]") : null;
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
  } catch {
    return; // no clipboard access (for example not a secure context): nothing to confirm
  }
  button.classList.add("is-copied");
  setTimeout(() => button.classList.remove("is-copied"), 1500);
});
