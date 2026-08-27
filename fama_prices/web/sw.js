// Service Worker fuer die Farmer-App.
//
// Aufgabe: nur die Huelle (HTML, Symbole, Manifest) offline verfuegbar halten,
// damit die App auch ohne Netz startet. Die zuletzt gesehenen Preise legt die
// Seite selbst im localStorage ab.
//
// Bewusst NICHT im Cache: alles, was an Supabase geht. Jeder Datenabruf prueft
// serverseitig den Freigabe-Token (numis.assert_client). Wuerde der Service
// Worker diese Antworten zwischenspeichern, liesse sich eine gesperrte Fassung
// weiter benutzen. Cross-Origin-Anfragen werden daher gar nicht angefasst.

const CACHE = "numis-huelle-v1";
const HUELLE = [
  "/tani",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/apple-touch-icon.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(HUELLE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((namen) => Promise.all(namen.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // Supabase & Co. unberuehrt lassen

  // Seitenaufrufe: erst das Netz fragen, damit eine neue Fassung sofort greift.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((antwort) => {
          const kopie = antwort.clone();
          caches.open(CACHE).then((c) => c.put(req, kopie)).catch(() => {});
          return antwort;
        })
        .catch(() => caches.match(req).then((t) => t || caches.match("/tani")))
    );
    return;
  }

  // Symbole und Manifest: aus dem Cache, im Hintergrund auffrischen.
  e.respondWith(
    caches.match(req).then((treffer) => {
      const frisch = fetch(req)
        .then((antwort) => {
          const kopie = antwort.clone();
          caches.open(CACHE).then((c) => c.put(req, kopie)).catch(() => {});
          return antwort;
        })
        .catch(() => treffer);
      return treffer || frisch;
    })
  );
});
