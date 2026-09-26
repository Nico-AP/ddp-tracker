// The shared modal (#modal in base.html): htmx loads a form into it, which opens it; a response
// that swaps in nothing (a successful save) closes it. Esc, backdrop and focus come with the
// native <dialog>; close buttons are <form method="dialog">.
document.addEventListener("htmx:afterSwap", (event) => {
  const dialog = document.getElementById("modal");
  if (event.detail.target !== dialog) return;
  if (dialog.innerHTML.trim() === "") {
    dialog.close();
  } else if (!dialog.open) {
    dialog.showModal();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.getElementById("modal");
  dialog?.addEventListener("close", () => {
    dialog.replaceChildren();
  });
});
