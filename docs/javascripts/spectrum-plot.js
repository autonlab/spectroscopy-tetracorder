(() => {
  "use strict";

  const chartJsUrl =
    "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js";
  let chartJsPromise;

  function loadChartJs() {
    if (window.Chart) return Promise.resolve(window.Chart);
    if (chartJsPromise) return chartJsPromise;

    chartJsPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = chartJsUrl;
      script.async = true;
      script.crossOrigin = "anonymous";
      script.addEventListener("load", () => resolve(window.Chart));
      script.addEventListener(
        "error",
        () => reject(new Error("Could not load the pinned Chart.js build.")),
      );
      document.head.appendChild(script);
    });
    return chartJsPromise;
  }

  function nearestPoint(points, center) {
    return points.reduce((best, point) =>
      Math.abs(point.x - center) < Math.abs(best.x - center) ? point : best,
    );
  }

  function renderChart(canvas) {
    const example = window.tetracorderpyExamples?.syntheticAviris1995;
    const status = canvas.parentElement.querySelector(".tc-spectrum-status");
    if (!example) throw new Error("The synthetic spectrum data did not load.");

    const points = example.wavelength.map((x, index) => ({
      x,
      y: example.reflectance[index],
    }));
    const featurePoints = [0.92, 2.20, 2.33].map((center) =>
      nearestPoint(points, center),
    );
    const context = canvas.getContext("2d");
    const gradient = context.createLinearGradient(0, 0, canvas.clientWidth, 0);
    gradient.addColorStop(0, "#10ad9d");
    gradient.addColorStop(0.55, "#5f6df2");
    gradient.addColorStop(1, "#d84ea4");
    const styles = getComputedStyle(document.body);
    const ink = styles.getPropertyValue("--md-default-fg-color").trim() || "#17213a";
    const grid = "rgba(130, 145, 175, 0.18)";

    new window.Chart(context, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Synthetic reflectance",
            data: points,
            parsing: false,
            borderColor: gradient,
            borderWidth: 2.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.08,
          },
          {
            label: "Constructed absorption centers",
            data: featurePoints,
            parsing: false,
            borderColor: "#d84ea4",
            backgroundColor: "#d84ea4",
            pointRadius: 4,
            pointHoverRadius: 6,
            showLine: false,
          },
        ],
      },
      options: {
        animation: false,
        maintainAspectRatio: false,
        normalized: false,
        interaction: {
          intersect: false,
          mode: "nearest",
        },
        plugins: {
          legend: {
            labels: {
              color: ink,
              usePointStyle: true,
            },
          },
          tooltip: {
            callbacks: {
              label(item) {
                return `${item.dataset.label}: ${item.parsed.y.toFixed(5)}`;
              },
              title(items) {
                return `${items[0].parsed.x.toFixed(5)} µm`;
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            min: 0.35,
            max: 2.52,
            title: {
              display: true,
              text: "Wavelength (µm)",
              color: ink,
            },
            ticks: { color: ink },
            grid: { color: grid },
          },
          y: {
            suggestedMin: 0.35,
            suggestedMax: 0.56,
            title: {
              display: true,
              text: "Reflectance",
              color: ink,
            },
            ticks: { color: ink },
            grid: { color: grid },
          },
        },
      },
    });
    if (status) status.hidden = true;
  }

  function initialize() {
    const canvases = [...document.querySelectorAll("[data-spectrum-chart]")];
    if (!canvases.length) return;

    loadChartJs()
      .then(() => canvases.forEach(renderChart))
      .catch((error) => {
        canvases.forEach((canvas) => {
          const status = canvas.parentElement.querySelector(".tc-spectrum-status");
          if (status) {
            status.textContent =
              `${error.message} The numeric example and expected output remain available below.`;
          }
        });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
