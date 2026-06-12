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
