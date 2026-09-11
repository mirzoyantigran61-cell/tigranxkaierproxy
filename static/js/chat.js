(() => {
  let activeChatId = null;
  let abortController = null;
  let attachment = null;
  let streaming = false;

  const state = {
    chats: [],
    messages: []
  };

  // ============================================================
  // HELPERS
  // ============================================================

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = String(text ?? "");
    return div.innerHTML;
  }

  function markdown(text) {
    try {
      if (!window.marked) {
        return escapeHtml(text);
      }

      const html = marked.parse(
        String(text || ""),
        {
          breaks: true,
          gfm: true
        }
      );

      return window.DOMPurify
        ? DOMPurify.sanitize(html)
        : html;
    } catch (_) {
      return escapeHtml(text);
    }
  }

  async function authHeaders(
    extra = {}
  ) {
    const token =
      await TigranAPI.getToken();

    return {
      ...extra,

      ...(token
        ? {
            Authorization:
              `Bearer ${token}`,

            "X-ID-Token":
              token
          }
        : {})
    };
  }

  function normalizeChats(raw) {
    if (Array.isArray(raw)) {
      return raw.map(chat => ({
        id:
          chat.id ||
          chat.chat_id,

        ...chat
      }));
    }

    return Object.entries(
      raw || {}
    ).map(([id, value]) => ({
      id,
      ...value
    }));
  }

  function normalizeMessages(raw) {
    if (Array.isArray(raw)) {
      return raw;
    }

    return Object.entries(
      raw || {}
    )
      .sort(
        (a, b) =>
          Number(
            a[1]?.ts || 0
          ) -
          Number(
            b[1]?.ts || 0
          )
      )
      .map(
        ([id, value]) => ({
          id,
          ...value
        })
      );
  }

  // ============================================================
  // CHATS
  // ============================================================

  async function loadChats() {
    const data =
      await TigranAPI.get(
        "/api/ai/chats"
      );

    state.chats =
      normalizeChats(
        data.chats || {}
      );

    renderChatList();

    return state.chats;
  }

  async function openChat(id) {
    try {
      activeChatId = id;

      const data =
        await TigranAPI.get(
          `/api/ai/chats/${encodeURIComponent(id)}`
        );

      const chat =
        data.chat || data;

      state.messages =
        normalizeMessages(
          chat.messages ||
          data.messages ||
          {}
        );

      renderMessages();
      renderChatList();
    } catch (e) {
      window.toast?.(
        e.message,
        "error"
      );
    }
  }

  async function newChat() {
    if (streaming) {
      stop();
    }

    activeChatId = null;
    attachment = null;
    state.messages = [];

    clearAttachment();
    renderMessages();
    renderChatList();
  }

  async function renameChat(
    chatId
  ) {
    const chat =
      state.chats.find(
        item =>
          String(item.id) ===
          String(chatId)
      );

    const title =
      window.prompt(
        "Новое название чата:",
        chat?.title ||
        "Новый чат"
      );

    if (!title?.trim()) {
      return;
    }

    try {
      await TigranAPI.patch(
        `/api/ai/chats/${encodeURIComponent(chatId)}`,
        {
          title:
            title.trim()
        }
      );

      await loadChats();

      window.toast?.(
        "Чат переименован",
        "success"
      );
    } catch (e) {
      window.toast?.(
        e.message,
        "error"
      );
    }
  }

  async function deleteChat(
    chatId
  ) {
    const confirmed =
      window.confirm(
        "Удалить этот чат?"
      );

    if (!confirmed) {
      return;
    }

    try {
      await TigranAPI.delete(
        `/api/ai/chats/${encodeURIComponent(chatId)}`
      );

      if (
        String(activeChatId) ===
        String(chatId)
      ) {
        activeChatId = null;
        state.messages = [];
        renderMessages();
      }

      await loadChats();

      window.toast?.(
        "Чат удалён",
        "success"
      );
    } catch (e) {
      window.toast?.(
        e.message,
        "error"
      );
    }
  }

  function renderChatList() {
    const box =
      document.getElementById(
        "chat-list"
      );

    if (!box) {
      return;
    }

    if (!state.chats.length) {
      box.innerHTML = `
        <div
          class="muted small"
          style="padding:10px"
        >
          История пока пуста
        </div>
      `;

      return;
    }

    box.innerHTML =
      state.chats
        .map(chat => {
          const id =
            chat.id ||
            chat.chat_id;

          return `
            <div
              class="chat-item ${
                String(id) ===
                String(activeChatId)
                  ? "active"
                  : ""
              }"
              data-chat-id="${escapeHtml(id)}"
            >

              <div
                class="chat-item-title"
              >
                ${escapeHtml(
                  chat.title ||
                  "Новый чат"
                )}
              </div>

              <div
                class="chat-item-actions"
              >

                <button
                  type="button"
                  title="Переименовать"
                  data-chat-rename="${escapeHtml(id)}"
                >
                  ✎
                </button>

                <button
                  type="button"
                  title="Удалить"
                  data-chat-delete="${escapeHtml(id)}"
                >
                  ✕
                </button>

              </div>

            </div>
          `;
        })
        .join("");

    box
      .querySelectorAll(
        "[data-chat-id]"
      )
      .forEach(element => {
        element.addEventListener(
          "click",
          event => {
            if (
              event.target.closest(
                "[data-chat-rename], [data-chat-delete]"
              )
            ) {
              return;
            }

            openChat(
              element.dataset
                .chatId
            );
          }
        );
      });

    box
      .querySelectorAll(
        "[data-chat-rename]"
      )
      .forEach(button => {
        button.onclick =
          event => {
            event.stopPropagation();

            renameChat(
              button.dataset
                .chatRename
            );
          };
      });

    box
      .querySelectorAll(
        "[data-chat-delete]"
      )
      .forEach(button => {
        button.onclick =
          event => {
            event.stopPropagation();

            deleteChat(
              button.dataset
                .chatDelete
            );
          };
      });
  }

  // ============================================================
  // MESSAGES
  // ============================================================

  function renderMessages() {
    const box =
      document.getElementById(
        "chat-messages"
      );

    if (!box) {
      return;
    }

    if (!state.messages.length) {
      box.innerHTML = `
        <div
          class="muted small"
          style="
            margin:auto;
            text-align:center;
            padding:30px
          "
        >
          Напиши сообщение TIGRAN AI
        </div>
      `;

      return;
    }

    box.innerHTML =
      state.messages
        .map(
          (message, index) => {
            const role =
              message.role === "user"
                ? "user"
                : "ai";

            const text =
              message.content ??
              message.text ??
              "";

            return `
              <div
                class="msg ${role}"
              >

                <div class="msg-body">
                  ${
                    role === "ai"
                      ? markdown(text)
                      : escapeHtml(text)
                          .replace(
                            /\n/g,
                            "<br>"
                          )
                  }
                </div>

                <div class="msg-actions">

                  <button
                    type="button"
                    data-copy-message="${index}"
                  >
                    Copy
                  </button>

                </div>

              </div>
            `;
          }
        )
        .join("");

    box
      .querySelectorAll(
        "[data-copy-message]"
      )
      .forEach(button => {
        button.onclick =
          async () => {
            const message =
              state.messages[
                Number(
                  button.dataset
                    .copyMessage
                )
              ];

            try {
              await navigator
                .clipboard
                .writeText(
                  String(
                    message?.content ??
                    message?.text ??
                    ""
                  )
                );

              window.toast?.(
                "Скопировано",
                "success"
              );
            } catch (_) {
              window.toast?.(
                "Не удалось скопировать",
                "error"
              );
            }
          };
      });

    if (window.hljs) {
      box
        .querySelectorAll(
          "pre code"
        )
        .forEach(block => {
          try {
            hljs.highlightElement(
              block
            );
          } catch (_) {}
        });
    }

    box.scrollTop =
      box.scrollHeight;
  }

  // ============================================================
  // ATTACHMENT / VISION
  // ============================================================

  function clearAttachment() {
    attachment = null;

    const input =
      document.getElementById(
        "chat-attachment-input"
      );

    if (input) {
      input.value = "";
    }

    const preview =
      document.getElementById(
        "chat-attachment-preview"
      );

    if (preview) {
      preview.innerHTML = "";
    }
  }

  function setAttachment(file) {
    const allowed = [
      "image/jpeg",
      "image/png",
      "image/webp"
    ];

    if (
      !allowed.includes(
        file.type
      )
    ) {
      window.toast?.(
        "Разрешены JPEG, PNG и WEBP",
        "warning"
      );

      clearAttachment();
      return;
    }

    if (
      file.size >
      8 * 1024 * 1024
    ) {
      window.toast?.(
        "Максимальный размер изображения — 8 MB",
        "warning"
      );

      clearAttachment();
      return;
    }

    attachment = file;

    const preview =
      document.getElementById(
        "chat-attachment-preview"
      );

    if (!preview) {
      return;
    }

    const url =
      URL.createObjectURL(
        file
      );

    preview.innerHTML = `
      <div class="attach-item">

        <img
          src="${url}"
          alt="Attachment preview"
        >

        <button
          type="button"
          id="remove-chat-attachment"
          aria-label="Удалить изображение"
        >
          ✕
        </button>

      </div>
    `;

    document
      .getElementById(
        "remove-chat-attachment"
      )
      .onclick =
        () => {
          URL.revokeObjectURL(
            url
          );

          clearAttachment();
        };
  }

  async function sendVision(
    prompt
  ) {
    if (!attachment) {
      return;
    }

    const file =
      attachment;

    const text =
      String(
        prompt ||
        "Что изображено на этом изображении?"
      ).trim();

    state.messages.push({
      role: "user",
      content:
        `${text}\n📎 Image`
    });

    renderMessages();

    const form =
      new FormData();

    form.append(
      "image",
      file
    );

    form.append(
      "prompt",
      text
    );

    const token =
      await TigranAPI.getToken();

    clearAttachment();

    const response =
      await fetch(
        "/api/ai/vision",
        {
          method: "POST",

          headers: token
            ? {
                Authorization:
                  `Bearer ${token}`,

                "X-ID-Token":
                  token
              }
            : {},

          body: form
        }
      );

    const data =
      await response
        .json()
        .catch(
          () => ({})
        );

    if (!response.ok) {
      throw new Error(
        data.message ||
        data.error ||
        `HTTP ${response.status}`
      );
    }

    const reply =
      data.reply ||
      data.response ||
      data.result ||
      data.text ||
      data.message;

    if (!reply) {
      throw new Error(
        "AI не вернул ответ для изображения"
      );
    }

    state.messages.push({
      role: "assistant",
      content:
        String(reply)
    });

    renderMessages();
  }

  // ============================================================
  // STREAMING CHAT
  // ============================================================

  async function sendMessage(text) {
    text =
      String(
        text || ""
      ).trim();

    if (streaming) {
      return;
    }

    if (attachment) {
      await sendVision(
        text
      );

      return;
    }

    if (!text) {
      return;
    }

    state.messages.push({
      role: "user",
      content: text
    });

    const assistant = {
      role: "assistant",
      content: ""
    };

    state.messages.push(
      assistant
    );

    renderMessages();

    streaming = true;

    abortController =
      new AbortController();

    updateStreamingButtons();

    try {
      const token =
        await TigranAPI.getToken();

      const response =
        await fetch(
          "/api/ai/chat/stream",
          {
            method: "POST",

            signal:
              abortController.signal,

            headers: {
              "Content-Type":
                "application/json",

              ...(token
                ? {
                    Authorization:
                      `Bearer ${token}`,

                    "X-ID-Token":
                      token
                  }
                : {})
            },

            body:
              JSON.stringify({
                message: text,
                chat_id:
                  activeChatId
              })
          }
        );

      if (!response.ok) {
        const data =
          await response
            .json()
            .catch(
              () => ({})
            );

        throw new Error(
          data.message ||
          data.error ||
          `HTTP ${response.status}`
        );
      }

      const headerChatId =
        response.headers.get(
          "X-Chat-Id"
        );

      if (
        headerChatId &&
        !activeChatId
      ) {
        activeChatId =
          headerChatId;
      }

      if (!response.body) {
        throw new Error(
          "Streaming response unavailable"
        );
      }

      const reader =
        response.body
          .getReader();

      const decoder =
        new TextDecoder();

      let buffer = "";

      while (true) {
        const {
          value,
          done
        } =
          await reader.read();

        if (done) {
          break;
        }

        buffer +=
          decoder.decode(
            value,
            {
              stream: true
            }
          );

        const lines =
          buffer.split("\n");

        buffer =
          lines.pop() || "";

        for (
          const rawLine
          of lines
        ) {
          const line =
            rawLine.trim();

          if (
            !line.startsWith(
              "data:"
            )
          ) {
            continue;
          }

          const payload =
            line
              .slice(5)
              .trim();

          if (
            !payload ||
            payload ===
              "[DONE]"
          ) {
            continue;
          }

          try {
            const event =
              JSON.parse(
                payload
              );

            if (
              typeof event.delta ===
              "string"
            ) {
              assistant.content +=
                event.delta;

              renderMessages();
            }

            if (
              event.chat_id
            ) {
              activeChatId =
                event.chat_id;
            }

            if (
              event.warning
            ) {
              window.toast?.(
                event.warning,
                "warning"
              );
            }

            if (
              event.error
            ) {
              window.toast?.(
                event.error,
                "error"
              );
            }
          } catch (_) {}
        }
      }

      await loadChats()
        .catch(
          () => {}
        );

      renderChatList();

    } finally {
      streaming = false;
      abortController = null;

      updateStreamingButtons();
    }
  }

  function stop() {
    if (
      abortController
    ) {
      abortController.abort();
      abortController = null;
    }

    streaming = false;

    updateStreamingButtons();

    window.toast?.(
      "Генерация остановлена",
      "warning"
    );
  }

  function updateStreamingButtons() {
    const send =
      document.getElementById(
        "send-chat-btn"
      );

    const stopButton =
      document.getElementById(
        "stop-chat-btn"
      );

    const regenerateButton =
      document.getElementById(
        "regen-chat-btn"
      );

    if (send) {
      send.disabled =
        streaming;
    }

    if (stopButton) {
      stopButton.disabled =
        !streaming;
    }

    if (
      regenerateButton
    ) {
      regenerateButton.disabled =
        streaming;
    }
  }

  async function regenerate() {
    if (streaming) {
      return;
    }

    const lastUser =
      [...state.messages]
        .reverse()
        .find(
          message =>
            message.role ===
            "user"
        );

    if (!lastUser) {
      return;
    }

    const text =
      lastUser.content ||
      lastUser.text ||
      "";

    if (!text) {
      return;
    }

    await sendMessage(
      text
    );
  }

  // ============================================================
  // RENDER
  // ============================================================

  async function render(
    container
  ) {
    if (streaming) {
      stop();
    }

    container.innerHTML = `
      <div class="page-header">

        <div>

          <div class="page-title">
            TIGRAN AI
          </div>

          <div class="page-sub">
            AI Assistant
          </div>

        </div>

        <button
          id="new-chat-btn"
          class="btn"
          type="button"
        >
          + Новый чат
        </button>

      </div>

      <div class="chat-layout">

        <div class="chat-sidebar">

          <div class="chat-sidebar-title">
            История
          </div>

          <div id="chat-list">
          </div>

        </div>

        <div class="chat-container">

          <div
            id="chat-messages"
            class="chat-messages"
          ></div>

          <div
            id="chat-attachment-preview"
            class="attach-preview"
          ></div>

          <div class="chat-composer">

            <input
              id="chat-attachment-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              hidden
            >

            <button
              id="attach-chat-btn"
              class="btn btn-secondary"
              type="button"
              title="Добавить изображение"
            >
              +
            </button>

            <textarea
              id="chat-input"
              class="input"
              placeholder="Напишите сообщение..."
              rows="1"
            ></textarea>

            <button
              id="send-chat-btn"
              class="btn"
              type="button"
            >
              Отправить
            </button>

            <button
              id="stop-chat-btn"
              class="btn btn-secondary"
              type="button"
              disabled
            >
              Stop
            </button>

            <button
              id="regen-chat-btn"
              class="btn btn-secondary"
              type="button"
            >
              Regenerate
            </button>

          </div>

        </div>

      </div>
    `;

    const input =
      document.getElementById(
        "chat-input"
      );

    const fileInput =
      document.getElementById(
        "chat-attachment-input"
      );

    document
      .getElementById(
        "new-chat-btn"
      )
      .onclick =
        newChat;

    document
      .getElementById(
        "attach-chat-btn"
      )
      .onclick =
        () =>
          fileInput.click();

    fileInput.onchange =
      () => {
        const file =
          fileInput.files?.[0];

        if (file) {
          setAttachment(
            file
          );
        }
      };

    document
      .getElementById(
        "send-chat-btn"
      )
      .onclick =
        async () => {
          const text =
            input.value;

          if (
            !text.trim() &&
            !attachment
          ) {
            return;
          }

          input.value = "";
          input.style.height = "";

          try {
            await sendMessage(
              text
            );
          } catch (e) {
            if (
              e.name !==
              "AbortError"
            ) {
              window.toast?.(
                e.message,
                "error"
              );
            }
          }
        };

    document
      .getElementById(
        "stop-chat-btn"
      )
      .onclick =
        stop;

    document
      .getElementById(
        "regen-chat-btn"
      )
      .onclick =
        async () => {
          try {
            await regenerate();
          } catch (e) {
            if (
              e.name !==
              "AbortError"
            ) {
              window.toast?.(
                e.message,
                "error"
              );
            }
          }
        };

    input.addEventListener(
      "input",
      () => {
        input.style.height =
          "auto";

        input.style.height =
          Math.min(
            input.scrollHeight,
            170
          ) + "px";
      }
    );

    input.addEventListener(
      "keydown",
      event => {
        if (
          event.key ===
            "Enter" &&
          !event.shiftKey
        ) {
          event.preventDefault();

          document
            .getElementById(
              "send-chat-btn"
            )
            .click();
        }
      }
    );

    try {
      await loadChats();
    } catch (e) {
      console.error(e);

      window.toast?.(
        "Не удалось загрузить историю чатов",
        "error"
      );
    }

    renderMessages();
    updateStreamingButtons();
  }

  window.TigranChat = {
    render,
    stop,
    newChat,
    openChat
  };
})();
