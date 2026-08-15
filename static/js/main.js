/* ══════════════════════════════════════════════════════════════════════
   OutfitGenie — upload page
   File selection, the read, profile, location and weather picks.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var MAX_UPLOAD_BYTES = 16 * 1024 * 1024;

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : null;
  }

  function say(message, isError) {
    if (window.ogToast) window.ogToast(message, isError);
    else if (isError) console.error(message);
  }

  function pieces(n) {
    return n + (n === 1 ? " piece" : " pieces");
  }

  document.addEventListener("DOMContentLoaded", function () {

    /* ── the read ───────────────────────────────────────────────────── */
    var fileInput = document.getElementById("clothing-upload");
    var dropzone = document.getElementById("dropzone");
    var tray = document.getElementById("upload-preview");
    var tiles = document.getElementById("preview-container");
    var confirmBtn = document.getElementById("confirm-upload");
    var clearBtn = document.getElementById("deselect-all");
    var countEl = document.getElementById("selected-count");

    var queued = [];

    function totalBytes() {
      return queued.reduce(function (sum, entry) { return sum + entry.file.size; }, 0);
    }

    function refreshTray() {
      if (!tray) return;
      var n = queued.length;
      if (countEl) countEl.textContent = String(n);
      if (confirmBtn) {
        confirmBtn.disabled = n === 0;
        confirmBtn.textContent = n === 0 ? "Read pieces" : "Read " + pieces(n);
      }
      tray.hidden = n === 0;
    }

    function addTile(entry) {
      var reader = new FileReader();
      reader.onload = function (event) {
        var tile = document.createElement("div");
        tile.className = "tile";
        tile.dataset.filename = entry.file.name;

        var img = document.createElement("img");
        img.src = event.target.result;
        img.alt = entry.file.name;

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "tile-remove";
        remove.setAttribute("aria-label", "Remove " + entry.file.name);
        remove.innerHTML =
          '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
          '<path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>';
        remove.addEventListener("click", function () { removeQueued(entry.file.name); });

        var name = document.createElement("span");
        name.className = "tile-name";
        name.textContent = entry.file.name;

        tile.appendChild(img);
        tile.appendChild(remove);
        tile.appendChild(name);
        if (tiles) tiles.appendChild(tile);
      };
      reader.readAsDataURL(entry.file);
    }

    function removeQueued(fileName) {
      queued = queued.filter(function (entry) { return entry.file.name !== fileName; });
      var tile = tiles && tiles.querySelector('[data-filename="' + CSS.escape(fileName) + '"]');
      if (tile) tile.remove();
      refreshTray();
    }

    function acceptFiles(fileList) {
      var incoming = Array.prototype.slice.call(fileList).filter(function (file) {
        return file.type.indexOf("image/") === 0;
      });
      if (!incoming.length) {
        say("Those aren't images. Choose JPG or PNG files.", true);
        return;
      }

      var added = 0;
      incoming.forEach(function (file) {
        var duplicate = queued.some(function (entry) {
          return entry.file.name === file.name && entry.file.size === file.size;
        });
        if (duplicate) return;
        var entry = { file: file };
        queued.push(entry);
        addTile(entry);
        added++;
      });

      if (totalBytes() > MAX_UPLOAD_BYTES) {
        say("That's over the 16MB limit. Remove a few and try again.", true);
      }
      if (!added && incoming.length) say("Already in the tray.");
      refreshTray();
    }

    if (fileInput) {
      fileInput.addEventListener("change", function (event) {
        acceptFiles(event.target.files);
        // Let the same file be chosen again after being removed.
        fileInput.value = "";
      });
    }

    if (dropzone) {
      ["dragenter", "dragover"].forEach(function (name) {
        dropzone.addEventListener(name, function (event) {
          event.preventDefault();
          dropzone.classList.add("is-dragging");
        });
      });
      ["dragleave", "drop"].forEach(function (name) {
        dropzone.addEventListener(name, function (event) {
          event.preventDefault();
          if (name === "dragleave" && dropzone.contains(event.relatedTarget)) return;
          dropzone.classList.remove("is-dragging");
        });
      });
      dropzone.addEventListener("drop", function (event) {
        if (event.dataTransfer && event.dataTransfer.files.length) {
          acceptFiles(event.dataTransfer.files);
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        queued = [];
        if (tiles) tiles.innerHTML = "";
        refreshTray();
      });
    }

    if (confirmBtn) {
      confirmBtn.addEventListener("click", async function () {
        if (!queued.length) {
          say("Add a photo first.", true);
          return;
        }
        if (totalBytes() > MAX_UPLOAD_BYTES) {
          say("That's over the 16MB limit. Remove a few and try again.", true);
          return;
        }

        var count = queued.length;
        var formData = new FormData();
        queued.forEach(function (entry) { formData.append("image", entry.file); });

        var originalLabel = confirmBtn.textContent;
        confirmBtn.disabled = true;
        confirmBtn.textContent = "Reading…";

        try {
          var response = await fetch("/upload", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken() },
            body: formData
          });
          var data = await response.json();
          if (!response.ok) throw new Error(data.error || "Upload failed");

          say(pieces(count) + " read");
          queued = [];
          if (tiles) tiles.innerHTML = "";
          if (fileInput) fileInput.value = "";
          refreshTray();
          // Reload so the new colours join the spectrum.
          setTimeout(function () { window.location.reload(); }, 700);
        } catch (error) {
          say(error.message || "Couldn't read those. Try again.", true);
          confirmBtn.disabled = false;
          confirmBtn.textContent = originalLabel;
        }
      });
    }

    refreshTray();

    /* ── profile ────────────────────────────────────────────────────── */
    var styleOther = document.querySelector('input[name="styles"][value="other"]');
    var otherStyleBox = document.getElementById("other-style-container");
    if (styleOther && otherStyleBox) {
      var syncStyleOther = function () { otherStyleBox.hidden = !styleOther.checked; };
      styleOther.addEventListener("change", syncStyleOther);
      syncStyleOther();
    }

    var hairSelect = document.getElementById("hair_color");
    var hairOtherInput = document.getElementById("other_hair_color");
    var hairOtherBox = document.getElementById("other_hair_color_container");
    if (hairSelect && hairOtherInput && hairOtherBox) {
      var syncHairOther = function () {
        var isOther = hairSelect.value === "other";
        hairOtherBox.hidden = !isOther;
        hairOtherInput.required = isOther;
      };
      hairSelect.addEventListener("change", syncHairOther);
      syncHairOther();
    }

    // Keep the swatch and the words for it in step.
    var skinSwatch = document.getElementById("skin-tone-color");
    var skinText = document.getElementById("skin-tone-text");
    if (skinSwatch && skinText) {
      skinSwatch.addEventListener("input", function () {
        if (/^#[0-9a-f]{6}$/i.test(skinText.value.trim()) || !skinText.value.trim()) {
          skinText.value = skinSwatch.value;
        }
      });
      skinText.addEventListener("input", function () {
        var value = skinText.value.trim();
        if (/^#[0-9a-f]{6}$/i.test(value)) skinSwatch.value = value;
      });
    }

    var preferencesForm = document.getElementById("preferences-form");
    if (preferencesForm) {
      preferencesForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        var formData = new FormData(this);
        var styles = Array.prototype.slice
          .call(document.querySelectorAll('input[name="styles"]:checked'))
          .map(function (box) { return box.value; });
        var otherStyleInput = document.querySelector('input[name="other_style"]');

        var payload = {
          styles: styles,
          skin_tone_color: formData.get("skin_tone_color"),
          skin_tone_text: formData.get("skin_tone_text"),
          hair_color: hairSelect ? hairSelect.value : null,
          other_hair_color: formData.get("other_hair_color"),
          height: formData.get("height"),
          weight: formData.get("weight"),
          gender: formData.get("gender")
        };
        if (styleOther && styleOther.checked && otherStyleInput && otherStyleInput.value.trim()) {
          payload.other_style = otherStyleInput.value.trim();
        }

        var token = formData.get("csrf_token");
        if (!token) {
          say("Your session expired. Reload the page and try again.", true);
          return;
        }

        var submitBtn = this.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        try {
          var response = await fetch("/preferences", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify(payload)
          });
          var data = await response.json();
          if (!response.ok) throw new Error(data.error || "Failed to save your profile");
          say("Profile saved");
        } catch (error) {
          say(error.message || "Couldn't save your profile. Try again.", true);
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    /* ── location ───────────────────────────────────────────────────── */
    window.updateLocation = async function () {
      var input = document.getElementById("location-input");
      var location = input ? input.value.trim() : "";
      if (!location) {
        say("Enter a city first.", true);
        return;
      }
      var token = csrfToken();
      if (!token) {
        say("Your session expired. Reload the page and try again.", true);
        return;
      }

      try {
        var response = await fetch("/update-location", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": token },
          body: JSON.stringify({ location: location })
        });
        var data = await response.json();
        if (!response.ok) throw new Error(data.error || "Couldn't find that city");
        renderWeather(data.weather);
        say("Weather set for " + location);
      } catch (error) {
        say(error.message || "Couldn't update your city. Try again.", true);
      }
    };

    function renderWeather(weather) {
      var section = document.getElementById("weather-section");
      if (!section || !weather) return;
      var stat = function (label, value) {
        if (value === undefined || value === null || value === "") return "";
        return '<div class="weather-stat"><span class="t-data t-quiet">' + label +
               "</span><b>" + value + "</b></div>";
      };
      section.hidden = false;
      section.innerHTML =
        '<div class="weather">' +
          (weather.icon ? '<img src="' + weather.icon + '" alt="">' : "") +
          "<div>" +
            '<div class="weather-temp">' + weather.temperature + "°F</div>" +
            '<div class="t-data t-quiet">' + (weather.description || "") + "</div>" +
          "</div>" +
          '<div class="weather-stats">' +
            stat("Feels like", weather.feels_like !== undefined ? weather.feels_like + "°F" : "") +
            stat("Humidity", weather.humidity !== undefined ? weather.humidity + "%" : "") +
            stat("Wind", weather.wind_speed !== undefined ? weather.wind_speed + " mph" : "") +
          "</div>" +
        "</div>";
    }

    /* ── weather picks ──────────────────────────────────────────────── */
    var recommendationsBox = document.getElementById("weather-recommendations");
    var refreshBtn = document.getElementById("refresh-recommendations");

    function notice(message) {
      if (!recommendationsBox) return;
      recommendationsBox.innerHTML =
        '<div class="empty"><p class="empty-title">Nothing to pick from yet</p>' +
        '<p class="t-voice t-quiet" style="margin:0">' + message + "</p></div>";
    }

    function renderRecommendations(list) {
      if (!recommendationsBox) return;
      if (!list || !list.length) {
        notice("Upload a few pieces and the stylist will put outfits together.");
        return;
      }
      recommendationsBox.innerHTML = "";
      list.forEach(function (outfit, index) {
        var panel = document.createElement("div");
        panel.className = "panel";

        var itemsHtml = (outfit.items || []).map(function (item) {
          return '<span class="piece-tag">' +
            (item.image_url
              ? '<img src="' + item.image_url + '" alt="" data-full-image="' + item.image_url +
                '" style="width:1.25rem;height:1.25rem;object-fit:cover;border-radius:2px;cursor:zoom-in">'
              : "") +
            "<span>" + (item.name || "") + "</span></span>";
        }).join("");

        panel.innerHTML =
          '<div class="panel-head">' +
            '<span class="t-data">Option ' + (index + 1) + "</span>" +
            (typeof outfit.confidence === "number"
              ? '<span class="t-data t-quiet">' + Math.round(outfit.confidence * 100) + "% match</span>"
              : "") +
          "</div>" +
          '<div class="panel-body stack-tight">' +
            '<div class="look-pieces">' + itemsHtml + "</div>" +
            '<p class="t-voice" style="margin:0">' + (outfit.explanation || "") + "</p>" +
          "</div>";
        recommendationsBox.appendChild(panel);
      });
    }

    // Exposed because the markup and older callers both reach for it.
    window.displayWeatherRecommendations = renderRecommendations;

    window.refreshRecommendations = async function () {
      if (!recommendationsBox) return;
      if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "Picking…"; }
      try {
        var response = await fetch("/get-weather-recommendations");
        var data = await response.json();
        if (data.error) {
          notice(data.error);
          return;
        }
        try {
          localStorage.setItem("weatherRecommendations", JSON.stringify(data.recommendations));
        } catch (e) { /* private mode */ }
        renderRecommendations(data.recommendations);
      } catch (error) {
        notice("Couldn't reach the stylist. Try again in a moment.");
      } finally {
        if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "Refresh"; }
      }
    };

    if (recommendationsBox) {
      var cached = null;
      try { cached = localStorage.getItem("weatherRecommendations"); } catch (e) { /* private mode */ }
      if (cached) {
        try {
          var parsed = JSON.parse(cached);
          if (Array.isArray(parsed) && parsed.length) renderRecommendations(parsed);
          else notice("Hit refresh to see what works for today.");
        } catch (e) {
          notice("Hit refresh to see what works for today.");
        }
      } else {
        notice("Hit refresh to see what works for today.");
      }
    }

    // One listener, not the two the page used to bind.
    if (refreshBtn) refreshBtn.addEventListener("click", window.refreshRecommendations);
  });
})();
