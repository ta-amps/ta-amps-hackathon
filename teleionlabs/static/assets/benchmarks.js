// Filter chips on /benchmarks/. Holds no copy, stores nothing and makes no request.
(function () {
  "use strict";
  var root = document.querySelector("[data-benchmarks]");
  if (!root) return;
  var buttons = Array.prototype.slice.call(root.querySelectorAll("[data-bench-filter]"));
  var groups = Array.prototype.slice.call(root.querySelectorAll("[data-bench-group]"));
  if (!buttons.length || !groups.length) return;

  function pick(selected) {
    buttons.forEach(function (btn) {
      var active = btn.getAttribute("data-bench-filter") === selected;
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    groups.forEach(function (sec) {
      var show = selected === "all" || sec.getAttribute("data-bench-group") === selected;
      if (show) sec.removeAttribute("hidden");
      else sec.setAttribute("hidden", "");
    });
  }

  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      pick(btn.getAttribute("data-bench-filter") || "all");
    });
  });
  root.setAttribute("data-ready", "true");
})();
