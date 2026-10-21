import asyncio
import pygame
import sys
import math
import random
import json
import os
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "1")
import time as _time
import traceback
import hashlib
import hmac
import re


# Dossier des sauvegardes : sur Android (APK) c'est le stockage privé de l'application (conservé lors des mises à jour) ;
# sur Pydroid ou PC, rien ne change : les fichiers restent à côté du jeu.
IS_WEB = sys.platform == "emscripten"
_DOSSIER_DONNEES = os.environ.get("ANDROID_PRIVATE", "")
if IS_WEB:
    _DOSSIER_DONNEES = "/data/data/flexcyber"   # dossier persistant du navigateur (pygbag)
    try:
        os.makedirs(_DOSSIER_DONNEES, exist_ok=True)
    except Exception:
        _DOSSIER_DONNEES = ""


def chemin_donnees(nom):
    return os.path.join(_DOSSIER_DONNEES, nom) if _DOSSIER_DONNEES else nom


# ==================== PROTECTION DU JEU (dissuasion) ====================
# Empreinte du code officiel : calculée à la livraison. Si main.py est modifié, le jeu affiche « VERSION MODIFIÉE ».
# (Tu modifies toi-même le code ? Lance le jeu, copie « Empreinte actuelle » affichée dans la console, colle-la ci-dessous.)
EMPREINTE_OFFICIELLE = "13b857d470e366cb8f20b2174da60f639ed4e9703d474bd2baecab8c86859fc9"


def _empreinte_du_fichier():
    try:
        with open(__file__, "rb") as f:
            texte = f.read().decode("utf-8", "ignore").lstrip("\ufeff")
    except Exception:
        return None                      # impossible de lire le fichier (autre environnement) : pas de vérification
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    texte = re.sub(r'^EMPREINTE_OFFICIELLE = "[0-9a-f]*"$', 'EMPREINTE_OFFICIELLE = ""', texte, flags=re.M)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


_empreinte_actuelle = _empreinte_du_fichier()
VERSION_MODIFIEE = False if IS_WEB else (_empreinte_actuelle is not None and _empreinte_actuelle != EMPREINTE_OFFICIELLE)
if VERSION_MODIFIEE:
    print("⚠️ Version modifiée. Empreinte actuelle :", _empreinte_actuelle)

# Sauvegardes signées : un fichier modifié à la main (pièces, niveaux...) est refusé et remis à zéro.
_SECRET = b"flex" + b"play" + bytes([37, 91, 12, 77, 205, 8]) + b"-cyber-2026"
AVERTISSEMENT = {"texte": "", "debut": None}


def _signature(donnees):
    msg = json.dumps(donnees, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:32]


def ecrire_json_signe(chemin, donnees):
    d = dict(donnees)
    d.pop("sig", None)
    d["v"] = 2
    d["sig"] = _signature(d)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(d, f)


def lire_json_signe(chemin):
    """Retourne (données, statut) ; statut : 'absent', 'ok', 'ancien' (ancienne sauvegarde non signée) ou 'altere'."""
    if not os.path.exists(chemin):
        return None, "absent"
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None, "altere"
    if not isinstance(d, dict):
        return None, "altere"
    if d.get("v") == 2:
        sig = d.pop("sig", None)
        if sig != _signature(d):
            return None, "altere"
        d.pop("v", None)
        return d, "ok"
    return d, "ancien"


def signaler_sauvegarde_alteree():
    AVERTISSEMENT["texte"] = "Sauvegarde modifiée ou illisible : remise à zéro"
    print("⚠️", AVERTISSEMENT["texte"])


def _journal_erreur(type_, valeur, tb):
    """Écrit l'erreur dans crash_flex.log (à côté du jeu) avant que le programme se ferme."""
    try:
        with open(chemin_donnees("crash_flex.log"), "a", encoding="utf-8") as f:
            f.write("\n=== " + _time.strftime("%Y-%m-%d %H:%M:%S") + " ===\n")
            traceback.print_exception(type_, valeur, tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(type_, valeur, tb)


sys.excepthook = _journal_erreur

# 1. INITIALISATION DE PYGAME & PLEIN ÉCRAN
pygame.init()
info_ecran = pygame.display.Info()
LARGEUR, HAUTEUR = info_ecran.current_w, info_ecran.current_h
if HAUTEUR > LARGEUR:
    LARGEUR, HAUTEUR = HAUTEUR, LARGEUR
if IS_WEB:
    # Résolution virtuelle : tout est dessiné comme sur ton téléphone (1080 px de haut),
    # puis le navigateur adapte l'image à l'écran du joueur. Plus grand = interface plus petite.
    WEB_HAUTEUR = 1080
    try:
        import platform as _pf
        _w, _h = float(_pf.window.innerWidth), float(_pf.window.innerHeight)
    except Exception:
        _w, _h = float(LARGEUR), float(HAUTEUR)
    _INNER = (int(_w), int(_h))
    if _h > _w:
        _w, _h = _h, _w
    _asp = max(1.2, min(2.8, _w / max(1.0, _h)))
    try:     # réglage dans le lien : ...?h=1500  (plus grand = interface plus petite)
        import re as _re
        _m = _re.search(r"[?&]h=([0-9]+)", str(_pf.window.location.search))
        if _m and 500 <= int(_m.group(1)) <= 3200:
            WEB_HAUTEUR = int(_m.group(1))
    except Exception:
        pass
    HAUTEUR = WEB_HAUTEUR
    LARGEUR = int(round(WEB_HAUTEUR * _asp))
    try:
        _SEARCH = str(_pf.window.location.search)
    except Exception:
        _SEARCH = ""
    _DBG = "dbg=1" in _SEARCH          # ...?dbg=1 : affiche l'étiquette de diagnostic
    _HD = "hd=1" in _SEARCH            # ...?hd=1  : canvas à la vraie résolution de l'écran (plus net)
    try:
        _DPR = max(1.0, min(4.0, float(_pf.window.devicePixelRatio)))
    except Exception:
        _DPR = 1.0
    _K = _DPR if _HD else 1.0
    _REQ = (max(200, int(_INNER[0] * _K)), max(200, int(_INNER[1] * _K)))

ecran = pygame.display.set_mode(_REQ if IS_WEB else (LARGEUR, HAUTEUR), 0 if IS_WEB else pygame.FULLSCREEN)
# Sur certains téléphones (encoche / caméra) la surface réellement affichée est plus petite que celle annoncée :
# on utilise sa vraie taille, sinon les boutons à droite sont coupés et le toucher est décalé.
if IS_WEB:
    _VW, _VH = LARGEUR, HAUTEUR
    ecran = pygame.Surface((_VW, _VH)).convert()
    _FX = {"ox": 0, "oy": 0, "sc": 0.0, "rw": 1, "rh": 1, "w": _VW, "h": _VH, "n": 0}
    _FLIP_REEL = pygame.display.flip
    _EVENT_REEL = pygame.event.get
    _POLICE_DBG = {"f": None}

    def _maj_fx():
        reel = pygame.display.get_surface()
        rw, rh = reel.get_size()
        sc = min(rw / float(_VW), rh / float(_VH))
        w, h = max(1, int(_VW * sc)), max(1, int(_VH * sc))
        _FX.update(ox=(rw - w) // 2, oy=(rh - h) // 2, sc=sc, rw=rw, rh=rh, w=w, h=h)
        return reel

    def _flip_web():
        _FX["k"] = _FX.get("k", 0) + 1
        if _FX["k"] % 20 == 0:      # la fenêtre a changé (rotation du téléphone...) : on réajuste le canvas
            try:
                _iw, _ih = int(_pf.window.innerWidth), int(_pf.window.innerHeight)
                if _iw > 100 and _ih > 100 and (_iw, _ih) != _FX.get("req", (_iw, _ih)):
                    pygame.display.set_mode((int(_iw * _K), int(_ih * _K)), 0)
                    _style_canvas(_iw, _ih)
                _FX["req"] = (_iw, _ih)
            except Exception:
                pass
        reel = _maj_fx()
        f = _FX
        if f["ox"] or f["oy"]:
            reel.fill((0, 0, 0))
        if f["w"] == _VW and f["h"] == _VH:
            reel.blit(ecran, (f["ox"], f["oy"]))
        else:
            pygame.transform.scale(ecran, (f["w"], f["h"]), reel.subsurface((f["ox"], f["oy"], f["w"], f["h"])))
        f["n"] += 1
        try:
            if _POLICE_DBG["f"] is None:
                _POLICE_DBG["f"] = pygame.font.Font(None, 30)
            if _DBG:     # étiquette de version + tailles (diagnostic)
                t = _POLICE_DBG["f"].render("w10 R%dx%d V%dx%d I%s" % (f["rw"], f["rh"], _VW, _VH, str(globals().get("_INNER"))), True, (255, 255, 0), (0, 0, 0))
                reel.blit(t, (4, max(0, f["rh"] - t.get_height() - 4)))
                if f["n"] < 1200:
                    pygame.draw.rect(reel, (255, 255, 0), (0, 0, f["rw"], f["rh"]), 3)
            if f["rh"] > f["rw"]:
                t = _POLICE_DBG["f"].render("Tourne le telephone en paysage, puis recharge la page", True, (255, 255, 255), (200, 0, 80))
                reel.blit(t, (max(0, (f["rw"] - t.get_width()) // 2), f["rh"] - 60))
        except Exception:
            pass
        _FLIP_REEL()

    def _event_get_web(*a, **k):
        evs = _EVENT_REEL(*a, **k)
        f = _FX
        if f["sc"]:
            for e in evs:
                try:
                    if e.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
                        e.x = ((e.x * f["rw"] - f["ox"]) / f["sc"]) / float(_VW)
                        e.y = ((e.y * f["rh"] - f["oy"]) / f["sc"]) / float(_VH)
                    elif e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                        e.pos = (int((e.pos[0] - f["ox"]) / f["sc"]), int((e.pos[1] - f["oy"]) / f["sc"]))
                except Exception:
                    pass
        return evs

    def _style_canvas(w, h):
        if not _HD:
            return
        try:      # on garde la taille d'affichage = fenêtre, même si le canvas a plus de pixels
            _c = _pf.window.canvas
            _c.style.width = "%dpx" % w
            _c.style.height = "%dpx" % h
        except Exception:
            pass

    _maj_fx()
    _style_canvas(_INNER[0], _INNER[1])
    _FX["req"] = (_INNER[0], _INNER[1])
    pygame.display.flip = _flip_web
    pygame.display.update = lambda *a, **k: _flip_web()
    pygame.event.get = _event_get_web
LARGEUR, HAUTEUR = ecran.get_size()
pygame.display.set_caption("Flex Cyberpunk Réaliste 🚀 - MODE INFINI")

# TAILLES DU JEU
TAILLE_CASE = 100
TAILLE_PERSO = 45

# QUALITÉ DES EFFETS :  0 = léger (très bas de gamme)  |  1 = équilibré (par défaut)  |  2 = complet (téléphones puissants)
# Avec AUTO_QUALITE = True, le jeu baisse tout seul le niveau s'il détecte que ça rame.
QUALITE_EFFETS = 1
AUTO_QUALITE = True
QUALITE = {"niveau": QUALITE_EFFETS}

# ---- Résolution réduite : le jeu est dessiné en petit puis agrandi (ça allège beaucoup les téléphones faibles).
# Le reste du code dessine comme d'habitude : CibleEchelle convertit les coordonnées à la volée.
_cache_reduits = {}


class CibleEchelle:
    """Reçoit les ordres de dessin dans le repère du jeu (taille normale) et les convertit à l'échelle de la vraie surface."""

    def __init__(self, s, surf=None):
        self.s = s
        self.surf = surf if surf is not None else pygame.Surface((max(1, int(LARGEUR * s)), max(1, int(HAUTEUR * s)))).convert()

    def get_size(self):
        return (LARGEUR, HAUTEUR)

    def fill(self, c, *a, **k):
        self.surf.fill(c, *a, **k)

    def set_clip(self, r):
        if r is None:
            self.surf.set_clip(None)
            return
        s = self.s
        x, y, w, h = r
        nx, ny = math.floor(x * s), math.floor(y * s)
        self.surf.set_clip((nx, ny, max(1, int(round((x + w) * s)) - nx), max(1, int(round((y + h) * s)) - ny)))

    def blit(self, src, dest, area=None, special_flags=0):
        s = self.s
        cle = (id(src), s)
        v = _cache_reduits.get(cle)
        if v is None:
            if len(_cache_reduits) > 700:
                _cache_reduits.clear()
            w, h = src.get_size()
            taille = (max(1, int(round(w * s))), max(1, int(round(h * s))))
            try:
                r = pygame.transform.smoothscale(src, taille)
            except Exception:
                r = pygame.transform.scale(src, taille)
            v = (src, r)
            _cache_reduits[cle] = v
        self.surf.blit(v[1], (math.floor(dest[0] * s), math.floor(dest[1] * s)), None, special_flags)


_cible_monde = None


def obtenir_cible_monde():
    global _cible_monde
    if _cible_monde is None or _cible_monde.s != ECHELLE:
        _cible_monde = CibleEchelle(ECHELLE)
    return _cible_monde


def _pt(p, s):
    return (int(round(p[0] * s)), int(round(p[1] * s)))


def _lw(w, s):
    return max(1, int(round(w * s))) if w else 0


class _Dessin:
    def rect(self, surf, couleur, rect, width=0, **kw):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            nx, ny = math.floor(x * s), math.floor(y * s)
            nw = max(1, int(round((x + w) * s)) - nx)
            nh = max(1, int(round((y + h) * s)) - ny)
            if "border_radius" in kw:
                kw["border_radius"] = int(kw["border_radius"] * s)
            return pygame.draw.rect(surf.surf, couleur, (nx, ny, nw, nh), _lw(width, s), **kw)
        return pygame.draw.rect(surf, couleur, rect, width, **kw)

    def circle(self, surf, couleur, centre, rayon, width=0, **kw):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.circle(surf.surf, couleur, _pt(centre, s), max(1, int(round(rayon * s))), _lw(width, s), **kw)
        return pygame.draw.circle(surf, couleur, centre, rayon, width, **kw)

    def line(self, surf, couleur, a, b, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.line(surf.surf, couleur, _pt(a, s), _pt(b, s), max(1, int(round(width * s))))
        return pygame.draw.line(surf, couleur, a, b, width)

    def lines(self, surf, couleur, ferme, points, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.lines(surf.surf, couleur, ferme, [_pt(p, s) for p in points], max(1, int(round(width * s))))
        return pygame.draw.lines(surf, couleur, ferme, points, width)

    def polygon(self, surf, couleur, points, width=0):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            return pygame.draw.polygon(surf.surf, couleur, [_pt(p, s) for p in points], _lw(width, s))
        return pygame.draw.polygon(surf, couleur, points, width)

    def ellipse(self, surf, couleur, rect, width=0):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            return pygame.draw.ellipse(surf.surf, couleur, (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s))), _lw(width, s))
        return pygame.draw.ellipse(surf, couleur, rect, width)

    def arc(self, surf, couleur, rect, debut, fin, width=1):
        if isinstance(surf, CibleEchelle):
            s = surf.s
            x, y, w, h = rect
            return pygame.draw.arc(surf.surf, couleur, (int(x * s), int(y * s), max(1, int(w * s)), max(1, int(h * s))), debut, fin, max(1, int(round(width * s))))
        return pygame.draw.arc(surf, couleur, rect, debut, fin, width)


_DESSIN_ECHELLE = _Dessin()
DRAW = pygame.draw


# ==================== RÉSOLUTION MATÉRIELLE ====================
# Le jeu garde son repère habituel (LARGEUR x HAUTEUR) mais la vraie surface est plus petite : le téléphone dessine
# 2 à 4 fois moins de pixels, et SDL (carte graphique) agrandit gratuitement l'image à la fin.
def _lire_prefs_boot():
    try:
        with open(chemin_donnees("parametres_flex.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecrire_prefs_boot(maj):
    d = _lire_prefs_boot()
    d.update(maj)
    try:
        with open(chemin_donnees("parametres_flex.json"), "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def _mini_benchmark_ecran():
    """Mesure la vitesse réelle de l'écran (remplissage + 120 tuiles + affichage) pour choisir la résolution."""
    try:
        tuile = pygame.Surface((100, 100)).convert()
        tuile.fill((30, 40, 70))
        travail, affichage = [], []
        for _ in range(12):
            t0 = _time.perf_counter()
            ecran.fill((8, 10, 20))
            for a in range(15):
                for b in range(8):
                    ecran.blit(tuile, (a * 100, b * 90))
            t1 = _time.perf_counter()
            pygame.display.flip()
            affichage.append((_time.perf_counter() - t1) * 1000.0)
            travail.append((t1 - t0) * 1000.0)
        cout = sum(travail[4:]) / len(travail[4:]) + max(0.0, sum(affichage[4:]) / len(affichage[4:]) - 15.0)
    except Exception:
        return 1.0
    return 1.0 if cout <= 7 else (0.75 if cout <= 14 else 0.5)


_PB = _lire_prefs_boot()
EXTRA = {"echelle_auto": _PB.get("echelle_auto"), "_essai": int(_PB.get("_essai", 0) or 0), "suggere": False}
ECHELLE = 1.0
MOUSE_K = {"k": 1.0}
CAL = {"f": None, "m": None}
_idx_res = _PB.get("resolution", 0)
if not isinstance(_idx_res, int) or not 0 <= _idx_res <= 3:
    _idx_res = 0
if EXTRA["_essai"] >= 2:
    # deux lancements de suite n'ont pas tenu avec une résolution réduite : retour sécurisé à 100 %
    _idx_res, EXTRA["echelle_auto"], EXTRA["_essai"] = 1, 1.0, 0
    _ecrire_prefs_boot({"resolution": 1, "echelle_auto": 1.0, "_essai": 0})
_cible_ech = 1.0
if _idx_res == 2:
    _cible_ech = 0.75
elif _idx_res == 3:
    _cible_ech = 0.5
elif _idx_res == 0:
    if EXTRA["echelle_auto"] in (0.75, 0.5, 1.0):
        _cible_ech = EXTRA["echelle_auto"]
    else:
        _cible_ech = 1.0 if IS_WEB else _mini_benchmark_ecran()
        EXTRA["echelle_auto"] = _cible_ech
        _ecrire_prefs_boot({"echelle_auto": _cible_ech})
if IS_WEB:
    _cible_ech = 1.0
if _cible_ech < 0.99:
    try:
        _taille_petite = (int(LARGEUR * _cible_ech), int(HAUTEUR * _cible_ech))
        _petit = pygame.display.set_mode(_taille_petite, pygame.FULLSCREEN | pygame.SCALED)
        if _petit.get_size() != _taille_petite:
            raise RuntimeError("taille de surface inattendue : " + str(_petit.get_size()))
        ECHELLE = _cible_ech
        ecran = CibleEchelle(ECHELLE, _petit)
        DRAW = _DESSIN_ECHELLE
        MOUSE_K["k"] = 1.0 / ECHELLE
        EXTRA["_essai"] += 1
        _ecrire_prefs_boot({"_essai": EXTRA["_essai"]})
    except Exception as _e:
        print("⚠️ Résolution réduite indisponible, on reste à 100% :", _e)
        ecran = pygame.display.set_mode((LARGEUR, HAUTEUR), 0 if IS_WEB else pygame.FULLSCREEN)
        LARGEUR, HAUTEUR = ecran.get_size()


def pos_ev(event):
    """Position d'un événement souris dans le repère du jeu."""
    k = MOUSE_K["k"]
    return (event.pos[0] * k, event.pos[1] * k)


def _calibrer_souris(event):
    """Un toucher envoie un événement doigt ET souris : on compare les deux pour vérifier l'échelle de la souris."""
    if ECHELLE >= 0.99:
        return
    t = pygame.time.get_ticks()
    if event.type == pygame.FINGERDOWN:
        CAL["f"] = (event.x * LARGEUR, event.y * HAUTEUR, t)
    elif event.type == pygame.MOUSEBUTTONDOWN:
        CAL["m"] = (event.pos[0], event.pos[1], t)
    else:
        return
    f, m = CAL["f"], CAL["m"]
    if f and m and abs(f[2] - m[2]) < 80:
        for fv, mv in ((f[0], m[0]), (f[1], m[1])):
            if mv > 120 and fv > 120 and 0.9 <= fv / float(mv) <= 2.3:
                MOUSE_K["k"] = fv / float(mv)
        CAL["f"] = CAL["m"] = None



# ==================== ÉCRAN IMMÉDIAT ====================
# Dès que la fenêtre existe, on affiche le logo : le joueur ne reste jamais devant un écran noir pendant que les fichiers se chargent.
DEMARRAGE = {"actif": True}


def _ecran_precoce():
    try:
        police_logo = pygame.font.SysFont(None, 110)
        police_info = pygame.font.SysFont(None, 34)
        ecran.fill((4, 5, 14))
        cx, cy = LARGEUR // 2, int(HAUTEUR * 0.40)
        for dx, couleur in ((-4, (255, 60, 190)), (4, (0, 220, 255)), (0, (255, 255, 255))):
            t = police_logo.render("FLEXPLAY", True, couleur)
            ecran.blit(t, (cx - t.get_width() // 2 + dx, cy - t.get_height() // 2))
        t = police_info.render("présente", True, (0, 200, 240))
        ecran.blit(t, (cx - t.get_width() // 2, cy + 52))
        t = police_info.render("Chargement des ressources...", True, (235, 240, 255))
        ecran.blit(t, (cx - t.get_width() // 2, HAUTEUR - 112))
        bw = min(460, LARGEUR - 120)
        bx, by = cx - bw // 2, HAUTEUR - 64
        DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, 12), border_radius=6)
        DRAW.rect(ecran, (0, 220, 255), (bx, by, bw // 6, 12), border_radius=6)
        DRAW.rect(ecran, (0, 150, 190), (bx, by, bw, 12), 2, border_radius=6)
        pygame.display.flip()
        pygame.event.pump()
    except Exception as e:
        print("⚠️ Écran de démarrage immédiat indisponible :", e)


_ecran_precoce()


# 2. CHARGEMENT DES SONS (fichiers déposés dans le dossier du jeu)
try:
    pygame.mixer.init()
    son_tir = pygame.mixer.Sound("tir.wav")
    son_explosion = pygame.mixer.Sound("explosion.ogg" if IS_WEB else "explosion.mp3")
    son_echec = pygame.mixer.Sound("echec.wav")
    son_victoire = pygame.mixer.Sound("victoire.wav")
    son_tir.set_volume(0.5)
    son_explosion.set_volume(0.6)
    son_echec.set_volume(0.7)
    son_victoire.set_volume(0.7)
    SON_ACTIF = True
except Exception as e:
    print(f"⚠️ Sons indisponibles : {e}")
    SON_ACTIF = False

try:
    pygame.mixer.music.load("musique_ambiance.ogg" if IS_WEB else "musique_ambiance.mp3")
    pygame.mixer.music.set_volume(0.4)
    MUSIQUE_ACTIVE = True
except Exception as e:
    print(f"⚠️ Musique d'ambiance indisponible : {e}")
    MUSIQUE_ACTIVE = False

musique_lancee = False

# 3. CHARGEMENT DES SPRITES AVEC LES NOMS DE FICHIERS REMOVEBG
try:
    img_joueur_droite = pygame.image.load("perso-removebg-preview.png").convert_alpha()
    img_joueur_droite = pygame.transform.scale(img_joueur_droite, (TAILLE_PERSO, TAILLE_PERSO))
    img_joueur_gauche = pygame.transform.flip(img_joueur_droite, True, False)
    img_joueur_actuel = img_joueur_droite

    img_drone = pygame.image.load("drone__23_-removebg-preview.png").convert_alpha()
    img_drone = pygame.transform.scale(img_drone, (40, 40))

    img_core = pygame.image.load("core.png").convert_alpha()
    img_core = pygame.transform.scale(img_core, (TAILLE_CASE, TAILLE_CASE))

    MODE_GRAPHIQUE = "REALISTE"
except Exception as e:
    print(f"⚠️ Mode réaliste indisponible (fichiers manquants) : {e}")
    MODE_GRAPHIQUE = "NEON"

# 3bis. CHARGEMENT DU BOSS
TAILLE_BOSS = 260
RAYON_CORPS_BOSS = TAILLE_BOSS * 0.30
try:
    img_boss = pygame.image.load("boss.png").convert_alpha()
    img_boss = pygame.transform.smoothscale(img_boss, (TAILLE_BOSS, TAILLE_BOSS))
    BOSS_IMAGE_DISPONIBLE = True
except Exception as e:
    print(f"⚠️ Image du boss indisponible : {e}")
    BOSS_IMAGE_DISPONIBLE = False

# COULEURS
NOIR_ESPACE = (5, 5, 10)
GRIS_HACKER = (20, 25, 35)
BLANC_NEON = (240, 245, 255)
VERT_FLUO = (0, 255, 128)
ROUGE_ALERTE = (255, 0, 85)
VIOLET_CYBER = (180, 0, 255)
BLEU_CYBER = (0, 190, 255)
ORANGE_MEC = (255, 130, 0)
ROSE_SYNTH = (255, 0, 180)
JAUNE_CYBER = (255, 220, 0)
CYAN_NEON = (0, 235, 255)

NOMS = [
    "TRON GRID", "TRACKERS REZ", "SYSTEM OVERLOAD", "INFILTRATION CORE", "CYBER STREETS",
    "GHOST IN THE NET", "BLACKOUT HEIST", "THE MAINFRAME", "NEON DISTRICT", "OVERLORD INTRUSION",
    "PROXY GATE", "QUANTUM FIREWALL", "DATA CORRUPTION", "CYBERDOME FALL", "THE FINAL FLEX"
]
COULEURS = [BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE, VIOLET_CYBER, BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE,
            VERT_FLUO, ROSE_SYNTH, JAUNE_CYBER, BLEU_CYBER, ORANGE_MEC, ROUGE_ALERTE, VIOLET_CYBER, JAUNE_CYBER]


# ==================== MOTEUR D'EFFETS VISUELS ====================
# Halos lumineux (additifs), tuiles néon pré-rendues, particules, secousse d'écran.
# Tout est mis en cache : très peu de calculs par image, même sur téléphone.
def melange(c1, c2, a):
    a = max(0.0, min(1.0, a))
    return (int(c1[0] * (1 - a) + c2[0] * a), int(c1[1] * (1 - a) + c2[1] * a), int(c1[2] * (1 - a) + c2[2] * a))


def eclaircir(c, a):
    a = max(0.0, a)
    return (min(255, int(c[0] * a)), min(255, int(c[1] * a)), min(255, int(c[2] * a)))


_cache_halos = {}


def obtenir_halo(rayon, couleur, intensite=1.0):
    rayon = max(4, int(rayon) // 4 * 4)
    intensite = max(0.0, min(1.0, round(intensite * 6) / 6.0))
    cle = (rayon, couleur, intensite)
    surf = _cache_halos.get(cle)
    if surf is None:
        base_r = 24
        petit = pygame.Surface((base_r * 2, base_r * 2))
        petit.fill((0, 0, 0))
        for r in range(base_r, 0, -1):
            f = min(1.0, (1 - r / float(base_r)) ** 2 * intensite)
            DRAW.circle(petit, (int(couleur[0] * f), int(couleur[1] * f), int(couleur[2] * f)), (base_r, base_r), r)
        petit = petit.convert()
        if rayon == base_r:
            surf = petit
        else:
            try:
                surf = pygame.transform.smoothscale(petit, (rayon * 2, rayon * 2))
            except Exception:
                surf = pygame.transform.scale(petit, (rayon * 2, rayon * 2))
            surf = surf.convert()
        _cache_halos[cle] = surf
    return surf


def dessiner_halo(x, y, rayon, couleur, intensite=1.0, min_q=1):
    """Lueur additive. N'est dessinée que si la qualité actuelle >= min_q."""
    if intensite < 0.08 or QUALITE["niveau"] < min_q:
        return
    rayon_q = max(4, int(rayon) // 4 * 4)
    ecran.blit(obtenir_halo(rayon, couleur, intensite), (int(x) - rayon_q, int(y) - rayon_q),
               special_flags=pygame.BLEND_RGB_ADD)


_cache_tuiles = {}


def tuile_mur(couleur, masque):
    """Mur sombre avec arête néon du côté des couloirs. masque : 1=haut 2=bas 4=gauche 8=droite."""
    cle = ("m", couleur, masque)
    t = _cache_tuiles.get(cle)
    if t is None:
        T = TAILLE_CASE
        base = (12, 15, 27)
        t = pygame.Surface((T, T))
        t.fill(base)
        DRAW.rect(t, (22, 28, 46), (14, 14, T - 28, T - 28), 2)
        DRAW.line(t, (17, 22, 38), (14, 14), (T - 14, T - 14), 1)
        DRAW.line(t, (17, 22, 38), (T - 14, 14), (14, T - 14), 1)
        DRAW.circle(t, (30, 38, 64), (T // 2, T // 2), 6, 1)
        for i in range(14):
            a = (1 - i / 14.0) ** 2
            col = melange(base, couleur, a)
            if i == 0:
                col = melange(couleur, BLANC_NEON, 0.55)
            if masque & 1:
                DRAW.line(t, col, (0, i), (T, i))
            if masque & 2:
                DRAW.line(t, col, (0, T - 1 - i), (T, T - 1 - i))
            if masque & 4:
                DRAW.line(t, col, (i, 0), (i, T))
            if masque & 8:
                DRAW.line(t, col, (T - 1 - i, 0), (T - 1 - i, T))
        t = t.convert()
        _cache_tuiles[cle] = t
    return t


def tuile_sol(couleur, variante, masque=0):
    """Sol sombre teinté. masque (1=haut 2=bas 4=gauche 8=droite) : murs voisins qui projettent une ombre."""
    cle = ("s", couleur, variante, masque)
    t = _cache_tuiles.get(cle)
    if t is None:
        T = TAILLE_CASE
        fond = melange((5, 7, 14), couleur, 0.07 + 0.02 * variante)
        t = pygame.Surface((T, T))
        t.fill(fond)
        DRAW.rect(t, melange(fond, couleur, 0.22), (0, 0, T, T), 1)
        coin = melange(fond, couleur, 0.55)
        for cx_, cy_, sx, sy in ((0, 0, 1, 1), (T - 1, 0, -1, 1), (0, T - 1, 1, -1), (T - 1, T - 1, -1, -1)):
            DRAW.line(t, coin, (cx_, cy_), (cx_ + sx * 9, cy_), 2)
            DRAW.line(t, coin, (cx_, cy_), (cx_, cy_ + sy * 9), 2)
        if variante:
            DRAW.rect(t, melange(fond, couleur, 0.10), (20, 20, T - 40, T - 40), 1)
        if masque:
            ombre = pygame.Surface((T, T), pygame.SRCALPHA)
            for i in range(18):
                a = int(150 * (1 - i / 18.0) ** 2)
                if masque & 1:
                    DRAW.line(ombre, (0, 0, 8, a), (0, i), (T, i))
                if masque & 4:
                    DRAW.line(ombre, (0, 0, 8, a), (i, 0), (i, T))
            for i in range(10):
                a = int(95 * (1 - i / 10.0) ** 2)
                if masque & 2:
                    DRAW.line(ombre, (0, 0, 8, a), (0, T - 1 - i), (T, T - 1 - i))
                if masque & 8:
                    DRAW.line(ombre, (0, 0, 8, a), (T - 1 - i, 0), (T - 1 - i, T))
            t.blit(ombre, (0, 0))
        t = t.convert()
        _cache_tuiles[cle] = t
    return t


# ---- Particules, ondes de choc, secousse d'écran
particules_fx = []   # [x, y, vx, vy, vie, vie_max, couleur, taille]
ondes_fx = []        # [x, y, rayon, rayon_max, couleur, vie, vie_max]
ETAT_FX = {"secousse": 0.0}
CAM = {"x": 0.0, "y": 0.0}   # position lissée de la caméra
def max_particules():
    return (40, 90, 200)[QUALITE["niveau"]]


def creer_explosion(x, y, couleur, nombre=24, vitesse=7.0, secousse=3.0):
    if PARAMS["secousse"]:
        ETAT_FX["secousse"] = min(14.0, max(ETAT_FX["secousse"], secousse))
    if not PARAMS["particules"]:
        return
    palette = [couleur, couleur, BLANC_NEON, JAUNE_CYBER if couleur != VERT_FLUO else (180, 255, 210)]
    for _ in range(nombre):
        if len(particules_fx) >= max_particules():
            break
        ang = random.uniform(0, math.tau)
        v = random.uniform(1.0, vitesse)
        vie = random.randint(18, 40)
        particules_fx.append([x, y, math.cos(ang) * v, math.sin(ang) * v, vie, vie,
                              random.choice(palette), random.uniform(1.5, 3.6)])
    ondes_fx.append([x, y, 6.0, 40.0 + nombre * 1.2, couleur, 20, 20])


def creer_etincelles(x, y, couleur, nombre=6):
    if not PARAMS["particules"]:
        return
    for _ in range(nombre):
        if len(particules_fx) >= max_particules():
            break
        ang = random.uniform(0, math.tau)
        v = random.uniform(0.8, 4.0)
        vie = random.randint(8, 18)
        particules_fx.append([x, y, math.cos(ang) * v, math.sin(ang) * v, vie, vie,
                              random.choice([couleur, BLANC_NEON]), random.uniform(1.2, 2.4)])


def creer_propulsion(x, y, vx, vy, couleur):
    if not PARAMS["particules"]:
        return
    if len(particules_fx) < max_particules():
        vie = random.randint(10, 18)
        particules_fx.append([x - vx * 1.5 + random.uniform(-5, 5), y - vy * 1.5 + random.uniform(-5, 5),
                              -vx * 0.12 + random.uniform(-0.4, 0.4), -vy * 0.12 + random.uniform(-0.4, 0.4),
                              vie, vie, couleur, 2.6])


def mettre_a_jour_fx():
    for p in particules_fx:
        p[0] += p[2]
        p[1] += p[3]
        p[2] *= 0.93
        p[3] *= 0.93
        p[4] -= 1
    particules_fx[:] = [p for p in particules_fx if p[4] > 0]
    for o in ondes_fx:
        o[2] += (o[3] - o[2]) * 0.2
        o[5] -= 1
    ondes_fx[:] = [o for o in ondes_fx if o[5] > 0]
    s = ETAT_FX["secousse"]
    ETAT_FX["secousse"] = s * 0.86 if s > 0.4 else 0.0


def dessiner_fx(ox, oy):
    for o in ondes_fx:
        a = o[5] / float(o[6])
        ex_, ey_ = int(o[0] + ox), int(o[1] + oy)
        dessiner_halo(ex_, ey_, int(o[2]) + 24, o[4], 0.8 * a, 2)
        DRAW.circle(ecran, eclaircir(o[4], a), (ex_, ey_), max(2, int(o[2])), max(1, int(4 * a)))
    for p in particules_fx:
        a = p[4] / float(p[5])
        x, y = int(p[0] + ox), int(p[1] + oy)
        DRAW.line(ecran, eclaircir(p[6], a), (x, y), (int(x - p[2] * 2), int(y - p[3] * 2)),
                         max(1, int(p[7] * a + 0.5)))


_cache_textes = {}


def rendu_texte(police, texte, aa, couleur):
    """Comme police.render() mais mémorise le résultat (gros gain : le texte n'est dessiné qu'une fois)."""
    cle = (id(police), texte, couleur)
    s = _cache_textes.get(cle)
    if s is None:
        if len(_cache_textes) > 500:
            _cache_textes.clear()
        s = police.render(texte, aa, couleur)
        _cache_textes[cle] = s
    return s


_cache_voiles = {}


def obtenir_voile(w, h, rgba):
    """Surface translucide créée une seule fois (au lieu de la recréer à chaque image)."""
    cle = (w, h, rgba)
    s = _cache_voiles.get(cle)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill(rgba)
        s = s.convert_alpha()
        _cache_voiles[cle] = s
    return s


_cache_boutons = {}


def bouton_neon(rect, couleur, texte, police, plein=False, pulse=False):
    """Bouton néon pré-rendu (le halo 'respire' sur 4 niveaux mis en cache)."""
    complet = QUALITE["niveau"] >= 1
    niveau_pulse = 3
    if pulse and complet:
        niveau_pulse = int((math.sin(pygame.time.get_ticks() / 280.0) + 1) * 1.5 + 0.5)
    cle = (rect.width, rect.height, couleur, texte, id(police), plein, niveau_pulse, complet)
    s = _cache_boutons.get(cle)
    marge = 22
    if s is None:
        force = 0.55 + 0.15 * niveau_pulse
        s = pygame.Surface((rect.width + marge * 2, rect.height + marge * 2), pygame.SRCALPHA)
        r0 = pygame.Rect(marge, marge, rect.width, rect.height)
        rayon_coin = 12
        for i in (range(6, 0, -1) if complet else (3, 1)):
            a = (1 - i / 7.0) * 0.55 * force
            DRAW.rect(s, eclaircir(couleur, a), r0.inflate(i * 5, i * 5), width=3, border_radius=rayon_coin + i * 2)
        if plein:
            DRAW.rect(s, couleur, r0, border_radius=rayon_coin)
            DRAW.rect(s, melange(couleur, BLANC_NEON, 0.45), (r0.x + 4, r0.y + 4, r0.width - 8, r0.height // 3),
                             border_radius=min(rayon_coin - 3, r0.height // 6))
            couleur_texte = NOIR_ESPACE
        else:
            DRAW.rect(s, (8, 10, 20), r0, border_radius=rayon_coin)
            DRAW.rect(s, couleur, r0, width=3, border_radius=rayon_coin)
            couleur_texte = couleur
        t = rendu_texte(police, texte, True, couleur_texte)
        s.blit(t, (r0.centerx - t.get_width() // 2, r0.centery - t.get_height() // 2))
        s = s.convert_alpha()
        _cache_boutons[cle] = s
    ecran.blit(s, (rect.x - marge, rect.y - marge))


# ==================== FOND DE VILLE (vue du dessus, autour du labyrinthe) ====================
# Une seule tuile est dessinée au démarrage, puis répétée avec un effet de profondeur (parallaxe).
TUILE_VILLE = 480
LARGEUR_ROUTE = 40
_tuile_ville = None


def dessiner_toit(s, rect, couleur, alea):
    x, y, w, h = rect
    base = alea.choice([(10, 9, 24), (12, 10, 28), (8, 11, 24)])
    DRAW.rect(s, base, rect)
    DRAW.rect(s, melange(base, couleur, 0.10), (x - 4, y - 4, w + 8, h + 8), 4)
    DRAW.rect(s, melange(base, couleur, 0.30), rect, 3)
    DRAW.rect(s, melange(couleur, BLANC_NEON, 0.35), rect, 1)
    DRAW.rect(s, melange(base, couleur, 0.16), (x + 10, y + 10, w - 20, h - 20), 1)
    cx_, cy_ = x + w // 2, y + h // 2
    type_toit = alea.randint(0, 3)
    if type_toit == 0:      # héliport
        r = min(w, h) // 5
        DRAW.circle(s, melange(base, couleur, 0.55), (cx_, cy_), r, 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ - r // 2, cy_ - r // 2), (cx_ - r // 2, cy_ + r // 2), 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ + r // 2, cy_ - r // 2), (cx_ + r // 2, cy_ + r // 2), 3)
        DRAW.line(s, melange(base, couleur, 0.55), (cx_ - r // 2, cy_), (cx_ + r // 2, cy_), 3)
    elif type_toit == 1:    # panneaux / ventilateurs
        for gx in range(x + 22, x + w - 40, 38):
            for gy in range(y + 22, y + h - 40, 38):
                DRAW.rect(s, melange(base, (70, 90, 130), 0.30), (gx, gy, 28, 28))
                DRAW.rect(s, melange(base, couleur, 0.35), (gx, gy, 28, 28), 1)
                DRAW.circle(s, melange(base, couleur, 0.40), (gx + 14, gy + 14), 8, 1)
    elif type_toit == 2:    # bandeau néon + antennes
        DRAW.line(s, melange(base, couleur, 0.30), (x + 16, cy_), (x + w - 16, cy_), 7)
        DRAW.line(s, couleur, (x + 16, cy_), (x + w - 16, cy_), 2)
        for ax in (x + w // 4, x + 3 * w // 4):
            DRAW.circle(s, melange(couleur, BLANC_NEON, 0.5), (ax, y + h // 4), 3)
            DRAW.circle(s, melange(base, couleur, 0.5), (ax, y + h // 4), 9, 1)
    else:                   # noyau énergétique
        for k in range(4):
            c_k = melange(base, couleur, 0.15 + 0.12 * k)
            m = 20 + k * 16
            DRAW.rect(s, c_k, (x + m, y + m, w - 2 * m, h - 2 * m), 2)
        DRAW.rect(s, melange(base, couleur, 0.6), (cx_ - 8, cy_ - 8, 16, 16))
    for _ in range(alea.randint(2, 4)):
        bw, bh = alea.randint(12, 22), alea.randint(10, 18)
        bx = alea.randint(x + 14, max(x + 15, x + w - 14 - bw))
        by = alea.randint(y + 14, max(y + 15, y + h - 14 - bh))
        DRAW.rect(s, melange(base, (80, 95, 130), 0.28), (bx, by, bw, bh))
        DRAW.rect(s, melange(base, (80, 95, 130), 0.55), (bx, by, bw, bh), 1)
    for px_, py_ in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        DRAW.circle(s, melange(couleur, BLANC_NEON, 0.4), (px_, py_), 3)


def construire_tuile_ville():
    T, L = TUILE_VILLE, LARGEUR_ROUTE
    alea = random.Random(21)
    s = pygame.Surface((T, T))
    s.fill((5, 5, 13))
    route = (3, 3, 9)
    DRAW.rect(s, route, (0, 0, T, L))
    DRAW.rect(s, route, (0, 0, L, T))
    c = L // 2
    for d in range(0, T, 30):
        DRAW.line(s, (62, 54, 12), (d, c), (d + 15, c), 2)
        DRAW.line(s, (62, 54, 12), (c, d), (c, d + 15), 2)
    bord = melange((5, 5, 13), BLEU_CYBER, 0.30)
    for d in (3, L - 4):
        DRAW.line(s, bord, (0, d), (T, d), 1)
        DRAW.line(s, bord, (d, 0), (d, T), 1)
    for i in range(5):                                   # passages piétons
        DRAW.rect(s, (34, 34, 52), (L + 8 + i * 8, 7, 4, L - 14))
        DRAW.rect(s, (34, 34, 52), (7, L + 8 + i * 8, L - 14, 4))
    palette = [BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER]
    ruelle = 16
    cote = (T - L - ruelle) // 2
    for i in range(2):
        for j in range(2):
            marge = alea.randint(7, 12)
            x0 = L + i * (cote + ruelle) + marge
            y0 = L + j * (cote + ruelle) + marge
            dessiner_toit(s, (x0, y0, cote - 2 * marge, cote - 2 * marge), palette[(i * 2 + j + alea.randint(0, 2)) % 3], alea)
    return s.convert()


def dessiner_fond_ville(ox, oy, t_ms, rect_cache=None):
    global _tuile_ville
    if _tuile_ville is None:
        _tuile_ville = construire_tuile_ville()
    T = TUILE_VILLE
    c = LARGEUR_ROUTE // 2
    brut_x, brut_y = int(ox * 0.45), int(oy * 0.45)      # la ville bouge moins vite que le labyrinthe : effet de profondeur
    depart_x, depart_y = brut_x % T - T, brut_y % T - T
    tuile = obtenir_tuile_ville_floue() if PARAMS["dof"] else _tuile_ville
    avec_trafic = QUALITE["niveau"] >= 1 and bool(PARAMS["ville_anim"])
    couleurs_trafic = (ROSE_SYNTH, BLEU_CYBER, JAUNE_CYBER)
    x = depart_x
    while x < LARGEUR:
        y = depart_y
        while y < HAUTEUR:
            if rect_cache is not None and x >= rect_cache[0] and y >= rect_cache[1] \
                    and x + T <= rect_cache[0] + rect_cache[2] and y + T <= rect_cache[1] + rect_cache[3]:
                y += T          # tuile entièrement sous le labyrinthe : inutile de la dessiner
                continue
            ecran.blit(tuile, (x, y))
            if avec_trafic:
                wi, wj = (x - brut_x) // T, (y - brut_y) // T
                h = ((wi * 73856093) ^ (wj * 19349663)) & 0xFFFF
                if h % 3:
                    sens = 1 if h & 4 else -1
                    avance = int((t_ms * (0.16 + (h % 5) * 0.03) + h) % T)
                    tete = x + avance if sens > 0 else x + T - avance
                    ligne_y = y + c + 7 * sens
                    col = couleurs_trafic[h % 3]
                    DRAW.line(ecran, eclaircir(col, 0.35), (tete - sens * 46, ligne_y), (tete, ligne_y), 5)
                    DRAW.line(ecran, eclaircir(col, 1.0), (tete - sens * 30, ligne_y), (tete, ligne_y), 2)
                if (h >> 3) % 3:
                    sens = 1 if h & 8 else -1
                    avance = int((t_ms * (0.14 + (h % 4) * 0.03) + h * 3) % T)
                    tete = y + avance if sens > 0 else y + T - avance
                    ligne_x = x + c + 7 * sens
                    col = couleurs_trafic[(h >> 2) % 3]
                    DRAW.line(ecran, eclaircir(col, 0.35), (ligne_x, tete - sens * 46), (ligne_x, tete), 5)
                    DRAW.line(ecran, eclaircir(col, 1.0), (ligne_x, tete - sens * 30), (ligne_x, tete), 2)
            y += T
        x += T


def _anneau(x, y, w, h, ep, couleur):
    """Cadre d'épaisseur ep AUTOUR du rectangle (x, y, w, h), dessiné uniquement dans la zone visible."""
    X0, Y0, X1, Y1 = x - ep, y - ep, x + w + ep, y + h + ep
    for bx0, by0, bx1, by1 in ((X0, Y0, X1, Y0 + ep), (X0, Y1 - ep, X1, Y1),
                                (X0, Y0 + ep, X0 + ep, Y1 - ep), (X1 - ep, Y0 + ep, X1, Y1 - ep)):
        bx0, by0, bx1, by1 = max(bx0, 0), max(by0, 0), min(bx1, LARGEUR), min(by1, HAUTEUR)
        if bx1 > bx0 and by1 > by0:
            DRAW.rect(ecran, couleur, (bx0, by0, bx1 - bx0, by1 - by0))


def dessiner_cadre_carte(ox, oy, phase):
    """Phase 0 : ombre sombre autour du labyrinthe (avant). Phase 1 : liseré néon (après les murs)."""
    w, h = len(CARTE[0]) * TAILLE_CASE, len(CARTE) * TAILLE_CASE
    if phase == 0:
        _anneau(ox, oy, w, h, 22, (2, 2, 8))
    else:
        _anneau(ox, oy, w, h, 6, eclaircir(COULEUR_MUR, 0.22))
        _anneau(ox, oy, w, h, 3, eclaircir(COULEUR_MUR, 0.55))
        _anneau(ox + 1, oy + 1, w - 2, h - 2, 2, melange(COULEUR_MUR, BLANC_NEON, 0.5))


# ==================== TRANSITIONS D'ÉCRAN, ÉCRAN DE CHARGEMENT ET MARQUE ====================
# Durées en secondes (modifie-les à ta guise)
DUREE_CHARGEMENT = 2.0          # texte « Chargement... » pour un changement d'écran
DUREE_CHARGEMENT_RAPIDE = 0.9   # pour REJOUER / SUIVANT (pour ne pas trop attendre à chaque essai)
DUREE_COUVRIR = 0.35            # le rideau néon se ferme
DUREE_REVELER = 0.45            # le rideau néon s'ouvre sur le nouvel écran

TRANS = {"actif": False, "phase": 0, "t0": 0, "duree": 2000.0, "cible": None}
AIDE = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0}   # défilement vertical du guide


def lancer_transition(cible, duree=None):
    """cible = ('etat', ETAT_X) | ('commencer',) | ('niveau', idx) | ('quitter_partie',) | ('rejouer',) | ('suivant',)"""
    if TRANS["actif"]:
        return
    TRANS["actif"] = True
    TRANS["phase"] = 0
    TRANS["t0"] = pygame.time.get_ticks()
    TRANS["duree"] = (DUREE_CHARGEMENT if duree is None else duree) * 1000.0
    TRANS["cible"] = cible


def dessiner_rideau(w):
    """Deux panneaux sombres bordés de néon qui se ferment (ou s'ouvrent) depuis les côtés."""
    if w <= 0:
        return
    fond = (4, 5, 14)
    DRAW.rect(ecran, fond, (0, 0, w, HAUTEUR))
    DRAW.rect(ecran, fond, (LARGEUR - w, 0, w, HAUTEUR))
    for y in range(0, HAUTEUR, 48):
        DRAW.line(ecran, (10, 16, 34), (0, y), (w, y), 1)
        DRAW.line(ecran, (10, 16, 34), (LARGEUR - w, y), (LARGEUR, y), 1)
    for i in range(8):
        c = eclaircir(BLEU_CYBER, (1 - i / 8.0) ** 2)
        DRAW.line(ecran, c, (w + i, 0), (w + i, HAUTEUR))
        DRAW.line(ecran, c, (LARGEUR - w - i - 1, 0), (LARGEUR - w - i - 1, HAUTEUR))
    bord = melange(BLEU_CYBER, BLANC_NEON, 0.6)
    DRAW.line(ecran, bord, (w, 0), (w, HAUTEUR), 3)
    DRAW.line(ecran, bord, (LARGEUR - w - 1, 0), (LARGEUR - w - 1, HAUTEUR), 3)


def dessiner_chargement(avancement):
    ecran.fill((4, 5, 14))
    t = pygame.time.get_ticks()
    dessiner_halo(LARGEUR // 2, HAUTEUR // 2 - 40, 200, (60, 20, 110), 0.55)
    dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, LARGEUR // 2, HAUTEUR // 2 - 90)
    s2 = rendu_texte(police_petite, "Développé par FlexPlay", True, ROSE_SYNTH)
    ecran.blit(s2, (LARGEUR // 2 - s2.get_width() // 2, HAUTEUR // 2 + 5))

    aff = min(1.0, max(0.0, avancement)) ** 0.85
    nb_points = 1 + (t // 350) % 3
    ref = rendu_texte(police_jeu, "Chargement...", True, BLANC_NEON)
    txt = rendu_texte(police_jeu, "Chargement" + "." * nb_points, True, BLANC_NEON)
    ecran.blit(txt, (LARGEUR // 2 - ref.get_width() // 2, HAUTEUR - 112))

    bw, bh = min(460, LARGEUR - 120), 12
    bx, by = LARGEUR // 2 - bw // 2, HAUTEUR - 64
    DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, bh), border_radius=6)
    rempli = int(bw * aff)
    if rempli > 4:
        DRAW.rect(ecran, BLEU_CYBER, (bx, by, rempli, bh), border_radius=min(6, rempli // 2))
        DRAW.rect(ecran, (170, 235, 255), (bx + 2, by + 2, max(2, rempli - 4), 3), border_radius=1)
        dessiner_halo(bx + rempli, by + bh // 2, 34, BLEU_CYBER, 0.8)
    DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.55), (bx, by, bw, bh), 2, border_radius=6)
    pct = rendu_texte(police_petite, f"{int(aff * 100)}%", True, BLEU_CYBER)
    ecran.blit(pct, (LARGEUR // 2 - pct.get_width() // 2, by + 18))
    cr = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
    ecran.blit(cr, (LARGEUR - cr.get_width() - 24, HAUTEUR - 30))


def lisser(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def dessiner_transition():
    t = pygame.time.get_ticks() - TRANS["t0"]
    phase = TRANS["phase"]
    demi = LARGEUR // 2 + 2
    if phase == 0:
        dessiner_rideau(int(demi * lisser(t / (DUREE_COUVRIR * 1000.0))))
    elif phase == 1:
        dessiner_chargement(t / TRANS["duree"])
    else:
        dessiner_rideau(int(demi * (1.0 - lisser(t / (DUREE_REVELER * 1000.0)))))


def dessiner_marque(y_haut):
    """Signature du créateur (écrans hors jeu)."""
    l1 = rendu_texte(police_jeu, "FLEX CYBERPUNK", True, BLEU_CYBER)
    l2 = rendu_texte(police_petite, "Développé par FlexPlay", True, BLANC_NEON)
    l3 = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(320, 84, (5, 6, 16, 150)), (cx - 160, y_haut - 6))
    ecran.blit(l1, (cx - l1.get_width() // 2, y_haut))
    ecran.blit(l2, (cx - l2.get_width() // 2, y_haut + 30))
    ecran.blit(l3, (cx - l3.get_width() // 2, y_haut + 50))


_tuile_ville_floue = None


def _lisser(surf, taille):
    try:
        return pygame.transform.smoothscale(surf, taille)
    except Exception:
        return pygame.transform.scale(surf, taille)


def obtenir_tuile_ville_floue():
    """Version floutée et assombrie de la ville : le décor paraît lointain, le labyrinthe reste net (profondeur de champ)."""
    global _tuile_ville_floue, _tuile_ville
    if _tuile_ville_floue is None:
        if _tuile_ville is None:
            _tuile_ville = construire_tuile_ville()
        T = TUILE_VILLE
        pt = max(8, T // 5)
        petite = _lisser(_tuile_ville, (pt, pt))
        mosaique = pygame.Surface((pt * 3, pt * 3))
        for i in range(3):
            for j in range(3):
                mosaique.blit(petite, (i * pt, j * pt))
        flou = _lisser(mosaique, (T * 3, T * 3))
        res = pygame.Surface((T, T))
        res.blit(flou, (0, 0), (T, T, T, T))
        res.fill((165, 165, 185), special_flags=pygame.BLEND_RGB_MULT)
        _tuile_ville_floue = res.convert()
    return _tuile_ville_floue


_cache_ombres = {}


def dessiner_ombre(cx, cy, w, h):
    """Ombre douce (ellipse dégradée pré-calculée) sous un personnage."""
    cle = (w, h)
    s = _cache_ombres.get(cle)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(8):
            r = i * 0.09
            DRAW.ellipse(s, (0, 0, 0, 16 + i * 11),
                         (int(w * r / 2), int(h * r / 2), max(2, int(w * (1 - r))), max(2, int(h * (1 - r)))))
        s = s.convert_alpha()
        _cache_ombres[cle] = s
    ecran.blit(s, (int(cx - w // 2), int(cy - h // 2)))


# 4. GÉNÉRATION PROCÉDURALE DE LABYRINTHE (mode infini)
def generer_labyrinthe(largeur_cellules, hauteur_cellules):
    lignes = hauteur_cellules * 2 + 1
    colonnes = largeur_cellules * 2 + 1
    grille = [[1] * colonnes for _ in range(lignes)]

    def voisins_cellule(r, c):
        candidats = []
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nr, nc = r + dr, c + dc
            if 0 < nr < lignes - 1 and 0 < nc < colonnes - 1:
                candidats.append((nr, nc))
        random.shuffle(candidats)
        return candidats

    grille[1][1] = 0
    pile = [(1, 1)]
    while pile:
        r, c = pile[-1]
        suivants = [(nr, nc) for nr, nc in voisins_cellule(r, c) if grille[nr][nc] == 1]
        if suivants:
            nr, nc = suivants[0]
            grille[(r + nr) // 2][(c + nc) // 2] = 0
            grille[nr][nc] = 0
            pile.append((nr, nc))
        else:
            pile.pop()
    return grille


def cellule_la_plus_eloignee(grille, depart):
    lignes, colonnes = len(grille), len(grille[0])
    distances = {depart: 0}
    file = [depart]
    while file:
        r, c = file.pop(0)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < lignes and 0 <= nc < colonnes and grille[nr][nc] == 0 and (nr, nc) not in distances:
                distances[(nr, nc)] = distances[(r, c)] + 1
                file.append((nr, nc))
    plus_loin = max(distances, key=distances.get)
    return plus_loin, distances


def trouver_position_core(carte):
    for r, ligne in enumerate(carte):
        for c, val in enumerate(ligne):
            if val == 2:
                return r, c
    return 1, 1


def calcul_delais_spawn(niveau):
    delai_min = max(15, 90 - niveau * 3)
    delai_max = max(30, 180 - niveau * 5)
    return delai_min, delai_max


def position_spawn_ennemi(carte):
    colonnes, lignes = len(carte[0]), len(carte)
    largeur_px, hauteur_px = colonnes * TAILLE_CASE, lignes * TAILLE_CASE
    x = random.randint(int(largeur_px * 0.3), max(int(largeur_px * 0.3) + 50, largeur_px - 100))
    y = random.randint(100, max(150, hauteur_px - 100))
    return x, y


DUREE_MISSION_FRAMES = 130 * 60  
NIVEAU_APPARITION_POTIONS = 8  
BONUS_POTION_FRAMES = 5 * 60
TEMPS_MAX_FRAMES = 99 * 60


def position_spawn_potion(carte):
    cellules_libres = [(r, c) for r, ligne in enumerate(carte) for c, val in enumerate(ligne) if val == 0]
    r, c = random.choice(cellules_libres)
    return c * TAILLE_CASE + TAILLE_CASE / 2, r * TAILLE_CASE + TAILLE_CASE / 2


CHEMIN_PROGRESSION = chemin_donnees("progression_flex.json")


def charger_progression():
    d, statut = lire_json_signe(CHEMIN_PROGRESSION)
    if statut == "altere":
        signaler_sauvegarde_alteree()
        return 0
    if d is None:
        return 0
    try:
        return max(0, int(d.get("niveau", 0)))
    except Exception as e:
        print(f"⚠️ Progression illisible : {e}")
        return 0


def sauvegarder_progression(niveau):
    try:
        ecrire_json_signe(CHEMIN_PROGRESSION, {"niveau": niveau})
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder la progression : {e}")


def generer_niveau(niveau):
    largeur_cellules = min(8 + niveau, 34)
    hauteur_cellules = min(6 + niveau, 22)
    grille = generer_labyrinthe(largeur_cellules, hauteur_cellules)

    depart = (1, 1)
    sortie, distances = cellule_la_plus_eloignee(grille, depart)

    cellules_triees = sorted(distances.items(), key=lambda x: x[1])
    idx_core = max(1, int(len(cellules_triees) * 0.55))
    core = cellules_triees[idx_core][0]

    grille[core[0]][core[1]] = 2
    grille[sortie[0]][sortie[1]] = 3

    est_mission_boss = (niveau + 1) % 5 == 0
    nb_ennemis = 0 if est_mission_boss else min(3 + niveau * 2, 70)
    vitesse = min(2.2 + niveau * 0.10, 7.0)

    cycle = niveau // len(NOMS)
    suffixe = f" [CYCLE {cycle + 1}]" if cycle > 0 else ""
    nom_base = f"MISSION {niveau + 1:02d} : {NOMS[niveau % len(NOMS)]}{suffixe}"
    nom = f"⚠ BOSS ⚠ {nom_base}" if est_mission_boss else nom_base
    couleur = COULEURS[niveau % len(COULEURS)]

    return {
        "carte": grille,
        "couleur_mur": couleur,
        "nom": nom,
        "nb_ennemis": nb_ennemis,
        "vitesse_ennemis": vitesse,
        "depart": depart,
        "est_boss": est_mission_boss,
        "core_cell": core,
        "sortie_cell": sortie
    }


def initialiser_etat_boss(niveau_data, niveau):
    if not niveau_data["est_boss"]:
        return False, False, 0, 0, 0, 0, [], 0
    cycle_boss = (niveau + 1) // 5
    vie_max = min(35 + cycle_boss * 12, 260)
    ligne_core, colonne_core = trouver_position_core(niveau_data["carte"])
    bx = colonne_core * TAILLE_CASE + TAILLE_CASE / 2
    by = ligne_core * TAILLE_CASE + TAILLE_CASE / 2
    return True, False, bx, by, vie_max, vie_max, [], random.randint(60, 90)


def duree_mission_boss(cycle_boss):
    if cycle_boss <= 3:
        return 150 * 60
    elif cycle_boss <= 7:
        return 200 * 60
    else:
        return 300 * 60


niveau_actuel = charger_progression()
niveau_max_atteint = niveau_actuel
niveau_data = generer_niveau(niveau_actuel)
CARTE = niveau_data["carte"]
COULEUR_MUR = niveau_data["couleur_mur"]
liste_ennemis = []
ennemis_restants_a_spawner = niveau_data["nb_ennemis"]
vitesse_ennemis_niveau = niveau_data["vitesse_ennemis"]
delai_min_init, delai_max_init = calcul_delais_spawn(niveau_actuel)
minuteur_spawn = random.randint(delai_min_init, delai_max_init)

boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss = initialiser_etat_boss(niveau_data, niveau_actuel)
boss_angle_precedent = None
boss_surface_cache = None

# POSITIONS DU CORE ET DE LA SORTIE (pour le radar)
pos_core_x = niveau_data["core_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
pos_core_y = niveau_data["core_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2
pos_sortie_x = niveau_data["sortie_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
pos_sortie_y = niveau_data["sortie_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2

# PERSO & PROSPECTIVES
joueur_x = niveau_data["depart"][1] * TAILLE_CASE + TAILLE_CASE / 2
joueur_y = niveau_data["depart"][0] * TAILLE_CASE + TAILLE_CASE / 2
joueur_vitesse = 6.5
angle_visée_x, angle_visée_y = 1.0, 0.0
balles = []

jauge_hack = 0.0
hack_reussi = False
partie_gagnee = False
partie_perdue = False
message_defaite = "SYSTÈME CORROMPU"
if niveau_data["est_boss"]:
    temps_restant_frames = duree_mission_boss((niveau_actuel + 1) // 5)
else:
    temps_restant_frames = DUREE_MISSION_FRAMES
plafond_temps_frames = int(temps_restant_frames * 1.65)
liste_potions = []
minuteur_potion = random.randint(300, 600)
ETAT_MENU, ETAT_JEU, ETAT_AIDE, ETAT_PROFIL, ETAT_INFOS, ETAT_NIVEAUX = 0, 1, 2, 3, 4, 5
ETAT_PARAMS = 6
ETAT_BOUTIQUE = 7
ETAT_EDITEUR = 8
etat_actuel = ETAT_MENU
en_pause = False

# TOUCH UI
JOY_CENTRE_X, JOY_CENTRE_Y = 180, HAUTEUR - 180
JOY_RAYON_SOCLE, JOY_RAYON_MANETTE = 85, 35
manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y
joystick_actif = False
id_touch_joystick = None

# TIR MAINTENU (garder le doigt/clic appuyé pour tirer en continu)
tir_maintenu = False
id_touch_tir = None
CADENCE_TIR_FRAMES = 8  # nombre de frames entre 2 tirs pendant que le bouton est maintenu
minuteur_cadence_tir = 0

BTN_TIR_X, BTN_TIR_Y = LARGEUR - 180, HAUTEUR - 180
BTN_TIR_RAYON = 65
rect_tir_tactile = pygame.Rect(BTN_TIR_X - BTN_TIR_RAYON, BTN_TIR_Y - BTN_TIR_RAYON, BTN_TIR_RAYON * 2, BTN_TIR_RAYON * 2)

# RADAR (aide à la navigation : indique la direction du core et de la sortie)
RADAR_CENTRE_X, RADAR_CENTRE_Y = LARGEUR - 150, 150
RADAR_RAYON = 85
RADAR_PORTEE_MONDE = 900          # portée d'affichage des ennemis/potions sur le radar
RADAR_PORTEE_OBJECTIFS = 3200     # portée virtuelle utilisée pour situer le core/la sortie (toujours affichés, même très loin)

# BOUTON PAUSE (juste au-dessus du radar)
BTN_PAUSE_X, BTN_PAUSE_Y = LARGEUR - 150, 25
BTN_PAUSE_RAYON = 30
rect_bouton_pause = pygame.Rect(BTN_PAUSE_X - BTN_PAUSE_RAYON, BTN_PAUSE_Y - BTN_PAUSE_RAYON, BTN_PAUSE_RAYON * 2, BTN_PAUSE_RAYON * 2)

# ÉCRAN DE SÉLECTION DES MISSIONS (chaîne de niveaux)
NIVEAU_NODE_ESPACEMENT = 160
NIVEAU_NODE_RAYON = 42
NIVEAU_MARGE_GAUCHE = 100
defilement_niveaux = 0.0
glissement_niveaux_actif = False
type_glissement_niveaux = None
dernier_x_glissement_niveaux = 0


def check_collision_murs(x, y):
    gauche, droite = x - TAILLE_PERSO // 2, x + TAILLE_PERSO // 2
    haut, bas = y - TAILLE_PERSO // 2, y + TAILLE_PERSO // 2
    for cx, cy in [(gauche, haut), (droite, haut), (gauche, bas), (droite, bas)]:
        case_x, case_y = int(cx // TAILLE_CASE), int(cy // TAILLE_CASE)
        if not (0 <= case_x < len(CARTE[0]) and 0 <= case_y < len(CARTE)):
            return True
        if CARTE[case_y][case_x] == 1:
            return True
        if CARTE[case_y][case_x] == 3 and not hack_reussi:
            return True
    return False


def reinitialiser_partie(passer_au_suivant=False, niveau_cible=None):
    global joueur_x, joueur_y, jauge_hack, hack_reussi, partie_gagnee, partie_perdue, niveau_actuel, niveau_max_atteint
    global CARTE, COULEUR_MUR, etat_actuel, liste_ennemis, balles, img_joueur_actuel, niveau_data
    global ennemis_restants_a_spawner, vitesse_ennemis_niveau, minuteur_spawn
    global temps_restant_frames, liste_potions, minuteur_potion, message_defaite, plafond_temps_frames
    global boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss
    global boss_angle_precedent, boss_surface_cache
    global pos_core_x, pos_core_y, pos_sortie_x, pos_sortie_y

    if niveau_cible is not None:
        niveau_actuel = niveau_cible
    elif passer_au_suivant:
        niveau_actuel += 1
        if niveau_actuel > niveau_max_atteint:
            niveau_max_atteint = niveau_actuel
            sauvegarder_progression(niveau_max_atteint)

    niveau_data = generer_niveau(niveau_actuel)
    CARTE = niveau_data["carte"]
    COULEUR_MUR = niveau_data["couleur_mur"]
    liste_ennemis = []
    ennemis_restants_a_spawner = niveau_data["nb_ennemis"]
    vitesse_ennemis_niveau = niveau_data["vitesse_ennemis"]
    delai_min, delai_max = calcul_delais_spawn(niveau_actuel)
    minuteur_spawn = random.randint(delai_min, delai_max)

    pos_core_x = niveau_data["core_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
    pos_core_y = niveau_data["core_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2
    pos_sortie_x = niveau_data["sortie_cell"][1] * TAILLE_CASE + TAILLE_CASE / 2
    pos_sortie_y = niveau_data["sortie_cell"][0] * TAILLE_CASE + TAILLE_CASE / 2

    boss_actif, boss_vaincu, boss_x, boss_y, boss_vie, boss_vie_max, boules_feu, minuteur_tir_boss = initialiser_etat_boss(niveau_data, niveau_actuel)
    boss_angle_precedent = None
    boss_surface_cache = None

    if niveau_data["est_boss"]:
        temps_restant_frames = duree_mission_boss((niveau_actuel + 1) // 5)
    else:
        temps_restant_frames = DUREE_MISSION_FRAMES
    temps_restant_frames += STATS["chrono"]
    plafond_temps_frames = int(temps_restant_frames * 1.65)
    liste_potions = []
    minuteur_potion = random.randint(300, 600)
    message_defaite = "SYSTÈME CORROMPU"

    joueur_x = niveau_data["depart"][1] * TAILLE_CASE + TAILLE_CASE / 2
    joueur_y = niveau_data["depart"][0] * TAILLE_CASE + TAILLE_CASE / 2
    jauge_hack, hack_reussi, partie_gagnee, partie_perdue = 0.0, False, False, False
    CAM["x"], CAM["y"] = joueur_x, joueur_y
    balles.clear()
    particules_fx.clear()
    ondes_fx.clear()
    ETAT_FX["secousse"] = 0.0
    ETAT_JOUEUR["bouclier"], ETAT_JOUEUR["invuln"] = STATS["bouclier"], 0
    MISSION.update(drones=0, recompense=None, versee=False, duree=max(1, temps_restant_frames))
    if MODE_GRAPHIQUE == "REALISTE":
        img_joueur_actuel = img_joueur_droite
# 5. SYSTÈME DE PROFIL JOUEUR 
CHEMIN_PROFIL = chemin_donnees("profil_flex.json")
NATIONALITES = ["France", "Belgique", "Suisse", "Canada", "Maroc", "Algérie", "Tunisie",
                "Sénégal", "Côte d'Ivoire", "États-Unis", "Royaume-Uni", "Autre"]


def charger_profil():
    if os.path.exists(CHEMIN_PROFIL):
        try:
            with open(CHEMIN_PROFIL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Profil illisible : {e}")
    return {"pseudo": "", "nationalite": "France"}


def sauvegarder_profil(donnees_profil):
    try:
        with open(CHEMIN_PROFIL, "w", encoding="utf-8") as f:
            json.dump(donnees_profil, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder le profil : {e}")


def charger_photo_profil():
    for nom_fichier in ["photo_profil.png", "photo_profil.jpg", "photo_profil.jpeg"]:
        if os.path.exists(nom_fichier):
            try:
                taille = 160
                img = pygame.image.load(nom_fichier).convert_alpha()
                img = pygame.transform.smoothscale(img, (taille, taille))
                masque = pygame.Surface((taille, taille), pygame.SRCALPHA)
                DRAW.circle(masque, (255, 255, 255, 255), (taille // 2, taille // 2), taille // 2)
                img_ronde = pygame.Surface((taille, taille), pygame.SRCALPHA)
                img_ronde.blit(img, (0, 0))
                img_ronde.blit(masque, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                return img_ronde
            except Exception as e:
                print(f"⚠️ Erreur chargement photo : {e}")
    return None


def dessiner_icone_personne(surface, centre_x, centre_y, taille, couleur):
    rayon_tete = int(taille * 0.22)
    DRAW.circle(surface, couleur, (centre_x, int(centre_y - taille * 0.14)), rayon_tete)
    rect_corps = pygame.Rect(0, 0, int(taille * 0.58), int(taille * 0.42))
    rect_corps.centerx = centre_x
    rect_corps.top = int(centre_y - taille * 0.14 + rayon_tete * 0.55)
    DRAW.ellipse(surface, couleur, rect_corps)


profil = charger_profil()
photo_profil_surface = charger_photo_profil()
index_nationalite = NATIONALITES.index(profil.get("nationalite", "France")) if profil.get("nationalite") in NATIONALITES else 0
saisie_pseudo_active = False


# 6. EFFETS VISUELS DU MENU (ville cyberpunk de nuit, grille néon, pluie)
HORIZON_Y = int(HAUTEUR * 0.60)
_fond_menu_surface = None
grille_scroll_offset = 0.0
pluie_menu = [[random.uniform(0, LARGEUR + 200), random.uniform(0, HAUTEUR), random.uniform(16, 28), random.randint(14, 30)]
              for _ in range(60)]
particules_menu = [[random.uniform(0, LARGEUR), random.uniform(0, HAUTEUR), random.uniform(0.3, 1.2), random.randint(1, 3)]
                   for _ in range(45)]


def couleur_ciel(y):
    a = (y / float(max(1, HORIZON_Y))) ** 2.2
    return melange((3, 2, 14), (70, 8, 95), a)


def construire_fond_menu():
    """Décor statique pré-rendu une seule fois : ciel, soleil néon, gratte-ciels, enseignes."""
    surf = pygame.Surface((LARGEUR, HAUTEUR))
    alea = random.Random(7)
    for y in range(HORIZON_Y):
        DRAW.line(surf, couleur_ciel(y), (0, y), (LARGEUR, y))

    # soleil néon rayé
    cx_s, rayon_s = int(LARGEUR * 0.74), int(HAUTEUR * 0.20)
    for r in range(rayon_s, 0, -2):
        a = 1 - r / float(rayon_s)
        DRAW.circle(surf, melange((200, 25, 120), (255, 150, 60), a), (cx_s, HORIZON_Y - 5), r)
    for k in range(7):
        y_bande = HORIZON_Y - 10 - k * int(rayon_s / 7.5)
        DRAW.rect(surf, couleur_ciel(y_bande), (cx_s - rayon_s, y_bande, rayon_s * 2, max(2, 9 - k)))

    # sol
    for y in range(HORIZON_Y, HAUTEUR):
        a = min(1.0, (y - HORIZON_Y) / float(max(1, HAUTEUR - HORIZON_Y)) * 1.6)
        DRAW.line(surf, melange((30, 8, 52), (2, 3, 10), a), (0, y), (LARGEUR, y))

    # skyline : 2 couches (lointaine puis proche)
    for couche, (couleur_bat, hmax, lum) in enumerate([((16, 7, 34), 0.30, 0.45), ((7, 5, 18), 0.42, 1.0)]):
        x = -20
        while x < LARGEUR:
            w = alea.randint(50, 130)
            h = int(HAUTEUR * alea.uniform(0.10, hmax))
            top = HORIZON_Y - h
            DRAW.rect(surf, couleur_bat, (x, top, w, h + 4))
            col_ar = alea.choice([BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER])
            DRAW.line(surf, eclaircir(col_ar, 0.55 * lum), (x, top), (x + w, top), 2)
            for wy in range(top + 12, HORIZON_Y - 8, 20):
                for wx in range(x + 8, x + w - 10, 14):
                    if alea.random() < 0.22:
                        col_f = alea.choice([JAUNE_CYBER, BLEU_CYBER, ROSE_SYNTH, BLANC_NEON])
                        DRAW.rect(surf, eclaircir(col_f, 0.75 * lum), (wx, wy, 6, 9))
            if couche == 1 and alea.random() < 0.28 and h > 90:
                col_e = alea.choice([ROSE_SYNTH, BLEU_CYBER, VERT_FLUO])
                ex_, ey_ = x + w - 14, top + 20
                hh = alea.randint(40, 90)
                DRAW.rect(surf, col_e, (ex_, ey_, 5, hh))
                surf.blit(obtenir_halo(44, col_e, 0.7), (ex_ + 2 - 44, ey_ + hh // 2 - 44),
                          special_flags=pygame.BLEND_RGB_ADD)
            x += w + alea.randint(-10, 12)

    # lueur de l'horizon
    lueur = pygame.Surface((LARGEUR, 90))
    for i in range(90):
        a = (1 - abs(i - 45) / 45.0) ** 3
        DRAW.line(lueur, (int(150 * a), int(40 * a), int(200 * a)), (0, i), (LARGEUR, i))
    surf.blit(lueur, (0, HORIZON_Y - 45), special_flags=pygame.BLEND_RGB_ADD)
    return surf.convert()


def dessiner_fond_menu():
    global _fond_menu_surface, grille_scroll_offset
    if _fond_menu_surface is None:
        _fond_menu_surface = construire_fond_menu()
    ecran.blit(_fond_menu_surface, (0, 0))

    # grille en perspective qui défile vers nous
    cx = LARGEUR // 2
    prof = HAUTEUR - HORIZON_Y
    grille_scroll_offset = (grille_scroll_offset + 0.010) % 1.0
    for k in range(-18, 19, 1 if QUALITE["niveau"] >= 1 else 2):
        DRAW.line(ecran, (110, 20, 150), (cx + k * 12, HORIZON_Y), (cx + k * (LARGEUR // 12), HAUTEUR), 1)
    nb_lignes = 14
    for i in range(nb_lignes):
        z = (i + grille_scroll_offset) / float(nb_lignes)
        y = HORIZON_Y + int(prof * (z ** 2.2))
        DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.15 + 0.6 * z), (0, y), (LARGEUR, y), 1 if z < 0.6 else 2)

    # pluie de néon
    for g in pluie_menu[:(0, 28, 60)[QUALITE["niveau"]]]:
        g[1] += g[2]
        g[0] -= g[2] * 0.15
        if g[1] > HAUTEUR + 30 or g[0] < -60:
            g[1] = random.uniform(-60, -10)
            g[0] = random.uniform(0, LARGEUR + 200)
        DRAW.line(ecran, (70, 120, 175), (int(g[0]), int(g[1])), (int(g[0] + g[3] * 0.15), int(g[1] - g[3])), 1)

    # lucioles lumineuses
    for i, p in enumerate(particules_menu):
        couleur_p = BLEU_CYBER if i % 2 == 0 else ROSE_SYNTH
        p[1] -= p[2]
        if p[1] < -10:
            p[1] = HAUTEUR + 10
            p[0] = random.uniform(0, LARGEUR)
        DRAW.circle(ecran, couleur_p, (int(p[0]), int(p[1])), p[3])
        if p[3] == 3:
            dessiner_halo(p[0], p[1], 16, couleur_p, 0.8, 2)


def dessiner_panneau_neon(x, largeur, couleur, avec_fond=True, alpha=205):
    if avec_fond:
        dessiner_fond_menu()
    ecran.blit(obtenir_voile(largeur, HAUTEUR, (6, 8, 18, alpha)), (x, 0))
    for i in range(10):
        c = eclaircir(couleur, (1 - i / 10.0) ** 2 * (1.0 if i else 1.2))
        DRAW.line(ecran, c, (x - i, 0), (x - i, HAUTEUR))
        DRAW.line(ecran, c, (x + largeur + i, 0), (x + largeur + i, HAUTEUR))


def dessiner_titre_glitch(texte, police, x_centre, y):
    dessiner_halo(x_centre - 90, y + police.get_height() // 2, 150, (0, 90, 150), 0.7, 2)
    dessiner_halo(x_centre + 90, y + police.get_height() // 2, 150, (150, 20, 120), 0.6, 2)
    decalage_glitch = random.randint(-4, 4) if random.random() < 0.06 else 0
    surf_rouge = rendu_texte(police, texte, True, (255, 50, 60))
    surf_bleu = rendu_texte(police, texte, True, (50, 170, 255))
    surf_principal = rendu_texte(police, texte, True, BLANC_NEON)
    largeur_texte = surf_principal.get_width()
    ecran.blit(surf_rouge, (x_centre - largeur_texte // 2 - 3 + decalage_glitch, y))
    ecran.blit(surf_bleu, (x_centre - largeur_texte // 2 + 3 + decalage_glitch, y))
    ecran.blit(surf_principal, (x_centre - largeur_texte // 2 + decalage_glitch, y))


def point_sur_radar(px, py, portee):
    """Convertit une position du monde en un point sur le radar, centré sur le joueur.
    Si le point est hors de portée, il est ramené (clampé) sur le bord du radar
    pour indiquer uniquement la direction."""
    dx, dy = px - joueur_x, py - joueur_y
    echelle = RADAR_RAYON / portee
    rx, ry = dx * echelle, dy * echelle
    dist_radar = math.hypot(rx, ry)
    limite = RADAR_RAYON - 9
    if dist_radar > limite:
        rx, ry = rx / dist_radar * limite, ry / dist_radar * limite
    return int(RADAR_CENTRE_X + rx), int(RADAR_CENTRE_Y + ry)


def dessiner_radar():
    # Fond et cadre du radar
    DRAW.circle(ecran, (6, 12, 20), (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON)
    dessiner_halo(RADAR_CENTRE_X, RADAR_CENTRE_Y, RADAR_RAYON + 30, BLEU_CYBER, 0.35, 2)
    nb_bal = (0, 6, 12)[QUALITE["niveau"]]
    ang_balayage = pygame.time.get_ticks() / 700.0
    if nb_bal == 0:
        DRAW.line(ecran, (0, 150, 110), (RADAR_CENTRE_X, RADAR_CENTRE_Y),
                         (int(RADAR_CENTRE_X + math.cos(ang_balayage) * (RADAR_RAYON - 4)),
                          int(RADAR_CENTRE_Y + math.sin(ang_balayage) * (RADAR_RAYON - 4))), 2)
    for k_bal in range(nb_bal):
        a_bal = ang_balayage - k_bal * (0.72 / nb_bal)
        f_bal = (1 - k_bal / float(nb_bal)) ** 1.5
        DRAW.line(ecran, (0, int(150 * f_bal), int(110 * f_bal)), (RADAR_CENTRE_X, RADAR_CENTRE_Y),
                         (int(RADAR_CENTRE_X + math.cos(a_bal) * (RADAR_RAYON - 4)),
                          int(RADAR_CENTRE_Y + math.sin(a_bal) * (RADAR_RAYON - 4))), 4)
    DRAW.circle(ecran, (0, 60, 80), (RADAR_CENTRE_X, RADAR_CENTRE_Y), int(RADAR_RAYON * 0.5), 1)
    DRAW.line(ecran, (0, 55, 75), (RADAR_CENTRE_X - RADAR_RAYON, RADAR_CENTRE_Y), (RADAR_CENTRE_X + RADAR_RAYON, RADAR_CENTRE_Y), 1)
    DRAW.line(ecran, (0, 55, 75), (RADAR_CENTRE_X, RADAR_CENTRE_Y - RADAR_RAYON), (RADAR_CENTRE_X, RADAR_CENTRE_Y + RADAR_RAYON), 1)
    DRAW.circle(ecran, BLEU_CYBER, (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON, 3)

    # Le CORE (violet, devient vert une fois hacké, rouge si le boss le garde)
    if boss_actif and not boss_vaincu:
        couleur_core = ROUGE_ALERTE
    elif hack_reussi:
        couleur_core = VERT_FLUO
    else:
        couleur_core = VIOLET_CYBER
    cxr, cyr = point_sur_radar(pos_core_x, pos_core_y, RADAR_PORTEE_OBJECTIFS)
    DRAW.circle(ecran, couleur_core, (cxr, cyr), 7)
    DRAW.circle(ecran, BLANC_NEON, (cxr, cyr), 7, 1)

    # La SORTIE (verte quand elle devient utile, grise sinon)
    couleur_sortie = VERT_FLUO if hack_reussi else (70, 90, 80)
    sxr, syr = point_sur_radar(pos_sortie_x, pos_sortie_y, RADAR_PORTEE_OBJECTIFS)
    DRAW.circle(ecran, couleur_sortie, (sxr, syr), 7)
    DRAW.circle(ecran, BLANC_NEON, (sxr, syr), 7, 1)

    # Boss (repérable même s'il est mobile)
    if boss_actif and not boss_vaincu:
        bxr, byr = point_sur_radar(boss_x, boss_y, RADAR_PORTEE_OBJECTIFS)
        DRAW.circle(ecran, VIOLET_CYBER, (bxr, byr), 5)

    # Ennemis à portée du radar
    for ex in liste_ennemis:
        if math.hypot(ex[0] - joueur_x, ex[1] - joueur_y) <= RADAR_PORTEE_MONDE:
            exr, eyr = point_sur_radar(ex[0], ex[1], RADAR_PORTEE_MONDE)
            DRAW.circle(ecran, ROUGE_ALERTE, (exr, eyr), 3)

    # Potions à portée du radar
    for potion in liste_potions:
        if math.hypot(potion[0] - joueur_x, potion[1] - joueur_y) <= RADAR_PORTEE_MONDE:
            pxr, pyr = point_sur_radar(potion[0], potion[1], RADAR_PORTEE_MONDE)
            DRAW.circle(ecran, JAUNE_CYBER, (pxr, pyr), 3)

    # Le joueur, toujours au centre
    DRAW.circle(ecran, BLANC_NEON, (RADAR_CENTRE_X, RADAR_CENTRE_Y), 5)
    DRAW.circle(ecran, VERT_FLUO, (RADAR_CENTRE_X, RADAR_CENTRE_Y), 5, 2)

    etiquette = rendu_texte(police_petite, "RADAR", True, BLEU_CYBER)
    ecran.blit(etiquette, (RADAR_CENTRE_X - etiquette.get_width() // 2, RADAR_CENTRE_Y + RADAR_RAYON + 6))


police_bouton = pygame.font.SysFont(None, 40)
police_jeu = pygame.font.SysFont(None, 36)
police_petite = pygame.font.SysFont(None, 26)
police_aide = pygame.font.SysFont(None, 30)
police_victoire = pygame.font.SysFont(None, 90)
police_titre = pygame.font.SysFont(None, 80)
clock = pygame.time.Clock()

rect_bouton_jouer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 60, 300, 55)
rect_bouton_aide = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 20, 300, 55)
rect_bouton_boutique = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 100, 300, 55)
rect_bouton_retour = pygame.Rect(40, 40, 160, 50)   # en haut à gauche : ne cache plus le texte du guide
rect_bouton_rejouer = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR // 2 + 60, 240, 65)
rect_bouton_suivant = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR // 2 + 60, 240, 65)

rect_icone_profil = pygame.Rect(LARGEUR - 110, 30, 70, 70)
rect_icone_infos = pygame.Rect(40, 30, 70, 70)
rect_icone_params = pygame.Rect(130, 30, 70, 70)
rect_recharger_photo = pygame.Rect(LARGEUR // 2 - 140, 280, 280, 45)
rect_champ_pseudo = pygame.Rect(LARGEUR // 2 - 220, 350, 440, 60)
rect_fleche_gauche = pygame.Rect(LARGEUR // 2 - 220, 450, 60, 60)
rect_fleche_droite = pygame.Rect(LARGEUR // 2 + 160, 450, 60, 60)
rect_sauvegarder_profil = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR - 220, 240, 65)
rect_retour_profil = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR - 220, 240, 65)

# Boutons spécifiques
rect_bouton_rejouer_defaite = pygame.Rect(LARGEUR // 2 - 260, HAUTEUR // 2 + 60, 240, 65)
rect_bouton_quitter_defaite = pygame.Rect(LARGEUR // 2 + 20, HAUTEUR // 2 + 60, 240, 65)
rect_retour_infos = pygame.Rect(40, 40, 160, 50) # Nouveau bouton retour pour l'écran Infos
rect_retour_niveaux = pygame.Rect(40, 40, 160, 50)

# Menu PAUSE
rect_pause_continuer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 100, 300, 60)
rect_pause_rejouer = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 - 20, 300, 60)
rect_pause_params = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 60, 300, 60)
rect_pause_quitter = pygame.Rect(LARGEUR // 2 - 150, HAUTEUR // 2 + 140, 300, 60)

# ==================== PARAMÈTRES ====================
CHEMIN_PARAMS = chemin_donnees("parametres_flex.json")
LOGIQUE = {"t": _time.perf_counter(), "acc": 0.0, "k": 1}   # pas de temps réel de la logique
PAUSE_T = {"t": -1000}
SAUT = {"n": 1}                   # on dessine 1 image sur n (la logique du jeu, elle, tourne à chaque tour)
TMR = {"l": 0.0, "r": 0.0, "f": 0.0}   # temps moyens (ms) : logique / dessin / affichage
CTRL = {"k": 1.0, "dz": 10.0}      # sensibilité (multiplicateur du déplacement du doigt) et zone morte (en pixels)
PAR = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0, "x0": 0.0, "y0": 0.0, "moved": False,
       "origine": ETAT_MENU, "zones": [], "bench": [], "redemarrer": False}


def _liste_pct(debut, fin, pas):
    return [f"{p}%" for p in range(debut, fin + 1, pas)]


# ("SECTION", titre)  ou  (clé, libellé, [options], index par défaut)
PARAM_DEFS = [
    ("SECTION", "GRAPHISMES"),
    ("qualite", "Qualité graphique", ["Auto", "Léger", "Équilibré", "Complet"], 0),
    ("resolution", "Résolution (au lancement)", ["Auto", "100%", "75%", "50%"], 0),
    ("saut", "Images dessinées", ["Auto", "Toutes", "1 sur 2", "1 sur 3"], 0),
    ("ombres", "Ombres", ["Non", "Oui"], 1),
    ("dof", "Profondeur de champ", ["Non", "Oui"], 1),
    ("fps", "Afficher les FPS", ["Non", "Oui"], 0),
    ("SECTION", "EFFETS"),
    ("secousse", "Secousse d'écran", ["Non", "Oui"], 1),
    ("particules", "Particules", ["Non", "Oui"], 1),
    ("ville_anim", "Ville animée", ["Non", "Oui"], 1),
    ("SECTION", "COMMANDES"),
    ("sensibilite", "Sensibilité", _liste_pct(50, 150, 10), 5),
    ("zone_morte", "Zone morte", ["0%", "5%", "12%", "20%", "30%"], 2),
    ("ACTION", "Disposition des commandes", "editeur"),
    ("SECTION", "AUDIO"),
    ("vol_musique", "Volume musique", _liste_pct(0, 100, 10), 4),
    ("vol_effets", "Volume effets", _liste_pct(0, 100, 10), 10),
]
PARAM_OPTIONS = {d[0]: d[2] for d in PARAM_DEFS if len(d) == 4}
PARAM_DEFAUT = {d[0]: d[3] for d in PARAM_DEFS if len(d) == 4}
PARAMS = dict(PARAM_DEFAUT)


def dispo_par_defaut():
    """Disposition d'origine : joystick en bas à gauche, bouton TIR en bas à droite (positions en fraction de l'écran)."""
    return {"joy": {"x": 180.0 / LARGEUR, "y": (HAUTEUR - 180.0) / HAUTEUR, "s": 1.0},
            "tir": {"x": (LARGEUR - 180.0) / LARGEUR, "y": (HAUTEUR - 180.0) / HAUTEUR, "s": 1.0}}


DISPO = dispo_par_defaut()
ECHELLE_COMMANDE_MIN, ECHELLE_COMMANDE_MAX = 0.6, 1.8


def charger_parametres():
    if os.path.exists(CHEMIN_PARAMS):
        try:
            with open(CHEMIN_PARAMS, "r", encoding="utf-8") as f:
                donnees = json.load(f)
            for cle, options in PARAM_OPTIONS.items():
                v = donnees.get(cle)
                if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(options):
                    PARAMS[cle] = v
            for nom in ("joy", "tir"):                                   # disposition personnalisée des commandes
                d = (donnees.get("dispo") or {}).get(nom)
                if isinstance(d, dict) and all(isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) for k in ("x", "y", "s")):
                    DISPO[nom] = {"x": min(1.0, max(0.0, float(d["x"]))), "y": min(1.0, max(0.0, float(d["y"]))),
                                  "s": min(ECHELLE_COMMANDE_MAX, max(ECHELLE_COMMANDE_MIN, float(d["s"])))}
        except Exception as e:
            print(f"⚠️ Paramètres illisibles : {e}")


def sauvegarder_parametres():
    try:
        with open(CHEMIN_PARAMS, "w", encoding="utf-8") as f:
            json.dump({**PARAMS, **EXTRA, "dispo": DISPO}, f)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder les paramètres : {e}")


def basculer_pause():
    """Active/désactive la pause (ignore le 2e événement d'un même toucher : doigt + souris)."""
    global en_pause
    maintenant = pygame.time.get_ticks()
    if maintenant - PAUSE_T["t"] < 350:
        return
    PAUSE_T["t"] = maintenant
    en_pause = not en_pause


def placer_manette(px, py):
    """Place le stick selon le doigt ; la sensibilité agrandit ou réduit le déplacement nécessaire."""
    global manette_x, manette_y
    vx, vy = (px - JOY_CENTRE_X) * CTRL["k"], (py - JOY_CENTRE_Y) * CTRL["k"]
    dist = math.hypot(vx, vy)
    if dist > JOY_RAYON_SOCLE:
        vx, vy = vx / dist * JOY_RAYON_SOCLE, vy / dist * JOY_RAYON_SOCLE
    manette_x, manette_y = JOY_CENTRE_X + vx, JOY_CENTRE_Y + vy


_cache_disques = {}


def _disque(rayon, rgba):
    """Disque translucide mémorisé : pas de recréation pendant qu'on déplace une commande dans l'éditeur."""
    cle = (rayon, rgba)
    if cle not in _cache_disques:
        _cache_disques[cle] = creer_disque_translucide(rayon, rgba)
    return _cache_disques[cle]


def _borner_commande(x, y, rayon):
    """Garde toute la commande à l'intérieur de l'écran."""
    marge = rayon + 6
    return (int(round(max(marge, min(LARGEUR - marge, x)))), int(round(max(marge, min(HAUTEUR - marge, y)))))


def appliquer_controles():
    """Place le joystick et le bouton TIR d'après DISPO (position et taille choisies dans l'éditeur de commandes)."""
    global JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE, JOY_RAYON_MANETTE
    global BTN_TIR_X, BTN_TIR_Y, BTN_TIR_RAYON, rect_tir_tactile
    global manette_x, manette_y, SURF_SOCLE_JOY, SURF_BTN_TIR
    joy, tir = DISPO["joy"], DISPO["tir"]
    JOY_RAYON_SOCLE, JOY_RAYON_MANETTE = int(85 * joy["s"]), int(35 * joy["s"])
    BTN_TIR_RAYON = int(65 * tir["s"])
    JOY_CENTRE_X, JOY_CENTRE_Y = _borner_commande(joy["x"] * LARGEUR, joy["y"] * HAUTEUR, JOY_RAYON_SOCLE)
    BTN_TIR_X, BTN_TIR_Y = _borner_commande(tir["x"] * LARGEUR, tir["y"] * HAUTEUR, BTN_TIR_RAYON)
    rect_tir_tactile = pygame.Rect(BTN_TIR_X - BTN_TIR_RAYON, BTN_TIR_Y - BTN_TIR_RAYON, BTN_TIR_RAYON * 2, BTN_TIR_RAYON * 2)
    manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y
    SURF_SOCLE_JOY = _disque(JOY_RAYON_SOCLE, (10, 30, 45, 85))
    SURF_BTN_TIR = _disque(BTN_TIR_RAYON, (70, 0, 25, 95))
    CTRL["k"] = 0.5 + 0.1 * PARAMS["sensibilite"]
    CTRL["dz"] = (0.0, 0.05, 0.12, 0.20, 0.30)[PARAMS["zone_morte"]] * JOY_RAYON_SOCLE


def appliquer_audio():
    vm, ve = PARAMS["vol_musique"] / 10.0, PARAMS["vol_effets"] / 10.0
    try:
        if MUSIQUE_ACTIVE:
            pygame.mixer.music.set_volume(vm)
            if vm <= 0:
                pygame.mixer.music.pause()      # musique coupée : le téléphone n'a plus à la décoder
            elif musique_lancee:
                pygame.mixer.music.unpause()
        if SON_ACTIF:
            son_tir.set_volume(0.5 * ve)
            son_explosion.set_volume(0.6 * ve)
            son_echec.set_volume(0.7 * ve)
            son_victoire.set_volume(0.7 * ve)
    except Exception as e:
        print(f"⚠️ Volume : {e}")


def appliquer_parametres(cle=None):
    """Applique les réglages (tous si cle=None, sinon seulement ceux liés à la clé modifiée)."""
    global AUTO_QUALITE, ECHELLE
    AUTO_QUALITE = (PARAMS["qualite"] == 0)
    if cle in (None, "qualite"):
        QUALITE["niveau"] = (1, 0, 1, 2)[PARAMS["qualite"]]
    if cle in (None, "saut"):
        SAUT["n"] = (1, 1, 2, 3)[PARAMS["saut"]]
    if cle in (None, "sensibilite", "zone_morte"):
        appliquer_controles()
    if cle in (None, "vol_musique", "vol_effets"):
        appliquer_audio()


def changer_param(cle, delta):
    options = PARAM_OPTIONS[cle]
    i = PARAMS[cle] + delta
    i = i % len(options) if len(options) <= 4 else max(0, min(len(options) - 1, i))
    if i != PARAMS[cle]:
        PARAMS[cle] = i
        appliquer_parametres(cle)
        if cle == "resolution":
            PAR["redemarrer"] = True
        sauvegarder_parametres()


def reinitialiser_parametres():
    PARAMS.update(PARAM_DEFAUT)
    d = dispo_par_defaut()
    DISPO["joy"], DISPO["tir"] = d["joy"], d["tir"]
    appliquer_parametres()
    sauvegarder_parametres()


def dessiner_icone_engrenage(cx, cy, r, couleur):
    for k in range(8):
        a = k * math.pi / 4
        DRAW.line(ecran, couleur, (cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45),
                  (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82), 6)
    DRAW.circle(ecran, couleur, (cx, cy), int(r * 0.52), 4)
    DRAW.circle(ecran, couleur, (cx, cy), int(r * 0.18))


FPS_AFF = {"v": 60.0, "n": 0}


def dessiner_fps():
    FPS_AFF["n"] += 1
    if FPS_AFF["n"] % 10 == 1:
        FPS_AFF["v"] = clock.get_fps()
    v = FPS_AFF["v"]
    col = VERT_FLUO if v >= 52 else (JAUNE_CYBER if v >= 38 else ROUGE_ALERTE)
    rendu = f" (dessin 1/{SAUT['n']})" if SAUT["n"] > 1 else ""
    l1 = rendu_texte(police_petite, f"FPS {int(round(v))}{rendu}   Q{QUALITE['niveau']}   {int(round(ECHELLE * 100))}%", True, col)
    pas = f"   pas x{LOGIQUE['k']}" if LOGIQUE["k"] > 1 else ""
    l2 = rendu_texte(police_petite, f"logique {int(TMR['l'])} ms   dessin {int(TMR['r'])} ms   écran {int(TMR['f'])} ms{pas}", True, (170, 180, 210))
    larg = max(l1.get_width(), l2.get_width()) + 16
    haut = l1.get_height() + l2.get_height() + 8
    ecran.blit(obtenir_voile(larg, haut, (5, 6, 16, 160)), (10, HAUTEUR - haut - 10))
    ecran.blit(l1, (18, HAUTEUR - haut - 7))
    ecran.blit(l2, (18, HAUTEUR - haut - 7 + l1.get_height() + 2))


def adapter_qualite():
    """Mode Auto : si le jeu rame, on allège d'abord les effets, puis on saute des images ; si ça ne suffit pas,
    on note une résolution plus basse pour le PROCHAIN lancement (la résolution ne se change pas en pleine partie)."""
    global frames_total, fps_bas_consecutifs
    frames_total += 1
    if frames_total < 120 or frames_total % 20 != 0:
        return
    if etat_actuel != ETAT_JEU or en_pause or TRANS["actif"]:
        fps_bas_consecutifs = 0
        return
    fps = clock.get_fps()
    peut_effets = AUTO_QUALITE and QUALITE["niveau"] > 0
    peut_saut = PARAMS["saut"] == 0 and SAUT["n"] < 3
    suggerer = PARAMS["resolution"] == 0 and ECHELLE > 0.55 and not EXTRA["suggere"]
    if fps >= 48 or not (peut_effets or peut_saut or suggerer):
        fps_bas_consecutifs = 0
        return
    fps_bas_consecutifs += 1
    if fps_bas_consecutifs < 2:
        return
    fps_bas_consecutifs = 0
    if suggerer and not peut_effets:
        EXTRA["echelle_auto"] = 0.75 if ECHELLE > 0.8 else 0.5
        EXTRA["suggere"] = True
        sauvegarder_parametres()
    for _ in range(2 if fps < 25 else 1):
        if AUTO_QUALITE and QUALITE["niveau"] > 0:
            QUALITE["niveau"] -= 1
        elif PARAMS["saut"] == 0 and SAUT["n"] < 3:
            SAUT["n"] += 1


def lancer_benchmark():
    """Mesure les coûts réels sur CE téléphone et affiche le résultat dans les Paramètres (et dans bench_flex.txt)."""
    def mesurer(f, n):
        t = _time.perf_counter()
        for _ in range(n):
            f()
        return (_time.perf_counter() - t) * 1000.0 / n

    tm, ts = tuile_mur(COULEUR_MUR, 5), tuile_sol(COULEUR_MUR, 0, 3)

    def tuiles():
        for i in range(15):
            for j in range(8):
                ecran.blit(tm if (i + j) % 3 == 0 else ts, (i * 100, j * 90))

    def lueurs():
        for i in range(20):
            dessiner_halo(100 + i * 60, 300, 84, BLEU_CYBER, 0.8, 0)

    def ombres():
        for i in range(20):
            dessiner_ombre(100 + i * 60, 300, 44, 16)

    def calcul():
        s = 0
        for i in range(60000):
            s += i * i
        return s

    ecran.fill((8, 10, 20))
    lueurs()
    ombres()
    tuiles()
    pygame.display.flip()                       # échauffement (création des caches)
    t_fill = mesurer(lambda: ecran.fill((10, 10, 20)), 10)
    t_flip = mesurer(pygame.display.flip, 10)
    t_tuiles = mesurer(tuiles, 5)
    t_lueurs = mesurer(lueurs, 10)
    t_ombres = mesurer(ombres, 10)
    t_calcul = mesurer(calcul, 3)
    total = t_fill + t_flip + t_tuiles + t_lueurs * 0.5 + t_ombres * 0.5 + t_calcul * 0.3
    fps = 1000.0 / max(1.0, total)
    lignes = [
        f"Remplir l'écran : {t_fill:.1f} ms     Afficher (flip) : {t_flip:.1f} ms",
        f"120 tuiles : {t_tuiles:.1f} ms     20 lueurs : {t_lueurs:.1f} ms     20 ombres : {t_ombres:.1f} ms",
        f"Calcul Python : {t_calcul:.1f} ms     Écran : {LARGEUR}x{HAUTEUR}",
        f"Estimation d'une image : {total:.0f} ms  (~{fps:.0f} FPS)",
    ]
    s2 = max(0.25, ECHELLE) ** 2
    est_plein = (t_fill + t_flip + t_tuiles + t_lueurs * 0.5 + t_ombres * 0.5) / s2
    conseil = 1.0 if est_plein <= 16 else (0.75 if est_plein <= 30 else 0.5)
    lignes.append(f"Résolution conseillée : {int(conseil * 100)}%  (redémarre le jeu pour l'appliquer)")
    if PARAMS["resolution"] == 0:
        EXTRA["echelle_auto"] = conseil
        sauvegarder_parametres()
    PAR["bench"] = lignes
    try:
        with open(chemin_donnees("bench_flex.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
    except Exception:
        pass


def traiter_tap_parametres(x, y):
    for rect, genre, cle, delta in PAR["zones"]:
        if rect.collidepoint(x, y):
            if genre == "chg":
                changer_param(cle, delta)
            elif genre == "reset":
                reinitialiser_parametres()
            elif genre == "bench":
                lancer_benchmark()
            elif genre == "action" and cle == "editeur":
                lancer_transition(("etat", ETAT_EDITEUR))
            elif genre == "retour":
                sauvegarder_parametres()
                if PAR["origine"] == ETAT_JEU:
                    lancer_transition(("retour_jeu",), DUREE_CHARGEMENT_RAPIDE)
                else:
                    lancer_transition(("etat", ETAT_MENU))
            return


def dessiner_parametres():
    dessiner_fond_menu()
    pw = min(780, LARGEUR - 40)
    px0 = LARGEUR // 2 - pw // 2
    dessiner_panneau_neon(px0, pw, BLEU_CYBER, False, 215)
    dessiner_titre_glitch("PARAMÈTRES", police_titre, LARGEUR // 2, 50)
    note = None
    if PAR["redemarrer"]:
        note = "Redémarre le jeu pour appliquer la nouvelle résolution"
    elif PARAMS["resolution"] == 0 and EXTRA.get("echelle_auto") not in (None, ECHELLE):
        note = f"Résolution automatique au prochain lancement : {int(EXTRA['echelle_auto'] * 100)}%"
    if note:
        tn_ = rendu_texte(police_petite, note, True, JAUNE_CYBER)
        ecran.blit(tn_, (LARGEUR // 2 - tn_.get_width() // 2, 110))

    y_zone = 130
    nb_sections = sum(1 for d in PARAM_DEFS if len(d) == 2)
    nb_lignes = len(PARAM_DEFS) - nb_sections
    hauteur_contenu = nb_sections * 50 + nb_lignes * 74 + 180 + (len(PAR["bench"]) * 26 + 16 if PAR["bench"] else 0) + 40
    hauteur_visible = HAUTEUR - y_zone - 8
    defil_max = max(0, hauteur_contenu - hauteur_visible)
    PAR["scroll"] = max(-defil_max, min(0, PAR["scroll"]))

    zones = [(rect_retour_infos, "retour", None, 0)]
    couleurs_section = (ROSE_SYNTH, BLEU_CYBER, JAUNE_CYBER, VIOLET_CYBER)
    idx_section = 0
    y = y_zone + 6 + PAR["scroll"]
    ecran.set_clip(pygame.Rect(px0 - 14, y_zone, pw + 28, HAUTEUR - y_zone))
    for defn in PARAM_DEFS:
        if len(defn) == 2:
            col = couleurs_section[idx_section % 4]
            idx_section += 1
            if y_zone - 50 < y < HAUTEUR:
                t = rendu_texte(police_jeu, defn[1], True, col)
                ecran.blit(t, (px0 + 28, int(y + 8)))
                DRAW.line(ecran, eclaircir(col, 0.5), (px0 + 28, int(y + 40)), (px0 + pw - 28, int(y + 40)), 2)
            y += 50
            continue
        if defn[0] == "ACTION":
            if y_zone - 66 < y < HAUTEUR:
                r = pygame.Rect(px0 + 24, int(y), pw - 48, 62)
                DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
                DRAW.rect(ecran, eclaircir(VIOLET_CYBER, 0.5), r, 2, border_radius=12)
                tl = rendu_texte(police_aide, defn[1], True, BLANC_NEON)
                ecran.blit(tl, (r.x + 18, r.centery - tl.get_height() // 2))
                rb = pygame.Rect(r.right - 232, r.y + 8, 214, 46)
                bouton_neon(rb, VIOLET_CYBER, "MODIFIER", police_petite, plein=True)
                if y_zone + 8 < r.centery < HAUTEUR - 8:
                    zones.append((rb, "action", defn[2], 0))
            y += 74
            continue
        cle, label, options, _defaut = defn
        if y_zone - 66 < y < HAUTEUR:
            r = pygame.Rect(px0 + 24, int(y), pw - 48, 62)
            DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
            DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.35), r, 2, border_radius=12)
            tl = rendu_texte(police_aide, label, True, BLANC_NEON)
            ecran.blit(tl, (r.x + 18, r.centery - tl.get_height() // 2))
            lc = min(320, r.width // 2 + 10)
            xc = r.right - 12 - lc
            rg = pygame.Rect(xc, r.y + 8, 46, 46)
            rd = pygame.Rect(xc + lc - 46, r.y + 8, 46, 46)
            for rr, sens in ((rg, -1), (rd, 1)):
                DRAW.rect(ecran, (14, 20, 44), rr, border_radius=10)
                DRAW.rect(ecran, BLEU_CYBER, rr, 2, border_radius=10)
                cx_, cy_ = rr.center
                DRAW.lines(ecran, BLANC_NEON, False,
                           [(cx_ - sens * 6, cy_ - 11), (cx_ + sens * 6, cy_), (cx_ - sens * 6, cy_ + 11)], 4)
            valeur = options[PARAMS[cle]]
            cv = VERT_FLUO if valeur == "Oui" else ((150, 160, 190) if valeur == "Non" else CYAN_NEON)
            tv = rendu_texte(police_aide, valeur, True, cv)
            ecran.blit(tv, (xc + lc // 2 - tv.get_width() // 2, r.centery - tv.get_height() // 2))
            if y_zone + 8 < r.centery < HAUTEUR - 8:
                zones.append((rg, "chg", cle, -1))
                zones.append((rd, "chg", cle, 1))
                zones.append((pygame.Rect(xc + 46, r.y, lc - 92, 62), "chg", cle, 1))
        y += 74
    rr = pygame.Rect(px0 + 60, int(y + 14), pw - 120, 56)
    if y_zone - 60 < y + 14 < HAUTEUR:
        bouton_neon(rr, ROUGE_ALERTE, "RÉTABLIR PAR DÉFAUT", police_bouton)
        if y_zone < rr.centery < HAUTEUR - 8:
            zones.append((rr, "reset", None, 0))
    rb = pygame.Rect(px0 + 60, int(y + 84), pw - 120, 56)
    if y_zone - 60 < y + 84 < HAUTEUR:
        bouton_neon(rb, VIOLET_CYBER, "TEST DE PERFORMANCE", police_bouton)
        if y_zone < rb.centery < HAUTEUR - 8:
            zones.append((rb, "bench", None, 0))
    for k_b, ligne_b in enumerate(PAR["bench"]):
        yb = int(y + 84 + 56 + 14 + k_b * 26)
        if y_zone - 26 < yb < HAUTEUR:
            tb = rendu_texte(police_petite, ligne_b, True, CYAN_NEON if k_b == len(PAR["bench"]) - 1 else BLANC_NEON)
            ecran.blit(tb, (LARGEUR // 2 - tb.get_width() // 2, yb))
    ecran.set_clip(None)
    PAR["zones"] = zones

    if defil_max > 0:
        x_barre, haut_piste = px0 + pw - 9, y_zone + 6
        long_piste = HAUTEUR - y_zone - 22
        long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
        y_pouce = haut_piste + int((long_piste - long_pouce) * (-PAR["scroll"]) / float(defil_max))
        DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
        DRAW.rect(ecran, BLEU_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)
        if PAR["scroll"] > -6:
            indice = rendu_texte(police_petite, "Glisse pour voir les autres réglages", True, BLEU_CYBER)
            ecran.blit(obtenir_voile(indice.get_width() + 30, 34, (5, 6, 16, 200)), (LARGEUR // 2 - indice.get_width() // 2 - 15, HAUTEUR - 50))
            ecran.blit(indice, (LARGEUR // 2 - indice.get_width() // 2, HAUTEUR - 41))

    bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)


# ==================== BOUTIQUE ET ÉCONOMIE ====================
# Les pièces se gagnent en fin de mission ; la boutique les transforme en bouclier, armes, améliorations et skins de laser.
CHEMIN_BOUTIQUE = chemin_donnees("boutique_flex.json")

# Articles à niveaux : clé, nom, description, prix de chaque niveau, libellé de l'effet pour le niveau 0, 1, 2...
BOUTIQUE_ARTICLES = [
    {"section": "ARMURE"},
    {"cle": "bouclier", "nom": "Bouclier énergétique", "desc": "Absorbe des coups de drone ou de Boss",
     "prix": [150, 400, 900], "effets": ["Aucun", "1 coup", "2 coups", "3 coups"]},
    {"section": "ARMES"},
    {"cle": "cadence", "nom": "Cadence de tir", "desc": "Tire plus vite quand tu maintiens TIR",
     "prix": [100, 250, 500, 900], "effets": ["Normale", "+12%", "+28%", "+50%", "+80%"]},
    {"cle": "degats", "nom": "Puissance anti-Boss", "desc": "Plus de dégâts contre le Boss",
     "prix": [200, 500, 1000], "effets": ["Normale", "+40%", "+80%", "+120%"]},
    {"cle": "perfo", "nom": "Tir perforant", "desc": "Le laser traverse plusieurs drones",
     "prix": [250, 600, 1200], "effets": ["Aucun", "1 drone", "2 drones", "3 drones"]},
    {"section": "AMÉLIORATIONS"},
    {"cle": "hack", "nom": "Hack accéléré", "desc": "Le CORE se pirate plus vite",
     "prix": [150, 400, 800], "effets": ["Normal", "+25%", "+50%", "+80%"]},
    {"cle": "potion", "nom": "Potions prolongées", "desc": "Chaque potion donne plus de temps",
     "prix": [100, 300], "effets": ["+5 s", "+7 s", "+9 s"]},
    {"cle": "chrono", "nom": "Chrono étendu", "desc": "Plus de temps au départ de la mission",
     "prix": [150, 400, 800], "effets": ["+0 s", "+5 s", "+10 s", "+15 s"]},
    {"section": "SKINS DE LASER"},
]
# Skins : identifiant, nom, prix, couleur du laser, couleur de sa traînée
SKINS_LASER = [
    ("cyan", "Cyan néon", 0, (0, 235, 255), (0, 80, 150)),
    ("rose", "Rose synthwave", 150, (255, 70, 200), (140, 20, 100)),
    ("acide", "Vert acide", 150, (170, 255, 0), (70, 120, 0)),
    ("or", "Or électrique", 350, (255, 205, 50), (140, 90, 0)),
    ("violet", "Violet plasma", 350, (175, 95, 255), (80, 30, 150)),
]
ARTICLES_NIVEAUX = {a["cle"]: a for a in BOUTIQUE_ARTICLES if "cle" in a}

BOUTIQUE = {"pieces": 0, "niveaux": {}, "skins": ["cyan"], "skin_actif": "cyan", "faits": [], "etoiles": {}}
STATS = {"bouclier": 0, "cadence": 8, "degats": 1.0, "perfo": 0, "hack": 1.0, "potion": 0, "chrono": 0}
LASER = {"main": SKINS_LASER[0][3], "trail": SKINS_LASER[0][4]}
MISSION = {"drones": 0, "recompense": None, "versee": False, "duree": 1}      # suivi de la mission en cours
ETAT_JOUEUR = {"bouclier": 0, "invuln": 0}                         # bouclier restant et invulnérabilité (en pas de logique)
BQ = {"scroll": 0.0, "drag": False, "id": None, "y": 0.0, "x0": 0.0, "y0": 0.0, "moved": False,
      "zones": [], "msg": "", "msg_couleur": VERT_FLUO, "msg_t": -10000}


def charger_boutique():
    d, statut = lire_json_signe(CHEMIN_BOUTIQUE)
    if statut == "altere":
        signaler_sauvegarde_alteree()
        return
    if d is None:
        return
    try:
        if isinstance(d.get("pieces"), int) and d["pieces"] >= 0:
            BOUTIQUE["pieces"] = d["pieces"]
        for cle, art in ARTICLES_NIVEAUX.items():
            v = d.get("niveaux", {}).get(cle, 0)
            if isinstance(v, int) and 0 <= v <= len(art["prix"]):
                BOUTIQUE["niveaux"][cle] = v
        ids = [s[0] for s in SKINS_LASER]
        BOUTIQUE["skins"] = [s for s in d.get("skins", []) if s in ids]
        if "cyan" not in BOUTIQUE["skins"]:
            BOUTIQUE["skins"].insert(0, "cyan")
        actif = d.get("skin_actif")
        BOUTIQUE["skin_actif"] = actif if actif in BOUTIQUE["skins"] else "cyan"
        BOUTIQUE["faits"] = [n for n in d.get("faits", []) if isinstance(n, int)]
        BOUTIQUE["etoiles"] = {k: v for k, v in d.get("etoiles", {}).items() if isinstance(v, int) and 1 <= v <= 3}
    except Exception as e:
        print(f"⚠️ Boutique illisible : {e}")
    if statut == "ancien":
        sauvegarder_boutique()            # une ancienne sauvegarde (sans signature) est acceptée une fois, puis signée


def sauvegarder_boutique():
    try:
        ecrire_json_signe(CHEMIN_BOUTIQUE, BOUTIQUE)
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder la boutique : {e}")


def recalculer_stats():
    """Traduit les niveaux achetés en valeurs de jeu."""
    n = BOUTIQUE["niveaux"]
    STATS["bouclier"] = n.get("bouclier", 0)
    STATS["cadence"] = (8, 7, 6, 5, 4)[n.get("cadence", 0)]
    STATS["degats"] = (1.0, 1.4, 1.8, 2.2)[n.get("degats", 0)]
    STATS["perfo"] = n.get("perfo", 0)
    STATS["hack"] = (1.0, 1.25, 1.5, 1.8)[n.get("hack", 0)]
    STATS["potion"] = (0, 120, 240)[n.get("potion", 0)]
    STATS["chrono"] = (0, 300, 600, 900)[n.get("chrono", 0)]


def appliquer_skin():
    for sid, _nom, _prix, principal, traine in SKINS_LASER:
        if sid == BOUTIQUE["skin_actif"]:
            LASER["main"], LASER["trail"] = principal, traine


def niveau_article(cle):
    return BOUTIQUE["niveaux"].get(cle, 0)


# ---------------------------------------------------------------- dégâts subis et récompenses
def subir_degats(message):
    """Retourne True si le joueur est vaincu ; False si le bouclier (ou l'invulnérabilité) a encaissé le coup."""
    global partie_perdue, message_defaite
    if ETAT_JOUEUR["invuln"] > 0:
        return False
    if ETAT_JOUEUR["bouclier"] > 0:
        ETAT_JOUEUR["bouclier"] -= 1
        ETAT_JOUEUR["invuln"] = 90
        creer_explosion(joueur_x, joueur_y, LASER["main"], 18, 6.0, 5.0)
        if SON_ACTIF:
            son_explosion.play()
        return False
    partie_perdue = True
    message_defaite = message
    if SON_ACTIF:
        son_echec.play()
    return True


def calculer_recompense(victoire):
    drones = MISSION["drones"]
    if not victoire:
        return {"total": drones, "base": 0, "temps": 0, "drones": drones, "boss": 0, "reduite": False}
    n = niveau_actuel
    base = 30 + 8 * n
    temps = max(0, temps_restant_frames) // 60 // 2
    bonus_drones = drones * 2
    boss = (100 + 20 * ((n + 1) // 5)) if niveau_data["est_boss"] else 0
    total = base + temps + bonus_drones + boss
    reduite = n in BOUTIQUE["faits"]
    if reduite:
        total //= 2
    return {"total": total, "base": base, "temps": temps, "drones": bonus_drones, "boss": boss, "reduite": reduite}


def accorder_recompense(victoire):
    """Verse les pièces de la mission (une seule fois par partie)."""
    if MISSION["versee"]:
        return
    MISSION["versee"] = True
    r = calculer_recompense(victoire)
    MISSION["recompense"] = r
    BOUTIQUE["pieces"] += r["total"]
    if victoire and niveau_actuel not in BOUTIQUE["faits"]:
        BOUTIQUE["faits"].append(niveau_actuel)
    sauvegarder_boutique()


# ---------------------------------------------------------------- achats
def message_boutique(texte, couleur):
    BQ["msg"], BQ["msg_couleur"], BQ["msg_t"] = texte, couleur, pygame.time.get_ticks()


def acheter_niveau(cle):
    art = ARTICLES_NIVEAUX[cle]
    niv = niveau_article(cle)
    if niv >= len(art["prix"]):
        message_boutique("Déjà au niveau maximum", JAUNE_CYBER)
        return
    prix = art["prix"][niv]
    if BOUTIQUE["pieces"] < prix:
        message_boutique(f"Il te manque {prix - BOUTIQUE['pieces']} pièces", ROUGE_ALERTE)
        return
    BOUTIQUE["pieces"] -= prix
    BOUTIQUE["niveaux"][cle] = niv + 1
    recalculer_stats()
    sauvegarder_boutique()
    message_boutique(f"{art['nom']} : niveau {niv + 1} acheté !", VERT_FLUO)


def acheter_ou_equiper_skin(sid):
    for ident, nom, prix, _principal, _traine in SKINS_LASER:
        if ident != sid:
            continue
        if sid not in BOUTIQUE["skins"]:
            if BOUTIQUE["pieces"] < prix:
                message_boutique(f"Il te manque {prix - BOUTIQUE['pieces']} pièces", ROUGE_ALERTE)
                return
            BOUTIQUE["pieces"] -= prix
            BOUTIQUE["skins"].append(sid)
            message_boutique(f"Skin « {nom} » acheté et équipé !", VERT_FLUO)
        else:
            message_boutique(f"Skin « {nom} » équipé", VERT_FLUO)
        BOUTIQUE["skin_actif"] = sid
        appliquer_skin()
        sauvegarder_boutique()
        return


def traiter_tap_boutique(x, y):
    for rect, genre, cle in BQ["zones"]:
        if rect.collidepoint(x, y):
            if genre == "niveau":
                acheter_niveau(cle)
            elif genre == "skin":
                acheter_ou_equiper_skin(cle)
            elif genre == "retour":
                lancer_transition(("etat", ETAT_MENU))
            return


def gerer_liste_tactile(liste, event, etat_cible, action_tap):
    """Défilement au doigt d'un écran à liste ; un simple toucher (sans glisser) appelle action_tap(x, y)."""
    if etat_actuel == etat_cible:
        if event.type == pygame.FINGERDOWN:
            liste.update(drag=True, id=event.finger_id, y=event.y * HAUTEUR, x0=event.x * LARGEUR, y0=event.y * HAUTEUR, moved=False)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not liste["drag"]:
            p = pos_ev(event)
            liste.update(drag=True, id="souris", y=p[1], x0=p[0], y0=p[1], moved=False)
        elif event.type == pygame.FINGERMOTION and liste["drag"] and event.finger_id == liste["id"]:
            y_nouveau = event.y * HAUTEUR
            liste["scroll"] += y_nouveau - liste["y"]
            liste["y"] = y_nouveau
            if abs(y_nouveau - liste["y0"]) > 14:
                liste["moved"] = True
        elif event.type == pygame.MOUSEMOTION and liste["drag"] and liste["id"] == "souris":
            y_nouveau = pos_ev(event)[1]
            liste["scroll"] += y_nouveau - liste["y"]
            liste["y"] = y_nouveau
            if abs(y_nouveau - liste["y0"]) > 14:
                liste["moved"] = True
    if liste["drag"] and ((event.type == pygame.MOUSEBUTTONUP and liste["id"] == "souris") or
                          (event.type == pygame.FINGERUP and event.finger_id == liste["id"])):
        liste["drag"], liste["id"] = False, None
        if not liste["moved"] and etat_actuel == etat_cible and not TRANS["actif"]:
            action_tap(liste["x0"], liste["y0"])


# ---------------------------------------------------------------- dessin
def dessiner_piece(cx, cy, r):
    DRAW.circle(ecran, (255, 200, 40), (cx, cy), r)
    DRAW.circle(ecran, (255, 235, 140), (cx, cy), r, 2)
    DRAW.circle(ecran, (185, 125, 10), (cx, cy), max(2, r // 2), 2)


def dessiner_pieces(cx, y):
    """Compteur de pièces centré en cx."""
    t = rendu_texte(police_jeu, f"{BOUTIQUE['pieces']}", True, JAUNE_CYBER)
    largeur = t.get_width() + 62
    rect = pygame.Rect(cx - largeur // 2, y, largeur, 44)
    DRAW.rect(ecran, (8, 10, 20), rect, border_radius=14)
    DRAW.rect(ecran, eclaircir(JAUNE_CYBER, 0.7), rect, 2, border_radius=14)
    dessiner_piece(rect.x + 24, rect.centery, 12)
    ecran.blit(t, (rect.x + 46, rect.centery - t.get_height() // 2))


def dessiner_hud_boutique():
    """En mission : pastilles de bouclier et pièces en banque (sous le texte des drones)."""
    x, y = 40, 108
    for i in range(STATS["bouclier"]):
        centre = (x + 11 + i * 28, y + 11)
        if i < ETAT_JOUEUR["bouclier"]:
            DRAW.circle(ecran, eclaircir(LASER["main"], 0.35), centre, 12)
            DRAW.circle(ecran, LASER["main"], centre, 12, 3)
        else:
            DRAW.circle(ecran, (60, 70, 100), centre, 12, 2)
    x_pieces = x + max(0, STATS["bouclier"]) * 28 + (8 if STATS["bouclier"] else 0)
    dessiner_piece(x_pieces + 11, y + 11, 10)
    t = rendu_texte(police_petite, f"{BOUTIQUE['pieces']}", True, JAUNE_CYBER)
    ecran.blit(t, (x_pieces + 28, y + 11 - t.get_height() // 2))


def _bouton_achat(rect, texte, couleur, actif=True, plein=False):
    """Petit bouton de la boutique (zone tactile gérée par l'appelant)."""
    if actif:
        bouton_neon(rect, couleur, texte, police_petite, plein=plein)
    else:
        DRAW.rect(ecran, (14, 18, 36), rect, border_radius=12)
        DRAW.rect(ecran, (60, 70, 100), rect, 2, border_radius=12)
        t = rendu_texte(police_petite, texte, True, (110, 120, 150))
        ecran.blit(t, (rect.centerx - t.get_width() // 2, rect.centery - t.get_height() // 2))


def dessiner_boutique():
    dessiner_fond_menu()
    pw = min(780, LARGEUR - 40)
    px0 = LARGEUR // 2 - pw // 2
    dessiner_panneau_neon(px0, pw, JAUNE_CYBER, False, 215)
    dessiner_titre_glitch("BOUTIQUE", police_titre, LARGEUR // 2, 50)
    dessiner_pieces(LARGEUR - 170, 52)

    y_zone, h_carte, pas = 130, 92, 104
    nb_sections = sum(1 for a in BOUTIQUE_ARTICLES if "section" in a)
    nb_articles = len(BOUTIQUE_ARTICLES) - nb_sections
    hauteur_contenu = nb_sections * 50 + (nb_articles + len(SKINS_LASER)) * pas + 60
    hauteur_visible = HAUTEUR - y_zone - 8
    defil_max = max(0, hauteur_contenu - hauteur_visible)
    BQ["scroll"] = max(-defil_max, min(0, BQ["scroll"]))

    zones = [(rect_retour_infos, "retour", None)]
    couleurs_section = (ROSE_SYNTH, ROUGE_ALERTE, BLEU_CYBER, VIOLET_CYBER)
    idx_section = 0
    y = y_zone + 6 + BQ["scroll"]
    ecran.set_clip(pygame.Rect(px0 - 14, y_zone, pw + 28, HAUTEUR - y_zone))

    def entete(titre, y_):
        nonlocal idx_section
        col = couleurs_section[idx_section % 4]
        idx_section += 1
        if y_zone - 50 < y_ < HAUTEUR:
            t = rendu_texte(police_jeu, titre, True, col)
            ecran.blit(t, (px0 + 28, int(y_ + 8)))
            DRAW.line(ecran, eclaircir(col, 0.5), (px0 + 28, int(y_ + 40)), (px0 + pw - 28, int(y_ + 40)), 2)

    def carte(y_):
        r = pygame.Rect(px0 + 24, int(y_), pw - 48, h_carte)
        DRAW.rect(ecran, (10, 13, 28), r, border_radius=12)
        DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.35), r, 2, border_radius=12)
        return r

    def zone_visible(r):
        return y_zone + 8 < r.centery < HAUTEUR - 8

    for art in BOUTIQUE_ARTICLES:
        if "section" in art:
            entete(art["section"], y)
            y += 50
            if art["section"] == "SKINS DE LASER":
                break
            continue
        if y_zone - h_carte < y < HAUTEUR:
            cle = art["cle"]
            niv = niveau_article(cle)
            r = carte(y)
            ecran.blit(rendu_texte(police_aide, art["nom"], True, BLANC_NEON), (r.x + 18, r.y + 10))
            ecran.blit(rendu_texte(police_petite, art["desc"], True, (150, 160, 190)), (r.x + 18, r.y + 40))
            for k in range(len(art["prix"])):                                     # pastilles de niveau
                c = (r.x + 24 + k * 22, r.y + 74)
                if k < niv:
                    DRAW.circle(ecran, JAUNE_CYBER, c, 8)
                else:
                    DRAW.circle(ecran, (60, 70, 100), c, 8, 2)
            ecran.blit(rendu_texte(police_petite, art["effets"][niv], True, CYAN_NEON), (r.x + 24 + len(art["prix"]) * 22 + 6, r.y + 66))
            rb = pygame.Rect(r.right - 218, r.y + 20, 200, 52)
            if niv >= len(art["prix"]):
                _bouton_achat(rb, "NIVEAU MAX", JAUNE_CYBER, actif=False)
            else:
                prix = art["prix"][niv]
                _bouton_achat(rb, f"ACHETER  {prix}", JAUNE_CYBER, actif=BOUTIQUE["pieces"] >= prix, plein=BOUTIQUE["pieces"] >= prix)
                if zone_visible(rb):
                    zones.append((rb, "niveau", cle))
            if niv < len(art["prix"]) and BOUTIQUE["pieces"] < art["prix"][niv] and zone_visible(rb):
                zones.append((rb, "niveau", cle))
        y += pas

    for sid, nom, prix, principal, traine in SKINS_LASER:
        if y_zone - h_carte < y < HAUTEUR:
            r = carte(y)
            ecran.blit(rendu_texte(police_aide, nom, True, BLANC_NEON), (r.x + 90, r.y + 12))
            DRAW.line(ecran, traine, (r.x + 24, r.centery + 10), (r.x + 64, r.centery - 10), 9)
            DRAW.line(ecran, principal, (r.x + 30, r.centery + 7), (r.x + 64, r.centery - 10), 5)
            DRAW.circle(ecran, BLANC_NEON, (r.x + 64, r.centery - 10), 4)
            possede = sid in BOUTIQUE["skins"]
            etat_txt = "Équipé" if BOUTIQUE["skin_actif"] == sid else ("Possédé" if possede else f"{prix} pièces")
            ecran.blit(rendu_texte(police_petite, etat_txt, True, VERT_FLUO if possede else JAUNE_CYBER), (r.x + 90, r.y + 50))
            rb = pygame.Rect(r.right - 218, r.y + 20, 200, 52)
            if BOUTIQUE["skin_actif"] == sid:
                _bouton_achat(rb, "ÉQUIPÉ", VERT_FLUO, actif=False)
            elif possede:
                _bouton_achat(rb, "ÉQUIPER", VERT_FLUO)
            else:
                _bouton_achat(rb, f"ACHETER  {prix}", JAUNE_CYBER, actif=BOUTIQUE["pieces"] >= prix, plein=BOUTIQUE["pieces"] >= prix)
            if BOUTIQUE["skin_actif"] != sid and zone_visible(rb):
                zones.append((rb, "skin", sid))
        y += pas
    ecran.set_clip(None)
    BQ["zones"] = zones

    if defil_max > 0:
        x_barre, haut_piste = px0 + pw - 9, y_zone + 6
        long_piste = HAUTEUR - y_zone - 22
        long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
        y_pouce = haut_piste + int((long_piste - long_pouce) * (-BQ["scroll"]) / float(defil_max))
        DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
        DRAW.rect(ecran, JAUNE_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)

    if BQ["msg"] and pygame.time.get_ticks() - BQ["msg_t"] < 2200:
        tm = rendu_texte(police_aide, BQ["msg"], True, BQ["msg_couleur"])
        ecran.blit(obtenir_voile(tm.get_width() + 40, 44, (5, 6, 16, 235)), (LARGEUR // 2 - tm.get_width() // 2 - 20, HAUTEUR - 66))
        ecran.blit(tm, (LARGEUR // 2 - tm.get_width() // 2, HAUTEUR - 56))

    bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)


def dessiner_filigrane():
    """Bandeau permanent sur une version dont le code a été modifié."""
    t = rendu_texte(police_petite, "VERSION MODIFIÉE · non officielle · version officielle : TikTok @flexplay25", True, ROUGE_ALERTE)
    ecran.blit(obtenir_voile(t.get_width() + 24, 26, (5, 6, 16, 215)), (LARGEUR // 2 - t.get_width() // 2 - 12, 2))
    ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, 5))


def dessiner_avertissement():
    """Message temporaire (8 s) quand une sauvegarde modifiée à la main a été refusée."""
    if not AVERTISSEMENT["texte"]:
        return
    if AVERTISSEMENT["debut"] is None:
        AVERTISSEMENT["debut"] = _time.time()
    if _time.time() - AVERTISSEMENT["debut"] > 8:
        return
    t = rendu_texte(police_petite, AVERTISSEMENT["texte"], True, JAUNE_CYBER)
    ecran.blit(t, (LARGEUR // 2 - t.get_width() // 2, 88))


# ==================== ÉDITEUR DE COMMANDES ====================
def dessiner_commandes(mx, my, tir_actif):
    """Joystick et bouton TIR. Utilisée par le jeu et par l'éditeur : l'aperçu est donc identique à la réalité."""
    kj, kt = JOY_RAYON_SOCLE / 85.0, BTN_TIR_RAYON / 65.0
    ecran.blit(SURF_SOCLE_JOY, (JOY_CENTRE_X - JOY_RAYON_SOCLE - 6, JOY_CENTRE_Y - JOY_RAYON_SOCLE - 6))
    dessiner_halo(JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE + 25, COULEUR_MUR, 0.28, 2)
    DRAW.circle(ecran, COULEUR_MUR, (JOY_CENTRE_X, JOY_CENTRE_Y), JOY_RAYON_SOCLE, 4)
    DRAW.circle(ecran, eclaircir(COULEUR_MUR, 0.45), (JOY_CENTRE_X, JOY_CENTRE_Y), int(JOY_RAYON_SOCLE * 0.55), 1)
    mx_j, my_j = int(mx), int(my)
    dessiner_halo(mx_j, my_j, int(55 * kj), CYAN_NEON, 0.6)
    DRAW.circle(ecran, (0, 120, 190), (mx_j, my_j), JOY_RAYON_MANETTE)
    DRAW.circle(ecran, CYAN_NEON, (mx_j, my_j), max(2, JOY_RAYON_MANETTE - 4))
    DRAW.circle(ecran, (215, 250, 255), (mx_j - int(8 * kj), my_j - int(9 * kj)), max(2, int(9 * kj)))
    ecran.blit(SURF_BTN_TIR, (BTN_TIR_X - BTN_TIR_RAYON - 6, BTN_TIR_Y - BTN_TIR_RAYON - 6))
    dessiner_halo(BTN_TIR_X, BTN_TIR_Y, int((85 if tir_actif else 70) * kt), ROUGE_ALERTE, 0.95 if tir_actif else 0.35)
    DRAW.circle(ecran, ROUGE_ALERTE, (BTN_TIR_X, BTN_TIR_Y), BTN_TIR_RAYON, 5)
    tt = rendu_texte(police_bouton, "TIR", True, BLANC_NEON)
    ecran.blit(tt, (BTN_TIR_X - tt.get_width() // 2, BTN_TIR_Y - tt.get_height() // 2))


GRILLES_EDITEUR = (0, 32, 64, 96)      # 0 = pas de grille
ED = {"mode": "deplacer", "grille": 0, "drag": False, "id": None, "cible": None, "bouton": None, "bouge": False,
      "x0": 0.0, "y0": 0.0, "x": 0.0, "y": 0.0, "orig": None, "selection": None, "zones": []}


def centre_commande(nom):
    """(x, y, rayon) actuels d'une commande : 'joy' ou 'tir'."""
    if nom == "joy":
        return JOY_CENTRE_X, JOY_CENTRE_Y, JOY_RAYON_SOCLE
    return BTN_TIR_X, BTN_TIR_Y, BTN_TIR_RAYON


def _en_conflit(nom):
    """Vrai si la commande chevauche l'autre commande, le bouton pause ou le radar."""
    cx, cy, r = centre_commande(nom)
    ax, ay, ar = centre_commande("tir" if nom == "joy" else "joy")
    for zx, zy, zr in ((ax, ay, ar), (BTN_PAUSE_X, BTN_PAUSE_Y, BTN_PAUSE_RAYON), (RADAR_CENTRE_X, RADAR_CENTRE_Y, RADAR_RAYON)):
        if math.hypot(cx - zx, cy - zy) < r + zr - 4:
            return True
    return False


def _magnetiser(v):
    g = GRILLES_EDITEUR[ED["grille"]]
    return round(v / float(g)) * g if g else v


def _debut_toucher(identifiant, x, y):
    ED.update(drag=True, id=identifiant, x0=x, y0=y, x=x, y=y, bouge=False, cible=None, bouton=None, orig=None)
    for rect, action in ED["zones"]:                         # d'abord les boutons du panneau
        if rect.collidepoint(x, y):
            ED["bouton"] = (rect, action)
            return
    meilleure, dist_min = None, 10 ** 9                         # sinon : la commande touchée (la plus proche du doigt)
    for nom in ("tir", "joy"):
        cx, cy, r = centre_commande(nom)
        d = math.hypot(x - cx, y - cy)
        if d <= r + 30 and d < dist_min:
            meilleure, dist_min = nom, d
    if meilleure:
        cx, cy, _r = centre_commande(meilleure)
        ED["cible"], ED["selection"] = meilleure, meilleure
        ED["orig"] = (cx, cy, DISPO[meilleure]["s"])


def _mouvement_toucher(x, y):
    ED["x"], ED["y"] = x, y
    if math.hypot(x - ED["x0"], y - ED["y0"]) > 8:
        ED["bouge"] = True
    nom = ED["cible"]
    if not nom or not ED["bouge"]:
        return
    ox, oy, os_ = ED["orig"]
    if ED["mode"] == "deplacer":
        nx, ny = _magnetiser(ox + (x - ED["x0"])), _magnetiser(oy + (y - ED["y0"]))
        s = DISPO[nom]["s"]
    else:                                                       # redimensionner : plus le doigt s'éloigne du centre, plus c'est grand
        nx, ny = ox, oy
        d0, d = math.hypot(ED["x0"] - ox, ED["y0"] - oy), math.hypot(x - ox, y - oy)
        s = round((os_ + (d - d0) / 150.0) * 20) / 20.0
        s = max(ECHELLE_COMMANDE_MIN, min(ECHELLE_COMMANDE_MAX, s))
    rayon = int((85 if nom == "joy" else 65) * s)
    cx, cy = _borner_commande(nx, ny, rayon)
    DISPO[nom] = {"x": cx / float(LARGEUR), "y": cy / float(HAUTEUR), "s": s}
    appliquer_controles()


def _action_editeur(action):
    if action in ("deplacer", "taille"):
        ED["mode"] = action
    elif action == "grille":
        ED["grille"] = (ED["grille"] + 1) % len(GRILLES_EDITEUR)
    elif action == "inverser":                                  # miroir gauche/droite (mode gaucher)
        for nom in ("joy", "tir"):
            DISPO[nom]["x"] = 1.0 - DISPO[nom]["x"]
        appliquer_controles()
        sauvegarder_parametres()
    elif action == "reset":
        d = dispo_par_defaut()
        DISPO["joy"], DISPO["tir"] = d["joy"], d["tir"]
        appliquer_controles()
        sauvegarder_parametres()
    elif action == "retour":
        sauvegarder_parametres()
        lancer_transition(("etat", ETAT_PARAMS))


def _fin_toucher():
    ED["drag"], ED["id"] = False, None
    if ED["bouton"]:
        rect, action = ED["bouton"]
        if rect.collidepoint(ED["x"], ED["y"]) and not TRANS["actif"]:
            _action_editeur(action)
    elif ED["cible"] and ED["bouge"]:
        sauvegarder_parametres()


def gerer_editeur(event):
    """Événements tactiles de l'éditeur de commandes (doigt et souris ; le 2e événement d'un même toucher est ignoré)."""
    if etat_actuel == ETAT_EDITEUR and not TRANS["actif"]:
        if event.type == pygame.FINGERDOWN:
            _debut_toucher(event.finger_id, event.x * LARGEUR, event.y * HAUTEUR)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not ED["drag"]:
            p = pos_ev(event)
            _debut_toucher("souris", p[0], p[1])
        elif event.type == pygame.FINGERMOTION and ED["drag"] and event.finger_id == ED["id"]:
            _mouvement_toucher(event.x * LARGEUR, event.y * HAUTEUR)
        elif event.type == pygame.MOUSEMOTION and ED["drag"] and ED["id"] == "souris":
            p = pos_ev(event)
            _mouvement_toucher(p[0], p[1])
    if ED["drag"] and ((event.type == pygame.MOUSEBUTTONUP and ED["id"] == "souris") or
                       (event.type == pygame.FINGERUP and event.finger_id == ED["id"])):
        _fin_toucher()


def dessiner_editeur():
    # Aperçu : le sol du jeu, l'interface (pause, radar, chrono) et les vraies commandes, aux positions réelles
    T = TAILLE_CASE
    for j in range(HAUTEUR // T + 1):
        for i in range(LARGEUR // T + 1):
            mur = (i * 7 + j * 13) % 6 == 0 and 0 < i < LARGEUR // T
            ecran.blit(tuile_mur(COULEUR_MUR, 0) if mur else tuile_sol(COULEUR_MUR, (i + j) % 2, 0), (i * T, j * T))
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (4, 5, 14, 110)), (0, 0))
    g = GRILLES_EDITEUR[ED["grille"]]
    if g:
        for x in range(0, LARGEUR, g):
            DRAW.line(ecran, (40, 60, 95), (x, 0), (x, HAUTEUR), 1)
        for y in range(0, HAUTEUR, g):
            DRAW.line(ecran, (40, 60, 95), (0, y), (LARGEUR, y), 1)

    DRAW.circle(ecran, (6, 12, 20), (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON)
    DRAW.circle(ecran, BLEU_CYBER, (RADAR_CENTRE_X, RADAR_CENTRE_Y), RADAR_RAYON, 3)
    tr_ = rendu_texte(police_petite, "RADAR", True, BLEU_CYBER)
    ecran.blit(tr_, (RADAR_CENTRE_X - tr_.get_width() // 2, RADAR_CENTRE_Y + RADAR_RAYON + 6))
    DRAW.circle(ecran, (10, 10, 20), (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON)
    DRAW.circle(ecran, BLEU_CYBER, (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON, 3)
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X - 9, BTN_PAUSE_Y - 10, 6, 20))
    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X + 3, BTN_PAUSE_Y - 10, 6, 20))
    chrono = pygame.Rect(LARGEUR // 2 - 130, 96, 260, 44)
    DRAW.rect(ecran, (8, 10, 20), chrono, border_radius=14)
    DRAW.rect(ecran, VERT_FLUO, chrono, 2, border_radius=14)
    tc_ = rendu_texte(police_bouton, "TEMPS : 125s", True, VERT_FLUO)
    ecran.blit(tc_, (chrono.centerx - tc_.get_width() // 2, chrono.centery - tc_.get_height() // 2))

    dessiner_commandes(JOY_CENTRE_X, JOY_CENTRE_Y, False)

    for nom in ("joy", "tir"):                                  # commande sélectionnée : cercle jaune + taille ; conflit : rouge
        cx, cy, r = centre_commande(nom)
        conflit = _en_conflit(nom)
        if ED["selection"] == nom or conflit:
            col = ROUGE_ALERTE if conflit else JAUNE_CYBER
            DRAW.circle(ecran, col, (cx, cy), r + 14, 3)
            texte = f"{int(DISPO[nom]['s'] * 100)} %" + ("  ·  chevauche l'interface" if conflit else "")
            tl = rendu_texte(police_petite, texte, True, col)
            ecran.blit(obtenir_voile(tl.get_width() + 16, 26, (5, 6, 16, 200)), (int(cx - tl.get_width() // 2 - 8), int(cy - r - 46)))
            ecran.blit(tl, (int(cx - tl.get_width() // 2), int(cy - r - 42)))

    ecran.blit(obtenir_voile(250, 392, (4, 5, 14, 205)), (8, 14))     # panneau de boutons (à gauche, comme sur PPSSPP)
    g_txt = "GRILLE : OFF" if not g else f"GRILLE : {g}"
    boutons = [("deplacer", "DÉPLACER", BLEU_CYBER, ED["mode"] == "deplacer"),
               ("taille", "REDIMENSIONNER", BLEU_CYBER, ED["mode"] == "taille"),
               ("grille", g_txt, VIOLET_CYBER, bool(g)),
               ("inverser", "INVERSER G/D", JAUNE_CYBER, False),
               ("reset", "RÉTABLIR", ROUGE_ALERTE, False),
               ("retour", "RETOUR", VERT_FLUO, False)]
    zones = []
    for k, (action, texte, couleur, actif) in enumerate(boutons):
        rect = pygame.Rect(24, 28 + k * 62, 220, 50)
        bouton_neon(rect, couleur, texte, police_petite, plein=actif)
        zones.append((rect, action))
    ED["zones"] = zones
    aide = "Touche une commande, puis glisse" if ED["mode"] == "deplacer" else "Touche une commande, puis glisse pour agrandir / réduire"
    ta = rendu_texte(police_petite, aide, True, (170, 180, 210))
    ecran.blit(obtenir_voile(ta.get_width() + 24, 30, (5, 6, 16, 190)), (LARGEUR // 2 - ta.get_width() // 2 - 12, HAUTEUR - 44))
    ecran.blit(ta, (LARGEUR // 2 - ta.get_width() // 2, HAUTEUR - 40))


# ==================== ÉCRANS DE FIN DE MISSION ====================
FIN = {"t0": 0, "etoiles": 0, "record": False, "conseil": ""}
DELAI_BOUTONS_FIN = 1100          # les boutons n'apparaissent (et ne réagissent) qu'après l'animation : pas d'appui accidentel
CONSEILS_DEFAITE = [
    "Reste en mouvement : les drones foncent tout droit sur toi.",
    "Maintiens TIR : le laser vise tout seul le drone le plus proche.",
    "Les potions jaunes ajoutent du temps au chrono.",
    "Le Boss lance des boules de feu : esquive-les, puis tire.",
    "Reste dans la zone violette jusqu'à 100% pour pirater le CORE.",
]
CONSEIL_BOUCLIER = "Passe par la BOUTIQUE : le bouclier encaisse des coups à ta place."
_alea_confettis = random.Random(11)
CONFETTIS = [(_alea_confettis.random(), _alea_confettis.uniform(0.10, 0.28), _alea_confettis.uniform(0, 6.28),
              _alea_confettis.choice([VERT_FLUO, JAUNE_CYBER, ROSE_SYNTH, CYAN_NEON, VIOLET_CYBER]), _alea_confettis.randint(7, 12))
             for _ in range(40)]


def fin_pret():
    return pygame.time.get_ticks() - FIN["t0"] >= DELAI_BOUTONS_FIN


def demarrer_ecran_fin(victoire):
    """Appelé une seule fois quand la mission se termine : prépare étoiles, record ou conseil."""
    FIN["t0"] = pygame.time.get_ticks()
    FIN["record"] = False
    if victoire:
        ratio = max(0, temps_restant_frames) / float(MISSION["duree"])
        etoiles = 3 if ratio >= 0.45 else (2 if ratio >= 0.20 else 1)
        cle = str(niveau_actuel)
        ancien = BOUTIQUE["etoiles"].get(cle, 0)
        FIN["record"] = 0 < ancien < etoiles
        if etoiles > ancien:
            BOUTIQUE["etoiles"][cle] = etoiles
        FIN["etoiles"] = etoiles
    else:
        choix = list(CONSEILS_DEFAITE)
        if STATS["bouclier"] == 0:
            choix += [CONSEIL_BOUCLIER] * 3
        FIN["conseil"] = random.choice(choix)


def _avancement(t, debut, duree):
    return max(0.0, min(1.0, (t - debut) / float(duree)))


def dessiner_etoile(cx, cy, r, couleur, plein=True):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    if plein:
        DRAW.polygon(ecran, couleur, pts)
        DRAW.polygon(ecran, (255, 245, 170), pts, 2)
    else:
        DRAW.polygon(ecran, (70, 80, 110), pts, 3)


def dessiner_confettis(t):
    nb = 40 if QUALITE["niveau"] >= 1 else 16
    for x0, vit, phase, couleur, taille in CONFETTIS[:nb]:
        y = (t * vit + phase * 200) % (HAUTEUR + 60) - 30
        x = x0 * LARGEUR + 28 * math.sin(t / 380.0 + phase)
        DRAW.rect(ecran, couleur, (int(x), int(y), taille, taille // 2 + 2))


def dessiner_parasites():
    """Lignes rouges qui sautent : effet de signal corrompu."""
    for _ in range(8 if QUALITE["niveau"] >= 1 else 4):
        y = random.randint(0, HAUTEUR)
        x = random.randint(0, LARGEUR - 100)
        DRAW.line(ecran, (random.randint(120, 255), 0, random.randint(20, 60)), (x, y), (x + random.randint(80, 420), y), random.randint(1, 3))


def _panneau_fin(couleur, y_haut, y_bas, avancement):
    """Panneau central qui s'ouvre en hauteur, avec un contour néon."""
    largeur = min(780, LARGEUR - 60)
    h = int((y_bas - y_haut) * lisser(avancement))
    if h < 8:
        return
    rect = pygame.Rect(LARGEUR // 2 - largeur // 2, (y_haut + y_bas) // 2 - h // 2, largeur, h)
    DRAW.rect(ecran, (7, 9, 20), rect, border_radius=min(18, h // 2))
    for i in range(5, 0, -1):
        DRAW.rect(ecran, eclaircir(couleur, (1 - i / 6.0) * 0.55), rect.inflate(i * 4, i * 4), 3, border_radius=min(18 + i * 2, (h + i * 4) // 2))
    DRAW.rect(ecran, couleur, rect, 3, border_radius=min(18, h // 2))


def dessiner_ecran_victoire():
    t = pygame.time.get_ticks() - FIN["t0"]
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (4, 12, 14, 170)), (0, 0))
    dessiner_confettis(t)
    y_btn = rect_bouton_suivant.y
    y_haut, y_bas = y_btn - 312, y_btn + 90
    _panneau_fin(VERT_FLUO, y_haut, y_bas, t / 420.0)
    if t < 380:
        return
    dessiner_titre_glitch("DATA SECURED !", police_victoire, cx, y_haut + 18)

    for i in range(3):                                           # étoiles qui apparaissent une à une
        p = _avancement(t, 560 + i * 220, 300)
        centre = (cx + (i - 1) * 92, y_haut + 138)
        if i >= FIN["etoiles"]:
            if p > 0:
                dessiner_etoile(centre[0], centre[1], 30, None, plein=False)
        elif p > 0:
            echelle = p * (1.0 + 0.3 * math.sin(p * math.pi))
            dessiner_etoile(centre[0], centre[1], max(2, int(34 * echelle)), JAUNE_CYBER)
    if FIN["record"] and t > 1300 and (t // 300) % 2 == 0:
        tr = rendu_texte(police_petite, "NOUVEAU RECORD !", True, JAUNE_CYBER)
        ecran.blit(tr, (cx - tr.get_width() // 2, y_haut + 184))

    r = MISSION["recompense"]
    if r and t > 900:
        valeur = int(r["total"] * lisser(_avancement(t, 900, 900)))      # le total « monte » comme un compteur
        t1 = rendu_texte(police_jeu, f"+{valeur} PIÈCES", True, JAUNE_CYBER)
        dessiner_piece(cx - t1.get_width() // 2 - 24, y_haut + 218, 12)
        ecran.blit(t1, (cx - t1.get_width() // 2, y_haut + 206))
        morceaux = [f"Mission {r['base']}", f"Temps {r['temps']}", f"Drones {r['drones']}"]
        if r["boss"]:
            morceaux.append(f"Boss {r['boss']}")
        t2 = rendu_texte(police_petite, "   ·   ".join(morceaux), True, (170, 180, 210))
        ecran.blit(t2, (cx - t2.get_width() // 2, y_haut + 242))
        if r["reduite"]:
            t3 = rendu_texte(police_petite, "Mission déjà réussie : gains réduits de moitié", True, JAUNE_CYBER)
            ecran.blit(t3, (cx - t3.get_width() // 2, y_haut + 266))
    if t >= DELAI_BOUTONS_FIN:
        bouton_neon(rect_bouton_rejouer, BLEU_CYBER, "REJOUE", police_bouton)
        bouton_neon(rect_bouton_suivant, VERT_FLUO, "SUIVANT", police_bouton, plein=True, pulse=True)


def dessiner_ecran_defaite():
    t = pygame.time.get_ticks() - FIN["t0"]
    cx = LARGEUR // 2
    ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (22, 0, 6, 190)), (0, 0))
    if (t // 90) % 3:
        dessiner_parasites()
    y_btn = rect_bouton_rejouer_defaite.y
    y_haut, y_bas = y_btn - 300, y_btn + 90
    _panneau_fin(ROUGE_ALERTE, y_haut, y_bas, t / 420.0)
    if t < 380:
        return
    dessiner_titre_glitch(message_defaite, police_victoire, cx, y_haut + 20)
    ts = rendu_texte(police_jeu, "MISSION ÉCHOUÉE", True, ROSE_SYNTH)
    ecran.blit(ts, (cx - ts.get_width() // 2, y_haut + 112))
    if t > 600:
        stats = rendu_texte(police_petite, f"Drones détruits : {MISSION['drones']}   ·   Hack : {int(jauge_hack)}%", True, (170, 180, 210))
        ecran.blit(stats, (cx - stats.get_width() // 2, y_haut + 152))
    r = MISSION["recompense"]
    if r and r["total"] > 0 and t > 800:
        t1 = rendu_texte(police_aide, f"+{r['total']} pièces récupérées", True, JAUNE_CYBER)
        dessiner_piece(cx - t1.get_width() // 2 - 24, y_haut + 196, 11)
        ecran.blit(t1, (cx - t1.get_width() // 2, y_haut + 184))
    if t > 1000 and FIN["conseil"]:
        tc = rendu_texte(police_petite, FIN["conseil"], True, BLEU_CYBER)
        ecran.blit(tc, (cx - tc.get_width() // 2, y_haut + 232))
    if t >= DELAI_BOUTONS_FIN:
        bouton_neon(rect_bouton_rejouer_defaite, BLEU_CYBER, "REJOUER", police_bouton)
        bouton_neon(rect_bouton_quitter_defaite, ROUGE_ALERTE, "QUITTER", police_bouton)


# ==================== ÉCRAN DE DÉMARRAGE ====================
def _tache_vide():
    pass


def _tache_ville():
    global _tuile_ville
    if _tuile_ville is None:
        _tuile_ville = construire_tuile_ville()
    if PARAMS["dof"]:
        obtenir_tuile_ville_floue()


def _tache_menu():
    global _fond_menu_surface
    if _fond_menu_surface is None:
        _fond_menu_surface = construire_fond_menu()


def _tache_lueurs():
    for rayon in (24, 30, 36, 42, 56, 84, 110):
        for couleur in (BLEU_CYBER, ROSE_SYNTH, VIOLET_CYBER, ROUGE_ALERTE, JAUNE_CYBER, VERT_FLUO, CYAN_NEON, ORANGE_MEC):
            obtenir_halo(rayon, couleur, 0.8)


def _tache_labyrinthe():
    for masque in range(16):
        tuile_mur(COULEUR_MUR, masque)
        for variante in (0, 1):
            tuile_sol(COULEUR_MUR, variante, masque)


def _tache_textes():
    for texte in ("COMMENCER", "GUIDE TACTIQUE", "BOUTIQUE"):
        rendu_texte(police_bouton, texte, True, NOIR_ESPACE)
        rendu_texte(police_bouton, texte, True, ROSE_SYNTH)
    for texte in ("MODE INFINI", "DATA SECURED !", "MISSION ÉCHOUÉE"):
        rendu_texte(police_jeu, texte, True, ROSE_SYNTH)


ETAPES_DEMARRAGE = [
    ("Initialisation du système", _tache_vide),
    ("Génération de la ville futuriste", _tache_ville),
    ("Calibrage du décor du menu", _tache_menu),
    ("Compilation des lueurs néon", _tache_lueurs),
    ("Préparation du labyrinthe", _tache_labyrinthe),
    ("Synchronisation du profil et de la boutique", _tache_textes),
    ("Connexion au réseau neuronal", _tache_vide),
]
DUREE_ETAPE_DEMARRAGE = 430        # ms par étape (≈ 3 s au total) ; chaque étape fait un vrai préchargement


def dessiner_grille_demarrage(t_ms, horizon):
    cx = LARGEUR // 2
    for k in range(-16, 17):
        DRAW.line(ecran, (90, 20, 130), (cx + k * 10, horizon), (cx + k * (LARGEUR // 11), HAUTEUR), 1)
    decal = (t_ms / 1400.0) % 1.0
    for i in range(12):
        z = (i + decal) / 12.0
        y = horizon + int((HAUTEUR - horizon) * z ** 2.2)
        DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.12 + 0.55 * z), (0, y), (LARGEUR, y), 1 if z < 0.6 else 2)


async def ecran_de_demarrage():
    """Logo FlexPlay, titre du jeu et barre de chargement pendant que les décors sont réellement préparés."""
    n = len(ETAPES_DEMARRAGE)
    t_debut = pygame.time.get_ticks()
    derniere = -1
    t_pret = None
    cx = LARGEUR // 2
    horizon = int(HAUTEUR * 0.60)
    bw = min(520, LARGEUR - 120)
    bx, by = cx - bw // 2, HAUTEUR - 70
    while True:
        await asyncio.sleep(0)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                EXTRA["_essai"] = 0
                sauvegarder_parametres()
                pygame.quit()
                sys.exit()
        t = pygame.time.get_ticks() - t_debut
        etape = min(n - 1, int(t / DUREE_ETAPE_DEMARRAGE))
        if derniere < etape:                       # une nouvelle étape commence : on fait son vrai travail
            derniere = etape
            ETAPES_DEMARRAGE[etape][1]()
        fini = t >= n * DUREE_ETAPE_DEMARRAGE
        if fini and t_pret is None:
            t_pret = t
        avancement = min(1.0, t / float(n * DUREE_ETAPE_DEMARRAGE))

        ecran.fill((4, 5, 14))
        dessiner_halo(cx, horizon, 260, (110, 30, 170), 0.55)
        dessiner_grille_demarrage(t, horizon)
        dessiner_titre_glitch("FLEXPLAY", police_titre, cx, int(HAUTEUR * 0.10))
        ts = rendu_texte(police_petite, "présente", True, BLEU_CYBER)
        ecran.blit(ts, (cx - ts.get_width() // 2, int(HAUTEUR * 0.10) + 78))
        if t > 900:
            dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, cx, int(HAUTEUR * 0.33))
        if t > 1300:
            tm = rendu_texte(police_jeu, "MODE INFINI", True, ROSE_SYNTH)
            ecran.blit(tm, (cx - tm.get_width() // 2, int(HAUTEUR * 0.33) + 84))

        message = "Système prêt" if fini else ETAPES_DEMARRAGE[etape][0] + "..."
        tx = rendu_texte(police_aide, message, True, VERT_FLUO if fini else BLANC_NEON)
        ecran.blit(tx, (cx - tx.get_width() // 2, by - 44))
        DRAW.rect(ecran, (16, 20, 40), (bx, by, bw, 12), border_radius=6)
        rempli = int(bw * avancement)
        if rempli > 4:
            DRAW.rect(ecran, BLEU_CYBER, (bx, by, rempli, 12), border_radius=min(6, rempli // 2))
            DRAW.rect(ecran, (170, 235, 255), (bx + 2, by + 2, max(2, rempli - 4), 3), border_radius=1)
            dessiner_halo(bx + rempli, by + 6, 34, BLEU_CYBER, 0.8)
        DRAW.rect(ecran, eclaircir(BLEU_CYBER, 0.55), (bx, by, bw, 12), 2, border_radius=6)
        pct = rendu_texte(police_petite, f"{int(avancement * 100)}%", True, BLEU_CYBER)
        ecran.blit(pct, (cx - pct.get_width() // 2, by + 18))
        cr = rendu_texte(police_petite, "© 2026 FlexPlay", True, (150, 160, 195))
        ecran.blit(cr, (LARGEUR - cr.get_width() - 24, HAUTEUR - 30))

        if VERSION_MODIFIEE:
            dessiner_filigrane()
        if t_pret is not None and t - t_pret > 350:          # fermeture du rideau, puis le menu s'ouvre derrière
            dessiner_rideau(int((LARGEUR // 2 + 2) * lisser((t - t_pret - 350) / 400.0)))
            if t - t_pret > 750:
                break
        pygame.display.flip()
        clock.tick(60)

    DEMARRAGE["actif"] = False
    TRANS.update(actif=True, phase=2, t0=pygame.time.get_ticks(), duree=0.0, cible=None)
    LOGIQUE["t"] = _time.perf_counter()


# 7. ASSETS D'EFFETS PRÉ-CALCULÉS
def creer_disque_translucide(rayon, couleur_rgba):
    s = pygame.Surface((rayon * 2 + 12, rayon * 2 + 12), pygame.SRCALPHA)
    DRAW.circle(s, couleur_rgba, (rayon + 6, rayon + 6), rayon)
    return s


def construire_vignette():
    """Assombrit doucement les bords de l'écran (calculée une seule fois, appliquée en multiplication)."""
    pw, ph = max(2, LARGEUR // 10), max(2, HAUTEUR // 10)
    petite = pygame.Surface((pw, ph))
    for y in range(ph):
        for x in range(pw):
            nx = (x / float(pw - 1) - 0.5) * 2
            ny = (y / float(ph - 1) - 0.5) * 2
            d = math.sqrt(nx * nx * 0.8 + ny * ny)
            f = 1.0 - 0.65 * max(0.0, min(1.0, (d - 0.55) / 0.75)) ** 1.6
            petite.set_at((x, y), (int(255 * f), int(255 * f), int(255 * min(1.0, f * 1.05))))
    return pygame.transform.smoothscale(petite, (LARGEUR, HAUTEUR)).convert()


SURF_SOCLE_JOY = creer_disque_translucide(JOY_RAYON_SOCLE, (10, 30, 45, 85))
SURF_BTN_TIR = creer_disque_translucide(BTN_TIR_RAYON, (70, 0, 25, 95))
VIGNETTE = None


def obtenir_vignette():
    global VIGNETTE
    if VIGNETTE is None:
        VIGNETTE = construire_vignette()
    return VIGNETTE


charger_parametres()
appliquer_parametres()
charger_boutique()
recalculer_stats()
appliquer_skin()
async def main():
    global DRAW, ECHELLE, _cache_boss, _cache_drones, _cible, _dt_logique, _echelle_active, _ecoule, _ecran_reel, _k_logique, _maintenant, _pas, _tm0, _tm1, _tm2, _tm3, ang, ang_drone, ang_orbite, ang_q, angle_affichage_boss, angle_arrondi_boss, angle_boss, angle_visée_x, angle_visée_y, astuce, b, bh, boss_angle_precedent, boss_fx_faite, boss_surface_cache, boss_vaincu, boss_vie, boss_x, boss_y, boule, bw, bx, bx0, bx_e, bx_ecran, by, by0, by_e, by_ecran, case, cbx, cby, centre_avatar, cfx, cfy, ci, cible, clic_detecte, clic_x, clic_y, clignote, col_sortie, colonne_max, colonne_min, core_accessible, couleur_aura_boss, couleur_bordure, couleur_ligne, couleur_lueur_core, couleur_node, couleur_timer, curseur, cx, cy, d, d_boss, d_rep, db, decal_x, decal_y, defil_max, defilement_niveaux, delai_max, delai_min, demi, dernier_x_glissement_niveaux, dir_x, dir_y, dist, dist_dir, dist_min, drone_rot, dx, dy, ecran, en_pause, ennemis_restants_a_spawner, espacement_infos, est_boss_node, etat_actuel, event, ex, ex_spawn, ey_spawn, fps_bas_consecutifs, frames_total, fx_ecran, fy_ecran, glissement_niveaux_actif, gris_credit, hack_reussi, haut_piste, hauteur_contenu, hauteur_visible, id_touch_joystick, id_touch_tir, idx, idx_max_affiche, idx_max_clic, idx_min_affiche, idx_min_clic, img_joueur_actuel, index_nationalite, indication_niveaux, indice, info_drones, jauge_hack, joueur_x, joueur_y, joystick_actif, jx_e, jy_e, k_cadre, k_seg, k_traine, largeur_barre_boss, largeur_rempli, largeur_v, lc, lg, li, ligne_max, ligne_min, lignes, lignes_infos, lint, long_piste, long_pouce, lr, lueurs, lx, ly, manette_x, manette_y, masque, message_defaite, minuteur_cadence_tir, minuteur_potion, minuteur_spawn, minuteur_tir_boss, mort_fx_faite, ms, musique_lancee, nb_colonnes_carte, nb_lignes_carte, niveau_max_atteint, niveau_sauvegarde_affichage, ombres_actives, ox, oy, p_core, p_sortie, panneau_largeur, panneau_x, partie_gagnee, partie_perdue, pas, photo_profil_surface, points_chemin, police_l, police_texte, potion, pulsation, pulsation_feu, pulsation_node, pulse_boss, px_ecran, px_potion, py_ecran, py_potion, r_bouclier, ratio_vie_boss, rayon_affiche, rect_timer, rx, ry, saisie_pseudo_active, sec, secondes_restantes, surf_nat, surf_pseudo, t_ms, tag, tag_boss, tb, temps_restant_frames, texte_ligne, texte_node, texte_pseudo, texte_timer, th_hack, ti, ti_icone, til, tir_maintenu, tirer_balle, tl, tn, tp, tp5, txt_vie_boss, type_glissement_niveaux, victoire_fx_faite, vitesse_deplacement_boss, vx, vy, x_actuel_glissement, x_barre, x_barre_boss, x_node, x_node_clic, x_v, xk, y_depart_infos, y_node, y_node_clic, y_nouveau, y_pouce, y_zone, yy
    await ecran_de_demarrage()
    _cache_drones = {}
    _cache_boss = {}
    frames_total = 0
    fps_bas_consecutifs = 0
    mort_fx_faite = False
    victoire_fx_faite = False
    boss_fx_faite = False

    # LOOP
    while True:
        await asyncio.sleep(0)
        _tm0 = _time.perf_counter()
        dx, dy = 0, 0
        clic_detecte, tirer_balle = False, False
        clic_x, clic_y = 0, 0

        for event in pygame.event.get():
            if TRANS["actif"] and event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN, pygame.MOUSEMOTION,
                                                  pygame.FINGERMOTION, pygame.TEXTINPUT, pygame.KEYDOWN):
                continue
            _calibrer_souris(event)
            if event.type == pygame.QUIT:
                EXTRA["_essai"] = 0
                sauvegarder_parametres()
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clic_detecte = True
                clic_x, clic_y = pos_ev(event)
                if etat_actuel == ETAT_JEU and rect_bouton_pause.collidepoint(clic_x, clic_y) and not partie_gagnee and not partie_perdue:
                    basculer_pause()
                elif etat_actuel == ETAT_JEU and not en_pause and rect_tir_tactile.collidepoint(clic_x, clic_y):
                    tirer_balle = True
                    tir_maintenu = True
                    minuteur_cadence_tir = 0
                elif etat_actuel == ETAT_NIVEAUX:
                    glissement_niveaux_actif = True
                    type_glissement_niveaux = "souris"
                    dernier_x_glissement_niveaux = clic_x
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                tir_maintenu = False
                if type_glissement_niveaux == "souris":
                    glissement_niveaux_actif = False
                    type_glissement_niveaux = None
            elif event.type == pygame.MOUSEMOTION and glissement_niveaux_actif and type_glissement_niveaux == "souris":
                defilement_niveaux += pos_ev(event)[0] - dernier_x_glissement_niveaux
                defilement_niveaux = min(0, defilement_niveaux)
                dernier_x_glissement_niveaux = pos_ev(event)[0]
            elif event.type == pygame.FINGERDOWN:
                clic_detecte = True
                clic_x, clic_y = event.x * LARGEUR, event.y * HAUTEUR
                if etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue:
                    if rect_bouton_pause.collidepoint(clic_x, clic_y):
                        basculer_pause()
                    elif not en_pause and rect_tir_tactile.collidepoint(clic_x, clic_y):
                        tirer_balle = True
                        tir_maintenu = True
                        id_touch_tir = event.finger_id
                        minuteur_cadence_tir = 0
                    elif not en_pause and math.hypot(clic_x - JOY_CENTRE_X, clic_y - JOY_CENTRE_Y) <= JOY_RAYON_SOCLE + 40:
                        joystick_actif, id_touch_joystick = True, event.finger_id
                        placer_manette(clic_x, clic_y)
                elif etat_actuel == ETAT_NIVEAUX:
                    glissement_niveaux_actif = True
                    type_glissement_niveaux = event.finger_id
                    dernier_x_glissement_niveaux = clic_x

            elif event.type == pygame.TEXTINPUT and saisie_pseudo_active:
                if len(profil["pseudo"]) < 14:
                    profil["pseudo"] += event.text
            elif event.type == pygame.KEYDOWN and saisie_pseudo_active:
                if event.key == pygame.K_BACKSPACE:
                    profil["pseudo"] = profil["pseudo"][:-1]
                elif event.key == pygame.K_RETURN:
                    saisie_pseudo_active = False
                    pygame.key.stop_text_input()

            if partie_gagnee and clic_detecte and fin_pret():
                if rect_bouton_rejouer.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_bouton_suivant.collidepoint(clic_x, clic_y):
                    lancer_transition(("suivant",), DUREE_CHARGEMENT_RAPIDE)

            if partie_perdue and clic_detecte and fin_pret():
                if rect_bouton_rejouer_defaite.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_bouton_quitter_defaite.collidepoint(clic_x, clic_y):
                    lancer_transition(("quitter_partie",))

            if en_pause and clic_detecte:
                if rect_pause_continuer.collidepoint(clic_x, clic_y):
                    en_pause = False
                elif rect_pause_rejouer.collidepoint(clic_x, clic_y):
                    lancer_transition(("rejouer",), DUREE_CHARGEMENT_RAPIDE)
                elif rect_pause_params.collidepoint(clic_x, clic_y):
                    lancer_transition(("params", ETAT_JEU), DUREE_CHARGEMENT_RAPIDE)
                elif rect_pause_quitter.collidepoint(clic_x, clic_y):
                    lancer_transition(("quitter_partie",))

            if event.type == pygame.FINGERMOTION and joystick_actif and event.finger_id == id_touch_joystick:
                placer_manette(event.x * LARGEUR, event.y * HAUTEUR)

            if event.type == pygame.FINGERMOTION and glissement_niveaux_actif and event.finger_id == type_glissement_niveaux:
                x_actuel_glissement = event.x * LARGEUR
                defilement_niveaux += x_actuel_glissement - dernier_x_glissement_niveaux
                defilement_niveaux = min(0, defilement_niveaux)
                dernier_x_glissement_niveaux = x_actuel_glissement

            if event.type == pygame.FINGERUP and joystick_actif and event.finger_id == id_touch_joystick:
                joystick_actif, id_touch_joystick = False, None
                manette_x, manette_y = JOY_CENTRE_X, JOY_CENTRE_Y

            if event.type == pygame.FINGERUP and glissement_niveaux_actif and event.finger_id == type_glissement_niveaux:
                glissement_niveaux_actif = False
                type_glissement_niveaux = None

            if event.type == pygame.FINGERUP and event.finger_id == id_touch_tir:
                tir_maintenu = False
                id_touch_tir = None

            # Guide tactique : on fait défiler le texte en glissant le doigt vers le haut / le bas
            if etat_actuel == ETAT_AIDE:
                if event.type == pygame.FINGERDOWN:
                    AIDE["drag"], AIDE["id"], AIDE["y"] = True, event.finger_id, event.y * HAUTEUR
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not AIDE["drag"]:
                    AIDE["drag"], AIDE["id"], AIDE["y"] = True, "souris", pos_ev(event)[1]
                elif event.type == pygame.FINGERMOTION and AIDE["drag"] and event.finger_id == AIDE["id"]:
                    y_nouveau = event.y * HAUTEUR
                    AIDE["scroll"] += y_nouveau - AIDE["y"]
                    AIDE["y"] = y_nouveau
                elif event.type == pygame.MOUSEMOTION and AIDE["drag"] and AIDE["id"] == "souris":
                    AIDE["scroll"] += pos_ev(event)[1] - AIDE["y"]
                    AIDE["y"] = pos_ev(event)[1]
            if (event.type == pygame.MOUSEBUTTONUP and AIDE["id"] == "souris") or \
                    (event.type == pygame.FINGERUP and event.finger_id == AIDE["id"]):
                AIDE["drag"], AIDE["id"] = False, None

            # Écrans à liste (Paramètres, Boutique) : glisser = défiler, toucher = agir
            gerer_liste_tactile(PAR, event, ETAT_PARAMS, traiter_tap_parametres)
            gerer_liste_tactile(BQ, event, ETAT_BOUTIQUE, traiter_tap_boutique)
            gerer_editeur(event)

        # --- Nombre de pas de logique à effectuer ce tour (temps réel)
        _maintenant = _time.perf_counter()
        _dt_logique = min(0.25, _maintenant - LOGIQUE["t"])
        LOGIQUE["t"] = _maintenant
        _k_logique = 1
        if etat_actuel == ETAT_JEU and not en_pause and not partie_gagnee and not partie_perdue and not TRANS["actif"]:
            LOGIQUE["acc"] += _dt_logique
            _k_logique = max(1, min(4, int(round(LOGIQUE["acc"] / 0.016667))))
            LOGIQUE["acc"] -= _k_logique * 0.016667
            if abs(LOGIQUE["acc"]) > 0.05:
                LOGIQUE["acc"] = 0.0
        else:
            LOGIQUE["acc"] = 0.0
        LOGIQUE["k"] = _k_logique

        # --- Transition en cours : le rideau se ferme, l'action est appliquée derrière l'écran de chargement, puis il s'ouvre
        if TRANS["actif"]:
            _ecoule = pygame.time.get_ticks() - TRANS["t0"]
            if TRANS["phase"] == 0 and _ecoule >= DUREE_COUVRIR * 1000.0:
                TRANS["phase"], TRANS["t0"] = 1, pygame.time.get_ticks()
                _cible = TRANS["cible"]
                TRANS["cible"] = None
                if _cible is not None:
                    if _cible[0] == "etat":
                        etat_actuel = _cible[1]
                        if etat_actuel == ETAT_AIDE:
                            AIDE["scroll"], AIDE["drag"], AIDE["id"] = 0.0, False, None
                        elif etat_actuel == ETAT_BOUTIQUE:
                            BQ.update(scroll=0.0, drag=False, id=None, msg="")
                        elif etat_actuel == ETAT_EDITEUR:
                            ED.update(drag=False, id=None, cible=None, bouton=None, selection=None, mode="deplacer")
                    elif _cible[0] == "params":
                        PAR["origine"], PAR["scroll"], PAR["drag"], PAR["id"] = _cible[1], 0.0, False, None
                        etat_actuel = ETAT_PARAMS
                    elif _cible[0] == "retour_jeu":
                        etat_actuel = ETAT_JEU
                    elif _cible[0] == "commencer":
                        niveau_max_atteint = charger_progression()
                        defilement_niveaux = min(0, LARGEUR / 2 - NIVEAU_MARGE_GAUCHE - niveau_max_atteint * NIVEAU_NODE_ESPACEMENT)
                        etat_actuel = ETAT_NIVEAUX
                    elif _cible[0] == "niveau":
                        reinitialiser_partie(False, niveau_cible=_cible[1])
                        etat_actuel = ETAT_JEU
                        en_pause = False
                        if MUSIQUE_ACTIVE and not musique_lancee:
                            pygame.mixer.music.play(-1)
                            musique_lancee = True
                            appliquer_audio()
                    elif _cible[0] == "quitter_partie":
                        reinitialiser_partie(False)
                        etat_actuel = ETAT_MENU
                        en_pause = False
                    elif _cible[0] == "rejouer":
                        reinitialiser_partie(False)
                        en_pause = False
                    elif _cible[0] == "suivant":
                        reinitialiser_partie(True)
                        en_pause = False
            elif TRANS["phase"] == 1 and _ecoule >= TRANS["duree"]:
                TRANS["phase"], TRANS["t0"] = 2, pygame.time.get_ticks()
            elif TRANS["phase"] == 2 and _ecoule >= DUREE_REVELER * 1000.0:
                TRANS["actif"] = False

        if etat_actuel == ETAT_MENU and clic_detecte:
            if rect_bouton_jouer.collidepoint(clic_x, clic_y):
                lancer_transition(("commencer",))
            elif rect_bouton_aide.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_AIDE))
            elif rect_bouton_boutique.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_BOUTIQUE))
            elif rect_icone_profil.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_PROFIL))
            elif rect_icone_infos.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_INFOS))
            elif rect_icone_params.collidepoint(clic_x, clic_y):
                lancer_transition(("params", ETAT_MENU))
        elif etat_actuel == ETAT_NIVEAUX and clic_detecte:
            if rect_retour_niveaux.collidepoint(clic_x, clic_y):
                lancer_transition(("etat", ETAT_MENU))
            else:
                idx_min_clic = max(0, int((-defilement_niveaux - 150) / NIVEAU_NODE_ESPACEMENT))
                idx_max_clic = min(niveau_max_atteint + 30, int((LARGEUR - defilement_niveaux + 150) / NIVEAU_NODE_ESPACEMENT))
                for idx in range(idx_min_clic, idx_max_clic + 1):
                    if idx > niveau_max_atteint:
                        continue
                    x_node_clic = NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux
                    y_node_clic = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                    if math.hypot(clic_x - x_node_clic, clic_y - y_node_clic) <= NIVEAU_NODE_RAYON + 10:
                        lancer_transition(("niveau", idx))
                        break
        elif etat_actuel == ETAT_AIDE and clic_detecte and rect_bouton_retour.collidepoint(clic_x, clic_y):
            lancer_transition(("etat", ETAT_MENU))
        elif etat_actuel == ETAT_INFOS and clic_detecte and rect_retour_infos.collidepoint(clic_x, clic_y):
            lancer_transition(("etat", ETAT_MENU))
        elif etat_actuel == ETAT_PROFIL and clic_detecte:
            if rect_champ_pseudo.collidepoint(clic_x, clic_y):
                saisie_pseudo_active = True
                pygame.key.start_text_input()
            elif rect_fleche_gauche.collidepoint(clic_x, clic_y):
                index_nationalite = (index_nationalite - 1) % len(NATIONALITES)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_fleche_droite.collidepoint(clic_x, clic_y):
                index_nationalite = (index_nationalite + 1) % len(NATIONALITES)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_recharger_photo.collidepoint(clic_x, clic_y):
                photo_profil_surface = charger_photo_profil()
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_sauvegarder_profil.collidepoint(clic_x, clic_y):
                profil["nationalite"] = NATIONALITES[index_nationalite]
                sauvegarder_profil(profil)
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
            elif rect_retour_profil.collidepoint(clic_x, clic_y):
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
                lancer_transition(("etat", ETAT_MENU))
            else:
                saisie_pseudo_active = False
                pygame.key.stop_text_input()
        elif etat_actuel == ETAT_JEU and not partie_gagnee and not partie_perdue and not en_pause and not TRANS["actif"]:
            # Chaque tour de boucle fait autant de pas de logique (1/60 s) que de temps réellement écoulé : la vitesse du jeu reste normale
            for _pas in range(_k_logique):
                if _pas > 0 and (partie_perdue or partie_gagnee):
                    break
                temps_restant_frames -= 1
                if ETAT_JOUEUR["invuln"] > 0:
                    ETAT_JOUEUR["invuln"] -= 1
                if temps_restant_frames <= 0:
                    partie_perdue = True
                    message_defaite = "TEMPS ÉCOULÉ"
                    if SON_ACTIF:
                        son_echec.play()

                if niveau_actuel >= NIVEAU_APPARITION_POTIONS:
                    minuteur_potion -= 1
                    if minuteur_potion <= 0 and len(liste_potions) < 3:
                        px_potion, py_potion = position_spawn_potion(CARTE)
                        liste_potions.append([px_potion, py_potion])
                        minuteur_potion = random.randint(300, 600)

                for potion in liste_potions[:]:
                    if math.hypot(joueur_x - potion[0], joueur_y - potion[1]) < (TAILLE_PERSO / 2 + 25):
                        liste_potions.remove(potion)
                        temps_restant_frames = min(temps_restant_frames + BONUS_POTION_FRAMES + STATS["potion"], plafond_temps_frames)

                if ennemis_restants_a_spawner > 0:
                    minuteur_spawn -= 1
                    if minuteur_spawn <= 0:
                        ex_spawn, ey_spawn = position_spawn_ennemi(CARTE)
                        liste_ennemis.append([ex_spawn, ey_spawn, vitesse_ennemis_niveau])
                        ennemis_restants_a_spawner -= 1
                        delai_min, delai_max = calcul_delais_spawn(niveau_actuel)
                        minuteur_spawn = random.randint(delai_min, delai_max)

                if joystick_actif:
                    vx, vy = manette_x - JOY_CENTRE_X, manette_y - JOY_CENTRE_Y
                    dist = math.hypot(vx, vy)
                    if dist > CTRL["dz"]:
                        dx, dy = (vx / dist) * joueur_vitesse, (vy / dist) * joueur_vitesse
                        angle_visée_x, angle_visée_y = vx / dist, vy / dist

                        if MODE_GRAPHIQUE == "REALISTE":
                            if vx < -15:
                                img_joueur_actuel = img_joueur_gauche
                            elif vx > 15:
                                img_joueur_actuel = img_joueur_droite

                if dx != 0 and not check_collision_murs(joueur_x + dx, joueur_y):
                    joueur_x += dx
                if dy != 0 and not check_collision_murs(joueur_x, joueur_y + dy):
                    joueur_y += dy
                if (dx != 0 or dy != 0) and QUALITE["niveau"] >= 1:
                    creer_propulsion(joueur_x, joueur_y, dx, dy, BLEU_CYBER)

                if tir_maintenu:
                    if minuteur_cadence_tir <= 0:
                        tirer_balle = True
                        minuteur_cadence_tir = STATS["cadence"]
                    else:
                        minuteur_cadence_tir -= 1

                if tirer_balle:
                    if SON_ACTIF:
                        son_tir.play()
                    cible, dist_min = None, 900
                    for ex in liste_ennemis:
                        d = math.hypot(ex[0] - joueur_x, ex[1] - joueur_y)
                        if d < dist_min:
                            dist_min, cible = d, ex
                    if boss_actif and not boss_vaincu:
                        d_boss = math.hypot(boss_x - joueur_x, boss_y - joueur_y)
                        if d_boss < dist_min:
                            dist_min, cible = d_boss, [boss_x, boss_y]
                    if cible:
                        bx, by = cible[0] - joueur_x, cible[1] - joueur_y
                        db = math.hypot(bx, by)
                        balles.append([joueur_x, joueur_y, (bx / db) * 13, (by / db) * 13, STATS["perfo"]])
                    else:
                        balles.append([joueur_x, joueur_y, angle_visée_x * 13, angle_visée_y * 13, STATS["perfo"]])

                # CORRECTION DE LA FUITE DE MÉMOIRE DES BALLES
                for b in balles[:]:
                    b[0] += b[2]
                    b[1] += b[3]
                    cbx, cby = int(b[0] // TAILLE_CASE), int(b[1] // TAILLE_CASE)
                    # Suppression si hors de la carte OU si ça touche un mur
                    if not (0 <= cbx < len(CARTE[0]) and 0 <= cby < len(CARTE)):
                        balles.remove(b)
                    elif CARTE[cby][cbx] == 1:
                        creer_etincelles(b[0], b[1], LASER["main"], 5)
                        balles.remove(b)

                for ex in liste_ennemis[:]:
                    ang = math.atan2(joueur_y - ex[1], joueur_x - ex[0]) + random.uniform(-0.08, 0.08)
                    ex[0] += math.cos(ang) * ex[2]
                    ex[1] += math.sin(ang) * ex[2]
                    if QUALITE["niveau"] >= 1 and len(liste_ennemis) <= 8 and random.random() < 0.3:
                        creer_propulsion(ex[0], ex[1], math.cos(ang) * ex[2], math.sin(ang) * ex[2], ROUGE_ALERTE)
                    for b in balles[:]:
                        if math.hypot(ex[0] - b[0], ex[1] - b[1]) < 28:
                            if ex in liste_ennemis:
                                liste_ennemis.remove(ex)
                                MISSION["drones"] += 1
                                creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 24, 7.0, 3.0)
                                if SON_ACTIF:
                                    son_explosion.play()
                            if b in balles:
                                if b[4] > 0:
                                    b[4] -= 1          # tir perforant : le laser continue sa route
                                else:
                                    balles.remove(b)
                    if not partie_perdue and math.hypot(joueur_x - ex[0], joueur_y - ex[1]) < (TAILLE_PERSO / 2 + 16):
                        if not subir_degats("SYSTÈME CORROMPU") and ex in liste_ennemis:
                            liste_ennemis.remove(ex)          # le choc détruit le drone
                            MISSION["drones"] += 1
                            creer_explosion(ex[0], ex[1], ROUGE_ALERTE, 24, 7.0, 3.0)

                if boss_actif and not boss_vaincu and not partie_perdue and not partie_gagnee:
                    angle_boss = math.atan2(joueur_y - boss_y, joueur_x - boss_x) + random.uniform(-0.05, 0.05)
                    vitesse_deplacement_boss = 1.6
                    boss_x += math.cos(angle_boss) * vitesse_deplacement_boss
                    boss_y += math.sin(angle_boss) * vitesse_deplacement_boss

                    for b in balles[:]:
                        if math.hypot(boss_x - b[0], boss_y - b[1]) < RAYON_CORPS_BOSS:
                            boss_vie -= STATS["degats"]
                            creer_etincelles(b[0], b[1], ORANGE_MEC, 7)
                            if b in balles:
                                balles.remove(b)
                            if boss_vie <= 0:
                                boss_vie = 0
                                boss_vaincu = True
                                if SON_ACTIF:
                                    son_victoire.play()

                    minuteur_tir_boss -= 1
                    if minuteur_tir_boss <= 0 and not boss_vaincu:
                        dir_x, dir_y = joueur_x - boss_x, joueur_y - boss_y
                        dist_dir = math.hypot(dir_x, dir_y)
                        if dist_dir > 0:
                            boules_feu.append([boss_x, boss_y, (dir_x / dist_dir) * 5.5, (dir_y / dist_dir) * 5.5])
                        minuteur_tir_boss = random.randint(60, 90)

                    if not partie_perdue and math.hypot(joueur_x - boss_x, joueur_y - boss_y) < (TAILLE_PERSO / 2 + RAYON_CORPS_BOSS):
                        if not subir_degats("ÉCRASÉ PAR LE BOSS"):
                            d_rep = max(1.0, math.hypot(boss_x - joueur_x, boss_y - joueur_y))
                            boss_x += (boss_x - joueur_x) / d_rep * 170          # le bouclier repousse le Boss
                            boss_y += (boss_y - joueur_y) / d_rep * 170

                for boule in boules_feu[:]:
                    boule[0] += boule[2]
                    boule[1] += boule[3]
                    cfx, cfy = int(boule[0] // TAILLE_CASE), int(boule[1] // TAILLE_CASE)
                    if not (0 <= cfx < len(CARTE[0]) and 0 <= cfy < len(CARTE)):
                        boules_feu.remove(boule)
                        continue
                    if CARTE[cfy][cfx] == 1:
                        boules_feu.remove(boule)
                        continue
                    if not partie_perdue and math.hypot(joueur_x - boule[0], joueur_y - boule[1]) < (TAILLE_PERSO / 2 + 14):
                        subir_degats("BRÛLÉ PAR LE BOSS")
                        boules_feu.remove(boule)

                cx, cy = int(joueur_x // TAILLE_CASE), int(joueur_y // TAILLE_CASE)
                if 0 <= cx < len(CARTE[0]) and 0 <= cy < len(CARTE):
                    core_accessible = (not boss_actif) or boss_vaincu
                    if CARTE[cy][cx] == 2 and not hack_reussi and core_accessible:
                        jauge_hack = min(jauge_hack + 0.7 * STATS["hack"], 100.0)
                        if jauge_hack >= 100.0:
                            hack_reussi = True
                    elif not hack_reussi:
                        jauge_hack = max(jauge_hack - 0.3, 0.0)
                    if CARTE[cy][cx] == 3 and hack_reussi and not partie_gagnee:
                        partie_gagnee = True
                        if SON_ACTIF:
                            son_victoire.play()
                tirer_balle = False          # un appui ne tire qu'une seule fois, même s'il y a plusieurs pas

        _tm1 = _time.perf_counter()
        if etat_actuel == ETAT_JEU:
            if partie_perdue and not mort_fx_faite:
                creer_explosion(joueur_x, joueur_y, ROUGE_ALERTE, 46, 9.0, 12.0)
                mort_fx_faite = True
                demarrer_ecran_fin(False)
                accorder_recompense(False)
            elif not partie_perdue:
                mort_fx_faite = False
            if partie_gagnee and not victoire_fx_faite:
                creer_explosion(joueur_x, joueur_y, VERT_FLUO, 50, 8.0, 4.0)
                victoire_fx_faite = True
                demarrer_ecran_fin(True)
                accorder_recompense(True)
            elif not partie_gagnee:
                victoire_fx_faite = False
            if boss_actif and boss_vaincu and not boss_fx_faite:
                creer_explosion(boss_x, boss_y, VIOLET_CYBER, 90, 12.0, 14.0)
                creer_explosion(boss_x, boss_y, ORANGE_MEC, 60, 8.0, 0.0)
                boss_fx_faite = True
            elif not boss_vaincu:
                boss_fx_faite = False

        # Mises à jour qui doivent avoir lieu à CHAQUE tour (même si on saute le dessin) : particules et caméra
        if etat_actuel == ETAT_JEU:
            if not en_pause:
                mettre_a_jour_fx()
            if abs(CAM["x"] - joueur_x) > 700 or abs(CAM["y"] - joueur_y) > 700:
                CAM["x"], CAM["y"] = joueur_x, joueur_y
            elif not en_pause:
                CAM["x"] += (joueur_x - CAM["x"]) * 0.2
                CAM["y"] += (joueur_y - CAM["y"]) * 0.2

        # Saut d'images : on ne dessine qu'une image sur n, le jeu garde ainsi sa vitesse normale
        if (SAUT["n"] > 1 and etat_actuel == ETAT_JEU and not en_pause and not TRANS["actif"]
                and not partie_gagnee and not partie_perdue and frames_total % SAUT["n"] != 0):
            clock.tick(60)
            adapter_qualite()
            continue

        ecran.fill(NOIR_ESPACE)
        largeur_v = 500
        x_v = (LARGEUR - largeur_v) // 2

        if etat_actuel == ETAT_MENU:
            dessiner_fond_menu()
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER, False, 150)

            dessiner_titre_glitch("FLEX CYBERPUNK", police_titre, LARGEUR // 2, HAUTEUR // 4)
            ti = rendu_texte(police_jeu, "MODE INFINI", True, ROSE_SYNTH)
            ecran.blit(ti, (LARGEUR // 2 - ti.get_width() // 2, HAUTEUR // 4 + 90))

            niveau_sauvegarde_affichage = niveau_max_atteint
            if niveau_sauvegarde_affichage > 0:
                tp = rendu_texte(police_petite, f"Reprise à la MISSION {niveau_sauvegarde_affichage + 1:02d}", True, BLEU_CYBER)
                ecran.blit(tp, (LARGEUR // 2 - tp.get_width() // 2, HAUTEUR // 4 + 125))

            bouton_neon(rect_bouton_jouer, ROSE_SYNTH, "COMMENCER", police_bouton, plein=True, pulse=True)
            bouton_neon(rect_bouton_aide, BLEU_CYBER, "GUIDE TACTIQUE", police_bouton)
            bouton_neon(rect_bouton_boutique, JAUNE_CYBER, "BOUTIQUE", police_bouton)
            dessiner_pieces(LARGEUR // 2, 36)
            dessiner_avertissement()
            dessiner_marque(HAUTEUR - 84)

            dessiner_halo(rect_icone_profil.centerx, rect_icone_profil.centery, 60, VERT_FLUO, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_profil.center, 35)
            DRAW.circle(ecran, VERT_FLUO, rect_icone_profil.center, 35, 3)
            dessiner_icone_personne(ecran, rect_icone_profil.centerx, rect_icone_profil.centery, 52, VERT_FLUO)
            if profil.get("pseudo"):
                tag = rendu_texte(police_petite, profil["pseudo"], True, VERT_FLUO)
                ecran.blit(tag, (rect_icone_profil.centerx - tag.get_width() // 2, rect_icone_profil.bottom + 6))

            dessiner_halo(rect_icone_infos.centerx, rect_icone_infos.centery, 60, BLEU_CYBER, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_infos.center, 35)
            DRAW.circle(ecran, BLEU_CYBER, rect_icone_infos.center, 35, 3)
            ti_icone = rendu_texte(police_titre, "i", True, BLEU_CYBER)
            ecran.blit(ti_icone, (rect_icone_infos.centerx - ti_icone.get_width() // 2, rect_icone_infos.centery - ti_icone.get_height() // 2 - 4))

            dessiner_halo(rect_icone_params.centerx, rect_icone_params.centery, 60, VIOLET_CYBER, 0.45, 2)
            DRAW.circle(ecran, GRIS_HACKER, rect_icone_params.center, 35)
            DRAW.circle(ecran, VIOLET_CYBER, rect_icone_params.center, 35, 3)
            dessiner_icone_engrenage(rect_icone_params.centerx, rect_icone_params.centery, 27, VIOLET_CYBER)

        elif etat_actuel == ETAT_NIVEAUX:
            dessiner_fond_menu()
            dessiner_titre_glitch("MISSIONS", police_titre, LARGEUR // 2, 50)

            idx_min_affiche = max(0, int((-defilement_niveaux - 150) / NIVEAU_NODE_ESPACEMENT))
            idx_max_affiche = min(niveau_max_atteint + 30, int((LARGEUR - defilement_niveaux + 150) / NIVEAU_NODE_ESPACEMENT))

            points_chemin = []
            for idx in range(idx_min_affiche, idx_max_affiche + 1):
                x_node = int(NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux)
                y_node = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                points_chemin.append((x_node, y_node))
            if len(points_chemin) >= 2:
                DRAW.lines(ecran, (0, 40, 60), False, points_chemin, 12)
                DRAW.lines(ecran, (0, 90, 130), False, points_chemin, 6)
                DRAW.lines(ecran, (80, 200, 255), False, points_chemin, 2)

            for idx in range(idx_min_affiche, idx_max_affiche + 1):
                x_node = int(NIVEAU_MARGE_GAUCHE + idx * NIVEAU_NODE_ESPACEMENT + defilement_niveaux)
                y_node = HAUTEUR // 2 + int(60 * math.sin(idx * 0.9))
                est_boss_node = (idx + 1) % 5 == 0
                pulsation_node = 0

                if idx < niveau_max_atteint:
                    couleur_node = VERT_FLUO
                elif idx == niveau_max_atteint:
                    pulsation_node = 4 * math.sin(pygame.time.get_ticks() / 200)
                    couleur_node = VIOLET_CYBER if est_boss_node else BLEU_CYBER
                else:
                    couleur_node = GRIS_HACKER

                rayon_affiche = NIVEAU_NODE_RAYON + int(pulsation_node)
                if idx <= niveau_max_atteint:
                    dessiner_halo(x_node, y_node, 65, couleur_node, 0.6)
                DRAW.circle(ecran, (8, 8, 16), (x_node, y_node), rayon_affiche)
                DRAW.circle(ecran, couleur_node, (x_node, y_node), rayon_affiche, 5 if idx == niveau_max_atteint else 4)

                if idx > niveau_max_atteint:
                    DRAW.rect(ecran, GRIS_HACKER, (x_node - 13, y_node - 4, 26, 22), border_radius=4)
                    DRAW.arc(ecran, GRIS_HACKER, (x_node - 11, y_node - 24, 22, 26), 3.4, 6.0, 3)
                else:
                    if idx < niveau_max_atteint:
                        DRAW.lines(ecran, NOIR_ESPACE, False, [
                            (x_node - 13, y_node),
                            (x_node - 3, y_node + 10),
                            (x_node + 15, y_node - 13)
                        ], 5)
                    else:
                        texte_node = rendu_texte(police_bouton, str(idx + 1), True, BLANC_NEON)
                        ecran.blit(texte_node, (x_node - texte_node.get_width() // 2, y_node - texte_node.get_height() // 2))
                    if est_boss_node:
                        tag_boss = rendu_texte(police_petite, "BOSS", True, ROUGE_ALERTE)
                        ecran.blit(tag_boss, (x_node - tag_boss.get_width() // 2, y_node + NIVEAU_NODE_RAYON + 10))

            indication_niveaux = rendu_texte(police_petite, "Glisse pour naviguer  •  Touche une mission débloquée pour jouer", True, BLEU_CYBER)
            ecran.blit(indication_niveaux, (LARGEUR // 2 - indication_niveaux.get_width() // 2, HAUTEUR - 112))
            dessiner_marque(HAUTEUR - 84)

            bouton_neon(rect_retour_niveaux, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_AIDE:
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER)
            dessiner_titre_glitch("GUIDE TACTIQUE", police_titre, LARGEUR // 2, 50)

            gris_credit = (170, 180, 210)
            lignes = [
                ("CONTRÔLES", ROSE_SYNTH),
                ("Manette gauche : déplacement", BLANC_NEON),
                ("Bouton TIR : laser avec autolock sur le", BLANC_NEON),
                ("drone (ou boss) le plus proche", BLANC_NEON),
                ("", BLANC_NEON),
                ("OBJECTIF DE CHAQUE MISSION", ROSE_SYNTH),
                ("1. Rejoins la zone violette (CORE)", BLANC_NEON),
                ("2. Reste dedans jusqu'à 100% de hack", BLANC_NEON),
                ("3. Fonce vers la sortie (zone verte)", BLANC_NEON),
                ("", BLANC_NEON),
                ("DANGERS À ÉVITER", ROUGE_ALERTE),
                ("Drones ennemis : 1 seul contact = échec", BLANC_NEON),
                ("Chrono : 130s par mission (plus sur boss)", BLANC_NEON),
                ("Temps écoulé avant la sortie = échec", BLANC_NEON),
                ("", BLANC_NEON),
                ("BONUS", JAUNE_CYBER),
                ("Potions jaunes +5s, dès la mission 9", BLANC_NEON),
                ("", BLANC_NEON),
                ("BOSS", ROUGE_ALERTE),
                ("Toutes les 5 missions, sans drones", BLANC_NEON),
                ("Le CORE reste verrouillé tant qu'il est en vie", BLANC_NEON),
                ("Tire sans arrêt et esquive ses boules de feu", BLANC_NEON),
                ("", BLANC_NEON),
                ("MODE INFINI : la difficulté augmente sans", VIOLET_CYBER),
                ("fin, les missions n'ont pas de limite !", VIOLET_CYBER),
                ("", BLANC_NEON),
                ("---", BLANC_NEON),
                ("", BLANC_NEON),
                ("FLEX CYBERPUNK", ROSE_SYNTH),
                ("", BLANC_NEON),
                ("Un jeu créé et développé par FlexPlay.", BLANC_NEON),
                ("", BLANC_NEON),
                ("Toute modification ou redistribution doit", gris_credit),
                ("conserver les crédits du créateur original.", gris_credit),
                ("", BLANC_NEON),
            ]
            y_zone, pas = 130, 32
            hauteur_contenu = len(lignes) * pas + 20
            hauteur_visible = HAUTEUR - y_zone - 10
            defil_max = max(0, hauteur_contenu - hauteur_visible)
            AIDE["scroll"] = max(-defil_max, min(0, AIDE["scroll"]))

            ecran.set_clip(pygame.Rect(x_v - 14, y_zone, largeur_v + 28, HAUTEUR - y_zone))
            for idx, (texte_ligne, couleur_ligne) in enumerate(lignes):
                yy = int(y_zone + 8 + idx * pas + AIDE["scroll"])
                if yy < y_zone - 40 or yy > HAUTEUR:
                    continue
                if texte_ligne == "---":
                    DRAW.line(ecran, eclaircir(BLEU_CYBER, 0.35), (x_v + 40, yy + 14), (x_v + largeur_v - 40, yy + 14), 5)
                    DRAW.line(ecran, BLEU_CYBER, (x_v + 40, yy + 14), (x_v + largeur_v - 40, yy + 14), 2)
                elif texte_ligne:
                    police_l = police_jeu if texte_ligne == "FLEX CYBERPUNK" else police_aide
                    tl = rendu_texte(police_l, texte_ligne, True, couleur_ligne)
                    ecran.blit(tl, (LARGEUR // 2 - tl.get_width() // 2, yy))
            ecran.set_clip(None)

            if defil_max > 0:
                x_barre, haut_piste = x_v + largeur_v - 9, y_zone + 6
                long_piste = HAUTEUR - y_zone - 22
                long_pouce = max(30, int(long_piste * hauteur_visible / float(hauteur_contenu)))
                y_pouce = haut_piste + int((long_piste - long_pouce) * (-AIDE["scroll"]) / float(defil_max))
                DRAW.rect(ecran, (16, 20, 40), (x_barre, haut_piste, 4, long_piste), border_radius=2)
                DRAW.rect(ecran, BLEU_CYBER, (x_barre, y_pouce, 4, long_pouce), border_radius=2)
                if AIDE["scroll"] > -6:
                    indice = rendu_texte(police_petite, "Glisse pour voir la suite", True, BLEU_CYBER)
                    ecran.blit(obtenir_voile(280, 34, (5, 6, 16, 200)), (LARGEUR // 2 - 140, HAUTEUR - 50))
                    ecran.blit(indice, (LARGEUR // 2 - indice.get_width() // 2, HAUTEUR - 41))

            bouton_neon(rect_bouton_retour, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_INFOS:
            dessiner_fond_menu()
        
            panneau_largeur = 520
            panneau_x = (LARGEUR - panneau_largeur) // 2
        
            ecran.blit(obtenir_voile(panneau_largeur, HAUTEUR, (10, 10, 20, 220)), (panneau_x, 0))
        
            DRAW.line(ecran, BLEU_CYBER, (panneau_x, 0), (panneau_x, HAUTEUR), 3)
            DRAW.line(ecran, BLEU_CYBER, (panneau_x + panneau_largeur, 0), (panneau_x + panneau_largeur, HAUTEUR), 3)
        
            dessiner_titre_glitch("INFORMATIONS", police_titre, LARGEUR // 2, 50)
        
            lignes_infos = [
                ("DÉVELOPPEUR ET CRÉATEUR", VERT_FLUO),
                ("FLEXPLAY", BLANC_NEON),
                ("", BLANC_NEON),
                ("CONNAISSANCES", BLEU_CYBER),
                ("ZZED GAMING23", BLANC_NEON),
                ("GLOD'S", BLANC_NEON),
                ("GAMEPLAY PSP", BLANC_NEON),
                ("ROMULUS GAMES", BLANC_NEON),
                ("BENI TUBE", BLANC_NEON),
                ("ISHAQ GAMER", VERT_FLUO),
                ("BADLEX PRO GAMING", BLANC_NEON),
                ("GAMER REPUBLIC", BLANC_NEON),
                ("BEN GAMING23", BLANC_NEON),
                ("GAMEHUB XD", BLANC_NEON),
                ("JHONS GAMING", BLANC_NEON),
                ("DARK GAMES", BLANC_NEON),
            ]
        
            y_depart_infos = 135
            espacement_infos = min(32, max(22, (HAUTEUR - 135 - 110) // max(1, len(lignes_infos) - 1)))
            for idx, (texte_ligne, couleur_ligne) in enumerate(lignes_infos):
                if texte_ligne:
                    police_texte = police_jeu if couleur_ligne in [VERT_FLUO, BLEU_CYBER] else police_petite
                    til = rendu_texte(police_texte, texte_ligne, True, couleur_ligne)
                    ecran.blit(til, (LARGEUR // 2 - til.get_width() // 2, y_depart_infos + idx * espacement_infos))

            dessiner_marque(HAUTEUR - 84)
            bouton_neon(rect_retour_infos, ROUGE_ALERTE, "< RETOUR", police_bouton)

        elif etat_actuel == ETAT_PROFIL:
            dessiner_panneau_neon(x_v, largeur_v, BLEU_CYBER)
            dessiner_titre_glitch("MON PROFIL", police_titre, LARGEUR // 2, 60)

            centre_avatar = (LARGEUR // 2, 190)
            if photo_profil_surface:
                ecran.blit(photo_profil_surface, (centre_avatar[0] - 80, centre_avatar[1] - 80))
                DRAW.circle(ecran, VERT_FLUO, centre_avatar, 80, 3)
            else:
                DRAW.circle(ecran, NOIR_ESPACE, centre_avatar, 80)
                DRAW.circle(ecran, VERT_FLUO, centre_avatar, 80, 3)
                dessiner_icone_personne(ecran, centre_avatar[0], centre_avatar[1], 110, VERT_FLUO)

            astuce = rendu_texte(police_petite, "Depose 'photo_profil.png' dans le dossier du jeu", True, BLANC_NEON)
            ecran.blit(astuce, (LARGEUR // 2 - astuce.get_width() // 2, centre_avatar[1] + 90))

            bouton_neon(rect_recharger_photo, BLEU_CYBER, "RECHARGER LA PHOTO", police_petite)

            DRAW.rect(ecran, NOIR_ESPACE, rect_champ_pseudo, border_radius=8)
            couleur_bordure = VERT_FLUO if saisie_pseudo_active else BLEU_CYBER
            DRAW.rect(ecran, couleur_bordure, rect_champ_pseudo, border_radius=8, width=3)
            curseur = "|" if (saisie_pseudo_active and (pygame.time.get_ticks() // 500) % 2 == 0) else ""
            texte_pseudo = profil["pseudo"] if (profil["pseudo"] or saisie_pseudo_active) else "Toucher pour saisir un pseudo"
            surf_pseudo = rendu_texte(police_jeu, texte_pseudo + curseur, True, BLANC_NEON)
            ecran.blit(surf_pseudo, (rect_champ_pseudo.x + 15, rect_champ_pseudo.centery - surf_pseudo.get_height() // 2))

            bouton_neon(rect_fleche_gauche, BLEU_CYBER, "<", police_bouton)
            bouton_neon(rect_fleche_droite, BLEU_CYBER, ">", police_bouton)
            surf_nat = rendu_texte(police_jeu, NATIONALITES[index_nationalite], True, VERT_FLUO)
            ecran.blit(surf_nat, (LARGEUR // 2 - surf_nat.get_width() // 2, rect_fleche_gauche.centery - surf_nat.get_height() // 2))

            bouton_neon(rect_sauvegarder_profil, ROSE_SYNTH, "ENREGISTRER", police_bouton, plein=True, pulse=True)
            bouton_neon(rect_retour_profil, ROUGE_ALERTE, "RETOUR", police_bouton)
            dessiner_marque(HAUTEUR - 84)

        elif etat_actuel == ETAT_EDITEUR:
            dessiner_editeur()

        elif etat_actuel == ETAT_BOUTIQUE:
            dessiner_boutique()

        elif etat_actuel == ETAT_PARAMS:
            dessiner_parametres()

        elif etat_actuel == ETAT_JEU:
            t_ms = pygame.time.get_ticks()
            sec = ETAT_FX["secousse"]
            decal_x = random.uniform(-sec, sec) if sec > 0 else 0.0
            decal_y = random.uniform(-sec, sec) if sec > 0 else 0.0
            ox = int(LARGEUR // 2 - CAM["x"] + decal_x)
            oy = int(HAUTEUR // 2 - CAM["y"] + decal_y)

            _echelle_active = False
            if _echelle_active:
                _ecran_reel = ecran
                ecran = obtenir_cible_monde()
                DRAW = _DESSIN_ECHELLE
            dessiner_fond_ville(ox, oy, t_ms, (ox, oy, len(CARTE[0]) * TAILLE_CASE, len(CARTE) * TAILLE_CASE))
            dessiner_cadre_carte(ox, oy, 0)
            nb_lignes_carte, nb_colonnes_carte = len(CARTE), len(CARTE[0])
            colonne_min = max(0, int((-ox) // TAILLE_CASE) - 1)
            colonne_max = min(nb_colonnes_carte, int((LARGEUR - ox) // TAILLE_CASE) + 2)
            ligne_min = max(0, int((-oy) // TAILLE_CASE) - 1)
            ligne_max = min(nb_lignes_carte, int((HAUTEUR - oy) // TAILLE_CASE) + 2)

            lueurs = []
            demi = TAILLE_CASE // 2
            ombres_actives = bool(PARAMS["ombres"]) and QUALITE["niveau"] >= 1
            for li in range(ligne_min, ligne_max):
                lg = CARTE[li]
                for ci in range(colonne_min, colonne_max):
                    case = lg[ci]
                    rx, ry = ci * TAILLE_CASE + ox, li * TAILLE_CASE + oy
                    if case == 1:
                        masque = 0
                        if li > 0 and CARTE[li - 1][ci] != 1:
                            masque |= 1
                        if li < nb_lignes_carte - 1 and CARTE[li + 1][ci] != 1:
                            masque |= 2
                        if ci > 0 and lg[ci - 1] != 1:
                            masque |= 4
                        if ci < nb_colonnes_carte - 1 and lg[ci + 1] != 1:
                            masque |= 8
                        ecran.blit(tuile_mur(COULEUR_MUR, masque), (rx, ry))
                        continue

                    ms = 0
                    if ombres_actives:
                        if li > 0 and CARTE[li - 1][ci] == 1:
                            ms |= 1
                        if li < nb_lignes_carte - 1 and CARTE[li + 1][ci] == 1:
                            ms |= 2
                        if ci > 0 and lg[ci - 1] == 1:
                            ms |= 4
                        if ci < nb_colonnes_carte - 1 and lg[ci + 1] == 1:
                            ms |= 8
                    ecran.blit(tuile_sol(COULEUR_MUR, (li + ci) % 2, ms), (rx, ry))
                    if case == 2:
                        if boss_actif and not boss_vaincu:
                            p_core = 0.6 + 0.4 * math.sin(t_ms / 180.0)
                            DRAW.rect(ecran, eclaircir(ROUGE_ALERTE, p_core), (rx + 3, ry + 3, TAILLE_CASE - 6, TAILLE_CASE - 6), 5)
                            DRAW.line(ecran, eclaircir(ROUGE_ALERTE, 0.35), (rx + 12, ry + 12), (rx + TAILLE_CASE - 12, ry + TAILLE_CASE - 12), 3)
                            DRAW.line(ecran, eclaircir(ROUGE_ALERTE, 0.35), (rx + TAILLE_CASE - 12, ry + 12), (rx + 12, ry + TAILLE_CASE - 12), 3)
                            lueurs.append((rx + demi, ry + demi, 110, ROUGE_ALERTE, 0.55 * p_core))
                        else:
                            if MODE_GRAPHIQUE == "REALISTE":
                                ecran.blit(img_core, (rx, ry))
                            else:
                                DRAW.rect(ecran, VIOLET_CYBER, (rx, ry, TAILLE_CASE, TAILLE_CASE))
                            couleur_lueur_core = VERT_FLUO if hack_reussi else VIOLET_CYBER
                            lueurs.append((rx + demi, ry + demi, 120, couleur_lueur_core, 0.5 + 0.2 * math.sin(t_ms / 300.0)))
                    elif case == 3:
                        col_sortie = VERT_FLUO if hack_reussi else ROUGE_ALERTE
                        p_sortie = 0.55 + 0.45 * math.sin(t_ms / (200.0 if hack_reussi else 350.0))
                        DRAW.rect(ecran, melange(NOIR_ESPACE, col_sortie, 0.18), (rx + 4, ry + 4, TAILLE_CASE - 8, TAILLE_CASE - 8))
                        for k_cadre in range(3):
                            DRAW.rect(ecran, eclaircir(col_sortie, max(0.0, p_sortie - k_cadre * 0.2)),
                                             (rx + 4 + k_cadre * 8, ry + 4 + k_cadre * 8,
                                              TAILLE_CASE - 8 - k_cadre * 16, TAILLE_CASE - 8 - k_cadre * 16), 3)
                        lueurs.append((rx + demi, ry + demi, 100, col_sortie, 0.35 + 0.35 * p_sortie))

            dessiner_cadre_carte(ox, oy, 1)
            if ombres_actives:
                if not partie_perdue:
                    dessiner_ombre(joueur_x + ox + 5, joueur_y + oy + 16, TAILLE_PERSO + 14, 22)
                for ex in liste_ennemis:
                    dessiner_ombre(ex[0] + ox + 4, ex[1] + oy + 18, 44, 16)
                if boss_actif and not boss_vaincu:
                    dessiner_ombre(boss_x + ox + 10, boss_y + oy + int(TAILLE_BOSS * 0.38), int(TAILLE_BOSS * 0.8), int(TAILLE_BOSS * 0.26))
            if not partie_perdue:
                lueurs.append((joueur_x + ox, joueur_y + oy, 120, BLEU_CYBER, 0.38))
            for lx, ly, lr, lc, lint in lueurs:
                dessiner_halo(lx, ly, lr if QUALITE["niveau"] >= 2 else int(lr * 0.7), lc, lint)

            for b in balles:
                bx_e, by_e = int(b[0] + ox), int(b[1] + oy)
                DRAW.line(ecran, LASER["trail"], (int(bx_e - b[2] * 3.2), int(by_e - b[3] * 3.2)), (bx_e, by_e), 9)
                DRAW.line(ecran, LASER["main"], (int(bx_e - b[2] * 2.0), int(by_e - b[3] * 2.0)), (bx_e, by_e), 5)
                DRAW.circle(ecran, BLANC_NEON, (bx_e, by_e), 4)
                dessiner_halo(bx_e, by_e, 24, LASER["main"], 0.95, 0)

            for potion in liste_potions:
                px_ecran, py_ecran = int(potion[0] + ox), int(potion[1] + oy)
                pulsation = 3 * math.sin(pygame.time.get_ticks() / 150)
                dessiner_halo(px_ecran, py_ecran, 36, JAUNE_CYBER, 0.85)
                ang_orbite = pygame.time.get_ticks() / 380.0
                DRAW.circle(ecran, BLANC_NEON, (int(px_ecran + math.cos(ang_orbite) * 27), int(py_ecran + math.sin(ang_orbite) * 27)), 3)
                DRAW.circle(ecran, JAUNE_CYBER, (px_ecran, py_ecran), int(18 + pulsation))
                DRAW.circle(ecran, NOIR_ESPACE, (px_ecran, py_ecran), int(11 + pulsation))
                tp5 = rendu_texte(police_petite, "+5", True, JAUNE_CYBER)
                ecran.blit(tp5, (px_ecran - tp5.get_width() // 2, py_ecran - tp5.get_height() // 2))

            for ex in liste_ennemis:
                if len(liste_ennemis) <= 10:
                    dessiner_halo(ex[0] + ox, ex[1] + oy, 30, ROUGE_ALERTE, 0.75)
                if MODE_GRAPHIQUE == "REALISTE":
                    ang_drone = math.degrees(math.atan2(-(joueur_y - ex[1]), joueur_x - ex[0])) - 90
                    ang_q = int(round(ang_drone / 6.0)) * 6
                    drone_rot = _cache_drones.get(ang_q)
                    if drone_rot is None:
                        drone_rot = pygame.transform.rotate(img_drone, ang_q)
                        _cache_drones[ang_q] = drone_rot
                    ecran.blit(drone_rot, (int(ex[0] + ox - drone_rot.get_width() // 2), int(ex[1] + oy - drone_rot.get_height() // 2)))
                else:
                    DRAW.circle(ecran, ROUGE_ALERTE, (int(ex[0] + ox), int(ex[1] + oy)), 16)

            if boss_actif and not boss_vaincu:
                bx_ecran, by_ecran = int(boss_x + ox), int(boss_y + oy)
                pulse_boss = 0.65 + 0.35 * math.sin(t_ms / 260.0)
                couleur_aura_boss = ROUGE_ALERTE if boss_vie < boss_vie_max * 0.3 else VIOLET_CYBER
                dessiner_halo(bx_ecran, by_ecran, 160 if QUALITE["niveau"] >= 2 else 110, couleur_aura_boss, 0.75 * pulse_boss)
                if BOSS_IMAGE_DISPONIBLE:
                    angle_affichage_boss = math.degrees(math.atan2(-(joueur_y - boss_y), joueur_x - boss_x)) - 90
                    angle_arrondi_boss = round(angle_affichage_boss / 6) * 6
                    if boss_surface_cache is None or angle_arrondi_boss != boss_angle_precedent:
                        boss_surface_cache = _cache_boss.get(angle_arrondi_boss)
                        if boss_surface_cache is None:
                            if len(_cache_boss) >= 40:
                                _cache_boss.pop(next(iter(_cache_boss)))
                            boss_surface_cache = pygame.transform.rotate(img_boss, angle_arrondi_boss)
                            _cache_boss[angle_arrondi_boss] = boss_surface_cache
                        boss_angle_precedent = angle_arrondi_boss
                    ecran.blit(boss_surface_cache, (bx_ecran - boss_surface_cache.get_width() // 2, by_ecran - boss_surface_cache.get_height() // 2))
                else:
                    DRAW.circle(ecran, VIOLET_CYBER, (bx_ecran, by_ecran), int(TAILLE_BOSS / 2))
                    tb = rendu_texte(police_bouton, "BOSS", True, BLANC_NEON)
                    ecran.blit(tb, (bx_ecran - tb.get_width() // 2, by_ecran - tb.get_height() // 2))

            for boule in boules_feu:
                fx_ecran, fy_ecran = int(boule[0] + ox), int(boule[1] + oy)
                for k_traine in (3, 2, 1):
                    DRAW.circle(ecran, eclaircir(ORANGE_MEC, 0.22 * (4 - k_traine)),
                                       (int(fx_ecran - boule[2] * k_traine * 2.4), int(fy_ecran - boule[3] * k_traine * 2.4)),
                                       5 + (4 - k_traine) * 3)
                dessiner_halo(fx_ecran, fy_ecran, 42, ORANGE_MEC, 1.0)
                pulsation_feu = 3 * math.sin(pygame.time.get_ticks() / 90)
                DRAW.circle(ecran, ORANGE_MEC, (fx_ecran, fy_ecran), int(16 + pulsation_feu))
                DRAW.circle(ecran, JAUNE_CYBER, (fx_ecran, fy_ecran), int(9 + pulsation_feu))

            if not partie_perdue:
                jx_e, jy_e = int(joueur_x + ox), int(joueur_y + oy) + int(3 * math.sin(t_ms / 230.0))
                if ETAT_JOUEUR["invuln"] <= 0 or (t_ms // 90) % 2 == 0:          # clignote après un coup encaissé
                    if MODE_GRAPHIQUE == "REALISTE":
                        ecran.blit(img_joueur_actuel, (jx_e - img_joueur_actuel.get_width() // 2, jy_e - img_joueur_actuel.get_height() // 2))
                    else:
                        DRAW.rect(ecran, VERT_FLUO, (jx_e - TAILLE_PERSO // 2, jy_e - TAILLE_PERSO // 2, TAILLE_PERSO, TAILLE_PERSO))
                if ETAT_JOUEUR["bouclier"] > 0:
                    r_bouclier = 36 + int(2 * math.sin(t_ms / 160.0))
                    DRAW.circle(ecran, eclaircir(LASER["main"], 0.4), (jx_e, jy_e), r_bouclier + 3, 3)
                    DRAW.circle(ecran, LASER["main"], (jx_e, jy_e), r_bouclier, 2)
                    dessiner_halo(jx_e, jy_e, 56, LASER["main"], 0.55)

            dessiner_fx(ox, oy)
            if QUALITE["niveau"] >= 2:
                ecran.blit(obtenir_vignette(), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            if _echelle_active:
                ecran = _ecran_reel
                DRAW = pygame.draw
                try:
                    pygame.transform.scale(_cible_monde.surf, _ecran_reel.get_size(), _ecran_reel)
                except Exception as _err:
                    print("⚠️ Résolution réduite impossible, retour à 100% :", _err)
                    ECHELLE = 1.0
                    PARAMS["resolution"] = 1

            tn = rendu_texte(police_jeu, niveau_data["nom"], True, COULEUR_MUR)
            ecran.blit(tn, (40, 40))

            dessiner_radar()

            if not partie_gagnee and not partie_perdue:
                dessiner_halo(BTN_PAUSE_X, BTN_PAUSE_Y, 52, BLEU_CYBER, 0.5, 2)
                DRAW.circle(ecran, (10, 10, 20), (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON)
                DRAW.circle(ecran, BLEU_CYBER, (BTN_PAUSE_X, BTN_PAUSE_Y), BTN_PAUSE_RAYON, 3)
                if en_pause:
                    DRAW.polygon(ecran, BLEU_CYBER, [
                        (BTN_PAUSE_X - 8, BTN_PAUSE_Y - 12),
                        (BTN_PAUSE_X - 8, BTN_PAUSE_Y + 12),
                        (BTN_PAUSE_X + 12, BTN_PAUSE_Y)
                    ])
                else:
                    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X - 11, BTN_PAUSE_Y - 12, 7, 24))
                    DRAW.rect(ecran, BLEU_CYBER, (BTN_PAUSE_X + 4, BTN_PAUSE_Y - 12, 7, 24))

            if boss_actif and not boss_vaincu:
                info_drones = rendu_texte(police_petite, "BOSS ACTIF : TIRE SANS ARRÊT ET ESQUIVE LE FEU", True, ROUGE_ALERTE)
            elif boss_actif and boss_vaincu:
                info_drones = rendu_texte(police_petite, "BOSS VAINCU : REJOINS LE CORE POUR HACKER", True, VERT_FLUO)
            else:
                info_drones = rendu_texte(police_petite, 
                    f"DRONES ACTIFS : {len(liste_ennemis)}   EN APPROCHE : {ennemis_restants_a_spawner}", True, ROUGE_ALERTE)
            ecran.blit(info_drones, (40, 80))
            dessiner_hud_boutique()

            secondes_restantes = max(0, temps_restant_frames // 60)
            couleur_timer = ROUGE_ALERTE if secondes_restantes <= 10 else VERT_FLUO
            texte_timer = rendu_texte(police_bouton, f"TEMPS : {secondes_restantes:02d}s", True, couleur_timer)
            rect_timer = texte_timer.get_rect(topleft=(LARGEUR // 2 - texte_timer.get_width() // 2, 100)).inflate(44, 14)
            DRAW.rect(ecran, (8, 10, 20), rect_timer, border_radius=14)
            clignote = 1.0 if secondes_restantes > 10 else 0.6 + 0.4 * math.sin(t_ms / 110.0)
            DRAW.rect(ecran, eclaircir(couleur_timer, clignote), rect_timer, width=2, border_radius=14)
            ecran.blit(texte_timer, (LARGEUR // 2 - texte_timer.get_width() // 2, 100))
            if jauge_hack > 0 and not hack_reussi:
                bx0, by0, bw, bh = LARGEUR // 2 - 175, 45, 350, 30
                largeur_rempli = int(jauge_hack * 3.5)
                DRAW.rect(ecran, (10, 10, 22), (bx0, by0, bw, bh), border_radius=6)
                if largeur_rempli > 8:
                    DRAW.rect(ecran, VIOLET_CYBER, (bx0, by0, largeur_rempli, bh), border_radius=6)
                    DRAW.rect(ecran, (225, 120, 255), (bx0 + 3, by0 + 3, largeur_rempli - 6, bh // 3), border_radius=4)
                dessiner_halo(bx0 + largeur_rempli, by0 + bh // 2, 40, VIOLET_CYBER, 0.7, 2)
                DRAW.rect(ecran, BLEU_CYBER, (bx0, by0, bw, bh), width=2, border_radius=6)
                th_hack = rendu_texte(police_petite, f"HACK {int(jauge_hack)}%", True, BLANC_NEON)
                ecran.blit(th_hack, (LARGEUR // 2 - th_hack.get_width() // 2, by0 + bh // 2 - th_hack.get_height() // 2))

            if boss_actif and not boss_vaincu:
                largeur_barre_boss = 460
                x_barre_boss = LARGEUR // 2 - largeur_barre_boss // 2
                DRAW.rect(ecran, GRIS_HACKER, (x_barre_boss, 140, largeur_barre_boss, 28), border_radius=6)
                ratio_vie_boss = max(0.0, boss_vie / boss_vie_max)
                DRAW.rect(ecran, ROUGE_ALERTE, (x_barre_boss, 140, int(largeur_barre_boss * ratio_vie_boss), 28), border_radius=6)
                if ratio_vie_boss > 0.03:
                    DRAW.rect(ecran, (255, 120, 150), (x_barre_boss + 3, 143, max(1, int(largeur_barre_boss * ratio_vie_boss) - 6), 8), border_radius=4)
                    dessiner_halo(x_barre_boss + int(largeur_barre_boss * ratio_vie_boss), 154, 40, ROUGE_ALERTE, 0.7, 2)
                for k_seg in range(1, 10):
                    xk = x_barre_boss + largeur_barre_boss * k_seg // 10
                    DRAW.line(ecran, (20, 0, 10), (xk, 142), (xk, 166), 2)
                DRAW.rect(ecran, BLANC_NEON, (x_barre_boss, 140, largeur_barre_boss, 28), width=2, border_radius=6)
                txt_vie_boss = rendu_texte(police_petite, f"BOSS {boss_vie}/{boss_vie_max}", True, BLANC_NEON)
                ecran.blit(txt_vie_boss, (LARGEUR // 2 - txt_vie_boss.get_width() // 2, 144))

            dessiner_commandes(manette_x, manette_y, tir_maintenu)

            if partie_gagnee:
                dessiner_ecran_victoire()
            elif partie_perdue:
                dessiner_ecran_defaite()

        if etat_actuel == ETAT_JEU and en_pause and not partie_gagnee and not partie_perdue:
            ecran.blit(obtenir_voile(LARGEUR, HAUTEUR, (5, 5, 10, 205)), (0, 0))

            dessiner_titre_glitch("PAUSE", police_titre, LARGEUR // 2, HAUTEUR // 2 - 230)

            bouton_neon(rect_pause_continuer, BLEU_CYBER, "CONTINUER", police_bouton)
            bouton_neon(rect_pause_rejouer, VERT_FLUO, "REJOUER", police_bouton)
            bouton_neon(rect_pause_params, VIOLET_CYBER, "PARAMÈTRES", police_bouton)
            bouton_neon(rect_pause_quitter, ROUGE_ALERTE, "QUITTER", police_bouton)

        if TRANS["actif"]:
            dessiner_transition()

        _tm2 = _time.perf_counter()
        if VERSION_MODIFIEE:
            dessiner_filigrane()
        if PARAMS["fps"]:
            dessiner_fps()

        pygame.display.flip()
        _tm3 = _time.perf_counter()
        TMR["l"] += ((_tm1 - _tm0) * 1000.0 - TMR["l"]) * 0.1
        TMR["r"] += ((_tm2 - _tm1) * 1000.0 - TMR["r"]) * 0.1
        TMR["f"] += ((_tm3 - _tm2) * 1000.0 - TMR["f"]) * 0.1
        clock.tick(60)
        adapter_qualite()
        if EXTRA["_essai"] and pygame.time.get_ticks() > 6000:
            EXTRA["_essai"] = 0          # le démarrage a tenu : la résolution réduite est validée
            sauvegarder_parametres()


asyncio.run(main())
