// Service worker minimal : aucune mise en cache hors-ligne pour l'instant
// (les données sont personnelles et servies par une API authentifiée).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
