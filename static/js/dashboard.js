(() => {
  let timer = null;

  function deviceTelemetry() {
    return {
      browser:
        navigator.userAgent,

      platform:
        navigator.platform,

      language:
        navigator.language,

      timezone:
        Intl
          .DateTimeFormat()
          .resolvedOptions()
          .timeZone,

      screen_width:
        screen.width,

      screen_height:
        screen.height,

      pixel_ratio:
        window.devicePixelRatio,

      touch:
        navigator.maxTouchPoints > 0,

      online:
        navigator.onLine
    };
  }

  async function sendTelemetry() {
    const started =
      performance.now();

    try {
      await TigranAPI.get(
        "/api/ping"
      );

      const latency =
        Math.round(
          performance.now()
          - started
        );

      await TigranAPI.post(
        "/api/dashboard/telemetry",
        {
          ...deviceTelemetry(),
          latency_ms:
            latency
        }
      );
    } catch (_) {}
  }

  function metric(
    key,
    value
  ) {
    return `
      <div class="metric-row">

        <div class="metric-key">
          ${key}
        </div>

        <div class="metric-value">
          ${
            value ??
            "—"
          }
        </div>

      </div>
    `;
  }

  async function render(
    container
  ) {
    if (timer) {
      clearInterval(
        timer
      );

      timer = null;
    }

    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Dashboard
          </div>

          <div class="page-sub">
            TIGRAN AI V4
          </div>
        </div>

      </div>

      <div
        id="dashboard-content"
        class="grid"
      ></div>
    `;

    await refresh();

    sendTelemetry();

    timer =
      setInterval(
        () => {
          refresh();
        },
        30000
      );
  }

  async function refresh() {
    const root =
      document.getElementById(
        "dashboard-content"
      );

    if (!root) {
      return;
    }

    try {
      const data =
        await TigranAPI.get(
          "/api/dashboard/overview"
        );

      const profile =
        data.profile || {};

      root.innerHTML = `
        <div class="card">

          <div class="card-title">
            Пользователь
          </div>

          <div class="card-value">
            ${
              profile.email
              || "—"
            }
          </div>

        </div>

        <div class="card">

          <div class="card-title">
            Чаты
          </div>

          <div class="card-value">
            ${
              data.chat_count
              ?? data.chats
              ?? 0
            }
          </div>

        </div>

        <div class="card">

          <div class="card-title">
            Изображения
          </div>

          <div class="card-value">
            ${
              data.image_count
              ?? data.images
              ?? 0
            }
          </div>

        </div>

        <div class="card">

          <div class="card-title">
            Server Time
          </div>

          <div class="card-description">
            ${
              data.server_time
              || "—"
            }
          </div>

        </div>

        <div class="card">

          <div class="card-title">
            Device
          </div>

          ${
            metric(
              "Browser",
              navigator.userAgent
            )
          }

          ${
            metric(
              "Language",
              navigator.language
            )
          }

          ${
            metric(
              "Timezone",
              Intl
                .DateTimeFormat()
                .resolvedOptions()
                .timeZone
            )
          }

          ${
            metric(
              "Screen",
              `${screen.width} × ${screen.height}`
            )
          }

        </div>
      `;
    } catch (e) {
      root.innerHTML = `
        <div class="card">
          ${e.message}
        </div>
      `;
    }
  }

  window.TigranDashboard = {
    render
  };
})();
