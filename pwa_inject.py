"""Ajoute la fiche d'application (PWA) à la page du jeu générée par pygbag.
Usage : python pwa_inject.py game/build/web
Le script peut être relancé sans risque : il n'ajoute rien deux fois."""
import re
import sys
from pathlib import Path

dossier = Path(sys.argv[1] if len(sys.argv) > 1 else "game/build/web")
page = dossier / "index.html"
html = page.read_text(encoding="utf-8")

TETE = """
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#05060f">
<meta name="application-name" content="Flex Cyberpunk">
<link rel="icon" type="image/png" sizes="192x192" href="pwa-icon-192.png">
<link rel="apple-touch-icon" href="pwa-icon-192.png">
<meta name="mobile-web-app-capable" content="yes">
<script>
/* garde la proposition d'installation de Chrome pour le bouton "Telecharger le jeu" */
window.__flexInstallEvt = null;
window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); window.__flexInstallEvt = e; });
</script>
"""
PIED = """
<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  });
}
</script>
<script src="install.js"></script>
"""

if 'rel="manifest"' not in html:
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", TETE + "</head>", html, count=1, flags=re.I)
    else:
        html = TETE + html
if "__flexInstallEvt" not in html and 'rel="manifest"' in html:
    # page déjà modifiée par une ancienne version du script : on ajoute seulement ce qui manque
    html = re.sub(r"</head>", TETE.split('<meta name="mobile-web-app-capable" content="yes">')[1] + "</head>", html, count=1, flags=re.I)
if 'src="install.js"' not in html and "serviceWorker.register" in html:
    html = re.sub(r"</body>", '<script src="install.js"></script>\n</body>', html, count=1, flags=re.I)
if "serviceWorker.register" not in html:
    if re.search(r"</body>", html, re.I):
        html = re.sub(r"</body>", PIED + "</body>", html, count=1, flags=re.I)
    else:
        html = html + PIED
# nom affiché dans l'onglet et dans la liste des applications
html = re.sub(r"<title>[^<]*</title>", "<title>Flex Cyberpunk</title>", html, count=1, flags=re.I)

page.write_text(html, encoding="utf-8")
print("Fiche d'application ajoutée à", page)
