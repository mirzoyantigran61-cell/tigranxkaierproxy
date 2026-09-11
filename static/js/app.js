(() => {
  const app =
    document.getElementById(
      "app"
    );

  let currentUser = null;
  let currentRole = "user";
  let currentPage = "chat";

  function toast(
    message,
    type = ""
  ) {
    const container =
      document.getElementById(
        "toast-container"
      );

    if (!container) {
      return;
    }

    const element =
      document.createElement(
        "div"
      );

    element.className =
      `toast ${type}`;

    element.textContent =
      message;

    container.appendChild(
      element
    );

    setTimeout(
      () => {
        element.remove();
      },
      3500
    );
  }

  window.toast = toast;

  function navButton(
    page,
    label
  ) {
    return `
      <button
        class="nav-item ${
          currentPage === page
            ? "active"
            : ""
        }"
        data-page="${page}"
      >
        ${label}
      </button>
    `;
  }

  function renderShell() {
    const isAdmin =
      currentRole === "admin";

    app.innerHTML = `
      <button
        id="menu-toggle"
        class="menu-toggle"
      >
        ☰
      </button>

      <div
        id="sidebar-overlay"
        class="overlay"
      ></div>

      <div class="layout">

        <aside
          id="sidebar"
          class="sidebar"
        >

          <div class="logo">
            TIGRAN AI
          </div>

          <div class="nav-group">

            ${
              navButton(
                "chat",
                "✦ Чат"
              )
            }

            ${
              navButton(
                "images",
                "◈ Изображения"
              )
            }

            ${
              navButton(
                "dashboard",
                "▦ Dashboard"
              )
            }

            ${
              navButton(
                "account",
                "◉ Аккаунт"
              )
            }

            ${
              navButton(
                "settings",
                "⚙ Настройки"
              )
            }

            ${
              isAdmin
                ? navButton(
                    "server",
                    "⌁ Server Controls"
                  )
                : ""
            }

          </div>

          <div class="sidebar-bottom">

            <div class="user-card">

              <div class="avatar">
                ${
                  (
                    currentUser?.email
                    || "T"
                  )[0]
                    .toUpperCase()
                }
              </div>

              <div class="user-meta">

                <div class="user-name">
                  ${
                    currentUser
                      ?.display_name
                    ||
                    currentUser
                      ?.email
                    ||
                    "User"
                  }
                </div>

                <div class="user-email">
                  ${
                    currentUser
                      ?.email
                    || ""
                  }
                </div>

              </div>

            </div>

            <button
              id="logout-btn"
              class="nav-item"
            >
              Выйти
            </button>

          </div>

        </aside>

        <main
          id="main-view"
          class="main"
        ></main>

      </div>
    `;

    document
      .querySelectorAll(
        "[data-page]"
      )
      .forEach(
        button => {
          button.onclick =
            () => {
              openPage(
                button.dataset
                  .page
              );
            };
        }
      );

    document
      .getElementById(
        "logout-btn"
      )
      .onclick =
        () =>
          TigranAuth.logout();

    const sidebar =
      document.getElementById(
        "sidebar"
      );

    const overlay =
      document.getElementById(
        "sidebar-overlay"
      );

    document
      .getElementById(
        "menu-toggle"
      )
      .onclick =
        () => {
          sidebar.classList
            .toggle(
              "open"
            );

          overlay.classList
            .toggle(
              "open"
            );
        };

    overlay.onclick =
      () => {
        sidebar.classList
          .remove(
            "open"
          );

        overlay.classList
          .remove(
            "open"
          );
      };

    openPage(
      currentPage
    );
  }

  async function openPage(
    page
  ) {
    currentPage = page;

    document
      .querySelectorAll(
        ".nav-item[data-page]"
      )
      .forEach(
        button => {
          button.classList
            .toggle(
              "active",
              button.dataset
                .page === page
            );
        }
      );

    const main =
      document.getElementById(
        "main-view"
      );

    if (!main) {
      return;
    }

    main.innerHTML = `
      <div class="initial-loader">
        <div class="initial-loader-spinner">
        </div>
      </div>
    `;

    try {
      if (
        page === "chat"
      ) {
        await TigranChat
          .render(
            main
          );

      } else if (
        page === "images"
      ) {
        await TigranImages
          .render(
            main
          );

      } else if (
        page === "dashboard"
      ) {
        await TigranDashboard
          .render(
            main
          );

      } else if (
        page === "account"
      ) {
        await TigranAccount
          .render(
            main
          );

      } else if (
        page === "settings"
      ) {
        await TigranSettings
          .render(
            main
          );

      } else if (
        page === "server"
        &&
        currentRole ===
        "admin"
      ) {
        await TigranServerControls
          .render(
            main
          );

      } else {
        main.innerHTML = `
          <div class="card">
            Страница недоступна.
          </div>
        `;
      }

    } catch (e) {
      console.error(e);

      main.innerHTML = `
        <div class="card">

          <div class="card-title">
            Ошибка
          </div>

          <div class="text-danger">
            ${escapeHtml(e.message)}
          </div>

        </div>
      `;
    }
  }

  function escapeHtml(
    text
  ) {
    const div =
      document.createElement(
        "div"
      );

    div.textContent =
      String(text || "");

    return div.innerHTML;
  }

  async function loadUser() {
    try {
      const data =
        await TigranAPI.get(
          "/api/auth/me"
        );

      currentUser =
        data.user || {};

      currentRole =
        currentUser.role
        || "user";

      return true;
    } catch (e) {
      console.error(
        "Could not load user:",
        e
      );

      return false;
    }
  }

  async function start() {
    app.innerHTML = `
      <div class="initial-loader">

        <div class="initial-loader-logo">
          TIGRAN AI
        </div>

        <div class="initial-loader-spinner">
        </div>

        <div class="initial-loader-text">
          Запуск V4...
        </div>

      </div>
    `;

    const firebaseReady =
      await TigranFirebase
        .initFirebase();

    if (!firebaseReady) {
      app.innerHTML = `
        <div class="login-page">

          <div class="login-box">

            <h1>TIGRAN AI</h1>

            <p>
              Firebase configuration unavailable.
            </p>

          </div>

        </div>
      `;

      return;
    }

    firebase
      .auth()
      .onAuthStateChanged(
        async user => {
          if (!user) {
            currentUser = null;
            currentRole = "user";

            TigranAuth
              .renderLogin(
                app
              );

            return;
          }

          try {
            await TigranAuth
              .syncSession();
          } catch (e) {
            console.error(
              "Session sync:",
              e
            );
          }

          const loaded =
            await loadUser();

          if (!loaded) {
            TigranAuth
              .renderLogin(
                app
              );

            return;
          }

          renderShell();
        }
      );
  }

  window.addEventListener(
    "DOMContentLoaded",
    start
  );
})();
