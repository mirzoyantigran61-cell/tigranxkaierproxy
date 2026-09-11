(() => {
  let activeChatId = null;
  let abortController = null;

  const state = {
    chats: [],
    messages: []
  };

  function markdown(
    text
  ) {
    try {
      const html =
        window.marked
          ? marked.parse(
              text || ""
            )
          : String(
              text || ""
            );

      return window.DOMPurify
        ? DOMPurify.sanitize(
            html
          )
        : html;
    } catch (_) {
      return String(
        text || ""
      );
    }
  }

  async function loadChats() {
    const data =
      await TigranAPI.get(
        "/api/ai/chats"
      );

    const raw =
      data.chats || {};

    state.chats =
      Array.isArray(raw)
        ? raw
        : Object.entries(raw)
            .map(
              ([id, value]) => ({
                id,
                ...value
              })
            );

    return state.chats;
  }

  async function openChat(
    id
  ) {
    activeChatId = id;

    const data =
      await TigranAPI.get(
        `/api/ai/chats/${encodeURIComponent(id)}`
      );

    const raw =
      data.chat?.messages
      || data.messages
      || {};

    state.messages =
      Array.isArray(raw)
        ? raw
        : Object.values(raw);

    renderMessages();
    renderChatList();
  }

  function renderChatList() {
    const box =
      document.getElementById(
        "chat-list"
      );

    if (!box) {
      return;
    }

    box.innerHTML =
      state.chats
        .map(
          chat => `
            <div
              class="chat-item ${
                String(
                  chat.id
                ) ===
                String(
                  activeChatId
                )
                  ? "active"
                  : ""
              }"
              data-chat-id="${chat.id}"
            >

              <div
                class="chat-item-title"
              >
                ${
                  chat.title
                  || "Новый чат"
                }
              </div>

            </div>
          `
        )
        .join("");

    box
      .querySelectorAll(
        "[data-chat-id]"
      )
      .forEach(
        element => {
          element.onclick =
            () =>
              openChat(
                element.dataset
                  .chatId
              );
        }
      );
  }

  function renderMessages() {
    const box =
      document.getElementById(
        "chat-messages"
      );

    if (!box) {
      return;
    }

    box.innerHTML =
      state.messages
        .map(
          (message, index) => {
            const role =
              message.role ===
              "user"
                ? "user"
                : "ai";

            return `
              <div
                class="msg ${role}"
              >

                <div>
                  ${
                    role === "ai"
                      ? markdown(
                          message.content
                          || message.text
                          || ""
                        )
                      : escapeHtml(
                          message.content
                          || message.text
                          || ""
                        )
                  }
                </div>

                <div
                  class="msg-actions"
                >

                  <button
                    data-copy="${index}"
                  >
                    Копировать
                  </button>

                </div>

              </div>
            `;
          }
        )
        .join("");

    box
      .querySelectorAll(
        "[data-copy]"
      )
      .forEach(
        button => {
          button.onclick =
            async () => {
              const message =
                state.messages[
                  Number(
                    button.dataset
                      .copy
                  )
                ];

              await navigator
                .clipboard
                .writeText(
                  message.content
                  || message.text
                  || ""
                );

              window.toast?.(
                "Скопировано",
                "success"
              );
            };
        }
      );

    box.scrollTop =
      box.scrollHeight;

    if (window.hljs) {
      box
        .querySelectorAll(
          "pre code"
        )
        .forEach(
          block =>
            hljs.highlightElement(
              block
            )
        );
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

  async function sendMessage(
    text
  ) {
    text =
      String(
        text || ""
      ).trim();

    if (!text) {
      return;
    }

    state.messages.push({
      role: "user",
      content: text
    });

    state.messages.push({
      role: "assistant",
      content: ""
    });

    renderMessages();

    abortController =
      new AbortController();

    const token =
      await TigranAPI
        .getToken();

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
        data.message
        || `HTTP ${response.status}`
      );
    }

    const reader =
      response.body
        .getReader();

    const decoder =
      new TextDecoder();

    let buffer = "";

    const assistant =
      state.messages[
        state.messages.length - 1
      ];

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
        const raw
        of lines
      ) {
        const line =
          raw.trim();

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
            event.delta
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
        } catch (_) {}
      }
    }

    abortController =
      null;

    await loadChats()
      .catch(
        () => {}
      );

    renderChatList();
  }

  function stop() {
    if (
      abortController
    ) {
      abortController.abort();
      abortController = null;

      window.toast?.(
        "Генерация остановлена",
        "warning"
      );
    }
  }

  async function regenerate() {
    const lastUser =
      [...state.messages]
        .reverse()
        .find(
          item =>
            item.role ===
            "user"
        );

    if (!lastUser) {
      return;
    }

    await sendMessage(
      lastUser.content
    );
  }

  async function newChat() {
    activeChatId = null;
    state.messages = [];
    renderMessages();
    renderChatList();
  }

  async function render(
    container
  ) {
    container.innerHTML = `
      <div class="page-header">
        <div>
          <div class="page-title">
            TIGRAN AI
          </div>

          <div class="page-sub">
            GPT assistant
          </div>
        </div>

        <button
          id="new-chat-btn"
          class="btn"
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

          <div class="chat-composer">

            <textarea
              id="chat-input"
              class="input"
              placeholder="Напишите сообщение..."
            ></textarea>

            <button
              id="send-chat-btn"
              class="btn"
            >
              Отправить
            </button>

            <button
              id="stop-chat-btn"
              class="btn btn-secondary"
            >
              Stop
            </button>

            <button
              id="regen-chat-btn"
              class="btn btn-secondary"
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

    document
      .getElementById(
        "new-chat-btn"
      )
      .onclick = newChat;

    document
      .getElementById(
        "send-chat-btn"
      )
      .onclick =
        async () => {
          const text =
            input.value;

          input.value = "";

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
      .onclick = stop;

    document
      .getElementById(
        "regen-chat-btn"
      )
      .onclick =
        async () => {
          try {
            await regenerate();
          } catch (e) {
            window.toast?.(
              e.message,
              "error"
            );
          }
        };

    input.addEventListener(
      "keydown",
      event => {
        if (
          event.key ===
          "Enter"
          &&
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
      renderChatList();
    } catch (e) {
      console.error(e);
    }
  }

  window.TigranChat = {
    render,
    stop
  };
})();
