/* CarCraft UI motion: progressive enhancement, everything works without it. */
(function () {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const inr = new Intl.NumberFormat("en-IN");

  /* Ignition intro: once per browser session */
  const ignition = document.getElementById("ignition");
  if (ignition) {
    let seen = false;
    try { seen = sessionStorage.getItem("cc-ignited") === "1"; sessionStorage.setItem("cc-ignited", "1"); } catch (e) {}
    if (seen || reduce) ignition.remove();
    else setTimeout(() => { ignition.classList.add("done"); setTimeout(() => ignition.remove(), 500); }, 1250);
  }

  /* Navbar shrinks on scroll */
  const nav = document.querySelector(".cc-nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", window.scrollY > 24);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* Highlight active nav link */
  document.querySelectorAll(".cc-nav .nav-link[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (href !== "/" && href !== "#" && location.pathname.startsWith(href)) a.classList.add("active");
  });

  /* Count-up numbers: <span data-count="12345" data-prefix="₹" data-suffix=" km"> */
  function countUp(el) {
    const target = parseFloat(el.dataset.count);
    if (isNaN(target)) return;
    const prefix = el.dataset.prefix || "", suffix = el.dataset.suffix || "";
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    const fmt = (v) => prefix + (decimals ? v.toFixed(decimals) : inr.format(Math.round(v))) + suffix;
    if (reduce) { el.textContent = fmt(target); return; }
    const dur = 1400, start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / dur);
      el.textContent = fmt(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /* Gauges & fuel bars animate from zero when they come into view */
  function animateMeter(el) {
    if (el.classList.contains("gauge")) {
      const p = el.dataset.p || "0";
      el.style.setProperty("--p", 0);
      void el.offsetWidth;
      requestAnimationFrame(() => el.style.setProperty("--p", p));
    } else if (el.classList.contains("fuelbar")) {
      const w = el.dataset.w || "0";
      el.style.setProperty("--w", "0%");
      void el.offsetWidth;
      requestAnimationFrame(() => el.style.setProperty("--w", w + "%"));
    }
  }

  const io = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      const el = e.target;
      if (el.hasAttribute("data-reveal")) {
        el.classList.add("in");
        // Hand control back to normal hover transitions once revealed.
        const delay = parseFloat(getComputedStyle(el).getPropertyValue("--d")) || 0;
        setTimeout(() => { el.removeAttribute("data-reveal"); el.classList.remove("in"); }, 900 + delay * 1000);
      }
      if (el.hasAttribute("data-count")) countUp(el);
      if (el.matches(".gauge, .fuelbar")) animateMeter(el);
      io.unobserve(el);
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }) : null;

  document.querySelectorAll("[data-reveal], [data-count], .gauge, .fuelbar").forEach((el) => {
    if (io) io.observe(el);
    else el.classList.add("in");
  });

  /* Auto stagger: children of [data-stagger] reveal one after another */
  document.querySelectorAll("[data-stagger]").forEach((group) => {
    const step = parseFloat(group.dataset.stagger) || 0.08;
    [...group.children].forEach((child, i) => {
      if (!child.hasAttribute("data-reveal")) { child.setAttribute("data-reveal", ""); if (io) io.observe(child); }
      child.style.setProperty("--d", (i * step).toFixed(2) + "s");
    });
  });

  /* Hero speed streaks */
  const lines = document.querySelector(".speed-lines");
  if (lines && !reduce) {
    for (let i = 0; i < 14; i++) {
      const s = document.createElement("i");
      s.style.top = (35 + Math.random() * 50) + "%";
      s.style.left = (Math.random() * 100) + "%";
      s.style.width = (60 + Math.random() * 160) + "px";
      s.style.animationDuration = (0.7 + Math.random() * 1.1) + "s";
      s.style.animationDelay = (Math.random() * 2) + "s";
      lines.appendChild(s);
    }
  }

  /* Toasts auto-dismiss */
  document.querySelectorAll(".cc-toast").forEach((t, i) => {
    const close = () => { t.classList.add("out"); setTimeout(() => t.remove(), 400); };
    t.querySelector("button")?.addEventListener("click", close);
    setTimeout(close, 5000 + i * 400);
  });

  /* Subtle 3D tilt on cards marked .tilt (pointer devices only) */
  if (!reduce && window.matchMedia("(hover: hover)").matches) {
    document.querySelectorAll(".tilt").forEach((card) => {
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = `perspective(900px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg) translateY(-6px)`;
      });
      card.addEventListener("mouseleave", () => { card.style.transform = ""; });
    });
  }

  /* Dark-theme defaults for Chart.js (if a page loads it) */
  window.ccChartDefaults = function () {
    if (!window.Chart) return;
    Chart.defaults.color = "#8d96a5";
    Chart.defaults.borderColor = "rgba(255,255,255,.06)";
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  };
})();
