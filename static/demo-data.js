/*
 * Demo data loader.
 *
 * The canonical fixtures live in static/demo.json. The FastAPI backend seeds its
 * SQLite demo database from that file and serves the same shape as
 * /api/bootstrap; if the API is unavailable (plain static hosting, a stopped
 * server), the JSON is loaded directly so the panels still work.
 *
 * Panel scripts await window.MARKETEYE_READY instead of reading a synchronous
 * global, so the data source can change without touching the panels.
 */
window.MARKETEYE_READY = (async () => {
  const sources = ["/api/bootstrap", "/static/demo.json"];
  for (const source of sources) {
    try {
      const response = await fetch(source, { cache: "no-store" });
      if (!response.ok) continue;
      const data = await response.json();
      if (data && Array.isArray(data.products) && Array.isArray(data.history)) {
        return data;
      }
    } catch (error) {
      // Fall through to the next source.
    }
  }
  return null;
})();
