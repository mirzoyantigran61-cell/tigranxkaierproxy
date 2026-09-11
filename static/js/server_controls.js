(() => {
  const labels = {
    maintenance_mode:
      "Maintenance Mode",

    ai_enabled:
      "AI",

    image_gen_enabled:
      "Image Generation",

    logging:
      "Logging"
  };

  async function render(
    container
  ) {
    const data =
      await TigranAPI.get(
        "/api/server-controls"
      );

    const settings =
      data.settings || {};

    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Server Controls
          </div>

          <div class="page-sub">
            Admin only
          </div>
        </div>

      </div>

      <div class="admin-warning">
        Изменения применяются на сервере.
      </div>

      <div style="height:14px">
      </div>

      <div class="card control-section">

        ${
          Object
            .entries(labels)
            .map(
              ([key, title]) => `
                <div class="switch-row">

                  <div class="switch-meta">

                    <div class="switch-title">
                      ${title}
                    </div>

                    <div class="switch-description">
                      ${key}
                    </div>

                  </div>

                  <label class="switch">

                    <input
                      type="checkbox"
                      data-setting="${key}"
                      ${
                        settings[key]
                          ? "checked"
                          : ""
                      }
                    >

                    <span
                      class="switch-slider"
                    ></span>

                  </label>

                </div>
              `
            )
            .join("")
        }

      </div>
    `;

    container
      .querySelectorAll(
        "[data-setting]"
      )
      .forEach(
        input => {
          input.onchange =
            async () => {
              const key =
                input.dataset
                  .setting;

              try {
                await TigranAPI.patch(
                  "/api/server-controls",
                  {
                    [key]:
                      input.checked
                  }
                );

                window.toast?.(
                  "Настройка обновлена",
                  "success"
                );
              } catch (e) {
                input.checked =
                  !input.checked;

                window.toast?.(
                  e.message,
                  "error"
                );
              }
            };
        }
      );
  }

  window.TigranServerControls = {
    render
  };
})();
