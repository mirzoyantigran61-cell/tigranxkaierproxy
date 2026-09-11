(() => {
  async function render(
    container
  ) {
    const data =
      await TigranAPI.get(
        "/api/settings"
      );

    const settings =
      data.settings
      || data
      || {};

    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Настройки
          </div>

          <div class="page-sub">
            Персонализация TIGRAN AI
          </div>
        </div>

      </div>

      <div class="card">

        <div class="form-group">

          <label class="form-label">
            Язык
          </label>

          <select
            id="setting-language"
            class="select"
          >
            <option value="ru">
              Русский
            </option>

            <option value="en">
              English
            </option>

            <option value="hy">
              Հայերեն
            </option>
          </select>

        </div>

        <div class="form-group">

          <label class="form-label">
            Тема
          </label>

          <select
            id="setting-theme"
            class="select"
          >
            <option value="dark">
              Dark
            </option>

            <option value="light">
              Light
            </option>

            <option value="system">
              System
            </option>
          </select>

        </div>

        <div class="switch-row">

          <div>
            <div class="switch-title">
              Notifications
            </div>
          </div>

          <label class="switch">

            <input
              id="setting-notifications"
              type="checkbox"
            >

            <span
              class="switch-slider"
            ></span>

          </label>

        </div>

        <div class="switch-row">

          <div>
            <div class="switch-title">
              Animations
            </div>
          </div>

          <label class="switch">

            <input
              id="setting-animations"
              type="checkbox"
            >

            <span
              class="switch-slider"
            ></span>

          </label>

        </div>

        <div style="height:14px">
        </div>

        <button
          id="save-settings"
          class="btn"
        >
          Сохранить
        </button>

        <button
          id="reset-settings"
          class="btn btn-secondary"
        >
          Сбросить
        </button>

      </div>
    `;

    const language =
      document.getElementById(
        "setting-language"
      );

    const theme =
      document.getElementById(
        "setting-theme"
      );

    const notifications =
      document.getElementById(
        "setting-notifications"
      );

    const animations =
      document.getElementById(
        "setting-animations"
      );

    language.value =
      settings.language
      || "ru";

    theme.value =
      settings.theme
      || "dark";

    notifications.checked =
      settings.notifications
      !== false;

    animations.checked =
      settings.animations
      !== false;

    document
      .getElementById(
        "save-settings"
      )
      .onclick =
        async () => {
          try {
            await TigranAPI.patch(
              "/api/settings",
              {
                language:
                  language.value,

                theme:
                  theme.value,

                notifications:
                  notifications.checked,

                animations:
                  animations.checked
              }
            );

            TigranI18N
              .setLanguage(
                language.value
              );

            window.toast?.(
              "Настройки сохранены",
              "success"
            );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          }
        };

    document
      .getElementById(
        "reset-settings"
      )
      .onclick =
        async () => {
          try {
            await TigranAPI.delete(
              "/api/settings"
            );

            window.toast?.(
              "Настройки сброшены",
              "success"
            );

            render(
              container
            );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          }
        };
  }

  window.TigranSettings = {
    render
  };
})();
