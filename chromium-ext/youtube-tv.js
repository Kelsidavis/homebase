// Runs in the page before YouTube's own scripts: present as a TV so youtube.com/tv
// serves its big-screen interface, and send "exit app" back to Home Base.
(() => {
  const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox One) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19041';
  Object.defineProperty(Navigator.prototype, 'userAgent', { get: () => ua });
  Object.defineProperty(Navigator.prototype, 'userAgentData', { get: () => undefined });
  window.close = () => { location.href = 'http://127.0.0.1:8099/'; };
})();
