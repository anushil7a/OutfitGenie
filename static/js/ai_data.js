/* ══════════════════════════════════════════════════════════════════════
   OutfitGenie — AI data
   Editing the notes and the per-photo analysis the stylist is given.
   Images open through the shared lightbox in ui.js.
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

  async function saveNotes(notes) {
    var token = csrfToken();
    if (!token) throw new Error("Your session expired. Reload the page.");
    var response = await fetch("/update-ai-notes", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify({ notes: notes })
    });
    if (!response.ok) throw new Error("Couldn't save your notes. Try again.");
  }

  document.addEventListener("DOMContentLoaded", function () {

    /* ── existing notes ─────────────────────────────────────────────── */
    var toggleEdit = document.getElementById("toggle-edit");
    var notes = document.getElementById("existing-notes");
    var saveNotesBtn = document.getElementById("save-existing-notes");

    if (toggleEdit && notes && saveNotesBtn) {
      var original = notes.value;

      var setEditing = function (editing) {
        notes.readOnly = !editing;
        saveNotesBtn.hidden = !editing;
        toggleEdit.textContent = editing ? "Cancel" : "Edit";
        if (editing) notes.focus();
      };
      setEditing(false);

      toggleEdit.addEventListener("click", function () {
        var editing = notes.readOnly;       // about to flip
        if (!editing) notes.value = original;   // cancelling discards
        setEditing(editing);
      });

      saveNotesBtn.addEventListener("click", async function () {
        saveNotesBtn.disabled = true;
        try {
          await saveNotes(notes.value);
          original = notes.value;
          setEditing(false);
          say("Notes saved");
        } catch (error) {
          say(error.message, true);
        } finally {
          saveNotesBtn.disabled = false;
        }
      });
    }

    /* ── add a note ─────────────────────────────────────────────────── */
    var notesForm = document.getElementById("notes-form");
    if (notesForm) {
      notesForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        var field = document.getElementById("new-notes");
        var addition = field ? field.value.trim() : "";
        if (!addition) { say("Write something first.", true); return; }

        var existing = notes ? notes.value : "";
        var combined = existing ? existing + "\n" + addition : addition;

        var submit = notesForm.querySelector('button[type="submit"]');
        if (submit) submit.disabled = true;
        try {
          await saveNotes(combined);
          if (notes) notes.value = combined;
          field.value = "";
          say("Note added");
        } catch (error) {
          say(error.message, true);
        } finally {
          if (submit) submit.disabled = false;
        }
      });
    }

    /* ── editing a photo's analysis ─────────────────────────────────── */
    function parts(outfitId) {
      return {
        view: document.getElementById("outfit-description-" + outfitId),
        form: document.getElementById("edit-form-" + outfitId)
      };
    }

    document.querySelectorAll(".edit-description-btn").forEach(function (button) {
      button.addEventListener("click", function () {
        var found = parts(button.dataset.outfitId);
        if (!found.view || !found.form) return;
        found.view.hidden = true;
        found.form.hidden = false;
        button.hidden = true;
        var field = found.form.querySelector("textarea");
        if (field) field.focus();
      });
    });

    document.querySelectorAll(".cancel-edit-btn").forEach(function (button) {
      button.addEventListener("click", function () {
        var outfitId = button.dataset.outfitId;
        var found = parts(outfitId);
        if (!found.view || !found.form) return;
        found.view.hidden = false;
        found.form.hidden = true;
        var opener = document.querySelector('.edit-description-btn[data-outfit-id="' + outfitId + '"]');
        if (opener) opener.hidden = false;
      });
    });

    document.querySelectorAll(".save-description-btn").forEach(function (button) {
      button.addEventListener("click", async function () {
        var outfitId = button.dataset.outfitId;
        var found = parts(outfitId);
        var field = found.form ? found.form.querySelector("textarea") : null;
        if (!field) return;

        var token = csrfToken();
        if (!token) { say("Your session expired. Reload the page.", true); return; }

        button.disabled = true;
        try {
          var response = await fetch("/update-outfit-description/" + outfitId, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ description: field.value })
          });
          if (!response.ok) throw new Error();
          if (found.view) {
            found.view.innerHTML = field.value;
            found.view.hidden = false;
          }
          found.form.hidden = true;
          var opener = document.querySelector('.edit-description-btn[data-outfit-id="' + outfitId + '"]');
          if (opener) opener.hidden = false;
          say("Analysis updated");
        } catch (error) {
          say("Couldn't update that analysis. Try again.", true);
        } finally {
          button.disabled = false;
        }
      });
    });
  });

  /* ── deleting feedback ────────────────────────────────────────────── */
  window.deleteFeedback = async function (feedbackId) {
    if (!confirm("Delete this feedback? This can't be undone.")) return;
    var token = csrfToken();
    if (!token) { say("Your session expired. Reload the page.", true); return; }

    try {
      var response = await fetch("/recommendation-feedback/" + feedbackId, {
        method: "DELETE",
        headers: { "X-CSRFToken": token }
      });
      if (!response.ok) {
        var error = await response.json().catch(function () { return {}; });
        throw new Error(error.error || "");
      }
      var trigger = document.querySelector('[data-feedback-id="' + feedbackId + '"]');
      // The card is a .panel now, not a .border-classed div.
      var card = trigger ? trigger.closest(".panel") : null;
      if (card) card.remove();
      say("Feedback deleted");
    } catch (error) {
      say(error.message || "Couldn't delete that feedback. Try again.", true);
    }
  };
})();
