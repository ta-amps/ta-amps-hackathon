// The setup writer on /start/. Every choice rewrites the setup shown, so no setting is dead.
// The templates and every word come from the page's #setup-data block (content/start.json); this file
// holds no copy, stores nothing and makes no request. build.py writes the same default setup into the
// page (setup_text), and tests/check_site.mjs checks that the two agree and that each setting changes it.
(function () {
  "use strict";
  var root = document.querySelector("[data-setup]");
  var block = document.getElementById("setup-data");
  if (!root || !block) return;
  var words;
  try {
    words = JSON.parse(block.textContent);
  } catch (error) {
    return;
  }
  var out = root.querySelector("[data-setup-output]");
  var status = root.querySelector("[data-setup-status]");
  var copyButton = root.querySelector("[data-setup-copy]");

  function value(name) {
    var el = root.querySelector('[name="' + name + '"]');
    if (!el) return "";
    if (el.type === "radio") return (root.querySelector('[name="' + name + '"]:checked') || el).value;
    if (el.type === "checkbox") return el.checked;
    return el.value;
  }

  function text() {
    var template = words.templates[value("goal") + "." + value("via") + "." + value("show")];
    if (typeof template !== "string") return out.textContent;
    // The same cleaning Tessera applies to an agent_label, so the setup shows what Tessera keeps.
    var agent = String(value("agent")).replace(/[^a-zA-Z0-9 ._:-]/g, "").slice(0, 64) || "agent";
    var swap = { agent: agent, queue: value("queue"), map: words.tokens[value("map") ? "map_on" : "map_off"] };
    return template.replace(/\{(agent|queue|map)\}/g, function (all, key) { return swap[key]; });
  }

  function render() {
    out.textContent = text();
    status.textContent = "";
  }

  root.addEventListener("input", render);
  root.addEventListener("change", render);
  copyButton.addEventListener("click", function () {
    var done = function (ok) {
      status.textContent = ok ? words.copy.done : words.copy.failed;
      if (!ok && window.getSelection) {
        try {
          window.getSelection().selectAllChildren(out);
        } catch (error) {
          // the setup stays on screen to select by hand
        }
      }
    };
    if (!navigator.clipboard || !window.isSecureContext) return done(false);
    navigator.clipboard.writeText(out.textContent).then(function () { done(true); }, function () { done(false); });
  });
  root.setAttribute("data-ready", "true");
  render();
})();
