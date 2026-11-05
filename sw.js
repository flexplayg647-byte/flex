// Service worker de Flex Cyberpunk.
// Il sert uniquement à rendre le jeu installable : il ne met RIEN en cache,
// donc chaque mise à jour du jeu arrive tout de suite chez les joueurs.
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", function () { /* le navigateur gère les requêtes normalement */ });
