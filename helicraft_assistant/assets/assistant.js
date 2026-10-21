/* HeliCraft assistant: every model suggestion is text/structured data, never executable code. */
(() => {
  'use strict';
  if (document.getElementById('hc-assistant')) return;
  const fields = ['base_type', 'chirality', 'R', 'P', 'N', 'Rbase', 'Rtop', 'k',
    'Length', 'twist_turns', 'W', 'L', 'insertion_angle', 'a_idx', 'b_idx', 'strand_count', 'strand_phase_deg', 'contact_cutoff'];
  const workbench = !!document.getElementById('buildForm');
  const page = workbench ? 'workbench' : 'home';
  const byId = id => document.getElementById(id === 'chirality' ? 'chirality_sel' : id);
  const storageKey = 'helicraft-assistant-v1';
  let history = [], busy = false, controller = null, latest = null, lastFocus = null;
  let sequence = 0, lastExchange = null;
  try { history = JSON.parse(sessionStorage.getItem(storageKey) || '[]').slice(-10); } catch (_) { /* Storage optional. */ }
  if (!Array.isArray(history) || history.some(t => !t || !['user', 'assistant'].includes(t.role) || typeof t.content !== 'string')) history = [];

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(text, handler, cls) {
    const node = el('button', cls, text); node.type = 'button';
    node.addEventListener('click', handler); return node;
  }
  function save() { try { sessionStorage.setItem(storageKey, JSON.stringify(history.slice(-10))); } catch (_) {} }
  window.helicraftMessage = value => {
    const messages = {
      '验证码错误或已过期': 'The verification code is incorrect or has expired.',
      '尚未建立档案，请切换至【注册】页面': 'No account found. Please select Register.',
      '验证身份失效，请重新获取验证码': 'Verification expired. Please request a new code.',
      '姓名不能为空': 'Please enter your name.',
      '验证码已发送，请查收邮件': 'Code sent. Please check your email.'
    };
    const text = typeof value === 'string' ? value : '';
    if (messages[text]) return messages[text];
    const cooldown = text.match(/^请求频繁，请等待 (\d+) 秒$/);
    if (cooldown) return `Please wait ${cooldown[1]} seconds before requesting another code.`;
    return !text || /[\u3400-\u9fff]/.test(text) ? 'The request could not be completed. Check your inputs or contact the site administrator.' : text;
  };
  function displayValue(value) {
    const values = { '圆柱状螺旋': 'Cylindrical helix', '锥形螺旋': 'Conical helix',
      '阿基米德螺旋': 'Archimedean spiral', '斐波那契螺旋': 'Fibonacci spiral',
      'Flat带': 'Flat ribbon', 'Twist带': 'Twisted ribbon', '右旋': 'Right-handed', '左旋': 'Left-handed' };
    return value == null ? 'Not set' : values[value] ?? value;
  }
  function current() {
    const values = {};
    fields.forEach(key => {
      const node = byId(key);
      const value = node ? node.value.trim() : '';
      values[key] = !value ? null : ['base_type', 'chirality'].includes(key) ? value : Number(value);
    });
    if (['Flat带', 'Twist带'].includes(values.base_type)) { values.strand_count = 1; values.strand_phase_deg = 0; }
    values.strand_count ??= 1; values.strand_phase_deg ??= 0;
    values.contact_cutoff ??= 1;
    return values;
  }
  function fileIdentity() {
    const file = byId('monomerFile')?.files[0];
    return file ? [file.name, file.size, file.lastModified].join('|') : '';
  }
  async function monomer() {
    const file = byId('monomerFile')?.files[0];
    if (!file) return null;
    if (file.size > 32 * 1024 * 1024) throw new Error('The monomer file exceeds the 32 MB assistant limit.');
    const lines = (await file.text()).trimEnd().split(/\r?\n/);
    const n = Number(lines[0]);
    const rows = lines.slice(2).filter(line => line.trim()).map(line => line.trim().split(/\s+/));
    if (!Number.isInteger(n) || n < 2 || n > 1000000 || rows.length !== n || rows.some(row =>
      row.length !== 4 || !/^[A-Za-z][A-Za-z0-9_+-]{0,15}$/.test(row[0]) || row.slice(1).some(v => (!v.trim() || !Number.isFinite(Number(v)) || Math.abs(Number(v)) > 1e8)))) {
      throw new Error('Check the XYZ format: atom count, comment line, then an element and three coordinates per atom.');
    }
    return { n, coordinates: rows.map(row => row.slice(1).map(Number)) };
  }
  const launcher = button('Jack', openAssistant);
  launcher.id = 'hc-ai-launcher'; launcher.setAttribute('aria-expanded', 'false');
  launcher.setAttribute('aria-controls', 'hc-assistant');
  launcher.setAttribute('aria-label', 'Open Jack, your HeliCraft assistant');
  const dock = el('div', 'hc-character'); dock.id = 'hc-ai-dock';
  const mascot = el('span', 'hc-mascot'); mascot.setAttribute('aria-hidden', 'true');
  // A fixed, local SVG illustration. Model output is never inserted as markup.
  // Jack, an Einstein-inspired cartoon scientist. Artwork is fixed local markup.
  mascot.innerHTML = `<svg viewBox="0 0 160 184" xmlns="http://www.w3.org/2000/svg" focusable="false">
  <defs>
    <linearGradient id="hc-einstein-skin" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="#ffe7c8"/><stop offset="1" stop-color="#efb88e"/></linearGradient>
    <linearGradient id="hc-einstein-hair" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fffef7"/><stop offset="1" stop-color="#d1ddec"/></linearGradient>
    <linearGradient id="hc-einstein-coat" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#8296ad"/><stop offset="1" stop-color="#4b637f"/></linearGradient>
  </defs>
  <ellipse class="hc-shadow" cx="79" cy="174" rx="33" ry="5" fill="#8ebada" opacity=".2"/>
  <g class="hc-float">
    <path d="m65 149-3 15m31-15 3 15" stroke="#40536c" stroke-width="10" stroke-linecap="round"/>
    <path d="M63 161q-12-1-15 7h24l-1-7m24 0q12-1 16 7H86l1-7" fill="#293e57" stroke="#92a8bf" stroke-width="1.7" stroke-linejoin="round"/>
    <path d="M49 114q-13 6-15 22" fill="none" stroke="#7188a1" stroke-width="14" stroke-linecap="round"/>
    <ellipse cx="34" cy="140" rx="8" ry="9" fill="url(#hc-einstein-skin)" transform="rotate(-12 34 140)"/>
    <g class="hc-arm-wave">
      <path d="M111 115q19-3 22-18" fill="none" stroke="#7188a1" stroke-width="14" stroke-linecap="round"/>
      <path d="m128 98-4-12q-1-4 2-4l6 9 1-17q1-4 4-1l1 16 6-10q3-3 4 1l-7 15q0 12-9 12Z" fill="url(#hc-einstein-skin)" stroke="#dca681" stroke-width="1.3" stroke-linejoin="round"/>
      <path d="M131 101q-2-6 4-9" fill="none" stroke="#d09a76" stroke-width="1.5" stroke-linecap="round"/>
      <path d="m126 104 12 3" stroke="#edf2ed" stroke-width="4"/>
    </g>
    <path d="M57 103q-14 6-16 39l4 13q34 10 69-1l2-14q-3-31-17-37Z" fill="url(#hc-einstein-coat)" stroke="#9aafc3" stroke-width="1.6"/>
    <path d="m66 104 13 36 14-36" fill="#fff4dc"/>
    <path d="m59 108-7 15 13 1-4 7 18 14m19-37 7 15-13 1 5 7-18 14" fill="#97aabd" stroke="#b8c7d2" stroke-width="1.2" stroke-linejoin="round"/>
    <path d="m78 116-8-4v10l8-4 10 4v-10Z" fill="#67c6cc" stroke="#3b8e9e" stroke-width="1.2" stroke-linejoin="round"/>
    <circle cx="79" cy="117" r="2.5" fill="#397b94"/>
    <path d="M79 143v14" stroke="#b5c4ce" stroke-width="1.2"/><circle cx="83" cy="149" r="1.7" fill="#dce8e8"/>
    <path d="M95 137h13" stroke="#405a75" stroke-width="2" stroke-linecap="round"/>
    <path d="M102 136v-8" stroke="#f2c886" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M41 93Q21 91 25 78L17 76Q20 67 31 64L18 59Q24 50 34 47L24 40Q34 33 47 35L43 25Q57 23 64 30L67 18Q80 19 84 28L95 17Q105 23 104 33L118 25Q124 34 118 43L133 39Q137 50 126 57L140 58Q141 70 130 74L139 81Q136 92 119 94Z" fill="url(#hc-einstein-hair)" stroke="#c7d6e4" stroke-width="1.6" stroke-linejoin="round"/>
    <ellipse cx="43" cy="81" rx="9" ry="12" fill="#efbd98"/><ellipse cx="116" cy="81" rx="9" ry="12" fill="#edb590"/>
    <path d="M48 66q0-31 32-30 32-1 32 30v21q-3 27-32 29-30-2-32-29Z" fill="url(#hc-einstein-skin)" stroke="#e5b690" stroke-width="1.5"/>
    <path d="M49 65q-3-14 8-25-16 6-17 26l3 19 7 2Zm59-1q2-17-8-25 18 8 18 26l-5 22-7-1Z" fill="url(#hc-einstein-hair)"/>
    <path d="M57 39q-8-5-14 1m65 0q7-4 15 4M29 59l12-5m78 2 10 7M30 78l11-5m78 4 10 6" fill="none" stroke="#b7c9db" stroke-width="1.7" stroke-linecap="round"/>
    <path d="M65 49q14-4 28 0m-23 6q9-2 18 0" fill="none" stroke="#dca987" stroke-width="1.3" stroke-linecap="round" opacity=".75"/>
    <path d="M54 67q8-6 17-2m17 0q10-4 16 2" fill="none" stroke="#fffff7" stroke-width="4" stroke-linecap="round"/>
    <g class="hc-eyes" fill="#37465a">
      <ellipse cx="63" cy="77" rx="3.8" ry="5.5"/><ellipse cx="96" cy="77" rx="3.8" ry="5.5"/>
      <circle cx="64" cy="75.5" r="1.25" fill="#fff"/><circle cx="97" cy="75.5" r="1.25" fill="#fff"/>
    </g>
    <path d="m53 78-3 1m55-1 3 1" stroke="#d19979" stroke-width="1.4" stroke-linecap="round"/>
    <ellipse cx="55" cy="88" rx="7" ry="4" fill="#e7a08c" opacity=".6"/><ellipse cx="105" cy="88" rx="7" ry="4" fill="#e7a08c" opacity=".6"/>
    <path d="M72 101q8 7 16 0" fill="none" stroke="#915d51" stroke-width="2.2" stroke-linecap="round"/>
    <path d="M79 90q-12-6-17 2l-5 6q10 5 22-1 12 6 23 0l-6-5q-5-8-17-2Z" fill="url(#hc-einstein-hair)" stroke="#d9d9cd" stroke-width="1" stroke-linejoin="round"/>
    <path d="m65 95 9-2m11 0 9 2" stroke="#c5cfd3" stroke-width="1" stroke-linecap="round"/>
    <path d="M77 82q-6 10 3 11 8-1 3-7" fill="#eab28c" stroke="#d5a07d" stroke-width="1.2" stroke-linecap="round"/>
  </g>
</svg>`;
  launcher.replaceChildren(mascot, el('span', 'hc-launcher-label', 'Jack'));
  let greeted = false, greetingTimer = null, statusTask = null, authenticated = false;
  try { greeted = sessionStorage.getItem('helicraft-mascot-welcomed') === '1'; } catch (_) {}
  const greeting = el('div', 'hc-greeting-card'); greeting.hidden = true;
  const greetingText = el('p', '', 'Welcome back! I am Jack. Tell me what you want to build, and we can work through the parameters.');
  greetingText.setAttribute('role', 'status');
  const dismissGreeting = button('×', hideGreeting); dismissGreeting.setAttribute('aria-label', 'Dismiss assistant greeting');
  const loginLink = el('a', 'hc-login-link', 'Log in to chat →'); loginLink.href = '/app.html'; loginLink.hidden = true;
  loginLink.addEventListener('click', event => {
    if (!workbench) return;
    const overlay = byId('auth-overlay');
    if (overlay) {
      event.preventDefault(); toggle(false);
      overlay.style.display = 'flex'; overlay.style.opacity = '1';
      byId('reg-email')?.focus();
    }
  });
  greeting.append(greetingText, loginLink, dismissGreeting);
  dock.append(greeting, launcher);
  function hideGreeting() { greeting.hidden = true; dock.classList.remove('hc-greeting'); clearTimeout(greetingTimer); }
  function authBlocked() {
    return ['auth-overlay', 'welcome-overlay'].some(id => {
      const node = document.getElementById(id);
      return node && !node.hidden && getComputedStyle(node).display !== 'none' && getComputedStyle(node).visibility !== 'hidden';
    });
  }
  function canChat() { return workbench && authenticated && !authBlocked(); }
  function showLoginPrompt() {
    hideGreeting();
    greetingText.textContent = workbench ? 'Please log in to chat with Jack and get modeling suggestions.'
      : 'Hi, I am Jack. Log in to the workspace to chat and explore your modeling parameters.';
    loginLink.textContent = authenticated && !workbench ? 'Open workspace →' : 'Log in to chat →';
    loginLink.hidden = false; greeting.hidden = false;
  }
  async function openAssistant() {
    if (!panel.hidden) { toggle(false); return; }
    if (!workbench) { showLoginPrompt(); return; }
    await refreshStatus();
    if (canChat()) toggle(true); else showLoginPrompt();
  }
  function updateAccess() {
    input.disabled = !canChat(); send.disabled = busy || !canChat();
    if (!canChat()) { if (!panel.hidden) toggle(false); return; }
    if (greeted || !panel.hidden) return;
    greeted = true;
    try { sessionStorage.setItem('helicraft-mascot-welcomed', '1'); } catch (_) {}
    greetingText.textContent = 'Welcome back! I am Jack. Tell me what you want to build, and we can work through the parameters.';
    loginLink.hidden = true;
    greeting.hidden = false; dock.classList.add('hc-greeting');
    greetingTimer = setTimeout(hideGreeting, 9000);
  }
  const panel = el('aside'); panel.id = 'hc-assistant'; panel.hidden = true;
  panel.setAttribute('aria-label', 'Jack, HeliCraft modeling assistant');
  const head = el('div', 'hc-head');
  const brand = el('div'); brand.append(el('strong', '', 'Jack · HeliCraft assistant'), el('small', '', 'DeepSeek · Modeling guidance'));
  const actions = el('div', 'hc-actions');
  const reset = button('New chat', clearChat); reset.setAttribute('aria-label', 'Start a new assistant conversation');
  const close = button('×', () => toggle(false)); close.setAttribute('aria-label', 'Close AI assistant');
  actions.append(reset, close); head.append(brand, actions);
  const context = el('p', 'hc-context', workbench ? 'Connected to your form · You review each change' : 'Explore features and parameters · Apply changes in the workspace');
  const log = el('div', 'hc-log'); log.setAttribute('role', 'log'); log.setAttribute('aria-live', 'polite');
  const compose = el('div', 'hc-compose');
  const status = el('p', 'hc-status'); status.setAttribute('role', 'status');
  const input = el('textarea'); input.maxLength = 2000;
  input.placeholder = workbench ? 'Try: Keep the radius, increase pitch by 20%' : 'Try: What do I need to build a helical ribbon?';
  input.setAttribute('aria-label', 'Ask Jack, your HeliCraft assistant');
  const row = el('div', 'hc-compose-row');
  const exportButton = button('Export record', exportRecipe, 'hc-export');
  const send = button('Send', sendMessage, 'hc-primary');
  row.append(exportButton, el('small', '', 'Enter to send · Shift+Enter for a new line'), send);
  compose.append(status, input, row); panel.append(head, context, log, compose);
  document.body.append(dock, panel);

  function toggle(open) {
    if (open && !canChat()) { showLoginPrompt(); return; }
    panel.hidden = !open; launcher.setAttribute('aria-expanded', String(open));
    launcher.setAttribute('aria-label', open ? 'Collapse Jack, your HeliCraft assistant' : 'Open Jack, your HeliCraft assistant');
    dock.classList.toggle('hc-chat-open', open); hideGreeting();
    if (open) { lastFocus = document.activeElement; input.focus(); }
    else if (lastFocus?.isConnected) lastFocus.focus();
  }
  function bubble(role, text) {
    const node = el('div', 'hc-message' + (role === 'user' ? ' hc-user' : ''));
    node.append(el('span', 'hc-speaker', role === 'user' ? 'You' : 'Jack'), el('p', '', text));
    log.append(node);
    while (log.childElementCount > 24) log.firstElementChild.remove();
    log.scrollTop = log.scrollHeight; return node;
  }
  function welcome() {
    bubble('assistant', workbench
      ? 'Hi, I am Jack. Tell me what you want to build or change. I can explain your current parameters and propose changes for you to review before applying.'
      : 'Hi, I am Jack. I can explain HeliCraft, help define your structure, and guide parameter choices. Open the workspace to review and apply suggestions. You can ask in English or Chinese.');
    const examples = el('div', 'hc-examples');
    (workbench ? ['What do W and L control?', 'Increase pitch by 20%, keeping other parameters', 'Which parameters still need clarification?']
      : ['Which file should I prepare?', 'Which geometries are supported?', 'How can AI help me?']).forEach(text =>
      examples.append(button(text, () => { input.value = text; input.focus(); })));
    log.append(examples);
  }
  function clearChat() {
    sequence++; controller?.abort(); controller = null; busy = false; send.disabled = !canChat();
    window.HeliCraftSessionRecord?.note('chat_cleared', { scope: 'Jack context only; modeling session record retained' });
    history = []; latest = null; lastExchange = null; save(); log.replaceChildren(); status.textContent = ''; welcome(); input.value = ''; input.focus();
  }
  // HELICRAFT_RESPONSE_HANDLING_V0152_START
  function responseMetadata(response) {
    const media = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
    const ray = response.headers.get('cf-ray') || '';
    const server = (response.headers.get('server') || '').toLowerCase();
    return {
      http_status: response.status,
      content_type: /^[a-z0-9.+/-]{1,64}$/.test(media) ? media : 'missing-or-unrecognized',
      redirected: response.redirected,
      cf_ray: /^[a-f0-9]{12,32}(?:-[a-z]{3})?$/i.test(ray) ? ray : null,
      server_hint: /cloudflare/.test(server) ? 'cloudflare' : /nginx/.test(server) ? 'nginx' : /uvicorn/.test(server) ? 'uvicorn' : 'other-or-unspecified'
    };
  }

  function responseProblem(response, reason) {
    const media = (response.headers.get('content-type') || 'missing content type').split(';')[0].trim();
    const safeMedia = /^[a-z0-9.+/ -]{1,64}$/i.test(media) ? media : 'unknown content type';
    const code = `HTTP ${response.status}; ${safeMedia}; ${reason}`;
    let message = 'Jack received an unexpected website response. Please refresh the page and try again.';
    if (response.status === 429) message = 'Too many assistant requests. Please wait before trying again.';
    else if (response.status === 403) message = 'The website denied the assistant request. Please contact the site administrator.';
    else if (response.status >= 500) message = 'The website could not complete the assistant request. Please try again later.';
    else if (response.redirected) message = 'The assistant request was redirected. Please refresh the page and log in again.';
    return new Error(`${message} Your form is unchanged. If this continues, share this code with the administrator: ${code}.`);
  }

  async function readAssistantResponse(response, kind) {
    // Never display or execute a proxy error page, even when it has HTTP 200.
    if (response.redirected) throw responseProblem(response, 'redirected response');
    const media = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
    if (!/^application\/(?:[a-z0-9.-]+\+)?json$/.test(media)) {
      throw responseProblem(response, 'expected JSON');
    }
    let data;
    try { data = await response.json(); }
    catch (error) {
      if (error.name === 'AbortError') throw error;
      throw responseProblem(response, 'invalid JSON');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw responseProblem(response, 'invalid response');
    }
    if (!response.ok) {
      // Existing API errors are plain messages. Do not echo an HTML error body.
      if (typeof data.detail === 'string' && data.detail.length <= 600 && !/<[a-z!][^>]*>/i.test(data.detail)) {
        throw new Error(`${data.detail} (HTTP ${response.status})`);
      }
      throw responseProblem(response, 'request rejected');
    }
    const strings = value => Array.isArray(value) && value.every(item => typeof item === 'string');
    if (kind === 'status') {
      if (typeof data.configured !== 'boolean' || typeof data.authenticated !== 'boolean') {
        throw responseProblem(response, 'invalid status response');
      }
    } else if (typeof data.reply !== 'string' || !strings(data.questions) || !strings(data.issues)
        || !strings(data.warnings) || typeof data.can_apply !== 'boolean'
        || typeof data.request_id !== 'string' || !data.candidate || typeof data.candidate !== 'object'
        || Array.isArray(data.candidate) || !Array.isArray(data.changes)
        || !data.changes.every(change => change && typeof change === 'object'
          && ['field', 'label', 'unit', 'reason', 'source'].every(key => typeof change[key] === 'string')
          && ['string', 'number'].includes(typeof change.value))) {
      throw responseProblem(response, 'invalid chat response');
    }
    return data;
  }
  // HELICRAFT_RESPONSE_HANDLING_V0152_END
  function refreshStatus() {
    if (statusTask) return statusTask;
    statusTask = (async () => {
      try {
      const response = await fetch('/api/assistant/status', { credentials: 'same-origin', cache: 'no-store', headers: { 'Accept': 'application/json' } });
      const data = await readAssistantResponse(response, 'status');
      authenticated = data.authenticated === true;
      updateAccess();
      if (busy) return;
      status.textContent = !data.configured ? 'The model service is not configured yet.'
        : !canChat() ? 'Log in to the workspace to use the AI assistant.' : 'Ready · Suggestions never change your form automatically';
      } catch (error) {
        authenticated = false; updateAccess();
        if (!busy) status.textContent = error.message || 'The assistant is unavailable. You can continue manual modeling.';
      } finally { statusTask = null; }
    })();
    return statusTask;
  }
  function renderPlan(node, data, snapshot, fileId, recordSessionId) {
    if (!data.changes.length && !data.questions.length) return;
    const box = el('div', 'hc-plan');
    if (data.changes.length) box.append(el('strong', '', 'Proposed changes · Not applied'));
    const sourceLabels = { explicit: 'Requested', derived: 'Calculated', suggestion: 'Starting point' };
    data.changes.forEach(change => {
      const item = el('div', 'hc-change');
      item.append(el('b', '', change.label), el('span', '', `${displayValue(change.before)} → ${displayValue(change.value)} ${change.unit}`),
        el('small', '', `${sourceLabels[change.source] || 'Suggestion'} · ${change.reason}`)); box.append(item);
    });
    const questions = [...data.questions, ...(workbench && data.changes.length ? data.issues : [])];
    if (questions.length) {
      const list = el('ul'); [...new Set(questions)].forEach(text => list.append(el('li', '', text))); box.append(list);
    }
    if (data.changes.length) {
      const details = el('details'); details.append(el('summary', '', 'Validation scope and notes'));
      data.warnings.forEach(text => details.append(el('p', '', text))); box.append(details);
      if (!workbench) {
        const link = el('a', '', 'Continue in the workspace →'); link.href = '/app.html'; box.append(link);
      } else {
        const apply = button(data.can_apply ? 'Review and apply' : 'More information needed', async () => {
          if (latest?.request_id !== data.request_id || JSON.stringify(current()) !== snapshot || fileIdentity() !== fileId) {
            apply.disabled = true; status.textContent = 'The form or monomer has changed. Please request a new suggestion.'; return;
          }
          try {
            const parsed = await monomer();
            const a = parsed?.coordinates[data.candidate.a_idx], b = parsed?.coordinates[data.candidate.b_idx];
            if (!a || !b || Math.hypot(...a.map((x, i) => x - b[i])) < 1e-8) throw new Error('Reference atoms are invalid or overlap. Choose different atoms A and B.');
            if (latest?.request_id !== data.request_id || JSON.stringify(current()) !== snapshot || fileIdentity() !== fileId) {
              throw new Error('The form changed while reading the monomer. Please request a new suggestion.');
            }
            data.changes.forEach(change => { if (byId(change.field)) byId(change.field).value = change.value; });
            const angle = byId('angle_disp'); if (angle) angle.textContent = byId('insertion_angle').value;
            byId('base_type').dispatchEvent(new Event('change', { bubbles: true }));
            apply.disabled = true; apply.textContent = 'Applied to form';
            window.HeliCraftSessionRecord?.note('parameters_applied', { request_id: data.request_id, source_session_id: recordSessionId, before: JSON.parse(snapshot), after: current(), changes: data.changes, proposal: data });
            history.push({role: 'assistant', content: 'The user confirmed and applied these parameters: ' + JSON.stringify(current())}); history = history.slice(-10); save();
            status.textContent = 'Parameters updated. Check the preview, then select Build assembly.';
          } catch (error) { status.textContent = error.message; }
        }, 'hc-primary');
        apply.disabled = !data.can_apply;
        if (data.questions.length && !data.issues.length) apply.textContent = 'Answer the questions before applying';
        box.append(apply);
      }
    }
    node.append(box); log.scrollTop = log.scrollHeight;
  }
  function preferredLocale() {
    // Browsers expose language preferences, not a separate OS-language API.
    // Send one bounded language tag only; never send the full navigator object.
    try {
      const candidates = Array.from(navigator.languages || []);
      if (navigator.language) candidates.push(navigator.language);
      for (const value of candidates) {
        if (typeof value !== 'string') continue;
        const tag = value.trim();
        if (tag.length > 35 || !/^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(tag)) continue;
        try {
          if (typeof Intl !== 'undefined' && typeof Intl.getCanonicalLocales === 'function') {
            return Intl.getCanonicalLocales(tag)[0] || 'en';
          }
          return tag;
        } catch (_) { /* Try the next browser preference. */ }
      }
    } catch (_) { /* Language preferences unavailable. */ }
    return 'en';
  }

  async function sendMessage() {
    if (!canChat()) { showLoginPrompt(); return; }
    const message = input.value.trim(); if (!message || busy) return;
    busy = true; send.disabled = true; const turn = ++sequence; controller = new AbortController();
    const timeout = setTimeout(() => controller?.abort(), 60000);
    status.textContent = 'Reviewing your parameters…';
    const values = current(), snapshot = JSON.stringify(values), fileId = fileIdentity();
    let recordSessionId = null;
    let exchange = null; const started = Date.now();
    try {
      const parsed = workbench ? await monomer() : null;
      if (turn !== sequence) return;
      recordSessionId = window.HeliCraftSessionRecord?.sessionId() ?? null;
      const request = { message, history: history.slice(-10), current: values, atom_count: parsed?.n ?? null, page, ui_locale: preferredLocale() };
      exchange = { started_at: new Date().toISOString(), request, response: null, outcome: 'pending' };
      lastExchange = exchange;
      bubble('user', message); input.value = '';
      const response = await fetch('/api/assistant/chat', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(request), signal: controller.signal });
      if (turn !== sequence) return;
      exchange.response = responseMetadata(response);
      if (response.status === 401) {
        authenticated = false; updateAccess(); showLoginPrompt();
        throw new Error('Your session has expired. Please log in again.');
      }
      const data = await readAssistantResponse(response, 'chat');
      if (turn !== sequence) return;
      latest = data; exchange.outcome = 'success';
      window.HeliCraftSessionRecord?.note('proposal_ready', { request_id: data.request_id, can_apply: data.can_apply, issues: data.issues, warnings: data.warnings }, recordSessionId);
      const node = bubble('assistant', data.reply); renderPlan(node, data, snapshot, fileId, recordSessionId);
      history.push({ role: 'user', content: message }, { role: 'assistant', content: JSON.stringify({
        reply: data.reply.slice(0, 2000), questions: data.questions.map(text => text.slice(0, 200)),
        proposed_changes: data.changes.map(({field, value, source}) => ({field, value, source})),
        application_status: 'not_applied' }) });
      history = history.slice(-10); save();
      status.textContent = data.can_apply ? 'Parameter checks complete. Review before applying.' : 'Add more details or ask a follow-up question.';
    } catch (error) {
      if (turn !== sequence) return;
      if (exchange) { exchange.outcome = 'error'; exchange.error_type = ['AbortError', 'TypeError', 'SyntaxError', 'Error'].includes(error.name) ? error.name : 'Error'; }
      const text = error.name === 'AbortError' ? 'The request timed out. Your form is unchanged. Please try again.' : error.message;
      status.textContent = text; bubble('assistant', text); input.value = message;
    } finally {
      if (exchange) exchange.elapsed_ms = Date.now() - started;
      clearTimeout(timeout);
      if (turn === sequence) { busy = false; send.disabled = !canChat(); controller = null; }
    }
  }
  function exportRecipe() {
    if (window.HeliCraftSessionRecord) {
      window.HeliCraftSessionRecord.exportRecord().catch(() => { status.textContent = 'The record could not be downloaded. Keep this tab open and try again.'; });
      return;
    }
    const record = { format: 'helicraft-assistant-record-v1', exported_at: new Date().toISOString(),
      page, current_parameters: current(), monomer_file: byId('monomerFile')?.files[0]?.name ?? null,
      conversation: history, latest_proposal: latest,
      frontend_version: '0.2.0', last_exchange: lastExchange,
      note: 'Includes recent conversation, parameters and the last request with response metadata. Contains no API key, session cookie, coordinates or raw response page. Preserve the original XYZ separately. No AI physical validation is implied.' };
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' }));
    const link = el('a'); link.href = url; link.download = 'HeliCraft-AI-record.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(); }
  });
  panel.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); toggle(false); } });
  byId('buildForm')?.addEventListener('input', () => {
    if (latest) status.textContent = 'The form has changed. Please request an updated suggestion.';
  });
  byId('monomerFile')?.addEventListener('change', () => {
    latest = null;
    const name = document.getElementById('hc-file-name');
    if (name) name.textContent = byId('monomerFile').files[0]?.name || 'No file selected';
  });
  byId('ai_predict_btn')?.addEventListener('click', openAssistant);
  welcome();
  history.forEach(turn => {
    let text = turn.content;
    if (turn.role === 'assistant') { try { text = JSON.parse(text).reply || text; } catch (_) {} }
    bubble(turn.role, text);
  });
  let wasBlocked = authBlocked();
  const authObserver = new MutationObserver(() => {
    const blocked = authBlocked();
    if (wasBlocked && !blocked) refreshStatus();
    wasBlocked = blocked;
  });
  ['auth-overlay', 'welcome-overlay'].forEach(id => {
    const node = document.getElementById(id);
    if (node) authObserver.observe(node, { attributes: true, attributeFilter: ['style', 'class', 'hidden'] });
  });
  const syncVisibility = () => dock.classList.toggle('hc-suspended', document.hidden);
  document.addEventListener('visibilitychange', syncVisibility);
  syncVisibility();
  updateAccess();
  refreshStatus();
})();
