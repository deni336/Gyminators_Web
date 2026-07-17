(() => {
  "use strict";

  document.querySelectorAll("[data-signature-pad]").forEach((pad) => {
    const canvas = pad.querySelector("[data-signature-canvas]");
    const clearButton = pad.querySelector("[data-signature-clear]");
    const output = document.querySelector("[data-signature-output]");
    const form = canvas.closest("form");
    const error = pad.querySelector("[data-signature-error]");
    const submitButton = form.querySelector("[data-submit-button]");
    const context = canvas.getContext("2d", { alpha: true });
    let drawing = false;
    let hasInk = false;
    let previous = null;

    const point = (event) => {
      const rect = canvas.getBoundingClientRect();
      const source = event.touches ? event.touches[0] : event;
      return {
        x: (source.clientX - rect.left) * (canvas.width / rect.width),
        y: (source.clientY - rect.top) * (canvas.height / rect.height),
      };
    };

    const configurePen = () => {
      context.strokeStyle = "#252422";
      context.lineWidth = Math.max(3, canvas.width / 260);
      context.lineCap = "round";
      context.lineJoin = "round";
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const old = document.createElement("canvas");
      old.width = canvas.width || 1;
      old.height = canvas.height || 1;
      old.getContext("2d").drawImage(canvas, 0, 0);
      const ratio = Math.min(
        window.devicePixelRatio || 1,
        2,
        1800 / rect.width,
        900 / rect.height
      );
      const width = Math.round(rect.width * ratio);
      const height = Math.round(rect.height * ratio);
      if (canvas.width === width && canvas.height === height) return;
      canvas.width = width;
      canvas.height = height;
      configurePen();
      if (hasInk) context.drawImage(old, 0, 0, old.width, old.height, 0, 0, width, height);
    };

    const begin = (event) => {
      event.preventDefault();
      drawing = true;
      previous = point(event);
      if (event.pointerId !== undefined) canvas.setPointerCapture(event.pointerId);
    };

    const move = (event) => {
      if (!drawing) return;
      event.preventDefault();
      const current = point(event);
      context.beginPath();
      context.moveTo(previous.x, previous.y);
      context.lineTo(current.x, current.y);
      context.stroke();
      previous = current;
      hasInk = true;
      error.hidden = true;
    };

    const end = (event) => {
      if (drawing && event) event.preventDefault();
      drawing = false;
      previous = null;
    };

    if (window.PointerEvent) {
      canvas.addEventListener("pointerdown", begin);
      canvas.addEventListener("pointermove", move);
      canvas.addEventListener("pointerup", end);
      canvas.addEventListener("pointercancel", end);
    } else {
      canvas.addEventListener("mousedown", begin);
      canvas.addEventListener("mousemove", move);
      window.addEventListener("mouseup", end);
      canvas.addEventListener("touchstart", begin, { passive: false });
      canvas.addEventListener("touchmove", move, { passive: false });
      canvas.addEventListener("touchend", end, { passive: false });
    }

    clearButton.addEventListener("click", () => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      output.value = "";
      hasInk = false;
      error.hidden = true;
      canvas.focus();
    });

    form.addEventListener("submit", (event) => {
      if (!hasInk) {
        event.preventDefault();
        error.textContent = "Draw your signature before submitting.";
        error.hidden = false;
        canvas.focus();
        return;
      }
      output.value = canvas.toDataURL("image/png");
      if (form.checkValidity()) {
        submitButton.disabled = true;
        submitButton.textContent = "Submitting…";
      }
    });

    if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);
    window.addEventListener("resize", resize, { passive: true });
    resize();
  });
})();
