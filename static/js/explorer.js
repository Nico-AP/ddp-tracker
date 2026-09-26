// The platform explorer: keep the tree node whose details are shown in the side panel
// highlighted (#node-detail is loaded by htmx when a .tree__name button is clicked).
document.addEventListener("htmx:beforeRequest", (event) => {
  const button = event.detail.elt;
  if (!button.matches(".tree__name") || event.detail.target?.id !== "node-detail") return;
  document.querySelectorAll(".tree__name--selected").forEach((previous) => {
    previous.classList.remove("tree__name--selected");
    previous.removeAttribute("aria-current");
  });
  button.classList.add("tree__name--selected");
  button.setAttribute("aria-current", "true");
});
