/* ══════════════════════════════════════════════════════════════════════
   OutfitGenie — wardrobe
   Selection, favouriting, deletion, and filtering the rail by colour.
   The lightbox and theme live in ui.js.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : null;
  }

  function say(message, isError) {
    if (window.ogToast) window.ogToast(message, isError);
    else if (isError) console.error(message);
  }

  function looks(n) {
    return n + (n === 1 ? " look" : " looks");
  }

  function checkboxes() {
    return Array.prototype.slice.call(document.querySelectorAll("input.outfit-checkbox"));
  }

  function selectedIds() {
    return checkboxes().filter(function (box) { return box.checked; })
                       .map(function (box) { return box.dataset.outfitId; });
  }

  /* ── single-look actions ──────────────────────────────────────────
     Exposed on window because the markup calls them inline. */
  window.toggleFavorite = async function (id) {
    var card = document.querySelector('[data-outfit-id="' + id + '"]');
    var button = card ? card.querySelector(".favorite-btn") : null;
    var wasFavourite = button ? button.getAttribute("aria-pressed") === "true" : false;

    var token = csrfToken();
    if (!token) { say("Your session expired. Reload the page.", true); return false; }

    try {
      var response = await fetch("/feedback", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": token },
        body: JSON.stringify({ outfit_id: id, rating: wasFavourite ? 0 : 1 })
      });
      if (!response.ok) throw new Error();
      if (button) button.setAttribute("aria-pressed", wasFavourite ? "false" : "true");
      return true;
    } catch (error) {
      say("Couldn't update that favourite. Try again.", true);
      return false;
    }
  };

  window.deleteOutfit = async function (id, confirmFirst) {
    if (confirmFirst !== false && !confirm("Delete this look? This can't be undone.")) return false;

    var token = csrfToken();
    if (!token) { say("Your session expired. Reload the page.", true); return false; }

    try {
      var response = await fetch("/delete-outfit/" + id, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": token }
      });
      if (!response.ok) throw new Error();
      var card = document.querySelector('[data-outfit-id="' + id + '"]');
      if (card) card.remove();
      if (!document.querySelectorAll("[data-outfit-id]").length) {
        window.location.reload();
      }
      return true;
    } catch (error) {
      say("Couldn't delete that look. Try again.", true);
      return false;
    }
  };

  document.addEventListener("DOMContentLoaded", function () {

    /* ── bulk actions ───────────────────────────────────────────────── */
    var selectAll = document.getElementById("select-all");
    var clearAll = document.getElementById("deselect-all");
    var favouriteSelected = document.getElementById("favorite-selected");
    var deleteSelected = document.getElementById("delete-selected");

    if (selectAll) {
      selectAll.addEventListener("click", function () {
        checkboxes().forEach(function (box) { box.checked = true; });
      });
    }
    if (clearAll) {
      clearAll.addEventListener("click", function () {
        checkboxes().forEach(function (box) { box.checked = false; });
      });
    }

    if (favouriteSelected) {
      favouriteSelected.addEventListener("click", async function () {
        var ids = selectedIds();
        if (!ids.length) { say("Select a look first.", true); return; }
        favouriteSelected.disabled = true;
        var done = 0;
        for (var i = 0; i < ids.length; i++) {
          if (await window.toggleFavorite(ids[i])) done++;
        }
        checkboxes().forEach(function (box) { box.checked = false; });
        favouriteSelected.disabled = false;
        if (done) say(looks(done) + " updated");
      });
    }

    if (deleteSelected) {
      deleteSelected.addEventListener("click", async function () {
        var ids = selectedIds();
        if (!ids.length) { say("Select a look first.", true); return; }
        if (!confirm("Delete " + looks(ids.length) + "? This can't be undone.")) return;
        deleteSelected.disabled = true;
        var done = 0;
        for (var i = 0; i < ids.length; i++) {
          if (await window.deleteOutfit(ids[i], false)) done++;
        }
        deleteSelected.disabled = false;
        if (done) say(looks(done) + " deleted");
      });
    }

    /* ── the detail switch ──────────────────────────────────────────── */
    var detailSwitch = document.getElementById("toggle-detected-items");
    if (detailSwitch) {
      var applyDetail = function (isOn) {
        detailSwitch.setAttribute("aria-checked", isOn ? "true" : "false");
        document.querySelectorAll(".detected-items-section").forEach(function (section) {
          section.hidden = !isOn;
          if (!isOn) section.open = false;
        });
      };
      applyDetail(true);
      detailSwitch.addEventListener("click", function () {
        applyDetail(detailSwitch.getAttribute("aria-checked") !== "true");
      });
    }

    /* ── opening the analysis promotes the look to full width ───────
       Twelve attributes don't fit a 17rem column. Opening one expands
       it across the rail and puts the photo beside the text; only one
       stays open, so the rail never turns into a wall of specs. */
    document.querySelectorAll(".look .detected-items-section").forEach(function (panel) {
      panel.addEventListener("toggle", function () {
        var card = panel.closest(".look");
        if (!card) return;

        if (panel.open) {
          document.querySelectorAll(".look .detected-items-section[open]").forEach(function (other) {
            if (other !== panel) other.open = false;
          });
          card.classList.add("is-open");
          panel.querySelector("summary").textContent = "Close";
        } else {
          card.classList.remove("is-open");
          panel.querySelector("summary").textContent = "What the AI read";
        }
      });
    });

    /* Colour filtering is a server-side query now — see outfits.my_outfits.
       Doing it here only ever searched the cards on the current page, so a
       colour whose looks sat on page 2 reported no matches at all. */
  });
})();
