/** Tabler presentation adapters. No financial calculations or API calls. */
const ICONS = {
  screener: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12"/>',
  company: '<path d="M4 20V10h4v10m2 0V4h4v16m2 0V8h4v12M3 20h18"/>',
  compare: '<path d="M3 7h17m-4-4 4 4-4 4M21 17H4m4-4-4 4 4 4"/>',
  explain: '<path d="m3 8 5-4 8 4 5-4M3 14l5-4 8 4 5-4M3 20l5-4 8 4 5-4"/>',
  manual: '<path d="m14 5 5 5M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15z"/>',
  science: '<circle cx="7" cy="7" r="3"/><circle cx="17" cy="7" r="3"/><circle cx="7" cy="17" r="3"/><circle cx="17" cy="17" r="3"/>',
  reports: '<path d="M7 3h8l4 4v14H5V3h2m7 0v5h5M8 12h8m-8 4h6"/>',
  admin: '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7zM8 12l3 3 5-6"/>',
};

/** Apply Tabler controls to newly rendered legacy components without rebinding actions. */
function enhance(root) {
  if (!(root instanceof Element || root instanceof Document)) return;
  const controls = [
    ['input:not([type="checkbox"]):not([type="radio"]):not([type="range"]), textarea', "form-control"],
    ["select", "form-select"],
    [".data-table", "table"],
    [".credit-action, .account-actions button, .account-form button, .system-status button, .command-bar > button, .analyze-form button, .admin-workspace td button, #account-close", "btn"],
  ];
  for (const [selector, className] of controls) {
    if (root instanceof Element && root.matches(selector)) root.classList.add(className);
    root.querySelectorAll(selector).forEach((element) => element.classList.add(className));
  }
}

/** Bind the responsive preview shell; leave the original dashboard event handlers intact. */
export function bindPreview() {
  for (const [name, paths] of Object.entries(ICONS)) {
    const icon = document.querySelector(`#tab-${name} .nav-icon`);
    if (icon) icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  }
  const button = document.getElementById("preview-menu");
  const sidebar = document.getElementById("preview-sidebar");
  const shell = document.querySelector(".main-shell");
  const media = window.matchMedia("(min-width: 1001px)");
  const backdrop = document.createElement("button");
  backdrop.className = "fh-menu-backdrop";
  backdrop.type = "button";
  backdrop.tabIndex = -1;
  backdrop.setAttribute("aria-label", "Đóng menu điều hướng");
  document.body.append(backdrop);
  const closeMenu = () => {
    document.body.classList.remove("fh-menu-open");
    button.setAttribute("aria-expanded", "false");
    shell.inert = false;
    if (!media.matches && sidebar.contains(document.activeElement)) button.focus();
    sidebar.inert = !media.matches;
  };
  button.addEventListener("click", () => {
    const open = document.body.classList.toggle("fh-menu-open");
    if (!open) return closeMenu();
    sidebar.inert = false;
    shell.inert = true;
    button.setAttribute("aria-expanded", String(open));
    if (open) document.querySelector('.workspace-nav [aria-selected="true"]')?.focus();
  });
  backdrop.addEventListener("click", closeMenu);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("fh-menu-open")) {
      closeMenu();
      button.focus();
    }
  });
  media.addEventListener("change", closeMenu);
  window.addEventListener("finhealth:close-menu", closeMenu);
  closeMenu();
  enhance(document);
  new MutationObserver((mutations) => {
    for (const mutation of mutations) for (const node of mutation.addedNodes) enhance(node);
  }).observe(document.body, { childList: true, subtree: true });
}
