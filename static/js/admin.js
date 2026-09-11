(() => {
  function escapeHtml(value) {
    const div =
      document.createElement(
        "div"
      );

    div.textContent =
      String(value ?? "");

    return div.innerHTML;
  }

  function metricCard(
    title,
    value,
    cls = ""
  ) {
    return `
      <div class="card">

        <div class="card-title">
          ${escapeHtml(title)}
        </div>

        <div
          class="card-value ${cls}"
        >
          ${escapeHtml(value)}
        </div>

      </div>
    `;
  }

  async function renderSystem() {
    const grid =
      document.getElementById(
        "admin-system-grid"
      );

    if (!grid) {
      return;
    }

    try {
      const system =
        await TigranAPI.get(
          "/api/admin/system"
        );

      const uptime =
        Number(
          system.uptime || 0
        );

      grid.innerHTML = [
        metricCard(
          "Version",
          system.version ||
          system.app_version ||
          "V4"
        ),

        metricCard(
          "Uptime",
          `${Math.floor(
            uptime / 60
          )} min`
        ),

        metricCard(
          "Sessions",
          system.sessions_count ??
          "—"
        ),

        metricCard(
          "Firebase",
          system.firebase_connected
            ? "ONLINE"
            : "OFFLINE",
          system.firebase_connected
            ? "ok"
            : "err"
        )
      ].join("");

    } catch (e) {
      grid.innerHTML = `
        <div class="card">
          <div class="text-danger">
            ${escapeHtml(e.message)}
          </div>
        </div>
      `;
    }
  }

  async function renderSessions() {
    const box =
      document.getElementById(
        "admin-session-info"
      );

    if (!box) {
      return;
    }

    try {
      const data =
        await TigranAPI.get(
          "/api/admin/sessions"
        );

      box.innerHTML = `
        <div class="metric-row">

          <div class="metric-key">
            Store
          </div>

          <div class="metric-value">
            ${escapeHtml(
              data.store ||
              "—"
            )}
          </div>

        </div>

        <div class="metric-row">

          <div class="metric-key">
            Sessions
          </div>

          <div class="metric-value">
            ${escapeHtml(
              data.count ??
              data.sessions_count ??
              "—"
            )}
          </div>

        </div>
      `;

    } catch (e) {
      box.innerHTML = `
        <div class="text-danger small">
          ${escapeHtml(e.message)}
        </div>
      `;
    }
  }

  async function renderPayments() {
    const box =
      document.getElementById(
        "admin-payment-info"
      );

    if (!box) {
      return;
    }

    try {
      const data =
        await TigranAPI.get(
          "/api/admin/payments"
        );

      const recent =
        Array.isArray(data.recent)
          ? data.recent
          : Object.values(
              data.recent || {}
            );

      box.innerHTML = `
        <div class="grid">

          ${metricCard(
            "Total",
            data.total ?? 0
          )}

          ${metricCard(
            "Success",
            data.success ?? 0,
            "ok"
          )}

          ${metricCard(
            "Pending",
            data.pending ?? 0,
            "warn"
          )}

          ${metricCard(
            "Failed",
            data.failed ?? 0,
            "err"
          )}

        </div>

        <div style="height:14px"></div>

        ${
          recent.length
            ? recent
                .map(payment => `
                  <div
                    class="card"
                    style="
                      margin-bottom:8px;
                      padding:12px
                    "
                  >

                    <div
                      style="
                        font-size:12px;
                        color:var(--text-dim);
                        word-break:break-word
                      "
                    >
                      ${escapeHtml(
                        payment.order_id ||
                        "—"
                      )}
                      •
                      ${escapeHtml(
                        payment.provider ||
                        "—"
                      )}
                      •
                      ${escapeHtml(
                        payment.amount ??
                        "—"
                      )}
                      ${escapeHtml(
                        payment.currency ||
                        ""
                      )}
                    </div>

                    <div
                      style="
                        margin-top:4px;
                        font-weight:700
                      "
                    >
                      ${escapeHtml(
                        payment.status ||
                        "unknown"
                      )}
                    </div>

                  </div>
                `)
                .join("")
            : `
                <div class="muted small">
                  Нет последних платежей.
                </div>
              `
        }
      `;

    } catch (e) {
      box.innerHTML = `
        <div class="text-danger small">
          ${escapeHtml(e.message)}
        </div>
      `;
    }
  }

  async function render(container) {
    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Admin Dashboard
          </div>

          <div class="page-sub">
            Системная информация
          </div>
        </div>

        <button
          id="admin-refresh-btn"
          class="btn btn-secondary"
          type="button"
        >
          Обновить
        </button>

      </div>

      <div
        id="admin-system-grid"
        class="grid"
      ></div>

      <div style="height:18px"></div>

      <div class="grid-2">

        <div class="card">

          <div class="card-title">
            Session Store
          </div>

          <div
            id="admin-session-info"
          ></div>

        </div>

        <div class="card">

          <div class="card-title">
            Server Controls
          </div>

          <div class="card-description">
            Maintenance, AI, Image Generation и Logging
            находятся в отдельном разделе Server Controls.
          </div>

        </div>

      </div>

      <div style="height:22px"></div>

      <div class="card-title">
        Payments
      </div>

      <div
        id="admin-payment-info"
        style="margin-top:10px"
      ></div>
    `;

    const refresh =
      async () => {
        await Promise.allSettled([
          renderSystem(),
          renderSessions(),
          renderPayments()
        ]);
      };

    document
      .getElementById(
        "admin-refresh-btn"
      )
      .onclick =
        refresh;

    await refresh();
  }

  window.TigranAdmin = {
    render
  };
})();
