/* ══════════════════════════════════════════════════════════════════════
   OutfitGenie — shared UI behaviour
   Theme, toasts, lightbox, and the spectrum's load animation.
   Loaded on every page that extends base.html.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── theme ────────────────────────────────────────────────────────
     Three viewer states: explicit light, explicit dark, and unset (follow
     the system). The toggle only ever writes the two explicit ones. */
  function systemPrefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function isDark() {
    var stamped = document.documentElement.getAttribute("data-theme");
    if (stamped === "dark") return true;
    if (stamped === "light") return false;
    return systemPrefersDark();
  }

  function syncThemeButton() {
    var button = document.getElementById("theme-toggle");
    var label = document.getElementById("theme-toggle-label");
    if (!button) return;
    var dark = isDark();
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    if (label) label.textContent = dark ? "Light" : "Dark";
  }

  var themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("og-theme", next); } catch (e) { /* private mode */ }
      syncThemeButton();
    });
  }
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeButton);
  syncThemeButton();

  /* ── toast ────────────────────────────────────────────────────────
     Replaces alert(). Says what happened, in the interface's voice. */
  var toastTimer = null;
  window.ogToast = function (message, isError) {
    var el = document.getElementById("toast");
    if (!el) { if (isError) console.error(message); return; }
    el.textContent = message;
    el.classList.toggle("is-error", !!isError);
    el.classList.add("is-shown");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove("is-shown"); }, isError ? 5200 : 3200);
  };

  /* ── lightbox ─────────────────────────────────────────────────────
     Any element carrying data-full-image opens its source full size. */
  var lightbox = null;
  var lightboxImage = null;
  var lastFocused = null;

  function ensureLightbox() {
    if (lightbox) return;
    lightbox = document.createElement("div");
    lightbox.className = "lightbox";
    lightbox.setAttribute("role", "dialog");
    lightbox.setAttribute("aria-modal", "true");
    lightbox.setAttribute("aria-label", "Full size image");
    lightbox.tabIndex = -1;
    lightboxImage = document.createElement("img");
    lightboxImage.alt = "";
    lightbox.appendChild(lightboxImage);
    document.body.appendChild(lightbox);
    lightbox.addEventListener("click", function (event) {
      if (event.target !== lightboxImage) closeLightbox();
    });
  }

  function openLightbox(source, alt) {
    ensureLightbox();
    lastFocused = document.activeElement;
    lightboxImage.src = source;
    lightboxImage.alt = alt || "";
    lightbox.classList.add("is-open");
    requestAnimationFrame(function () { lightbox.classList.add("is-shown"); });
    lightbox.focus();
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("is-shown");
    setTimeout(function () {
      lightbox.classList.remove("is-open");
      if (lastFocused && lastFocused.focus) lastFocused.focus();
    }, reduceMotion ? 0 : 220);
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-full-image]");
    if (!trigger) return;
    event.preventDefault();
    openLightbox(trigger.getAttribute("data-full-image"), trigger.getAttribute("data-full-alt"));
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && lightbox && lightbox.classList.contains("is-open")) closeLightbox();
  });

  /* ── the spectrum develops ────────────────────────────────────────
     Segments grow from zero, left to right, once on load. The only
     orchestrated motion in the app. */
  function developSpectrum(band) {
    if (!band || band.classList.contains("is-empty")) return;
    var segments = Array.prototype.slice.call(band.querySelectorAll(".seg"));
    if (!segments.length) return;
    if (reduceMotion) return;

    segments.forEach(function (segment) {
      segment.dataset.grow = segment.style.getPropertyValue("--n") || "1";
      segment.classList.add("is-loading");
    });
    requestAnimationFrame(function () {
      segments.forEach(function (segment, index) {
        setTimeout(function () { segment.classList.remove("is-loading"); }, 60 + index * 55);
      });
    });
  }

  document.querySelectorAll("[data-develop]").forEach(developSpectrum);
  window.ogDevelopSpectrum = developSpectrum;

  /* ── pointer glow ─────────────────────────────────────────────────
     Eased toward the cursor rather than pinned to it, so the light
     drifts in the background instead of tracking the eye. Its hue is
     the wardrobe's dominant colour, set on <body> by the template. */
  var glow = document.querySelector(".glow");
  var finePointer = window.matchMedia("(hover: hover)").matches;

  if (glow && finePointer && !reduceMotion) {
    var targetX = 0, targetY = 0;   // where the pointer is
    var glowX = 0, glowY = 0;       // where the light has caught up to
    var primed = false;
    var frame = null;

    function drift() {
      glowX += (targetX - glowX) * 0.045;
      glowY += (targetY - glowY) * 0.045;
      glow.style.setProperty("--mx", glowX.toFixed(1) + "px");
      glow.style.setProperty("--my", glowY.toFixed(1) + "px");
      frame = (Math.abs(targetX - glowX) > 0.5 || Math.abs(targetY - glowY) > 0.5)
        ? window.requestAnimationFrame(drift)
        : null;
    }

    window.addEventListener("pointermove", function (event) {
      targetX = event.clientX;
      targetY = event.clientY;
      if (!primed) {                // start where the pointer already is
        primed = true;
        glowX = targetX;
        glowY = targetY;
      }
      if (!frame) frame = window.requestAnimationFrame(drift);
    }, { passive: true });

    document.addEventListener("pointerleave", function () { glow.style.opacity = "0"; });
    document.addEventListener("pointerenter", function () { glow.style.opacity = ""; });
  }

  /* ── hover sheen ──────────────────────────────────────────────────
     Surfaces lift toward the cursor while it's over them. One delegated
     listener rather than one per card, so it costs nothing on a page
     with fifty of them. */
  if (finePointer && !reduceMotion) {
    document.addEventListener("pointermove", function (event) {
      var surface = event.target.closest(".sheen");
      if (!surface) return;
      var box = surface.getBoundingClientRect();
      surface.style.setProperty("--px", (event.clientX - box.left) + "px");
      surface.style.setProperty("--py", (event.clientY - box.top) + "px");
    }, { passive: true });
  }
})();
