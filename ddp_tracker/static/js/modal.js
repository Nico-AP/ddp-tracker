// The shared modal (#modal in base.html): htmx loads a form into it, which opens it; a response
// that swaps in nothing (a successful save) closes it. Close buttons are <form method="dialog">.
//
// On pages with a [data-dialog-over] element (the review's and the explorer's left column), it
// opens non-modal, over that element, so the side panel next to it stays visible and usable;
// elsewhere it is a centred modal (Esc, backdrop and focus from the native <dialog>).
const overlay = () => document.querySelector("[data-dialog-over]");

// Place the dialog over the element (inline styles through the CSSOM, which the CSP allows).
function place(dialog, over) {
  const box = over.getBoundingClientRect();
  dialog.style.left = `${Math.max(box.left, 0)}px`;
  dialog.style.width = `${box.width}px`;
}

function open(dialog) {
  const over = overlay();
  if (over) {
    dialog.classList.add("dialog--over");
    place(dialog, over);
    dialog.show();
  } else {
    dialog.showModal();
  }
  dialog.querySelector("input:not([type=hidden]), textarea, select")?.focus();
}

document.addEventListener("htmx:afterSwap", (event) => {
  const dialog = document.getElementById("modal");
  if (event.detail.target !== dialog) return;
  if (dialog.innerHTML.trim() === "") {
    dialog.close();
  } else if (!dialog.open) {
    open(dialog);
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.getElementById("modal");
  dialog?.addEventListener("close", () => {
    dialog.replaceChildren();
    dialog.classList.remove("dialog--over");
  });
});

window.addEventListener("resize", () => {
  const dialog = document.getElementById("modal");
  const over = overlay();
  if (dialog?.open && over && dialog.classList.contains("dialog--over")) place(dialog, over);
});

// A non-modal dialog doesn't close on Esc by itself.
document.addEventListener("keydown", (event) => {
  const dialog = document.getElementById("modal");
  if (event.key === "Escape" && dialog?.open && dialog.classList.contains("dialog--over")) {
    dialog.close();
  }
});

// [data-filter-table="#id"]: hide the table's rows whose data-filter-text doesn't contain the
// query; its [data-filter-empty] row shows when none are left.
document.addEventListener("input", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.dataset.filterTable) return;
  const table = document.querySelector(input.dataset.filterTable);
  if (!table) return;
  const query = input.value.trim().toLowerCase();
  let shown = 0;
  table.querySelectorAll("tbody tr[data-filter-text]").forEach((row) => {
    row.hidden = !row.dataset.filterText.includes(query);
    if (!row.hidden) shown += 1;
  });
  const empty = table.querySelector("[data-filter-empty]");
  if (empty) empty.hidden = shown > 0;
});
