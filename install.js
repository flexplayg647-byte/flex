/* Flex Cyberpunk - installation de l'application
   Bouton "TELECHARGER LE JEU", animation guidee, rappels. Aucune dependance. */
(function () {
  "use strict";
  if (window.flexInstall) { return; }
  var API = window.flexInstall = { peut: false };
  var UA = navigator.userAgent || "";
  var IOS = /iPad|iPhone|iPod/.test(UA) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var ANDROID = /Android/i.test(UA);
  var WEBVIEW = /; wv\)|FBAN|FBAV|FB_IAB|Instagram|Snapchat|MicroMessenger|TikTok|musical_ly|Twitter|Line\//i.test(UA);
  var MOBILE = ANDROID || IOS;
  var ICON = "pwa-icon-192.png";
  try { ICON = new URL("pwa-icon-192.png", location.href).href; } catch (e) {}
  var PRIV = "confidentialite.html";
  try { PRIV = new URL("confidentialite.html", location.href).href; } catch (e) {}

  function installe() {
    try {
      if (window.matchMedia("(display-mode: fullscreen)").matches || window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true) { return true; }
    } catch (e) {}
    try { if (localStorage.getItem("flex_installed") === "1") { return true; } } catch (e) {}
    return false;
  }
  function marquer() {
    try { localStorage.setItem("flex_installed", "1"); } catch (e) {}
    API.peut = false;
  }
  API.peut = !installe();
  window.addEventListener("appinstalled", function () { marquer(); });

  /* ---------- fenetre par-dessus le jeu (iframe : les touches ne genent pas le jeu) ---------- */
  var CSS = "*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%}" +
    "body{display:flex;align-items:center;justify-content:center;font-family:Arial,Helvetica,sans-serif;color:#eaf0ff;background:radial-gradient(ellipse at center,rgba(22,8,44,.95),rgba(3,4,12,.98) 70%);overflow:hidden}" +
    "body:before{content:'';position:fixed;left:0;top:0;right:0;bottom:0;background:repeating-linear-gradient(0deg,rgba(0,235,255,.05) 0,rgba(0,235,255,.05) 1px,transparent 1px,transparent 4px);pointer-events:none}" +
    "#box{width:100%;height:100%;display:flex;align-items:center;justify-content:center}" +
    ".pn{position:relative;width:min(94%,760px);max-height:96%;overflow:auto;padding:14px 18px;text-align:center;background:linear-gradient(160deg,rgba(14,18,40,.97),rgba(6,8,20,.97));border:2px solid #00ebff;border-radius:16px;box-shadow:0 0 24px rgba(0,235,255,.45),inset 0 0 22px rgba(255,0,180,.12)}" +
    ".t{font-size:clamp(20px,5.5vw,30px);font-weight:900;letter-spacing:2px;color:#fff;text-shadow:-3px 0 #ff00b4,3px 0 #00ebff}" +
    ".s{margin:4px 0 8px;font-size:12px;letter-spacing:2px;color:#ff00b4;font-weight:700}" +
    ".ic{width:64px;height:64px;border-radius:14px;box-shadow:0 0 18px rgba(255,0,180,.6);margin:0 auto 6px;display:block}" +
    "ul{list-style:none;text-align:left;max-width:560px;margin:6px auto 10px}li{font-size:14px;color:#cfd8f5;margin:6px 0;line-height:1.3}" +
    "button{padding:13px 12px;font-size:16px;font-weight:900;letter-spacing:1px;border-radius:12px;cursor:pointer;font-family:inherit}" +
    ".bp{background:#ff00b4;color:#05050a;border:2px solid #ff00b4;box-shadow:0 0 16px rgba(255,0,180,.7);animation:pu 1.6s infinite}" +
    ".big{width:100%;max-width:420px;font-size:19px;padding:15px 12px}" +
    ".bs{background:transparent;color:#00ebff;border:2px solid #00ebff}" +
    "@keyframes pu{50%{box-shadow:0 0 28px rgba(255,0,180,1)}}" +
    ".lk{display:inline-block;margin-top:12px;font-size:14px;color:#8fa0d8;text-decoration:underline;cursor:pointer}" +
    ".h{font-size:14px;color:#cfd8f5;line-height:1.45;margin:8px 0}.h b{color:#ffd646}" +
    ".row{display:flex;gap:10px;justify-content:center;margin-top:10px}.row button{flex:1;max-width:260px}" +
    /* animation du guide */
    ".gd{display:flex;gap:14px;align-items:center;text-align:left}" +
    ".mk{position:relative;flex:none;width:300px;height:200px;border-radius:14px;border:2px solid #3a4580;background:#0b1024;overflow:hidden}" +
    ".bar{position:absolute;left:0;right:0;top:0;height:30px;background:#171d3a;border-bottom:1px solid #2a3260;display:flex;align-items:center;padding:0 8px;gap:6px}" +
    ".url{flex:1;height:18px;border-radius:9px;background:#0b1024;color:#8fa0d8;font-size:9px;line-height:18px;padding-left:8px;overflow:hidden;white-space:nowrap}" +
    ".dots{width:22px;height:22px;border-radius:50%;color:#fff;font-size:17px;font-weight:900;line-height:20px;text-align:center}" +
    ".dots.on{background:rgba(255,0,180,.55);box-shadow:0 0 10px #ff00b4}" +
    ".pg{position:absolute;left:0;right:0;top:30px;bottom:0;display:flex;align-items:center;justify-content:center;color:#2a3470;font-size:22px;font-weight:900;letter-spacing:3px}" +
    ".mn{position:absolute;right:6px;top:32px;width:170px;background:#1c2346;border:1px solid #3a4580;border-radius:8px;padding:4px 0;opacity:0;transform:translateY(-6px);transition:all .3s}" +
    ".mn.on{opacity:1;transform:none}.mn div{font-size:10px;color:#cfd8f5;padding:6px 10px;height:24px}" +
    ".mn div.hl{background:rgba(255,0,180,.35);color:#fff;font-weight:800}" +
    ".dg{position:absolute;left:30px;right:30px;top:50px;background:#1c2346;border:1px solid #3a4580;border-radius:10px;padding:10px;opacity:0;transform:scale(.9);transition:all .3s;text-align:left}" +
    ".dg.on{opacity:1;transform:none}.dg .a{font-size:11px;font-weight:800;color:#fff;margin-bottom:4px}.dg .b2{font-size:9px;color:#8fa0d8;margin-bottom:8px}" +
    ".dg .bb{display:flex;justify-content:flex-end;gap:8px}.dg .bb span{font-size:10px;padding:5px 10px;border-radius:14px;color:#9fb0ff}.dg .bb span.ok{background:#4f7cff;color:#fff;font-weight:800}" +
    ".hm{position:absolute;left:0;right:0;top:0;bottom:0;background:linear-gradient(160deg,#1a1040,#05060f);opacity:0;transition:opacity .4s;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px}" +
    ".hm.on{opacity:1}.hm img{width:56px;height:56px;border-radius:13px;box-shadow:0 0 16px rgba(255,0,180,.7)}.hm span{font-size:10px;color:#fff;font-weight:700}" +
    ".fg{position:absolute;width:30px;height:30px;margin:-4px 0 0 -4px;font-size:26px;line-height:30px;text-align:center;transition:left .9s ease,top .9s ease,opacity .3s;opacity:0;z-index:5;filter:drop-shadow(0 2px 4px #000)}" +
    ".fg:before{content:'';position:absolute;left:-2px;top:-4px;width:30px;height:30px;border-radius:50%;border:3px solid #ffd646;opacity:0}" +
    ".fg.tap:before{animation:rp .7s ease-out}@keyframes rp{0%{transform:scale(.4);opacity:1}100%{transform:scale(1.6);opacity:0}}" +
    ".cp{flex:1;min-width:0}.cp .n{font-size:12px;letter-spacing:2px;color:#00ebff;font-weight:800}.cp .x{font-size:17px;font-weight:800;color:#fff;margin:6px 0;line-height:1.25;min-height:64px}" +
    ".pt{display:flex;gap:6px;margin:8px 0}.pt i{width:26px;height:6px;border-radius:3px;background:#2a3470}.pt i.on{background:#ff00b4;box-shadow:0 0 8px #ff00b4}" +
    "@media (max-width:620px){.gd{flex-direction:column}.mk{width:260px;height:180px}}";

  function fermer() {
    var f = document.getElementById("flexinst");
    if (f && f.parentNode) { f.parentNode.removeChild(f); }
    if (API._timers) { API._timers.forEach(function (t) { clearTimeout(t); }); API._timers = []; }
  }
  function ouvrir(cb) {
    fermer();
    var f = document.createElement("iframe");
    f.id = "flexinst";
    f.style.cssText = "position:fixed;left:0;top:0;width:100%;height:100%;border:0;z-index:2147483646;background:transparent";
    f.srcdoc = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>" + CSS + "</style></head><body><div id='box'></div></body></html>";
    f.onload = function () { try { cb(f.contentDocument); } catch (e) { fermer(); } };
    document.body.appendChild(f);
  }

  /* ---------- ecrans ---------- */
  function accueil() {
    ouvrir(function (d) {
      d.getElementById("box").innerHTML = "<div class='pn'><img class='ic' src='" + ICON + "' alt=''><div class='t'>FLEX CYBERPUNK</div><div class='s'>JOUE EN PLEIN &Eacute;CRAN, D'UN SEUL APPUI</div>" +
        "<ul><li>&#9989; Une <b>ic&ocirc;ne sur ton t&eacute;l&eacute;phone</b> : plus besoin de retaper le lien</li>" +
        "<li>&#9989; <b>Plein &eacute;cran en paysage</b>, sans barre d'adresse</li>" +
        "<li>&#9989; Ta progression, tes skins et ton classement sont sauvegard&eacute;s avec ton compte Google</li></ul>" +
        "<button id='dl' class='bp big'>&#11015; T&Eacute;L&Eacute;CHARGER LE JEU</button><br><a id='nv' class='lk'>Jouer dans le navigateur</a>" +
        "<div style='margin-top:8px;font-size:11px;color:#8fa0d8'><a href='" + PRIV + "' target='_blank' style='color:#8fa0d8'>Confidentialit&eacute; et conditions</a></div></div>";
      d.getElementById("dl").onclick = lancer;
      d.getElementById("nv").onclick = fermer;
    });
  }
  function merci() {
    ouvrir(function (d) {
      d.getElementById("box").innerHTML = "<div class='pn'><img class='ic' src='" + ICON + "' alt=''><div class='t'>INSTALLATION LANC&Eacute;E</div>" +
        "<div class='h'>Cherche l'ic&ocirc;ne <b>Flex Cyberpunk</b> sur ton &eacute;cran d'accueil ou dans le menu de tes applications, puis lance le jeu depuis cette ic&ocirc;ne.</div>" +
        "<div class='row'><button id='ok' class='bp'>OK</button></div></div>";
      d.getElementById("ok").onclick = fermer;
    });
  }
  function texte(titre, corps) {
    ouvrir(function (d) {
      d.getElementById("box").innerHTML = "<div class='pn'><div class='t'>" + titre + "</div><div class='h'>" + corps + "</div><div class='row'><button id='ok' class='bs'>COMPRIS</button></div></div>";
      d.getElementById("ok").onclick = fermer;
    });
  }
  function guide() {
    if (IOS) { return texte("INSTALLER SUR IPHONE", "Dans <b>Safari</b>, appuie sur le bouton <b>Partager</b>, puis sur <b>&laquo; Sur l'&eacute;cran d'accueil &raquo;</b>."); }
    if (WEBVIEW) { return texte("OUVRE LE JEU DANS CHROME", "Tu es dans le navigateur int&eacute;gr&eacute; d'une application (Facebook, WhatsApp...). L'installation et la connexion Google n'y fonctionnent pas.<br>Appuie sur <b>&#8942;</b> puis sur <b>&laquo; Ouvrir dans Chrome &raquo;</b> (ou &laquo; Ouvrir dans le navigateur &raquo;)."); }
    if (!MOBILE) { return texte("INSTALLER SUR ORDINATEUR", "Dans <b>Chrome</b> ou <b>Edge</b>, clique sur l'ic&ocirc;ne d'installation <b>&#8853;</b> &agrave; droite de la barre d'adresse, puis sur <b>&laquo; Installer &raquo;</b>.<br>Sinon : menu <b>&#8942;</b>, puis <b>&laquo; Installer Flex Cyberpunk &raquo;</b>."); }
    animation();
  }

  /* ---------- l'animation avec le doigt ---------- */
  var ETAPES = [
    "Appuie sur les <b>trois points &#8942;</b> en haut &agrave; droite de Chrome",
    "Appuie sur <b>&laquo; Installer l'application &raquo;</b><br><span style='font-size:12px;color:#8fa0d8;font-weight:400'>(ou &laquo; Ajouter &agrave; l'&eacute;cran d'accueil &raquo;)</span>",
    "Appuie sur <b>&laquo; Installer &raquo;</b>",
    "C'est fait ! Ouvre le jeu depuis cette <b>ic&ocirc;ne</b>"
  ];
  function animation() {
    ouvrir(function (d) {
      d.getElementById("box").innerHTML = "<div class='pn'><div class='gd'><div class='mk' id='mk'>" +
        "<div class='bar'><div class='url'>&#128274; flexplayg647-byte.github.io/flex</div><div class='dots' id='dots'>&#8942;</div></div>" +
        "<div class='pg'>FLEX</div>" +
        "<div class='mn' id='mn'><div>Nouvel onglet</div><div>Historique</div><div id='mi'>Installer l'application</div><div>Param&egrave;tres</div></div>" +
        "<div class='dg' id='dg'><div class='a'>Installer l'application ?</div><div class='b2'>Flex Cyberpunk</div><div class='bb'><span>Annuler</span><span class='ok' id='ok2'>Installer</span></div></div>" +
        "<div class='hm' id='hm'><img src='" + ICON + "' alt=''><span>Flex Cyberpunk</span></div>" +
        "<div class='fg' id='fg'>&#128070;</div></div>" +
        "<div class='cp'><div class='n' id='n'>&Eacute;TAPE 1 / 3</div><div class='x' id='x'></div><div class='pt' id='pt'><i></i><i></i><i></i><i></i></div>" +
        "<div class='row' style='justify-content:flex-start'><button id='rj' class='bs'>REJOUER</button><button id='fm' class='bs'>FERMER</button></div>" +
        "<div class='h' style='font-size:12px;color:#8fa0d8'>Si tu vois &laquo; Ouvrir l'application &raquo; au lieu d'&laquo; Installer &raquo;, le jeu est d&eacute;j&agrave; install&eacute; : lance-le depuis son ic&ocirc;ne.</div></div></div></div>";
      d.getElementById("fm").onclick = fermer;
      var el = function (i) { return d.getElementById(i); };
      var mk = el("mk");
      function centre(node) {
        var r = node.getBoundingClientRect(), m = mk.getBoundingClientRect();
        return [r.left - m.left + r.width * 0.5, r.top - m.top + r.height * 0.5];
      }
      function doigt(node) { var c = centre(node); el("fg").style.left = c[0] + "px"; el("fg").style.top = c[1] + "px"; }
      function tap() { var f = el("fg"); f.classList.remove("tap"); void f.offsetWidth; f.classList.add("tap"); }
      function etape(i) {
        el("n").innerHTML = i < 3 ? "&Eacute;TAPE " + (i + 1) + " / 3" : "TERMIN&Eacute;";
        el("x").innerHTML = ETAPES[i];
        var p = el("pt").children, k;
        for (k = 0; k < p.length; k++) { p[k].className = (k === i ? "on" : ""); }
      }
      function plan(ms, fn) { API._timers.push(setTimeout(fn, ms)); }
      function jouer() {
        API._timers.forEach(function (t) { clearTimeout(t); }); API._timers = [];
        el("mn").className = "mn"; el("dg").className = "dg"; el("hm").className = "hm"; el("dots").className = "dots";
        var fg = el("fg"); fg.style.opacity = "0"; fg.style.left = "120px"; fg.style.top = "140px";
        etape(0);
        plan(300, function () { fg.style.opacity = "1"; doigt(el("dots")); });
        plan(1300, function () { tap(); el("dots").className = "dots on"; });
        plan(2100, function () { etape(1); el("mn").className = "mn on"; });
        plan(2500, function () { doigt(el("mi")); });
        plan(3500, function () { tap(); el("mi").className = "hl"; });
        plan(4300, function () { etape(2); el("mn").className = "mn"; el("dots").className = "dots"; el("dg").className = "dg on"; });
        plan(4700, function () { doigt(el("ok2")); });
        plan(5700, function () { tap(); });
        plan(6400, function () { etape(3); el("dg").className = "dg"; fg.style.opacity = "0"; el("hm").className = "hm on"; });
        plan(10200, jouer);
      }
      API._timers = [];
      el("rj").onclick = jouer;
      jouer();
    });
  }

  /* ---------- action principale ---------- */
  function lancer() {
    var e = window.__flexInstallEvt;
    if (e && e.prompt) {
      try {
        e.prompt();
        var choix = e.userChoice || Promise.resolve({});
        choix.then(function (c) {
          window.__flexInstallEvt = null;
          if (c && c.outcome === "accepted") { marquer(); merci(); } else { fermer(); }
        });
      } catch (x) { guide(); }
      return;
    }
    guide();
  }
  API.ouvrir = lancer;
  API.accueil = accueil;
  API.guide = guide;

  /* ---------- petit rappel apres une victoire ---------- */
  var vuVictoire = false;
  API.victoire = function () {
    if (!API.peut || vuVictoire || IOS) { return; }
    try { if (localStorage.getItem("flex_inst_v") === "1") { return; } localStorage.setItem("flex_inst_v", "1"); } catch (e) {}
    vuVictoire = true;
    setTimeout(function () {
      var f = document.createElement("iframe");
      f.id = "flexinst2";
      f.style.cssText = "position:fixed;left:50%;bottom:10px;transform:translateX(-50%);width:min(96%,560px);height:74px;border:0;z-index:2147483645;background:transparent";
      f.srcdoc = "<!DOCTYPE html><html><head><meta charset='utf-8'><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;background:transparent}" +
        ".b{display:flex;align-items:center;gap:10px;height:70px;padding:8px 12px;background:rgba(10,14,32,.97);border:2px solid #ff00b4;border-radius:14px;box-shadow:0 0 18px rgba(255,0,180,.6);color:#fff;font-size:13px;line-height:1.25}" +
        "img{width:44px;height:44px;border-radius:10px;flex:none}.tx{flex:1}.tx b{color:#ffd646}button{padding:9px 10px;border-radius:10px;font-weight:900;font-size:13px;cursor:pointer;flex:none}" +
        ".y{background:#ff00b4;color:#05050a;border:2px solid #ff00b4}.n{background:transparent;color:#8fa0d8;border:2px solid #3a4580;padding:9px 12px}</style></head><body><div class='b'><img src='" + ICON + "' alt=''>" +
        "<div class='tx'>Bravo ! <b>Installe le jeu</b> pour retrouver ta progression en un appui.</div><button class='y' id='y'>INSTALLER</button><button class='n' id='n'>&#10005;</button></div></body></html>";
      f.onload = function () {
        var d = f.contentDocument;
        d.getElementById("y").onclick = function () { if (f.parentNode) { f.parentNode.removeChild(f); } lancer(); };
        d.getElementById("n").onclick = function () { if (f.parentNode) { f.parentNode.removeChild(f); } };
        setTimeout(function () { if (f.parentNode) { f.parentNode.removeChild(f); } }, 14000);
      };
      document.body.appendChild(f);
    }, 2500);
  };

  /* ---------- accueil automatique : 1re, 2e et 6e visite ---------- */
  var visites = 0;
  try {
    visites = parseInt(localStorage.getItem("flex_visits") || "0", 10);
    if (!sessionStorage.getItem("flex_visit_compte")) {
      visites += 1;
      localStorage.setItem("flex_visits", String(visites));
      sessionStorage.setItem("flex_visit_compte", "1");
    }
  } catch (e) {}
  if (!IOS && API.peut && (visites === 1 || visites === 2 || visites === 6)) {
    setTimeout(function () { if (API.peut && !document.getElementById("flexinst")) { accueil(); } }, 1500);
  }
})();
