/* ══════════════════════════════════════════════════════════════════════
   OutfitGenie — the stylist
   The AI's replies are set in serif and run unbubbled; yours are small,
   mono and right-aligned. Images and the theme come from ui.js.
   ══════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var EXAMPLES = [
    "What should I wear for a casual dinner?",
    "Can you suggest an outfit for a job interview?",
    "What goes well with my blue shirt?",
    "Help me put together a summer outfit",
    "What should I wear to a wedding?",
    "How can I style my black jeans?",
    "What works for a rainy day?",
    "Suggest something for a first date",
    "What can I wear to look taller?",
    "How do I dress for a business meeting?",
    "What goes well with white sneakers?",
    "Pick me an outfit for a party",
    "What should I wear for a winter walk?",
    "How do I style a denim jacket?",
    "What's a good outfit for brunch?",
    "How can I layer for autumn?",
    "What should I wear to a concert?",
    "Suggest a comfortable travel outfit",
    "What can I wear for a beach day?",
    "How do I dress for a hot day?",
    "What should I wear to train in?",
    "How do I style a floral dress?",
    "What goes with a red skirt?",
    "How do I dress up something casual?",
    "What's a good outfit for hiking?",
    "How do I make this look more formal?"
  ];

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : null;
  }

  function say(message, isError) {
    if (window.ogToast) window.ogToast(message, isError);
    else if (isError) console.error(message);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("chat-form");
    var input = document.getElementById("message-input");
    var log = document.getElementById("chat-messages");
    var rail = document.getElementById("chat-history");
    var modeSwitch = document.getElementById("recommendation-mode");
    var modeLabel = document.getElementById("mode-label");
    var newChatBtn = document.getElementById("new-chat-btn");

    if (!form || !log) return;

    var currentChatId = null;
    var feedbackMap = {};
    // Tracked rather than scraped back out of the DOM, which is what the
    // old code did by looking for a Tailwind class on the last bubble.
    var lastUserMessage = "";

    /* ── wardrobe-only switch ───────────────────────────────────────── */
    function wardrobeOnly() {
      return modeSwitch && modeSwitch.getAttribute("aria-checked") === "true";
    }
    if (modeSwitch) {
      modeSwitch.addEventListener("click", function () {
        var next = !wardrobeOnly();
        modeSwitch.setAttribute("aria-checked", next ? "true" : "false");
        if (modeLabel) {
          modeLabel.textContent = next ? "Only what you own" : "Anything";
        }
      });
    }

    /* ── rendering ──────────────────────────────────────────────────── */
    function addUserMessage(text) {
      lastUserMessage = text;
      var el = document.createElement("div");
      el.className = "bubble-you";
      el.textContent = text;                 // user text is never HTML
      log.appendChild(el);
      log.scrollTop = log.scrollHeight;
    }

    function addReply(options) {
      var text = options.text || "";
      var images = Array.isArray(options.images) ? options.images : [];
      var question = options.question || lastUserMessage;

      var wrap = document.createElement("div");
      wrap.className = "reply";

      var mark = document.createElement("p");
      mark.className = "t-data reply-mark";
      mark.textContent = "Stylist";
      wrap.appendChild(mark);

      var body = document.createElement("div");
      body.className = "reply-body";
      if (options.html) body.innerHTML = text;
      else body.textContent = text;
      wrap.appendChild(body);

      if (images.length) {
        var strip = document.createElement("div");
        strip.className = "reply-images";
        images.forEach(function (url) {
          var img = document.createElement("img");
          img.src = url;
          img.alt = "Recommended piece";
          img.loading = "lazy";
          img.setAttribute("data-full-image", url);   // ui.js lightbox
          strip.appendChild(img);
        });
        wrap.appendChild(strip);
      }

      if (options.rateable) {
        wrap.appendChild(buildFeedback(text, question));
      }

      log.appendChild(wrap);
      log.scrollTop = log.scrollHeight;
    }

    function buildFeedback(recommendation, question) {
      var key = recommendation + "||" + question;
      var chosen = feedbackMap[key] || null;

      var row = document.createElement("div");
      row.className = "feedback-row";

      ["like", "dislike"].forEach(function (kind) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "feedback-btn";
        button.textContent = kind === "like" ? "Good call" : "Not for me";
        button.setAttribute("aria-pressed", chosen === kind ? "true" : "false");

        button.addEventListener("click", async function () {
          var next = chosen === kind ? "remove" : kind;
          var token = csrfToken();
          if (!token) { say("Your session expired. Reload the page.", true); return; }

          try {
            var response = await fetch("/recommendation-feedback", {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-CSRFToken": token },
              body: JSON.stringify({
                recommendation: recommendation,
                feedback: next,
                question: question,
                context: { timestamp: new Date().toISOString() }
              })
            });
            if (!response.ok) throw new Error();

            chosen = next === "remove" ? null : kind;
            feedbackMap[key] = chosen;
            Array.prototype.forEach.call(row.children, function (other) {
              other.setAttribute("aria-pressed", "false");
            });
            if (chosen) button.setAttribute("aria-pressed", "true");
            say(chosen ? "Noted" : "Feedback cleared");
          } catch (error) {
            say("Couldn't save that. Try again.", true);
          }
        });

        row.appendChild(button);
      });

      return row;
    }

    function showWelcome() {
      addReply({
        text: "I can put outfits together from the pieces you've uploaded. Things worth asking:",
        rateable: false
      });
      var picks = EXAMPLES.slice().sort(function () { return 0.5 - Math.random(); }).slice(0, 4);
      addReply({
        html: true,
        text: "<ul>" + picks.map(function (q) {
          return "<li>" + q.replace(/[<>&]/g, "") + "</li>";
        }).join("") + "</ul>",
        rateable: false
      });
    }

    /* ── data ───────────────────────────────────────────────────────── */
    async function fetchFeedback() {
      try {
        var response = await fetch("/chat-feedback");
        var data = await response.json();
        feedbackMap = {};
        (data.feedback || []).forEach(function (entry) {
          feedbackMap[entry.recommendation + "||" + entry.question] = entry.feedback;
        });
      } catch (error) { /* feedback is decoration; the chat still works */ }
    }

    async function loadHistory(page) {
      page = page || 1;
      if (!rail) return;
      try {
        var response = await fetch("/chat-history?page=" + page);
        var data = await response.json();

        rail.innerHTML = "";
        if (!data.chats || !data.chats.length) {
          var none = document.createElement("p");
          none.className = "t-data t-quiet";
          none.textContent = "No past reads yet";
          rail.appendChild(none);
          return;
        }

        var list = document.createElement("div");
        list.className = "chat-list";

        data.chats.forEach(function (entry) {
          var item = document.createElement("div");
          item.className = "chat-item" + (entry.id === currentChatId ? " is-current" : "");

          var open = document.createElement("button");
          open.type = "button";
          open.className = "chat-item-open";
          var preview = document.createElement("span");
          preview.className = "chat-item-preview";
          preview.textContent = entry.preview;
          var time = document.createElement("span");
          time.className = "chat-item-time";
          time.textContent = new Date(entry.timestamp).toLocaleDateString(undefined,
            { day: "2-digit", month: "short" });
          open.appendChild(preview);
          open.appendChild(time);
          open.addEventListener("click", function () { loadChat(entry.id); });

          var remove = document.createElement("button");
          remove.type = "button";
          remove.className = "icon-btn is-danger";
          remove.setAttribute("aria-label", "Delete this read");
          remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="1.8" aria-hidden="true"><path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/></svg>';
          remove.addEventListener("click", async function (event) {
            event.stopPropagation();
            if (!confirm("Delete this read? This can't be undone.")) return;
            try {
              var res = await fetch("/chat/" + entry.id, {
                method: "DELETE",
                headers: { "X-CSRFToken": csrfToken() }
              });
              if (!res.ok) throw new Error();
              if (entry.id === currentChatId) {
                log.innerHTML = "";
                currentChatId = null;
                showWelcome();
              }
              say("Read deleted");
              loadHistory(page);
            } catch (error) {
              say("Couldn't delete that read. Try again.", true);
            }
          });

          item.appendChild(open);
          item.appendChild(remove);
          list.appendChild(item);
        });

        rail.appendChild(list);

        if (data.pages > 1) {
          var pager = document.createElement("div");
          pager.className = "chat-pager";

          var prev = document.createElement("button");
          prev.type = "button";
          prev.className = "btn btn-ghost";
          prev.textContent = "Prev";
          prev.disabled = !data.has_prev;
          prev.addEventListener("click", function () { loadHistory(data.page - 1); });

          var info = document.createElement("span");
          info.className = "t-data t-quiet";
          info.textContent = data.page + " / " + data.pages;

          var next = document.createElement("button");
          next.type = "button";
          next.className = "btn btn-ghost";
          next.textContent = "Next";
          next.disabled = !data.has_next;
          next.addEventListener("click", function () { loadHistory(data.page + 1); });

          pager.appendChild(prev);
          pager.appendChild(info);
          pager.appendChild(next);
          rail.appendChild(pager);
        }
      } catch (error) {
        console.error("Error loading chat history:", error);
      }
    }

    async function loadChat(chatId) {
      try {
        await fetchFeedback();
        var response = await fetch("/chat/" + chatId);
        var data = await response.json();

        log.innerHTML = "";
        lastUserMessage = "";
        (data.messages || []).forEach(function (message) {
          if (message.sender === "You") {
            addUserMessage(message.text);
          } else {
            addReply({
              text: message.text,
              images: message.image_urls,
              question: message.question,
              rateable: true
            });
          }
        });

        currentChatId = chatId;
        loadHistory();
      } catch (error) {
        say("Couldn't open that read. Try again.", true);
      }
    }

    /* ── sending ────────────────────────────────────────────────────── */
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var message = input.value.trim();
      if (!message) return;

      addUserMessage(message);
      input.value = "";

      var thinking = document.createElement("p");
      thinking.className = "t-data t-quiet";
      thinking.textContent = "Reading your closet…";
      log.appendChild(thinking);
      log.scrollTop = log.scrollHeight;

      try {
        var response = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
          body: JSON.stringify({
            message: message,
            chat_id: currentChatId,
            wardrobe_only: wardrobeOnly()
          })
        });
        var data = await response.json();
        thinking.remove();

        if (!response.ok) throw new Error(data.error || "");
        currentChatId = data.chat_id;
        addReply({
          text: data.response,
          images: data.image_urls,
          question: message,
          rateable: true
        });
        loadHistory();
      } catch (error) {
        thinking.remove();
        addReply({
          text: "That didn't go through. Ask again and I'll retry.",
          rateable: false
        });
      }
    });

    if (newChatBtn) {
      newChatBtn.addEventListener("click", function () {
        log.innerHTML = "";
        currentChatId = null;
        lastUserMessage = "";
        showWelcome();
        loadHistory();
        if (input) input.focus();
      });
    }

    showWelcome();
    fetchFeedback();
    loadHistory(1);
  });
})();
