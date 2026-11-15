(function () {
  'use strict';
  const intro = document.getElementById('satellite-intro');
  const button = document.getElementById('intro-skip'), status = document.getElementById('intro-status');
  const began = performance.now();
  let closed = false;
  const background = () => document.querySelectorAll('header, main, footer');
  document.addEventListener('DOMContentLoaded', () => {
    if (closed) return;
    background().forEach(el => { el.inert = true; });
    button.focus({ preventScroll: true });
  });
  function dismiss(enterWorkspace = false) {
    if (closed) return; closed = true;
    const focused = intro.contains(document.activeElement);
    intro.hidden = true;
    background().forEach(el => { el.inert = false; });
    window.dispatchEvent(new Event('seam-intro-dismissed'));
    if (focused) {
      // Automatic loading must not consume the first keyboard stop (the skip link).
      // An explicit Skip/Escape enters the workspace instead.
      const target = enterWorkspace ? document.getElementById('main') : document.body;
      const oldTabIndex = target.getAttribute('tabindex');
      target.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
      if (oldTabIndex === null) target.removeAttribute('tabindex');
      else target.setAttribute('tabindex', oldTabIndex);
    }
  }
  button.addEventListener('click', () => dismiss(true));
  intro.addEventListener('keydown', e => {
    if (e.key === 'Escape') dismiss(true);
    if (e.key === 'Tab') { e.preventDefault(); button.focus(); }
  });
  window.SeamIntro = { dismiss, ready() {
    status.textContent = 'Your workspace is ready';
    const motion = window.Seam ? Seam.motionMode() : 'reduced';
    setTimeout(dismiss, motion === 'full' ? Math.max(0, 1600 - (performance.now()-began)) : 0);
  }};
  // A slow request or broken script must never trap the user behind a splash.
  setTimeout(dismiss, 10000);
})();
