// The suggestion queues ([data-proposals]): one at a time. ↑/↓ move between suggestions, "a"
// accepts the focused one, "r" goes to its reason (Enter there rejects). Not while typing.
document.addEventListener("keydown", (event) => {
  const list = document.querySelector("[data-proposals]");
  if (!list || event.altKey || event.ctrlKey || event.metaKey) return;
  const target = event.target instanceof Element ? event.target : document.body;
  if (target.closest("input, textarea, select")) return;
  const entries = [...list.querySelectorAll("[data-proposal]")];
  const current = target.closest("[data-proposal]");
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const index = entries.indexOf(current);
    const step = event.key === "ArrowDown" ? 1 : -1;
    const next = index === -1 ? 0 : Math.min(Math.max(index + step, 0), entries.length - 1);
    entries[next]?.focus();
  } else if (event.key === "a" && current) {
    current.querySelector("[data-accept]")?.click();
  } else if (event.key === "r" && current) {
    event.preventDefault(); // don't type the "r" into the reason
    current.querySelector("[data-reason]")?.focus();
  }
});

// After a decision the entry is replaced: keep the focus on it, so ↓ goes on from there.
document.addEventListener("htmx:afterSettle", (event) => {
  const entry = event.detail.elt;
  if (entry instanceof HTMLElement && entry.matches("[data-proposals] [data-proposal]")) {
    entry.focus();
  }
});
