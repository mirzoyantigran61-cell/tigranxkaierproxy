(() => {
  async function render(
    container
  ) {
    const me =
      await TigranAPI.get(
        "/api/auth/me"
      );

    const user =
      me.user || {};

    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Аккаунт
          </div>

          <div class="page-sub">
            Firebase Authentication
          </div>
        </div>

      </div>

      <div class="card">

        <div class="account-header">

          <div class="account-avatar">

            ${
              user.photo_url
                ? `
                  <img
                    src="${user.photo_url}"
                    alt=""
                  >
                `
                : (
                    user.email
                    || "T"
                  )[0]
                    .toUpperCase()
            }

          </div>

          <div>

            <div
              style="
                font-size:18px;
                font-weight:800
              "
            >
              ${
                user.display_name
                || user.email
                || "User"
              }
            </div>

            <div class="muted small">
              ${
                user.email
                || ""
              }
            </div>

            <div
              style="margin-top:6px"
            >
              <span
                class="badge ${
                  user.email_verified
                    ? "success"
                    : "warning"
                }"
              >
                ${
                  user.email_verified
                    ? "Email verified"
                    : "Email not verified"
                }
              </span>
            </div>

          </div>

        </div>

      </div>

      <div style="height:14px">
      </div>

      <div class="card">

        <div class="card-header">

          <div class="card-title">
            Passkeys
          </div>

          <button
            id="add-passkey"
            class="btn"
          >
            + Добавить
          </button>

        </div>

        <div
          id="passkey-list"
          class="credential-list"
        >
        </div>

      </div>
    `;

    document
      .getElementById(
        "add-passkey"
      )
      .onclick =
        async () => {
          const name =
            prompt(
              "Название Passkey",
              "My Passkey"
            );

          if (!name) {
            return;
          }

          try {
            await TigranWebAuthn
              .register(
                name
              );

            window.toast?.(
              "Passkey добавлен",
              "success"
            );

            await loadPasskeys();
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          }
        };

    await loadPasskeys();
  }

  async function loadPasskeys() {
    const box =
      document.getElementById(
        "passkey-list"
      );

    if (!box) {
      return;
    }

    try {
      const data =
        await TigranWebAuthn
          .list();

      const raw =
        data.credentials
        || {};

      const list =
        Array.isArray(raw)
          ? raw
          : Object.entries(raw)
              .map(
                ([id, value]) => ({
                  id,
                  ...value
                })
              );

      if (!list.length) {
        box.innerHTML = `
          <div class="muted small">
            Passkeys пока нет.
          </div>
        `;

        return;
      }

      box.innerHTML =
        list
          .map(
            credential => `
              <div class="credential-item">

                <div>

                  <div class="credential-name">
                    ${
                      credential.name
                      || "Passkey"
                    }
                  </div>

                  <div class="credential-meta">
                    ${
                      credential.id
                      || credential.credential_id
                      || ""
                    }
                  </div>

                </div>

                <button
                  class="btn btn-danger"
                  data-remove-passkey="${
                    credential.id
                    || credential.credential_id
                    || credential.storage_key
                  }"
                >
                  Удалить
                </button>

              </div>
            `
          )
          .join("");

      box
        .querySelectorAll(
          "[data-remove-passkey]"
        )
        .forEach(
          button => {
            button.onclick =
              async () => {
                try {
                  await TigranWebAuthn
                    .remove(
                      button.dataset
                        .removePasskey
                    );

                  window.toast?.(
                    "Passkey удалён",
                    "success"
                  );

                  await loadPasskeys();
                } catch (e) {
                  window.toast?.(
                    e.message,
                    "error"
                  );
                }
              };
          }
        );

    } catch (e) {
      box.innerHTML = `
        <div class="text-danger small">
          ${e.message}
        </div>
      `;
    }
  }

  window.TigranAccount = {
    render
  };
})();
