// The explorer's and the review's trees: keep what the side panel shows highlighted. A click on
// a [data-panel-open] button loads #node-detail (htmx); the selected element is the button's
// [data-panel-row], or the button itself.
document.addEventListener("htmx:beforeRequest", (event) => {
  const opener = event.detail.elt;
  if (!opener.matches("[data-panel-open]")) return;
  if (event.detail.target?.id !== "node-detail") return;
  document.querySelectorAll(".is-selected").forEach((previous) => {
    previous.classList.remove("is-selected");
    previous.removeAttribute("aria-current");
  });
  const selected = opener.closest("[data-panel-row]") ?? opener;
  selected.classList.add("is-selected");
  selected.setAttribute("aria-current", "true");
});

// A click anywhere on a [data-panel-row] (not on its own buttons, links or forms) opens it too:
// through its [data-panel-open] button, which stays the keyboard's way in.
document.addEventListener("click", (event) => {
  const row = event.target.closest("[data-panel-row]");
  if (!row || event.target.closest("button, a, input, select, textarea, label, form, summary")) return;
  row.querySelector("[data-panel-open]")?.click();
});

// The review's and the explorer's trees: ↑/↓ select the previous/next row (opening its panel);
// in the review ([data-annotating]), Enter presses the panel's primary action ("Use suggestion"
// or "Add annotation"). Not while typing in a field.
document.addEventListener("keydown", (event) => {
  const tree = document.querySelector("[data-review-tree]");
  if (!tree || event.altKey || event.ctrlKey || event.metaKey) return;
  // not under an open dialog: the panel would switch to another row than the dialog's
  if (document.getElementById("modal")?.open) return;
  const target = event.target instanceof Element ? event.target : document.body;
  if (target.closest("input, select, textarea, dialog, [contenteditable]")) return;
  if (event.key === "Enter") {
    if (!tree.hasAttribute("data-annotating")) return; // the explorer: only the review annotates
    const action = document.querySelector("#node-detail [data-primary-action]");
    // on another button or link, Enter is that one's (a focused row name is the row itself)
    const other = target.closest("button, a, summary");
    if (!action || (other && !other.matches("[data-panel-open]"))) return;
    event.preventDefault();
    action.click();
    return;
  }
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  // rows in collapsed files or groups aren't visible: skip them
  const rows = [...tree.querySelectorAll("[data-panel-row]")].filter(
    (row) => !row.parentElement.closest("details:not([open])"),
  );
  if (!rows.length) return;
  event.preventDefault();
  const current = rows.findIndex((row) => row.classList.contains("is-selected"));
  const step = event.key === "ArrowDown" ? 1 : -1;
  const next = rows[current === -1 ? 0 : Math.min(Math.max(current + step, 0), rows.length - 1)];
  next.querySelector("[data-panel-open]")?.click();
  next.scrollIntoView({ block: "nearest" });
});

// [data-copy] buttons copy their value (e.g. a path) and say so for a moment.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
  } catch {
    return; // no clipboard access (e.g. not a secure context): nothing to confirm
  }
  button.classList.add("is-copied");
  setTimeout(() => button.classList.remove("is-copied"), 1500);
});

// A row reloads itself after a change (outerHTML): keep it highlighted if it was.
let selectedRow = null;
document.addEventListener("htmx:beforeRequest", (event) => {
  const opener = event.detail.elt;
  if (opener.matches("[data-panel-open]") && event.detail.target?.id === "node-detail") {
    selectedRow = opener.closest("[data-panel-row]")?.getAttribute("hx-get") ?? null;
  }
});
document.addEventListener("htmx:afterSettle", () => {
  if (!selectedRow) return;
  const row = document.querySelector(`[data-panel-row][hx-get="${CSS.escape(selectedRow)}"]`);
  if (row && !row.classList.contains("is-selected")) {
    row.classList.add("is-selected");
    row.setAttribute("aria-current", "true");
  }
});
