// Submit feedback: on a POST form submit, show a spinner on the submit button
// and disable further clicks. The page navigates (303 redirect) so the loading
// state naturally clears on the next render. Skips cancelled submits (e.g. a
// "confirm" dialog that returned false) and forms opting out with data-noloading.
document.addEventListener("submit", (e) => {
  if (e.defaultPrevented) return;
  const form = e.target;
  if ((form.getAttribute("method") || "get").toLowerCase() !== "post") return;
  if (form.dataset.noloading !== undefined) return;
  const btn = form.querySelector("button[type=submit], button:not([type])");
  if (btn) {
    btn.classList.add("is-loading");
    // defer disabling so the button's value (if any) is still submitted
    setTimeout(() => { btn.disabled = true; }, 0);
  }
});

// Checkbox toggles post to the API without a page reload.
document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.matches("[data-toggle-url]")) {
    const li = el.closest(".check-item");
    try {
      const res = await fetch(el.dataset.toggleUrl, { method: "POST" });
      const body = await res.json();
      if (li) li.classList.toggle("done", !!(body.done ?? body.status === "done"));
      if (el.dataset.reload !== undefined) location.reload();
    } catch {
      el.checked = !el.checked;
    }
  }
});
