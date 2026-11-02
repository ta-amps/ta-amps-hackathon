// The live strip on the home page. It reads /api/status (same origin, cached by the Worker for
// at most 60 s) and fills in each service's state. Every word it shows comes from the page's
// data attributes, which the build takes from content/home.json. No storage, no cookies.
(function () {
  "use strict";
  var list = document.querySelector("[data-status-src]");
  if (!list || !window.fetch) return;
  var note = document.querySelector("[data-checked-note]");
  var text = list.dataset;

  function setAll(state, label) {
    list.querySelectorAll("[data-service]").forEach(function (item) {
      item.dataset.state = state;
      var el = item.querySelector("[data-state-text]");
      if (el) el.textContent = label;
    });
  }

  fetch(list.getAttribute("data-status-src"), { headers: { Accept: "application/json" }, credentials: "omit", cache: "no-store" })
    .then(function (res) { if (!res.ok) throw new Error(String(res.status)); return res.json(); })
    .then(function (data) {
      var seen = {};
      (data.services || []).forEach(function (s) {
        var item = list.querySelector('[data-service="' + String(s.id).replace(/[^a-z0-9_-]/gi, "") + '"]');
        if (!item) return;
        seen[s.id] = true;
        var up = s.state === "up";
        item.dataset.state = up ? "up" : "down";
        var el = item.querySelector("[data-state-text]");
        if (el) el.textContent = up ? text.up : text.down;
      });
      list.querySelectorAll("[data-service]").forEach(function (item) {
        if (!seen[item.dataset.service]) {
          item.dataset.state = "unknown";
          var el = item.querySelector("[data-state-text]");
          if (el) el.textContent = text.unknown;
        }
      });
      var when = new Date(data.checked_at);
      if (note && !isNaN(when.getTime())) {
        note.textContent = text.checked.replace("{time}", when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      }
    })
    .catch(function () {
      setAll("unknown", text.unknown);
      if (note) note.textContent = text.failed;
    });
})();
