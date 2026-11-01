// The remote's Home key (and F1 as a fallback) returns to Home Base from any site.
window.addEventListener('keydown', (e) => {
  if (e.key === 'BrowserHome' || e.key === 'GoHome' || e.key === 'F1') {
    e.preventDefault();
    e.stopImmediatePropagation();
    location.href = 'http://127.0.0.1:8099/';
  }
}, true);
