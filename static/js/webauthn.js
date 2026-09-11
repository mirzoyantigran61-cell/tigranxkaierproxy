(() => {
  function b64urlToBytes(
    value
  ) {
    value =
      value
        .replace(/-/g, "+")
        .replace(/_/g, "/");

    while (
      value.length % 4
    ) {
      value += "=";
    }

    const raw =
      atob(value);

    return Uint8Array.from(
      raw,
      c => c.charCodeAt(0)
    );
  }

  function bytesToB64url(
    buffer
  ) {
    const bytes =
      new Uint8Array(
        buffer
      );

    let binary = "";

    for (
      const byte
      of bytes
    ) {
      binary +=
        String.fromCharCode(
          byte
        );
    }

    return btoa(binary)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  }

  function prepareCreationOptions(
    options
  ) {
    const publicKey =
      options.publicKey
      || options;

    publicKey.challenge =
      b64urlToBytes(
        publicKey.challenge
      );

    if (
      publicKey.user?.id
    ) {
      publicKey.user.id =
        b64urlToBytes(
          publicKey.user.id
        );
    }

    if (
      Array.isArray(
        publicKey.excludeCredentials
      )
    ) {
      publicKey
        .excludeCredentials
        .forEach(
          item => {
            item.id =
              b64urlToBytes(
                item.id
              );
          }
        );
    }

    return publicKey;
  }

  function prepareRequestOptions(
    options
  ) {
    const publicKey =
      options.publicKey
      || options;

    publicKey.challenge =
      b64urlToBytes(
        publicKey.challenge
      );

    if (
      Array.isArray(
        publicKey.allowCredentials
      )
    ) {
      publicKey
        .allowCredentials
        .forEach(
          item => {
            item.id =
              b64urlToBytes(
                item.id
              );
          }
        );
    }

    return publicKey;
  }

  function serializeCredential(
    credential
  ) {
    const response =
      credential.response;

    const data = {
      id:
        credential.id,

      rawId:
        bytesToB64url(
          credential.rawId
        ),

      type:
        credential.type,

      response: {}
    };

    if (
      response.clientDataJSON
    ) {
      data.response
        .clientDataJSON =
        bytesToB64url(
          response.clientDataJSON
        );
    }

    if (
      response
        .attestationObject
    ) {
      data.response
        .attestationObject =
        bytesToB64url(
          response
            .attestationObject
        );
    }

    if (
      response
        .authenticatorData
    ) {
      data.response
        .authenticatorData =
        bytesToB64url(
          response
            .authenticatorData
        );
    }

    if (
      response.signature
    ) {
      data.response
        .signature =
        bytesToB64url(
          response.signature
        );
    }

    if (
      response.userHandle
    ) {
      data.response
        .userHandle =
        bytesToB64url(
          response.userHandle
        );
    }

    if (
      typeof response
        .getTransports
      === "function"
    ) {
      data.response
        .transports =
        response
          .getTransports();
    }

    return data;
  }

  async function register(
    name = "Passkey"
  ) {
    if (
      !window
        .PublicKeyCredential
    ) {
      throw new Error(
        "Passkeys не поддерживаются этим браузером"
      );
    }

    const start =
      await TigranAPI.post(
        "/api/auth/passkeys/register/options",
        {}
      );

    const publicKey =
      prepareCreationOptions(
        start.options
        || start.publicKey
        || start
      );

    const credential =
      await navigator
        .credentials
        .create({
          publicKey
        });

    if (!credential) {
      throw new Error(
        "Passkey creation cancelled"
      );
    }

    return TigranAPI.post(
      "/api/auth/passkeys/register/verify",
      {
        ceremony_id:
          start.ceremony_id,

        credential:
          serializeCredential(
            credential
          ),

        name
      }
    );
  }

  async function login(
    email
  ) {
    if (
      !window
        .PublicKeyCredential
    ) {
      throw new Error(
        "Passkeys не поддерживаются"
      );
    }

    const start =
      await TigranAPI.post(
        "/api/auth/passkeys/login/options",
        {
          email
        }
      );

    const publicKey =
      prepareRequestOptions(
        start.options
        || start.publicKey
        || start
      );

    const credential =
      await navigator
        .credentials
        .get({
          publicKey
        });

    if (!credential) {
      throw new Error(
        "Passkey login cancelled"
      );
    }

    const result =
      await TigranAPI.post(
        "/api/auth/passkeys/login/verify",
        {
          ceremony_id:
            start.ceremony_id,

          credential:
            serializeCredential(
              credential
            )
        }
      );

    const token =
      result.custom_token
      || result.token;

    if (!token) {
      throw new Error(
        "Firebase custom token missing"
      );
    }

    await firebase
      .auth()
      .signInWithCustomToken(
        token
      );

    await TigranAuth
      .syncSession();

    return result;
  }

  async function list() {
    return TigranAPI.get(
      "/api/auth/passkeys"
    );
  }

  async function remove(
    id
  ) {
    return TigranAPI.delete(
      `/api/auth/passkeys/${encodeURIComponent(id)}`
    );
  }

  window.TigranWebAuthn = {
    register,
    login,
    list,
    remove
  };
})();
