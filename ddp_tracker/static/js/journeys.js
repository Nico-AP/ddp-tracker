// The user journeys prototype (ddp_tracker/journeys): [data-copy] buttons copy their value, for
// example the link to a shared shortlist or a citation. The page says so in its
// [data-copy-status] element (a role="status", so that screen readers announce it): the
// button's data-copied text, or "Copied". The button also gets .is-copied for a moment, which
// styles nothing of its own.
const announce = (text) => {
  const status = document.querySelector("[data-copy-status]");
  if (!status) return;
  status.textContent = ""; // cleared first, so that copying twice is announced twice
  setTimeout(() => {
    status.textContent = text;
  }, 50);
};

document.addEventListener("click", async (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-copy]") : null;
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
  } catch {
    // no clipboard access (for example not a secure context): nothing was copied
    announce("Could not copy. Select the text and copy it yourself.");
    return;
  }
  button.classList.add("is-copied");
  setTimeout(() => button.classList.remove("is-copied"), 1500);
  announce(button.dataset.copied || "Copied");
});
