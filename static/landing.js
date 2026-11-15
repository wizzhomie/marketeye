(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- eyes follow the pointer ------------------------------------------ */
  const eyeGroups = Array.from(document.querySelectorAll("[data-eyes]"));

  if (!reduceMotion && eyeGroups.length > 0) {
    let frame = 0;
    let pointerX = window.innerWidth / 2;
    let pointerY = window.innerHeight * 0.4;

    const update = () => {
      frame = 0;
      for (const group of eyeGroups) {
        for (const eye of group.querySelectorAll(".eye")) {
          const pupil = eye.querySelector(".eye__pupil");
          if (!pupil) continue;

          const rect = eye.getBoundingClientRect();
          const cx = rect.left + rect.width / 2;
          const cy = rect.top + rect.height / 2;
          const dx = pointerX - cx;
          const dy = pointerY - cy;
          const distance = Math.hypot(dx, dy) || 1;
          const reach = rect.width * 0.17;
          const strength = Math.min(1, distance / 240);

          pupil.style.setProperty("--px", `${(dx / distance) * reach * strength}px`);
          pupil.style.setProperty("--py", `${(dy / distance) * reach * strength}px`);
        }
      }
    };

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    window.addEventListener(
      "pointermove",
      (event) => {
        pointerX = event.clientX;
        pointerY = event.clientY;
        schedule();
      },
      { passive: true }
    );

    window.addEventListener("resize", schedule);
    window.addEventListener("blur", () => {
      pointerX = window.innerWidth / 2;
      pointerY = window.innerHeight * 0.4;
      schedule();
    });

    update();
  }

  /* --- reveal blocks on scroll ------------------------------------------- */
  const reveals = Array.from(document.querySelectorAll(".reveal"));
  if (reveals.length === 0) return;

  if (reduceMotion || !("IntersectionObserver" in window)) {
    reveals.forEach((element) => element.classList.add("is-in"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      }
    },
    { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
  );

  reveals.forEach((element) => observer.observe(element));
})();
