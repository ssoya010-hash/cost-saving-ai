// Deck navigation: ←/→/Space/PageUp/PageDown, Home/End, #n deep links, N = speaker notes, T = theme.
(function () {
  const deck = document.querySelector(".deck");
  const slides = Array.from(document.querySelectorAll(".slide"));
  const bar = document.querySelector(".chrome .bar");
  const counter = document.getElementById("counter");
  const notes = document.getElementById("notes");
  let i = 0;

  function fit() {
    const s = Math.min(window.innerWidth / 1640, window.innerHeight / 940);
    deck.style.transform = `scale(${Math.max(s, 0.2)})`;
  }

  function show(n, push) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach((el, k) => el.classList.toggle("active", k === i));
    if (bar) bar.style.width = ((i + 1) / slides.length * 100) + "%";
    if (counter) counter.textContent = `${i + 1} / ${slides.length}`;
    const note = slides[i].querySelector("aside.note");
    if (notes) notes.textContent = note ? note.textContent.trim() : "";
    if (push !== false) {
      try { history.replaceState(null, "", "#" + (i + 1)); } catch (e) { /* sandboxed */ }
    }
  }

  function fromHash() {
    const n = parseInt((location.hash || "").replace("#", ""), 10);
    return Number.isFinite(n) ? n - 1 : 0;
  }

  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (["ArrowRight", "PageDown", " ", "Enter"].includes(k)) { e.preventDefault(); show(i + 1); }
    else if (["ArrowLeft", "PageUp", "Backspace"].includes(k)) { e.preventDefault(); show(i - 1); }
    else if (k === "Home") show(0);
    else if (k === "End") show(slides.length - 1);
    else if (k === "n" || k === "N") notes && notes.classList.toggle("on");
    else if (k === "t" || k === "T") toggleTheme();
  });

  let x0 = null;
  document.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  document.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) show(i + (dx < 0 ? 1 : -1));
    x0 = null;
  });

  function toggleTheme() {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
  }

  document.getElementById("prev")?.addEventListener("click", () => show(i - 1));
  document.getElementById("next")?.addEventListener("click", () => show(i + 1));
  document.getElementById("notesBtn")?.addEventListener("click", () => notes.classList.toggle("on"));
  window.addEventListener("resize", fit);
  window.addEventListener("hashchange", () => show(fromHash(), false));
  fit();
  show(fromHash(), false);
})();
