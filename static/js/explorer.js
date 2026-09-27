// The explorer's tree and the review's tables: keep what the side panel shows highlighted. A
// click on a .tree__name or [data-panel-open] button loads #node-detail (htmx); the selected
// element is the button's [data-panel-row] (a table row), or the button itself.
document.addEventListener("htmx:beforeRequest", (event) => {
  const opener = event.detail.elt;
  if (!opener.matches(".tree__name, [data-panel-open]")) return;
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
