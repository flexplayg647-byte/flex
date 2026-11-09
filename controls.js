/* Flex Cyberpunk - clavier et manette
   Lit le clavier (touches physiques : ZQSD et WASD marchent) et les manettes (Gamepad API : Xbox, PlayStation, Switch Pro...).
   Il publie l'etat dans window.flexInJ (texte JSON) que le jeu lit a chaque image,
   et il pilote lui-meme les fenetres web par-dessus le jeu (SKINS, classement, installation...). */
(function () {
  "use strict";
  if (window.flexControls) { return; }
  var C = window.flexControls = {};
  var K = {};                                   /* touches enfoncees (code physique) */
  var N = { ok: 0, bk: 0, ps: 0, p1: 0, p2: 0, u: 0, d: 0, l: 0, r: 0 };   /* compteurs d'appuis lus par le jeu */
  var S = { src: "", act: 0, pad: 0, pmx: 0, pmy: 0, pax: 0, pay: 0, pfire: 0, sx: 0, sy: 0 };
  var DZ_MOVE = 0.25, DZ_AIM = 0.35;
  var padNom = "";
  var repTouche = {}, repPad = {};
  var prevB = [];
  var prevStick = { u: false, d: false, l: false, r: false };

  function act(src) { S.src = src; S.act += 1; }

  /* ---------- fenetre web ouverte par-dessus le jeu ? ---------- */
  function docOverlay() {
    var f = document.getElementById("flexui") || document.getElementById("flexinst");
    try { return f && f.contentDocument ? f.contentDocument : null; } catch (e) { return null; }
  }
  var STYLE_ID = "fpadcss";
  function preparerDoc(d) {
    if (!d.getElementById(STYLE_ID)) {
      var st = d.createElement("style");
      st.id = STYLE_ID;
      st.textContent = ".fpad{outline:3px solid #ffd646 !important;outline-offset:2px;box-shadow:0 0 16px #ffd646 !important}";
      (d.head || d.documentElement).appendChild(st);
    }
    if (!d.__fpadKeys) {
      d.__fpadKeys = true;
      d.addEventListener("keydown", function (e) { touche(e, true); });
      d.addEventListener("keyup", function (e) { touche(e, false); });
    }
  }
  function candidats(d) {
    var l = d.querySelectorAll("button:not([disabled]), .tl, a.lk, input"), out = [], i;
    for (i = 0; i < l.length; i++) {
      var r = l[i].getBoundingClientRect();
      if (r.width > 4 && r.height > 4) { out.push(l[i]); }
    }
    return out;
  }
  function courant(d) { return d.querySelector(".fpad"); }
  function focaliser(d, el) {
    var a = d.querySelectorAll(".fpad"), i;
    for (i = 0; i < a.length; i++) { a[i].classList.remove("fpad"); }
    el.classList.add("fpad");
    try { el.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (e) {}
  }
  function parDefaut(d) {
    var p = d.querySelector("button.bp:not([disabled])");
    if (p) { return p; }
    var c = candidats(d);
    return c.length ? c[0] : null;
  }
  function deplacer(d, dir) {
    var cur = courant(d), c = candidats(d);
    if (!c.length) { return; }
    if (!cur || c.indexOf(cur) < 0) { var def = parDefaut(d); if (def) { focaliser(d, def); } return; }
    var r0 = cur.getBoundingClientRect(), cx = r0.left + r0.width / 2, cy = r0.top + r0.height / 2;
    var meilleur = null, score = 1e12, i;
    for (i = 0; i < c.length; i++) {
      if (c[i] === cur) { continue; }
      var r = c[i].getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      var dx = x - cx, dy = y - cy, prim, perp;
      if (dir === "l") { prim = -dx; perp = Math.abs(dy); }
      else if (dir === "r") { prim = dx; perp = Math.abs(dy); }
      else if (dir === "u") { prim = -dy; perp = Math.abs(dx); }
      else { prim = dy; perp = Math.abs(dx); }
      if (prim < 4) { continue; }
      var s = prim + 2.2 * perp;
      if (s < score) { score = s; meilleur = c[i]; }
    }
    if (meilleur) { focaliser(d, meilleur); }
  }
  var IDS_RETOUR = ["#bk2", "#bk", "#x", "#no", "#nv", "#fm"];
  function navOverlay(nom, d) {
    preparerDoc(d);
    if (nom === "u" || nom === "d" || nom === "l" || nom === "r") { deplacer(d, nom); return; }
    if (nom === "ok") {
      var cur = courant(d);
      if (!cur) { var def = parDefaut(d); if (def) { focaliser(d, def); } return; }
      try { cur.click(); } catch (e) {}
      return;
    }
    if (nom === "bk" || nom === "ps") {
      var i;
      for (i = 0; i < IDS_RETOUR.length; i++) {
        var b = d.querySelector(IDS_RETOUR[i]);
        if (b && !b.disabled) { try { b.click(); } catch (e) {} return; }
      }
    }
  }
  /* un appui : va soit a la fenetre ouverte, soit au jeu (compteur) */
  function emettre(nom) {
    var d = docOverlay();
    if (d) { navOverlay(nom, d); } else { N[nom] += 1; }
  }

  /* ---------- clavier ---------- */
  var DIR = { KeyW: "u", ArrowUp: "u", KeyS: "d", ArrowDown: "d", KeyA: "l", ArrowLeft: "l", KeyD: "r", ArrowRight: "r" };
  function saisie(e) {
    var t = e.target;
    return !!(t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA") && !t.readOnly);
  }
  function touche(e, bas) {
    if (saisie(e) || e.ctrlKey || e.metaKey || e.altKey) { return; }
    var c = e.code;
    if (bas) {
      if (K[c]) { return; }                        /* repetition automatique du clavier : ignoree */
      K[c] = true;
      act("key");
      var d = DIR[c];
      if (d) { repTouche[c] = Date.now() + 320; emettre(d); }
      else if (c === "Enter" || c === "NumpadEnter" || c === "Space") { emettre("ok"); }
      else if (c === "Escape") { if (docOverlay()) { emettre("bk"); } else { emettre("bk"); emettre("ps"); } }
      else if (c === "Backspace") { emettre("bk"); }
      else if (c === "KeyP") { emettre("ps"); }
      else if (c === "KeyE" || c === "Digit1" || c === "Numpad1") { emettre("p1"); }
      else if (c === "KeyR" || c === "Digit2" || c === "Numpad2") { emettre("p2"); }
    } else {
      K[c] = false;
    }
  }
  window.addEventListener("keydown", function (e) { touche(e, true); }, true);
  window.addEventListener("keyup", function (e) { touche(e, false); }, true);
  window.addEventListener("blur", function () { K = {}; });

  /* ---------- manette ---------- */
  function dz(v, z) { v = v || 0; return Math.abs(v) < z ? 0 : v; }
  function lirePad() {
    var gps = [], g = null, i;
    try { gps = navigator.getGamepads ? navigator.getGamepads() : []; } catch (e) {}
    for (i = 0; i < gps.length; i++) { if (gps[i] && gps[i].connected) { g = gps[i]; break; } }
    if (!g) { S.pad = 0; S.pmx = S.pmy = S.pax = S.pay = S.pfire = S.sx = S.sy = 0; prevB = []; return; }
    S.pad = 1;
    var std = g.mapping === "standard";
    function b(n) { var x = g.buttons[n]; return !!x && (x.pressed || x.value > 0.5); }
    function axe(n) { return g.axes[n] || 0; }
    /* correspondance Xbox / PlayStation (disposition "standard") :
       0 = A / Croix (selectionner)   1 = B / Rond (retour)   4 = LB / L1   6 = LT / L2   7 = RT / R2
       9 = Start / Options            12-15 = croix directionnelle */
    var tL2 = b(6) || (!std && axe(4) > 0.5), tR2 = b(7) || (!std && axe(5) > 0.5);
    var now = {
      ok: b(0), bk: b(1), ps: b(9), p1: tL2, p2: b(4), fire: tR2,
      u: b(12), d: b(13), l: b(14), r: b(15)
    };
    var lx = dz(axe(0), DZ_MOVE), ly = dz(axe(1), DZ_MOVE), rx = dz(axe(2), DZ_AIM), ry = dz(axe(3), DZ_AIM);
    var dpx = (now.r ? 1 : 0) - (now.l ? 1 : 0), dpy = (now.d ? 1 : 0) - (now.u ? 1 : 0);
    S.pmx = lx || dpx; S.pmy = ly || dpy;
    S.pax = rx; S.pay = ry; S.pfire = now.fire ? 1 : 0;
    S.sx = lx; S.sy = ly;
    var actif = Math.abs(lx) + Math.abs(ly) + Math.abs(rx) + Math.abs(ry) > 0.5 || now.ok || now.bk || now.fire || now.p1 || now.p2 || now.ps;
    var noms = ["ok", "bk", "ps", "p1", "p2"], k;
    for (k = 0; k < noms.length; k++) {
      var n = noms[k];
      if (now[n] && !prevB[n]) { emettre(n); act("pad"); }
    }
    var dirs = ["u", "d", "l", "r"], t = Date.now();
    for (k = 0; k < dirs.length; k++) {
      var dd = dirs[k];
      if (now[dd]) {
        if (!prevB[dd]) { repPad[dd] = t + 320; emettre(dd); }
        else if (t > repPad[dd]) { repPad[dd] = t + 120; emettre(dd); }
      }
    }
    /* le stick gauche sert aussi a naviguer dans les fenetres web (pas dans les menus du jeu : il y deplace le curseur) */
    if (docOverlay()) {
      var st = { u: ly < -0.6, d: ly > 0.6, l: lx < -0.6, r: lx > 0.6 };
      for (k = 0; k < dirs.length; k++) {
        var s2 = dirs[k];
        if (st[s2]) {
          if (!prevStick[s2]) { repPad[s2 + "s"] = t + 320; emettre(s2); }
          else if (t > repPad[s2 + "s"]) { repPad[s2 + "s"] = t + 150; emettre(s2); }
        }
        prevStick[s2] = st[s2];
      }
    } else { prevStick = { u: false, d: false, l: false, r: false }; }
    prevB = now;
    if (actif) { act("pad"); }
  }

  /* ---------- message de connexion ---------- */
  function message(txt) {
    var m = document.createElement("div");
    m.style.cssText = "position:fixed;left:50%;top:10px;transform:translateX(-50%);z-index:2147483640;max-width:92%;padding:10px 16px;border-radius:12px;" +
      "background:rgba(10,14,32,.96);border:2px solid #00ebff;box-shadow:0 0 16px rgba(0,235,255,.6);color:#fff;font:13px/1.35 Arial,sans-serif;text-align:center;pointer-events:none";
    m.innerHTML = txt;
    document.body.appendChild(m);
    setTimeout(function () { if (m.parentNode) { m.parentNode.removeChild(m); } }, 6500);
  }
  window.addEventListener("gamepadconnected", function (e) {
    padNom = String((e.gamepad && e.gamepad.id) || "manette").replace(/\(.*$/, "").slice(0, 40);
    act("pad");
    message("&#127918; <b>Manette connect&eacute;e</b><br>Stick : bouger &middot; <b>R2</b> : tirer &middot; <b>L2</b> / <b>L1</b> : pouvoirs &middot; <b>Croix (A)</b> : choisir &middot; <b>Rond (B)</b> : retour &middot; <b>Start</b> : pause");
  });
  window.addEventListener("gamepaddisconnected", function () { S.pad = 0; message("Manette d&eacute;connect&eacute;e"); });
  C.legende = function () {
    message("<b>Clavier</b> : ZQSD / WASD ou fl&egrave;ches : bouger &middot; souris : viser &middot; clic ou Espace : tirer &middot; <b>E</b> / <b>R</b> : pouvoirs &middot; Entr&eacute;e : choisir &middot; &Eacute;chap : retour / pause");
  };

  /* ---------- publication de l'etat ---------- */
  function publier() {
    var kx = ((K.KeyD || K.ArrowRight) ? 1 : 0) - ((K.KeyA || K.ArrowLeft) ? 1 : 0);
    var ky = ((K.KeyS || K.ArrowDown) ? 1 : 0) - ((K.KeyW || K.ArrowUp) ? 1 : 0);
    var mx = S.pmx || kx, my = S.pmy || ky;
    var fire = (S.pfire || K.Space) ? 1 : 0;
    var o = { s: S.src, a: S.act, pad: S.pad, mx: Math.round(mx * 1000) / 1000, my: Math.round(my * 1000) / 1000,
      ax: Math.round(S.pax * 1000) / 1000, ay: Math.round(S.pay * 1000) / 1000, f: fire, sx: S.sx, sy: S.sy,
      n: [N.ok, N.bk, N.ps, N.p1, N.p2, N.u, N.d, N.l, N.r] };
    window.flexInJ = JSON.stringify(o);
    C.etat = o;
  }
  function boucle() {
    try {
      lirePad();
      var t = Date.now(), c;
      for (c in K) {                                  /* repetition des fleches / ZQSD maintenues (navigation) */
        if (K[c] && DIR[c] && t > (repTouche[c] || 0)) { repTouche[c] = t + 120; emettre(DIR[c]); }
      }
      var d = docOverlay();
      if (d) { preparerDoc(d); }
      publier();
    } catch (e) {}
    window.requestAnimationFrame(boucle);
  }
  window.flexInJ = "";
  boucle();
  C.pousser = function (nom) { emettre(nom); };    /* utile pour les tests */
})();
