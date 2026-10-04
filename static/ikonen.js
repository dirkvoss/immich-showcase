/* Symbole: Die Oberflaeche ist mit Zeichen wie "▶ Diashow" oder "📺 Auf den TV" geschrieben (die Uebersetzungen haengen daran).
   Hier werden fuehrende Zeichen in einheitliche Linien-Symbole (SVG, Sprite in index.html) verwandelt - nach der Uebersetzung (i18n.js laeuft zuerst). */
(function () {
  var IK = {
    "▶": "play", "⏹": "stop", "✕": "close", "✓": "check", "↶": "undo", "↩": "undo", "↻": "refresh",
    "📺": "tv", "🖥": "tv", "📡": "geraete", "❓": "hilfe", "🎤": "mic", "⭐": "stern", "★": "stern", "☆": "stern-leer",
    "🎵": "musik", "🎬": "film", "🔉": "leiser", "🔊": "lauter", "🔇": "stumm", "🌐": "welt", "⬇": "laden", "🐞": "fehler",
    "💡": "idee", "➕": "plus", "🖼": "bild", "🔋": "akku", "⚡": "blitz", "🕘": "uhr", "🎲": "zufall", "⛶": "gross", "⤢": "gross", "●": "punkt"
  };
  var zeichen = Object.keys(IK).join("|"), FUEHREND = new RegExp("^\\s*(" + zeichen + ")\\uFE0F?\\s*"), MITTEN = new RegExp("\\s*(" + zeichen + ")\\uFE0F?\\s*", "g"), ENTHAELT = new RegExp(zeichen);
  var NS = "http://www.w3.org/2000/svg";
  function svg(name) {
    var s = document.createElementNS(NS, "svg"), u = document.createElementNS(NS, "use");
    s.setAttribute("class", "ic ic-" + name); s.setAttribute("aria-hidden", "true"); u.setAttribute("href", "#i-" + name); s.appendChild(u); return s;
  }
  function knoten(t) {
    var el = t.parentNode, m, rest;
    if (!el || /^(SCRIPT|STYLE|TEXTAREA|TITLE)$/.test(el.nodeName) || !t.data) return;
    m = t.data.match(FUEHREND);
    if (m) {
      rest = t.data.slice(m[0].length);
      if (el.nodeName === "OPTION") { t.data = rest; return; }                      // in Auswahllisten sind keine Bilder moeglich
      el.insertBefore(svg(IK[m[1]]), t); t.data = rest;
      if (!rest) return;
    }
    if (ENTHAELT.test(t.data)) t.data = t.data.replace(MITTEN, function (all, g, off) { return off === 0 ? "" : " "; }).replace(/\s{2,}/g, " ");   // Zeichen mitten im Satz ("Nutze „📺 Auf den TV“")
  }
  function durchlaufe(n) {
    var w, k;
    if (n.nodeType === 3) { knoten(n); return; }
    if (n.nodeType !== 1 || /^(SCRIPT|STYLE|svg)$/i.test(n.nodeName)) return;
    w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT, null); k = [];
    while (w.nextNode()) k.push(w.currentNode);
    for (var i = 0; i < k.length; i++) knoten(k[i]);
  }
  function los() {
    durchlaufe(document.body);
    new MutationObserver(function (list) {
      for (var i = 0; i < list.length; i++) {
        var mu = list[i];
        if (mu.type === "childList") { for (var j = 0; j < mu.addedNodes.length; j++) durchlaufe(mu.addedNodes[j]); }
        else if (mu.type === "characterData") knoten(mu.target);
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.body) los(); else document.addEventListener("DOMContentLoaded", los);
})();
