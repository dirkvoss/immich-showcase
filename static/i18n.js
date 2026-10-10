/* Uebersetzungsschicht: Die Oberflaeche ist deutsch geschrieben; fuer andere Sprachen wird der fertig gerenderte Text
   (Textknoten + Attribute) anhand von /i18n/<sprache>.json ersetzt: exakte Texte ("texte") und Muster mit Platzhaltern ("muster").
   Sprache: ?lang=en (wird gemerkt) > gemerkte Wahl > Browsersprache; unbekannt -> Deutsch. ES5, damit auch Fernseher-Browser mitkommen. */
(function () {
  var lang = "de", m;
  try {
    m = location.search.match(/[?&]lang=([a-z]{2})/);
    if (m) localStorage.setItem("rw_lang", m[1]);
    lang = (m && m[1]) || localStorage.getItem("rw_lang") || (navigator.language || "de").slice(0, 2);
  } catch (e) {}
  var SPRACHEN = { en: "en-GB", es: "es-ES", fr: "fr-FR", nl: "nl-NL" };      // Uebersetzungen: /i18n/<sprache>.json; alles andere -> Deutsch
  if (!SPRACHEN[lang]) lang = "de";
  window.RW_LANG = lang;
  window.RW_SPRACHEN = ["de", "en", "es", "fr", "nl"];
  window.RW_LOCALE = SPRACHEN[lang] || "de-DE";
  document.documentElement.lang = lang;
  window.RW_T = function (s) { return s; };
  window.RW_MISS = [];
  if (lang === "de") return;

  var D = null;
  try {
    var x = new XMLHttpRequest();
    x.open("GET", "/i18n/" + lang + ".json", false);
    x.send(null);
    if (x.status === 200) D = JSON.parse(x.responseText);
  } catch (e) {}
  if (!D) return;
  var texte = D.texte || {}, muster = [], i;
  for (i = 0; i < (D.muster || []).length; i++) muster.push([new RegExp(D.muster[i][0]), D.muster[i][1], D.muster[i][2]]);
  var beschr = [];
  for (i = 0; i < (D.beschreibung || []).length; i++) beschr.push([new RegExp(D.beschreibung[i][0], "g"), D.beschreibung[i][1]]);
  var DEUTSCH = /[äöüÄÖÜß]|\b(und|der|die|das|nicht|Foto|Fotos|Rahmen|Show|Auswahl|wird|werden|oder|mit|auf|dem|den)\b/;

  function uebersetze(s) {
    var lead = s.match(/^\s*/)[0], trail = s.match(/\s*$/)[0];
    var t = s.replace(/\s+/g, " ").trim();
    if (!t) return s;
    var r = Object.prototype.hasOwnProperty.call(texte, t) ? texte[t] : undefined, k;
    if (r === undefined) {
      for (k = 0; k < muster.length; k++) {
        if (muster[k][0].test(t)) {
          r = t.replace(muster[k][0], muster[k][1]);
          if (muster[k][2]) { for (var b = 0; b < beschr.length; b++) r = r.replace(beschr[b][0], beschr[b][1]); }
          break;
        }
      }
    }
    if (r === undefined) {
      if (DEUTSCH.test(t) && !/^[^()]* \(\d[\d.,]*\)$/.test(t) && window.RW_MISS.indexOf(t) < 0) window.RW_MISS.push(t);
      return s;
    }
    return lead + r + trail;
  }
  window.RW_T = function (s) { var t = String(s); var r = uebersetze(t); return r; };

  var ATTR = ["placeholder", "title", "aria-label", "alt"];
  function ausgenommen(n) {                                   // Texte der Nutzer (Termine, Show-Namen) tragen translate="no" und bleiben, wie sie sind
    for (; n && n.nodeType === 1; n = n.parentNode) if (n.getAttribute("translate") === "no") return true;
    return false;
  }
  function knoten(n) {
    var j, a, v, c;
    if (n.nodeType === 3) {
      if (n.parentNode && /^(SCRIPT|STYLE)$/.test(n.parentNode.nodeName)) return;
      if (ausgenommen(n.parentNode)) return;
      v = uebersetze(n.data); if (v !== n.data) n.data = v;
    } else if (n.nodeType === 1) {
      if (/^(SCRIPT|STYLE)$/.test(n.nodeName) || ausgenommen(n)) return;
      for (j = 0; j < ATTR.length; j++) {
        a = n.getAttribute(ATTR[j]);
        if (a) { v = uebersetze(a); if (v !== a) n.setAttribute(ATTR[j], v); }
      }
      for (c = n.firstChild; c; c = c.nextSibling) knoten(c);
    }
  }
  function los() {
    knoten(document.documentElement);
    new MutationObserver(function (list) {
      var i2, j2, mu;
      for (i2 = 0; i2 < list.length; i2++) {
        mu = list[i2];
        if (mu.type === "childList") { for (j2 = 0; j2 < mu.addedNodes.length; j2++) knoten(mu.addedNodes[j2]); }
        else if (mu.type === "characterData") knoten(mu.target);
        else if (mu.type === "attributes") {
          var a2 = mu.target.getAttribute(mu.attributeName);
          if (a2) { var v2 = uebersetze(a2); if (v2 !== a2) mu.target.setAttribute(mu.attributeName, v2); }
        }
      }
    }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTR });
    var oc = window.confirm, oa = window.alert;
    window.confirm = function (s) { return oc.call(window, uebersetze(String(s))); };
    window.alert = function (s) { return oa.call(window, uebersetze(String(s))); };
  }
  if (document.body) los(); else document.addEventListener("DOMContentLoaded", los);
  document.title = uebersetze(document.title);
})();
