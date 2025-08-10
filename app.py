<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Workout Timer</title>
  <style>
    /* Existing styles above */

    /* Countdown pill centered and responsive */
    .countdown-pill{border:1px solid #ddd;border-radius:16px;padding:16px 20px;background:#fff;margin:8px auto 12px;max-width:460px}
    .countdown-pill .time-remaining{font-size:clamp(48px,12vw,96px);line-height:1;margin:0}
    .metric-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:8px 0 12px}
    @media (max-width:640px){.metric-row{grid-template-columns:1fr}}
    /* Color the countdown by effort (phase) */
    .timer-display.phase-blue   .countdown-pill{background:#eaf4ff;border-color:#90caf9}
    .timer-display.phase-green  .countdown-pill{background:#e8f5e9;border-color:#81c784}
    .timer-display.phase-yellow .countdown-pill{background:#fff8e1;border-color:#fbc02d}
    .timer-display.phase-orange .countdown-pill{background:#fff3e0;border-color:#ffb74d}
    .timer-display.phase-red    .countdown-pill{background:#ffebee;border-color:#ef9a9a}
    .timer-display.phase-blue   .countdown-pill .time-remaining{color:#1e88e5}
    .timer-display.phase-green  .countdown-pill .time-remaining{color:#2e7d32}
    .timer-display.phase-yellow .countdown-pill .time-remaining{color:#f9a825}
    .timer-display.phase-orange .countdown-pill .time-remaining{color:#fb8c00}
    .timer-display.phase-red    .countdown-pill .time-remaining{color:#e53935}
  </style>
</head>
<body>
  <!-- Other content above -->

  <div id="timer-section" class="timer-display">
    <div class="current-interval">
      <h3>Current Interval: <span id="current-section">-</span></h3>
      <div class="countdown-pill">
        <div id="timer" class="time-remaining">0:00</div>
        <div id="eta-line" class="eta-line" aria-live="polite"></div>
      </div>
      <div id="current-description">-</div>
    </div>

    <div class="metric-row">
      <div class="metric">
        <div class="metric-label">Speed</div>
        <div class="metric-value"><span id="current-speed">-</span><span class="metric-unit"> mph</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Incline</div>
        <div class="metric-value"><span id="current-incline">0</span><span class="metric-unit"> %</span></div>
      </div>
      <!-- Keep a hidden duration node so existing JS can update safely -->
      <span id="current-duration" hidden></span>
    </div>

    <div class="controls">
      <!-- Controls content -->
    </div>
  </div>

  <!-- Other content below -->

  <script>
    // Other JS code above

    function updateDisplay(current) {
      // Other update code

      const spEl = document.getElementById('current-speed'); if (spEl) spEl.textContent = current.speed_mph;
      const duEl = document.getElementById('current-duration'); if (duEl) duEl.textContent = current.duration_min;
      const inEl = document.getElementById('current-incline'); if (inEl) inEl.textContent = current.incline || 0;

      // Other update code
    }

    // Other JS code below
  </script>
</body>
</html>
