(() => {
  const state = {
    products: []
  };

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
  }

  async function loadProducts() {
    const data =
      await TigranAPI.get(
        "/api/payments/products"
      );

    state.products =
      Array.isArray(data.products)
        ? data.products
        : Object.entries(
            data.products || {}
          ).map(
            ([product_id, value]) => ({
              product_id,
              ...value
            })
          );

    renderProducts();
  }

  function renderProducts() {
    const box =
      document.getElementById(
        "payments-products"
      );

    if (!box) {
      return;
    }

    if (!state.products.length) {
      box.innerHTML = `
        <div class="card">
          <div class="muted small">
            Нет доступных продуктов.
          </div>
        </div>
      `;
      return;
    }

    box.innerHTML =
      state.products
        .map(product => {
          const id =
            product.product_id ||
            product.id ||
            "";

          return `
            <div class="card">

              <div class="card-title">
                ${escapeHtml(
                  product.name ||
                  id ||
                  "Product"
                )}
              </div>

              <div class="card-value">
                ${escapeHtml(
                  product.price ?? "—"
                )}
                ${escapeHtml(
                  product.currency || ""
                )}
              </div>

              ${
                product.duration
                  ? `
                    <div class="card-description">
                      ${escapeHtml(product.duration)}
                      дней
                    </div>
                  `
                  : ""
              }

              ${
                product.description
                  ? `
                    <div class="card-description">
                      ${escapeHtml(product.description)}
                    </div>
                  `
                  : ""
              }

              <div style="height:12px"></div>

              <select
                class="select"
                data-provider-for="${escapeHtml(id)}"
              >
                <option value="ameria">
                  Ameriabank
                </option>

                <option value="fastbank">
                  FastBank
                </option>

                <option value="cis">
                  CIS
                </option>

                <option value="kazakhstan">
                  Kazakhstan
                </option>
              </select>

              <div style="height:10px"></div>

              <button
                class="btn"
                type="button"
                data-buy-product="${escapeHtml(id)}"
              >
                Купить
              </button>

            </div>
          `;
        })
        .join("");

    box
      .querySelectorAll(
        "[data-buy-product]"
      )
      .forEach(button => {
        button.onclick =
          async () => {
            await buyProduct(
              button.dataset
                .buyProduct,
              button
            );
          };
      });
  }

  async function buyProduct(
    productId,
    button
  ) {
    const select =
      document.querySelector(
        `[data-provider-for="${CSS.escape(productId)}"]`
      );

    const provider =
      select?.value;

    if (!provider) {
      window.toast?.(
        "Выберите способ оплаты",
        "warning"
      );
      return;
    }

    try {
      button.disabled = true;

      const data =
        await TigranAPI.post(
          "/api/payments/create",
          {
            provider,
            product_id:
              productId
          }
        );

      const paymentUrl =
        data.payment_url ||
        data.checkout_url ||
        data.redirect_url;

      if (paymentUrl) {
        window.location.assign(
          paymentUrl
        );
        return;
      }

      window.toast?.(
        data.order_id
          ? `Ордер создан: ${data.order_id}`
          : "Платёж создан",
        "success"
      );

      await loadHistory();

    } catch (e) {
      window.toast?.(
        e.message,
        "error"
      );
    } finally {
      button.disabled = false;
    }
  }

  async function loadHistory() {
    const box =
      document.getElementById(
        "payments-history"
      );

    if (!box) {
      return;
    }

    try {
      const data =
        await TigranAPI.get(
          "/api/payments/history/me"
        );

      const raw =
        data.payments || [];

      const payments =
        Array.isArray(raw)
          ? raw
          : Object.entries(raw)
              .map(
                ([id, value]) => ({
                  order_id:
                    value.order_id ||
                    id,
                  ...value
                })
              );

      if (!payments.length) {
        box.innerHTML = `
          <div class="card">
            <div class="muted small">
              История платежей пуста.
            </div>
          </div>
        `;
        return;
      }

      box.innerHTML =
        payments
          .map(payment => {
            const status =
              String(
                payment.status ||
                "pending"
              ).toLowerCase();

            const badgeClass =
              status === "paid" ||
              status === "success"
                ? "success"
                : (
                    status === "failed" ||
                    status === "cancelled"
                      ? "danger"
                      : "warning"
                  );

            return `
              <div
                class="card"
                style="margin-bottom:10px"
              >

                <div class="card-header">

                  <div>

                    <div
                      style="
                        font-weight:700;
                        font-size:13px;
                        word-break:break-all
                      "
                    >
                      ${escapeHtml(
                        payment.order_id ||
                        payment.id ||
                        "—"
                      )}
                    </div>

                    <div class="card-description">
                      ${escapeHtml(
                        payment.provider ||
                        "—"
                      )}
                      •
                      ${escapeHtml(
                        payment.amount ??
                        "—"
                      )}
                      ${escapeHtml(
                        payment.currency ||
                        ""
                      )}
                    </div>

                  </div>

                  <span
                    class="badge ${badgeClass}"
                  >
                    ${escapeHtml(status)}
                  </span>

                </div>

              </div>
            `;
          })
          .join("");

    } catch (e) {
      box.innerHTML = `
        <div class="card">
          <div class="text-danger small">
            ${escapeHtml(e.message)}
          </div>
        </div>
      `;
    }
  }

  async function render(container) {
    container.innerHTML = `
      <div class="page-header">

        <div>
          <div class="page-title">
            Payments
          </div>

          <div class="page-sub">
            Покупки и история платежей
          </div>
        </div>

      </div>

      <div class="card-title">
        Products
      </div>

      <div
        id="payments-products"
        class="grid"
      >
        <div class="card">
          <div
            class="skeleton"
            style="height:120px"
          ></div>
        </div>
      </div>

      <div style="height:24px"></div>

      <div class="card-title">
        История платежей
      </div>

      <div
        id="payments-history"
        style="margin-top:10px"
      ></div>
    `;

    await Promise.allSettled([
      loadProducts(),
      loadHistory()
    ]);
  }

  window.TigranPayments = {
    render,
    loadProducts,
    loadHistory
  };
})();
