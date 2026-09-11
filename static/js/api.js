(() => {
  const API = {};

  API.getToken = async function () {
    try {
      if (
        window.firebase &&
        firebase.auth &&
        firebase.auth().currentUser
      ) {
        return await firebase
          .auth()
          .currentUser
          .getIdToken();
      }
    } catch (e) {
      console.error("Token error:", e);
    }

    return "";
  };

  API.request = async function (
    path,
    options = {}
  ) {
    const token = await API.getToken();

    const headers = {
      ...(options.headers || {})
    };

    if (token) {
      headers.Authorization =
        `Bearer ${token}`;
      headers["X-ID-Token"] = token;
    }

    let body = options.body;

    if (
      body &&
      !(body instanceof FormData) &&
      typeof body !== "string"
    ) {
      headers["Content-Type"] =
        "application/json";

      body = JSON.stringify(body);
    }

    const response = await fetch(
      path,
      {
        ...options,
        headers,
        body
      }
    );

    const contentType =
      response.headers.get(
        "content-type"
      ) || "";

    let data = null;

    if (
      contentType.includes(
        "application/json"
      )
    ) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const error =
        new Error(
          data?.message ||
          data?.error ||
          `HTTP ${response.status}`
        );

      error.status =
        response.status;

      error.data =
        data;

      throw error;
    }

    return data;
  };

  API.get = path =>
    API.request(
      path,
      {
        method: "GET"
      }
    );

  API.post = (
    path,
    body
  ) =>
    API.request(
      path,
      {
        method: "POST",
        body
      }
    );

  API.patch = (
    path,
    body
  ) =>
    API.request(
      path,
      {
        method: "PATCH",
        body
      }
    );

  API.delete = path =>
    API.request(
      path,
      {
        method: "DELETE"
      }
    );

  window.TigranAPI = API;
})();
