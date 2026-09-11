/* TIGRAN AI V3 — Frontend */
(function () {
  'use strict';

  const state = {
    sessionId: localStorage.getItem('tigran_session') || '',
    user: null,
    page: 'dashboard',
    chatId: null,
    chats: [],
    messages: [],
    streaming: false,
    abortController: null,
    attachment: null,
    products: [],
    theme: localStorage.getItem('tigran_theme') || 'dark',
    language: localStorage.getItem('tigran_lang') || 'auto',
  };

  // ============================================================
  //  API
  // ============================================================
  async function api(path, options = {}) {
    options.headers = options.headers || {};
    if (state.sessionId) options.headers['X-Session-ID'] = state.sessionId;
    const r = await fetch(path, options);
    let data = {};
    try { data = await r.json(); } catch (e) {}
    if (r.status === 401) { logout(); throw new Error('Session expired'); }
    if (!r.ok) throw new Error(data.message || ('HTTP ' + r.status));
    return data;
  }

  function toast(msg) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function renderMarkdown(text) {
    if (!window.marked || !window.DOMPurify) return esc(text);
    const raw = window.marked.parse(text, { breaks: true, gfm: true });
    return window.DOMPurify.sanitize(raw, { ADD_ATTR: ['target'] });
  }

  // ============================================================
  //  RENDER
  // ============================================================
  function render() {
    const app = document.getElementById('app');
    if (!state.user) {
      app.innerHTML = renderLogin();
      bindLogin();
    } else {
      app.innerHTML = renderLayout();
      bindLayout();
      renderPage();
    }
  }

  function renderLogin() {
    return `
      <div class="login-page"><div class="login-box">
        <h1>TIGRAN AI</h1><p>Welcome back</p>
        <div style="display:flex;flex-direction:column;gap:12px">
          <input class="input" id="username" placeholder="Username" autocomplete="username">
          <input class="input" id="password" type="password" placeholder="Password" autocomplete="current-password">
          <button class="btn" id="loginBtn">Sign In</button>
          <button class="btn btn-secondary" id="genKeyBtn">Generate Access Key</button>
          <div id="loginMsg" style="color:var(--danger);font-size:13px;text-align:center;min-height:18px"></div>
        </div>
      </div></div>`;
  }

  function bindLogin() {
    document.getElementById('loginBtn').onclick = doLogin;
    document.getElementById('password').addEventListener('keydown', e => {
      if (e.key === 'Enter') doLogin();
    });
    document.getElementById('genKeyBtn').onclick = () => {
      window.open('https://vplink.in/wFGkm', '_blank');
      toast('Пройди верификацию и вставь ссылку на странице /verify');
    };
  }

  async function doLogin() {
    const u = document.getElementById('username').value.trim();
    const p = document.getElementById('password').value.trim();
    const msg = document.getElementById('loginMsg');
    if (!u || !p) { msg.textContent = 'Заполни все поля'; return; }
    try {
      const data = await api('/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p }),
      });
      state.sessionId = data.session_id;
      localStorage.setItem('tigran_session', data.session_id);
      state.user = { username: u, role: data.role };
      render();
    } catch (e) { msg.textContent = e.message; }
  }

  function logout() {
    state.sessionId = '';
    state.user = null;
    localStorage.removeItem('tigran_session');
    render();
  }

  function renderLayout() {
    const nav = [
      { id: 'dashboard', label: '📊 Dashboard' },
      { id: 'chat', label: '💬 AI Chat' },
      { id: 'image', label: '🎨 Image Studio' },
      { id: 'payments', label: '💳 Payments' },
      { id: 'account', label: '👤 Account' },
      { id: 'settings', label: '⚙️ Settings' },
    ];
    if (state.user.role === 'admin') nav.push({ id: 'admin', label: '🛡️ Admin' });

    return `
      <button class="menu-toggle" id="menuToggle">☰</button>
      <div class="overlay" id="overlay"></div>
      <div class="layout">
        <aside class="sidebar" id="sidebar">
          <div class="logo">⚡ TIGRAN AI</div>
          <nav style="display:flex;flex-direction:column;gap:4px">
            ${nav.map(n => `<button class="nav-item ${state.page === n.id ? 'active' : ''}" data-page="${n.id}">${n.label}</button>`).join('')}
          </nav>
          <div class="sidebar-bottom">
            <div class="user-card">
              <div class="avatar">${esc((state.user.username || 'U')[0]).toUpperCase()}</div>
              <div style="flex:1;min-width:0">
                <div style="font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis">${esc(state.user.username)}</div>
                <div style="font-size:11px;color:var(--text-dim)">${esc(state.user.role)}</div>
              </div>
            </div>
            <button class="nav-item" id="logoutBtn" style="color:var(--danger)">🚪 Logout</button>
          </div>
        </aside>
        <main class="main" id="main"></main>
      </div>`;
  }

  function bindLayout() {
    document.querySelectorAll('[data-page]').forEach(el => {
      el.onclick = () => { state.page = el.dataset.page; render(); closeSidebar(); };
    });
    document.getElementById('logoutBtn').onclick = async () => {
      try { await api('/api/logout', { method: 'POST' }); } catch (e) {}
      logout();
    };
    document.getElementById('menuToggle').onclick = () => {
      document.getElementById('sidebar').classList.add('open');
      document.getElementById('overlay').classList.add('open');
    };
    document.getElementById('overlay').onclick = closeSidebar;
  }

  function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('overlay').classList.remove('open');
  }

  // ============================================================
  //  PAGES
  // ============================================================
  function renderPage() {
    const main = document.getElementById('main');
    const pages = {
      dashboard: renderDashboard, chat: renderChat, image: renderImage,
      payments: renderPayments, account: renderAccount,
      settings: renderSettings, admin: renderAdmin,
    };
    (pages[state.page] || renderDashboard)(main);
  }

  async function renderDashboard(main) {
    main.innerHTML = `
      <div class="page-title">Dashboard</div>
      <div class="page-sub">Системная информация</div>
      <div class="grid" id="dashGrid">
        <div class="card"><div class="card-title">Server</div><div class="card-value ok">ONLINE</div></div>
        <div class="card"><div class="card-title">Database</div><div class="card-value" id="dashDb">...</div></div>
        <div class="card"><div class="card-title">TIGRAN AI</div><div class="card-value" id="dashAi">...</div></div>
        <div class="card"><div class="card-title">Payments</div><div class="card-value" id="dashPay">...</div></div>
        <div class="card"><div class="card-title">Uptime</div><div class="card-value" id="dashUptime">...</div></div>
        <div class="card"><div class="card-title">Sessions</div><div class="card-value" id="dashSessions">...</div></div>
      </div>`;
    try {
      const h = await api('/api/system/health');
      const set = (id, ok, txt) => {
        const el = document.getElementById(id);
        el.textContent = txt || (ok ? 'ONLINE' : 'OFFLINE');
        el.className = 'card-value ' + (ok ? 'ok' : 'err');
      };
      set('dashDb', h.database);
      set('dashAi', h.ai_configured, h.ai_configured ? 'ONLINE' : 'OFFLINE');
      set('dashPay', h.payments_enabled, h.payments_enabled ? 'ENABLED' : 'DISABLED');
      document.getElementById('dashUptime').textContent = Math.floor(h.uptime / 60) + ' min';
      document.getElementById('dashSessions').textContent = h.sessions_count;
    } catch (e) { toast(e.message); }
  }

  // ============================================================
  //  CHAT
  // ============================================================
  async function renderChat(main) {
    main.innerHTML = `
      <div class="page-title">AI Chat</div>
      <div class="page-sub">TIGRAN AI — твой ассистент</div>
      <div class="chat-layout">
        <div class="chat-sidebar" id="chatSidebar">
          <button class="btn" id="newChatBtn" style="width:100%;margin-bottom:10px">+ New Chat</button>
          <div class="chat-sidebar-title">Chats</div>
          <div id="chatList"></div>
        </div>
        <div class="chat-container">
          <div class="chat-messages" id="chatMessages"></div>
          <div class="attach-preview" id="attachPreview"></div>
          <div class="chat-composer">
            <button class="btn btn-secondary" id="attachBtn" title="Attach image">+</button>
            <input type="file" id="attachInput" accept="image/jpeg,image/png,image/webp" style="display:none">
            <textarea class="input" id="chatInput" placeholder="Ask TIGRAN AI..." rows="1"></textarea>
            <button class="btn" id="sendBtn">Send</button>
          </div>
        </div>
      </div>`;
    await loadChats();

    const input = document.getElementById('chatInput');
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 160) + 'px';
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });
    document.getElementById('sendBtn').onclick = () => {
      if (state.streaming) stopStream(); else sendChat();
    };
    document.getElementById('newChatBtn').onclick = newChat;
    document.getElementById('attachBtn').onclick = () => document.getElementById('attachInput').click();
    document.getElementById('attachInput').onchange = handleAttach;
  }

  async function loadChats() {
    try {
      const data = await api('/api/ai/chats');
      state.chats = data.chats || [];
      const list = document.getElementById('chatList');
      if (!list) return;
      list.innerHTML = state.chats.map(c => `
        <div class="chat-item ${state.chatId === c.chat_id ? 'active' : ''}" data-cid="${esc(c.chat_id)}">
          <span class="chat-item-title">${esc(c.title || 'Untitled')}</span>
          <span class="chat-item-actions">
            <button data-act="rename" data-cid="${esc(c.chat_id)}">✎</button>
            <button data-act="delete" data-cid="${esc(c.chat_id)}">✕</button>
          </span>
        </div>`).join('');
      list.querySelectorAll('.chat-item').forEach(el => {
        el.onclick = (e) => {
          if (e.target.dataset.act) return;
          openChat(el.dataset.cid);
        };
      });
      list.querySelectorAll('[data-act="rename"]').forEach(b => {
        b.onclick = (e) => { e.stopPropagation(); renameChat(b.dataset.cid); };
      });
      list.querySelectorAll('[data-act="delete"]').forEach(b => {
        b.onclick = (e) => { e.stopPropagation(); deleteChat(b.dataset.cid); };
      });
    } catch (e) { toast(e.message); }
  }

  async function newChat() {
    state.chatId = null;
    state.messages = [];
    document.getElementById('chatMessages').innerHTML = '';
    renderChatMessages();
  }

  async function openChat(chatId) {
    try {
      const data = await api('/api/ai/chats/' + chatId);
      const chat = data.chat || {};
      const msgs = chat.messages || {};
      state.chatId = chatId;
      state.messages = Object.entries(msgs)
        .sort((a, b) => (a[1].ts || 0) - (b[1].ts || 0))
        .map(([k, v]) => ({ id: k, role: v.role, content: v.content }));
      renderChatMessages();
      document.querySelectorAll('.chat-item').forEach(el => {
        el.classList.toggle('active', el.dataset.cid === chatId);
      });
    } catch (e) { toast(e.message); }
  }

  function renderChatMessages() {
    const box = document.getElementById('chatMessages');
    if (!box) return;
    box.innerHTML = state.messages.map(m => renderMsg(m)).join('');
    box.scrollTop = box.scrollHeight;
    bindMsgActions();
  }

  function renderMsg(m) {
    const cls = m.role === 'user' ? 'user' : 'ai';
    const body = m.role === 'user' ? esc(m.content).replace(/\n/g, '<br>') : renderMarkdown(m.content);
    return `<div class="msg ${cls}" data-msg-id="${esc(m.id || '')}">
      <div class="msg-body">${body}</div>
      ${m.role === 'ai' ? `<div class="msg-actions">
        <button data-act="copy">Copy</button>
      </div>` : ''}
    </div>`;
  }

  function bindMsgActions() {
    document.querySelectorAll('.msg [data-act="copy"]').forEach(b => {
      b.onclick = () => {
        const body = b.closest('.msg').querySelector('.msg-body').textContent;
        navigator.clipboard.writeText(body).then(() => toast('Скопировано'));
      };
    });
    document.querySelectorAll('.msg pre').forEach(pre => {
      if (pre.querySelector('.code-copy')) return;
      const btn = document.createElement('button');
      btn.className = 'code-copy';
      btn.textContent = 'Copy';
      btn.style.cssText = 'position:absolute;top:6px;right:6px;background:rgba(0,0,0,0.6);border:1px solid rgba(0,255,200,0.3);color:#0ff;padding:2px 8px;border-radius:6px;font-size:11px;cursor:pointer;';
      btn.onclick = () => {
        navigator.clipboard.writeText(pre.querySelector('code')?.textContent || '');
        toast('Код скопирован');
      };
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
    if (window.hljs) {
      document.querySelectorAll('.msg pre code').forEach(el => {
        try { window.hljs.highlightElement(el); } catch (e) {}
      });
    }
  }

  async function handleAttach() {
    const input = document.getElementById('attachInput');
    const file = input.files[0];
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) { toast('Только JPEG/PNG/WEBP'); input.value = ''; return; }
    if (file.size > 8 * 1024 * 1024) { toast('Максимум 8MB'); input.value = ''; return; }
    state.attachment = file;
    const preview = document.getElementById('attachPreview');
    const url = URL.createObjectURL(file);
    preview.innerHTML = `<div class="attach-item">
      <img src="${url}" alt="">
      <button id="removeAttach">✕</button></div>`;
    document.getElementById('removeAttach').onclick = () => {
      state.attachment = null;
      preview.innerHTML = '';
      input.value = '';
    };
  }

  async function sendChat() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if ((!msg && !state.attachment) || state.streaming) return;

    const container = document.getElementById('chatMessages');
    const attachment = state.attachment;

    // Если есть attachment — отправляем в vision
    if (attachment) {
      const userMsg = msg || 'Что на этом изображении?';
      state.messages.push({ id: 'tmp_u', role: 'user', content: userMsg + '\n[📎 image]' });
      container.innerHTML += renderMsg({ id: 'tmp_u', role: 'user', content: userMsg + '\n[📎 image]' });
      container.scrollTop = container.scrollHeight;

      const fd = new FormData();
      fd.append('image', attachment);
      fd.append('prompt', userMsg);

      state.attachment = null;
      document.getElementById('attachPreview').innerHTML = '';
      document.getElementById('attachInput').value = '';
      input.value = '';

      try {
        const res = await fetch('/api/ai/vision', {
          method: 'POST',
          headers: { 'X-Session-ID': state.sessionId },
          body: fd,
        });
        const data = await res.json();
        const reply = data.reply || data.message || 'Ошибка';
        state.messages.push({ id: 'tmp_a', role: 'assistant', content: reply });
        container.innerHTML += renderMsg({ id: 'tmp_a', role: 'assistant', content: reply });
        container.scrollTop = container.scrollHeight;
        bindMsgActions();
      } catch (e) { toast(e.message); }
      return;
    }

    // Обычный стрим
    state.messages.push({ id: 'tmp_u', role: 'user', content: msg });
    container.innerHTML += renderMsg({ id: 'tmp_u', role: 'user', content: msg });
    container.scrollTop = container.scrollHeight;
    input.value = '';
    input.style.height = 'auto';

    state.streaming = true;
    state.abortController = new AbortController();
    document.getElementById('sendBtn').textContent = 'Stop';
    document.getElementById('sendBtn').classList.add('btn-secondary');

    const aiEl = document.createElement('div');
    aiEl.className = 'msg ai';
    aiEl.innerHTML = '<div class="msg-body typing"></div>';
    container.appendChild(aiEl);
    container.scrollTop = container.scrollHeight;
    const bodyEl = aiEl.querySelector('.msg-body');

    try {
      const resp = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': state.sessionId,
        },
        body: JSON.stringify({ message: msg, chat_id: state.chatId || '' }),
        signal: state.abortController.signal,
      });
      const newChatId = resp.headers.get('X-Chat-Id');
      if (newChatId && !state.chatId) state.chatId = newChatId;

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';
      bodyEl.classList.remove('typing');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;
          try {
            const parsed = JSON.parse(payload);
            if (parsed.delta) {
              accumulated += parsed.delta;
              bodyEl.innerHTML = renderMarkdown(accumulated);
              container.scrollTop = container.scrollHeight;
            } else if (parsed.error) {
              accumulated += '\n' + parsed.error;
              bodyEl.textContent = accumulated;
            }
          } catch (e) {}
        }
      }
      if (accumulated) {
        state.messages.push({ id: 'tmp_a', role: 'assistant', content: accumulated });
        bindMsgActions();
      }
      await loadChats();
    } catch (e) {
      if (e.name !== 'AbortError') {
        bodyEl.textContent = 'TIGRAN AI временно недоступен.';
      }
    } finally {
      state.streaming = false;
      state.abortController = null;
      const btn = document.getElementById('sendBtn');
      if (btn) { btn.textContent = 'Send'; btn.classList.remove('btn-secondary'); }
    }
  }

  function stopStream() {
    if (state.abortController) {
      state.abortController.abort();
      state.abortController = null;
    }
    state.streaming = false;
    const btn = document.getElementById('sendBtn');
    if (btn) { btn.textContent = 'Send'; btn.classList.remove('btn-secondary'); }
  }

  async function renameChat(chatId) {
    const title = prompt('Новое название:');
    if (!title) return;
    try {
      await api('/api/ai/chats/' + chatId, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      await loadChats();
    } catch (e) { toast(e.message); }
  }

  async function deleteChat(chatId) {
    if (!confirm('Удалить чат?')) return;
    try {
      await api('/api/ai/chats/' + chatId, { method: 'DELETE' });
      if (state.chatId === chatId) { state.chatId = null; state.messages = []; }
      await loadChats();
      renderChatMessages();
    } catch (e) { toast(e.message); }
  }

  // ============================================================
  //  IMAGE
  // ============================================================
  async function renderImage(main) {
    main.innerHTML = `
      <div class="page-title">Image Studio</div>
      <div class="page-sub">Генерация изображений через TIGRAN AI</div>
      <div class="card" style="margin-bottom:16px">
        <textarea class="input" id="imgPrompt" placeholder="Опиши изображение..." rows="3" style="margin-bottom:12px"></textarea>
        <button class="btn" id="genImgBtn">🎨 Generate Image</button>
      </div>
      <div id="imgResult"></div>
      <div class="page-sub" style="margin-top:20px">История</div>
      <div id="imgHistory" class="grid"></div>`;
    document.getElementById('genImgBtn').onclick = generateImage;
    await loadImageHistory();
  }

  async function generateImage() {
    const prompt = document.getElementById('imgPrompt').value.trim();
    if (!prompt) { toast('Введи prompt'); return; }
    const result = document.getElementById('imgResult');
    result.innerHTML = `<div class="card"><div class="skeleton" style="height:200px"></div><div style="margin-top:10px;color:var(--text-dim)">Generating...</div></div>`;
    try {
      const data = await api('/api/images/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });
      if (data.status === 'success' && data.image_url) {
        result.innerHTML = `<div class="card">
          <img src="${esc(data.image_url)}" style="width:100%;max-width:512px;border-radius:10px;margin:10px 0" alt="">
          <div style="font-size:12px;color:var(--text-dim)">${esc(data.revised_prompt || prompt)}</div>
          <a href="${esc(data.image_url)}" download class="btn btn-secondary" style="display:inline-block;margin-top:10px;text-decoration:none">Download</a>
        </div>`;
        await loadImageHistory();
      } else {
        result.innerHTML = `<div class="card"><div style="color:var(--danger)">${esc(data.message || 'Ошибка')}</div></div>`;
      }
    } catch (e) {
      result.innerHTML = `<div class="card"><div style="color:var(--danger)">${esc(e.message)}</div></div>`;
    }
  }

  async function loadImageHistory() {
    try {
      const data = await api('/api/images/history');
      const box = document.getElementById('imgHistory');
      if (!box) return;
      const imgs = data.images || [];
      if (!imgs.length) { box.innerHTML = '<div style="color:var(--text-dim);font-size:13px">Пока нет изображений</div>'; return; }
      box.innerHTML = imgs.slice(0, 12).map(i => `
        <div class="card" style="padding:10px">
          <img src="${esc(i.image_url)}" style="width:100%;border-radius:8px" alt="">
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.prompt)}</div>
        </div>`).join('');
    } catch (e) {}
  }

  // ============================================================
  //  PAYMENTS
  // ============================================================
  async function renderPayments(main) {
    main.innerHTML = `
      <div class="page-title">Payments</div>
      <div class="page-sub">Покупки и история</div>
      <div class="page-sub" style="margin-top:8px">Products</div>
      <div id="productsBox" class="grid"></div>
      <div class="page-sub" style="margin-top:20px">История платежей</div>
      <div id="paymentsBox"></div>`;
    await loadProducts();
    await loadMyPayments();
  }

  async function loadProducts() {
    try {
      const data = await api('/api/payments/products');
      state.products = data.products || [];
      const box = document.getElementById('productsBox');
      if (!state.products.length) {
        box.innerHTML = '<div style="color:var(--text-dim);font-size:13px">Нет доступных продуктов</div>';
        return;
      }
      box.innerHTML = state.products.map(p => `
        <div class="card">
          <div class="card-title">${esc(p.product_id)}</div>
          <div class="card-value">${esc(p.price)} ${esc(p.currency)}</div>
          <div style="font-size:12px;color:var(--text-dim);margin:6px 0">${esc(p.duration)} дней</div>
          <select class="input" id="prov_${esc(p.product_id)}" style="margin:8px 0">
            <option value="ameria">Ameriabank</option>
            <option value="fastbank">Fast Bank</option>
            <option value="cis">CIS</option>
            <option value="kazakhstan">Kazakhstan</option>
          </select>
          <button class="btn" data-buy="${esc(p.product_id)}">BUY</button>
        </div>`).join('');
      box.querySelectorAll('[data-buy]').forEach(b => {
        b.onclick = () => buyProduct(b.dataset.buy);
      });
    } catch (e) { toast(e.message); }
  }

  async function buyProduct(productId) {
    const provider = document.getElementById('prov_' + productId).value;
    try {
      const data = await api('/api/payments/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, product_id: productId }),
      });
      if (data.payment_url) {
        window.location.href = data.payment_url;
      } else {
        toast('Ордер создан: ' + data.order_id);
        await loadMyPayments();
      }
    } catch (e) { toast(e.message); }
  }

  async function loadMyPayments() {
    try {
      const data = await api('/api/payments/history/me');
      const list = data.payments || [];
      const box = document.getElementById('paymentsBox');
      if (!list.length) {
        box.innerHTML = '<div class="card"><div style="color:var(--text-dim)">Нет платежей</div></div>';
        return;
      }
      box.innerHTML = list.map(p => `
        <div class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
            <div style="min-width:0">
              <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis">${esc(p.order_id)}</div>
              <div style="font-size:12px;color:var(--text-dim)">${esc(p.provider)} • ${esc(p.amount)} ${esc(p.currency)}</div>
            </div>
            <div style="color:${p.status === 'paid' ? 'var(--success)' : 'var(--warn)'};font-weight:600">${esc(p.status)}</div>
          </div>
        </div>`).join('');
    } catch (e) { toast(e.message); }
  }

  // ============================================================
  //  ACCOUNT
  // ============================================================
  async function renderAccount(main) {
    main.innerHTML = `<div class="page-title">Account</div>
      <div class="page-sub">Информация об аккаунте</div>
      <div class="card"><div style="display:flex;flex-direction:column;gap:10px">
        <div><span style="color:var(--text-dim)">Username:</span> ${esc(state.user.username)}</div>
        <div><span style="color:var(--text-dim)">Role:</span> ${esc(state.user.role)}</div>
        <div><span style="color:var(--text-dim)">Session:</span> ${esc(state.sessionId.slice(0, 12))}...</div>
      </div></div>`;
  }

  // ============================================================
  //  SETTINGS
  // ============================================================
  function renderSettings(main) {
    main.innerHTML = `<div class="page-title">Settings</div>
      <div class="page-sub">Настройки интерфейса</div>
      <div class="card">
        <div class="card-title">Theme</div>
        <select class="input" id="themeSel" style="margin-bottom:12px">
          <option value="dark" ${state.theme === 'dark' ? 'selected' : ''}>Dark</option>
          <option value="system" ${state.theme === 'system' ? 'selected' : ''}>System</option>
        </select>
        <div class="card-title">Language</div>
        <select class="input" id="langSel">
          <option value="auto" ${state.language === 'auto' ? 'selected' : ''}>Auto</option>
          <option value="en" ${state.language === 'en' ? 'selected' : ''}>English</option>
          <option value="ru" ${state.language === 'ru' ? 'selected' : ''}>Русский</option>
          <option value="hy" ${state.language === 'hy' ? 'selected' : ''}>Հայերեն</option>
        </select>
      </div>`;
    document.getElementById('themeSel').onchange = (e) => {
      state.theme = e.target.value;
      localStorage.setItem('tigran_theme', state.theme);
      toast('Тема сохранена');
    };
    document.getElementById('langSel').onchange = (e) => {
      state.language = e.target.value;
      localStorage.setItem('tigran_lang', state.language);
      toast('Язык сохранён');
    };
  }

  // ============================================================
  //  ADMIN
  // ============================================================
  async function renderAdmin(main) {
    main.innerHTML = `<div class="page-title">Admin Dashboard</div>
      <div class="page-sub">Только для администраторов</div>
      <div class="grid" id="adminGrid"></div>
      <div class="page-sub" style="margin-top:20px">Последние платежи</div>
      <div id="adminPayments"></div>`;
    try {
      const sys = await api('/api/admin/system');
      const sessions = await api('/api/admin/sessions');
      document.getElementById('adminGrid').innerHTML = `
        <div class="card"><div class="card-title">Uptime</div><div class="card-value">${Math.floor(sys.uptime / 60)} min</div></div>
        <div class="card"><div class="card-title">Sessions</div><div class="card-value">${sys.sessions_count}</div></div>
        <div class="card"><div class="card-title">Session Store</div><div class="card-value" style="font-size:16px">${esc(sessions.store)}</div></div>
        <div class="card"><div class="card-title">Firebase</div><div class="card-value ${sys.firebase_connected ? 'ok' : 'err'}">${sys.firebase_connected ? 'ONLINE' : 'OFFLINE'}</div></div>`;

      const pay = await api('/api/admin/payments');
      const box = document.getElementById('adminPayments');
      box.innerHTML = `
        <div class="grid" style="margin-bottom:14px">
          <div class="card"><div class="card-title">Total</div><div class="card-value">${pay.total}</div></div>
          <div class="card"><div class="card-title">Success</div><div class="card-value ok">${pay.success}</div></div>
          <div class="card"><div class="card-title">Pending</div><div class="card-value warn">${pay.pending}</div></div>
          <div class="card"><div class="card-title">Failed</div><div class="card-value err">${pay.failed}</div></div>
        </div>
        ${(pay.recent || []).map(p => `
          <div class="card" style="margin-bottom:8px;padding:12px">
            <div style="font-size:12px;color:var(--text-dim)">${esc(p.order_id)} • ${esc(p.user_id || '')} • ${esc(p.provider)} • ${esc(p.amount)} ${esc(p.currency)}</div>
            <div style="font-weight:600;color:${p.status === 'paid' ? 'var(--success)' : 'var(--warn)'}">${esc(p.status)}</div>
          </div>`).join('')}`;
    } catch (e) { toast(e.message); }
  }

  // ============================================================
  //  INIT
  // ============================================================
  async function init() {
    if (state.sessionId) {
      try {
        const me = await api('/api/me');
        state.user = { username: me.username, role: me.role };
      } catch (e) {
        state.sessionId = '';
        localStorage.removeItem('tigran_session');
      }
    }
    render();
  }

  init();
})();
