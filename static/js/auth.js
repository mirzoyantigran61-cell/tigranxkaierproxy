(() => {
  async function syncSession() {
    const user =
      firebase.auth().currentUser;

    if (!user) {
      return null;
    }

    const token =
      await user.getIdToken();

    return TigranAPI.post(
      "/api/auth/session",
      {
        id_token: token
      }
    );
  }

  async function signIn(
    email,
    password
  ) {
    await firebase
      .auth()
      .signInWithEmailAndPassword(
        email,
        password
      );

    await syncSession();
  }

  async function signUp(
    email,
    password
  ) {
    await firebase
      .auth()
      .createUserWithEmailAndPassword(
        email,
        password
      );

    await syncSession();

    try {
      await TigranAPI.post(
        "/api/auth/email-verification",
        {}
      );
    } catch (_) {}
  }

  async function googleLogin() {
    const provider =
      new firebase
        .auth
        .GoogleAuthProvider();

    await firebase
      .auth()
      .signInWithPopup(
        provider
      );

    await syncSession();
  }

  async function resetPassword(
    email
  ) {
    return TigranAPI.post(
      "/api/auth/password-reset",
      {
        email
      }
    );
  }

  async function logout() {
    try {
      await TigranAPI.post(
        "/api/auth/logout",
        {}
      );
    } catch (_) {}

    await firebase
      .auth()
      .signOut();
  }

  function renderLogin(
    container
  ) {
    container.innerHTML = `
      <div class="login-page">
        <div class="login-box">

          <h1>TIGRAN AI</h1>
          <p>
            AI Workspace V4
          </p>

          <div class="form-group">
            <label class="form-label">
              Email
            </label>

            <input
              id="auth-email"
              class="input"
              type="email"
              autocomplete="email"
            >
          </div>

          <div class="form-group">
            <label class="form-label">
              Пароль
            </label>

            <input
              id="auth-password"
              class="input"
              type="password"
              autocomplete="current-password"
            >
          </div>

          <div class="auth-actions">

            <button
              id="login-btn"
              class="btn"
            >
              Войти
            </button>

            <button
              id="signup-btn"
              class="btn btn-secondary"
            >
              Создать аккаунт
            </button>

          </div>

          <div class="auth-divider">
            или
          </div>

          <div class="auth-actions">

            <button
              id="google-btn"
              class="btn btn-secondary"
            >
              Войти через Google
            </button>

            <button
              id="passkey-login-btn"
              class="btn btn-secondary"
            >
              Войти через Passkey
            </button>

            <button
              id="reset-btn"
              class="btn btn-secondary"
            >
              Сбросить пароль
            </button>

          </div>

        </div>
      </div>
    `;

    const email =
      document.getElementById(
        "auth-email"
      );

    const password =
      document.getElementById(
        "auth-password"
      );

    const busy =
      value => {
        document
          .querySelectorAll(
            ".login-box button"
          )
          .forEach(
            button => {
              button.disabled =
                value;
            }
          );
      };

    document
      .getElementById(
        "login-btn"
      )
      .onclick =
        async () => {
          try {
            busy(true);

            await signIn(
              email.value.trim(),
              password.value
            );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          } finally {
            busy(false);
          }
        };

    document
      .getElementById(
        "signup-btn"
      )
      .onclick =
        async () => {
          try {
            busy(true);

            await signUp(
              email.value.trim(),
              password.value
            );

            window.toast?.(
              "Аккаунт создан",
              "success"
            );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          } finally {
            busy(false);
          }
        };

    document
      .getElementById(
        "google-btn"
      )
      .onclick =
        async () => {
          try {
            busy(true);

            await googleLogin();
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          } finally {
            busy(false);
          }
        };

    document
      .getElementById(
        "reset-btn"
      )
      .onclick =
        async () => {
          const value =
            email.value.trim();

          if (!value) {
            window.toast?.(
              "Введите email",
              "warning"
            );
            return;
          }

          try {
            await resetPassword(
              value
            );

            window.toast?.(
              "Если аккаунт существует, письмо отправлено.",
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
        "passkey-login-btn"
      )
      .onclick =
        async () => {
          try {
            await window
              .TigranWebAuthn
              .login(
                email.value.trim()
              );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          }
        };
  }

  window.TigranAuth = {
    syncSession,
    signIn,
    signUp,
    googleLogin,
    resetPassword,
    logout,
    renderLogin
  };
})();
