(() => {
  const state = {
    ready: false,
    config: null
  };

  async function initFirebase() {
    try {
      const response =
        await fetch(
          "/api/config/public"
        );

      const data =
        await response.json();

      const config =
        data.firebase || {};

      state.config = config;

      if (
        !config.apiKey ||
        !config.projectId
      ) {
        console.warn(
          "Firebase web config missing"
        );

        state.ready = false;
        return false;
      }

      if (
        !firebase.apps.length
      ) {
        firebase.initializeApp(
          config
        );
      }

      await firebase
        .auth()
        .setPersistence(
          firebase.auth
            .Auth
            .Persistence
            .LOCAL
        );

      state.ready = true;

      return true;
    } catch (e) {
      console.error(
        "Firebase init failed:",
        e
      );

      state.ready = false;

      return false;
    }
  }

  window.TigranFirebase = {
    state,
    initFirebase
  };
})();
