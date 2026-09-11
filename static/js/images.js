(() => {
  async function loadHistory() {
    const data =
      await TigranAPI.get(
        "/api/images/history"
      );

    return data.images || {};
  }

  function renderHistory(
    images
  ) {
    const box =
      document.getElementById(
        "image-history"
      );

    if (!box) {
      return;
    }

    const list =
      Array.isArray(images)
        ? images
        : Object.values(images);

    box.innerHTML =
      list
        .reverse()
        .map(
          image => {
            const src =
              image.image_url
              || image.url
              || "";

            return `
              <div class="image-card">

                ${
                  src
                    ? `
                      <img
                        src="${src}"
                        alt=""
                        loading="lazy"
                      >
                    `
                    : ""
                }

                <div
                  class="image-card-body"
                >
                  <div
                    class="image-prompt"
                  >
                    ${
                      image.prompt
                      || ""
                    }
                  </div>
                </div>

              </div>
            `;
          }
        )
        .join("");
  }

  async function render(
    container
  ) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">
            Генерация изображений
          </div>

          <div class="page-sub">
            GPT Image
          </div>
        </div>
      </div>

      <div class="card">

        <div class="form-group">

          <label class="form-label">
            Описание изображения
          </label>

          <textarea
            id="image-prompt"
            class="input"
            rows="4"
            placeholder="Опишите изображение..."
          ></textarea>

        </div>

        <button
          id="generate-image-btn"
          class="btn"
        >
          Создать
        </button>

      </div>

      <div
        style="height:16px"
      ></div>

      <div
        id="image-history"
        class="image-grid"
      ></div>
    `;

    document
      .getElementById(
        "generate-image-btn"
      )
      .onclick =
        async () => {
          const button =
            document.getElementById(
              "generate-image-btn"
            );

          const prompt =
            document.getElementById(
              "image-prompt"
            ).value.trim();

          if (!prompt) {
            return;
          }

          try {
            button.disabled = true;

            const result =
              await TigranAPI.post(
                "/api/images/generate",
                {
                  prompt
                }
              );

            const image =
              result.image
              || result.result
              || result;

            if (
              image.url
              || image.image_url
            ) {
              window.open(
                image.url
                || image.image_url,
                "_blank",
                "noopener"
              );
            }

            window.toast?.(
              "Изображение создано",
              "success"
            );

            const history =
              await loadHistory();

            renderHistory(
              history
            );
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          } finally {
            button.disabled = false;
          }
        };

    try {
      renderHistory(
        await loadHistory()
      );
    } catch (_) {}
  }

  window.TigranImages = {
    render
  };
})();
