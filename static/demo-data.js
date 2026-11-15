/*
 * Frozen fixtures for the Overview panel (front-end first).
 *
 * The shape mirrors what the backend will eventually serve:
 *   our prices + a list of daily snapshots, each holding
 *   { productId: { competitor: price } }.
 *
 * Three snapshots are stored: yesterday, today and "tomorrow" —
 * the last one is what the simulated "Collect now" appends.
 *
 * `history` holds fifteen daily records (2–16 November 2026): the product page
 * shows the fourteen-day window that ends on the selected snapshot's date. Its
 * last three records are the same numbers as `snapshots`, so the two views
 * never disagree.
 */
window.MARKETEYE_DEMO = {
  currency: "RUB",
  ourPrices: {
    cement: 399,
    brick: 38,
    sand: 1150,
    mix: 285,
    rebar: 62500,
  },
  products: [
    { id: "cement", name: "Cement M500 · 50 kg" },
    { id: "brick", name: "Ceramic brick · pc" },
    { id: "sand", name: "Building sand · t" },
    { id: "mix", name: "Dry mix M150 · 25 kg" },
    { id: "rebar", name: "Rebar A500 · t" },
  ],
  competitors: ["StroyBaza", "MasterStroy", "GlavSnab"],
  snapshots: [
    {
      date: "14 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "15 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 370, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1200, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 62600 },
      },
    },
    {
      date: "16 November 2026",
      prices: {
        cement: { StroyBaza: 390, MasterStroy: 370, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1200, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 62600 },
      },
    },
  ],
  history: [
    {
      date: "2 November 2026",
      prices: {
        cement: { StroyBaza: 430, MasterStroy: 415, GlavSnab: 430 },
        brick: { StroyBaza: 39, MasterStroy: 40, GlavSnab: 40 },
        sand: { StroyBaza: 1180, MasterStroy: 1200, GlavSnab: 1180 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61200 },
      },
    },
    {
      date: "3 November 2026",
      prices: {
        cement: { StroyBaza: 428, MasterStroy: 418, GlavSnab: 430 },
        brick: { StroyBaza: 39, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1170, MasterStroy: 1200, GlavSnab: 1180 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63200, MasterStroy: 64000, GlavSnab: 61400 },
      },
    },
    {
      date: "4 November 2026",
      prices: {
        cement: { StroyBaza: 425, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1160, MasterStroy: 1190, GlavSnab: 1170 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63200, MasterStroy: 64000, GlavSnab: 61400 },
      },
    },
    {
      date: "5 November 2026",
      prices: {
        cement: { StroyBaza: 425, MasterStroy: 420, GlavSnab: 432 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1160, MasterStroy: 1190, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "6 November 2026",
      prices: {
        cement: { StroyBaza: 422, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61200 },
      },
    },
    {
      date: "7 November 2026",
      prices: {
        cement: { StroyBaza: 422, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "8 November 2026",
      prices: {
        cement: { StroyBaza: 422, MasterStroy: 418, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63200, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "9 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 418, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "10 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "11 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "12 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 432 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "13 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "14 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 420, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1150, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 61400 },
      },
    },
    {
      date: "15 November 2026",
      prices: {
        cement: { StroyBaza: 420, MasterStroy: 370, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1200, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 62600 },
      },
    },
    {
      date: "16 November 2026",
      prices: {
        cement: { StroyBaza: 390, MasterStroy: 370, GlavSnab: 430 },
        brick: { StroyBaza: 38, MasterStroy: 39, GlavSnab: 40 },
        sand: { StroyBaza: 1200, MasterStroy: 1180, GlavSnab: 1160 },
        mix: { StroyBaza: 290, MasterStroy: 285, GlavSnab: 300 },
        rebar: { StroyBaza: 63000, MasterStroy: 63800, GlavSnab: 62600 },
      },
    },
  ],
  collection: {
    pages: [
      "StroyBaza · saved page 1 of 3",
      "MasterStroy · saved page 2 of 3",
      "GlavSnab · saved page 3 of 3",
    ],
  },
};
