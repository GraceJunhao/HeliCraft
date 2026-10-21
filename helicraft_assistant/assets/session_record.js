/* HeliCraft: local, exportable modeling provenance. No extra server requests. */
(() => {
  'use strict';
  if (window.HeliCraftSessionRecord || !document.getElementById('buildForm')) return;
  const VERSION = '0.2.0', FORMAT = 'helicraft-modeling-session-v2';
  const KEY = 'helicraft-modeling-session-v2', ART_KEY = KEY + ':artifact:';
  const MAX_EVENTS = 10000, MAX_ARTIFACTS = 1000, MAX_EVENT_BYTES = 16 * 1024 * 1024;
  const MAX_TEXT_BYTES = 8 * 1024 * 1024, MAX_TOTAL_BYTES = 32 * 1024 * 1024;
  const parameterFields = ['base_type', 'chirality', 'R', 'P', 'N', 'Rbase', 'Rtop', 'k',
    'Length', 'twist_turns', 'W', 'L', 'insertion_angle', 'a_idx', 'b_idx', 'strand_count', 'strand_phase_deg', 'contact_cutoff', 'save_cg', 'cg_template_name'];
  const formFields = ['spiral_type', ...parameterFields.filter(x => !['base_type', 'chirality'].includes(x))];
  const form = document.getElementById('buildForm');
  const byId = field => document.getElementById(field === 'chirality' ? 'chirality_sel' : field);
  const now = () => new Date().toISOString();
  const clone = value => JSON.parse(JSON.stringify(value));
  const utf8 = value => new TextEncoder().encode(value);
  const tasks = new Set(), inflight = new Set();
  let fileIds = new WeakMap(), state, observed, persistTimer, storageWarning = '', counter = 0;
  let statusNode, exportButton, generation = 0, exportsInProgress = 0;

  function identifier(prefix) {
    const value = typeof crypto.randomUUID === 'function' ? crypto.randomUUID()
      : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    return prefix + '-' + value;
  }
  function parameters() {
    const result = {};
    parameterFields.forEach(field => {
      const input = byId(field); if (!input) return;
      if (input.type === 'checkbox') result[field] = input.checked;
      else if (input.type === 'number' || input.type === 'range') {
        const value = Number(input.value);
        result[field] = input.value.trim() && Number.isFinite(value) ? value : input.value;
      } else result[field] = input.value;
    });
    if (['Flat带', 'Twist带'].includes(result.base_type)) {
      result.strand_count = 1; result.strand_phase_deg = 0;
    }
    return result;
  }
  function frontendVersion() {
    const script = Array.from(document.scripts).find(s => /\/assistant\.js(?:\?|$)/.test(s.src));
    try { return script ? new URL(script.src).searchParams.get('v') : null; } catch (_) { return null; }
  }
  function fresh() {
    return { format: FORMAT, recorder_version: VERSION, session_id: identifier('session'), started_at: now(),
      origin: location.origin, page: 'workbench', initial_parameters: parameters(),
      source_versions: { recorder_version: VERSION, frontend_version: frontendVersion(),
        backend_version: null, prompt_version: null, model_configured: null },
      current_monomer_id: null, last_recorded_monomer_id: null, events: [], artifacts: [], limitations: [],
      event_capture_complete: true, recording_stopped: false, event_byte_count: 0,
      recording_scope: {
        events: 'Selected workspace form changes, XYZ selection, chat API request fields and allowlisted application response fields, reviewed application and build requests/results. This is not the provider raw HTTP envelope.',
        exclusions: 'Authentication, cookies, API keys, unrelated requests, camera movements and screenshots are not captured.',
        storage: 'Current browser tab; export before closing. Browser storage may be unavailable or lose coordinate text at quota.',
        model_identity: 'Model identifier is the configured API value, not a guaranteed provider model snapshot.',
        limits: { maximum_events: MAX_EVENTS, maximum_event_bytes: MAX_EVENT_BYTES, maximum_artifacts: MAX_ARTIFACTS,
          maximum_embedded_artifact_bytes: MAX_TEXT_BYTES, maximum_total_embedded_bytes: MAX_TOTAL_BYTES }
      } };
  }
  function warning(text) {
    storageWarning = text;
    if (state && !state.limitations.includes(text)) state.limitations.push(text);
    updateStatus();
  }
  function updateStatus() {
    if (!statusNode || !state) return;
    statusNode.textContent = storageWarning || `Recording this workspace · ${state.events.length} events · Local to this tab`;
    statusNode.style.color = storageWarning ? '#fbbf24' : '#94a3b8';
  }
  function storageShape() {
    const value = { ...state, artifacts: state.artifacts.map(artifact => {
      const copy = { ...artifact }; delete copy.text; return copy;
    }) };
    return JSON.stringify(value);
  }
  function persist() {
    clearTimeout(persistTimer);
    try { sessionStorage.setItem(KEY, storageShape()); }
    catch (_) {
      // Preserve the event log first; coordinate text remains available in memory for export.
      state.artifacts.forEach(a => { try { sessionStorage.removeItem(ART_KEY + a.id); } catch (_) {} });
      warning('Browser storage is limited. Export this session now; coordinate files may not survive a refresh.');
      try { sessionStorage.setItem(KEY, storageShape()); }
      catch (_) { warning('Browser storage is unavailable. The record is kept in memory: export before refreshing or closing this tab.'); }
    }
  }
  function schedulePersist() {
    clearTimeout(persistTimer); persistTimer = setTimeout(persist, 80);
  }
  function note(type, data = {}) {
    if (!state) return null;
    if (stopped()) return null;
    if (state.events.length >= MAX_EVENTS || state.event_byte_count >= MAX_EVENT_BYTES) {
      state.event_capture_complete = false;
      state.recording_stopped = true;
      warning('Recording reached its event limit. Export this record and start a new session record.');
      schedulePersist(); return null;
    }
    const event = { id: state.events.length + 1, at: now(), type, data: clone(data) };
    const bytes = utf8(JSON.stringify(event)).byteLength;
    if (state.event_byte_count + bytes > MAX_EVENT_BYTES) {
      state.event_capture_complete = false;
      state.recording_stopped = true;
      warning('Recording reached its 16 MiB event limit. Export and start a new record.');
      schedulePersist(); return null;
    }
    state.events.push(event); state.event_byte_count += bytes; schedulePersist();
    if (state.events.length === MAX_EVENTS) {
      state.event_capture_complete = false;
      state.recording_stopped = true;
      warning('Recording stopped at 10,000 events. Export this record and start a new session record.');
    } else updateStatus();
    return event.id;
  }
  function stopped() { return state.recording_stopped === true; }
  function track(task) {
    const safe = Promise.resolve(task).catch(() => {
      warning('An item could not be recorded. Export the record and keep the original files separately.');
    });
    tasks.add(safe); safe.finally(() => tasks.delete(safe)); return safe;
  }
  async function sha256(bytes) {
    if (!crypto.subtle) return null;
    try {
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest)).map(x => x.toString(16).padStart(2, '0')).join('');
    } catch (_) { return null; }
  }
  function embeddedBytes() {
    return state.artifacts.filter(a => a.included).reduce((sum, a) => sum + a.byte_count, 0);
  }
  function addTextArtifact(kind, text, filename, originalFilename = null) {
    if (stopped()) return null;
    if (state.artifacts.length >= MAX_ARTIFACTS) {
      warning('The record reached 1,000 coordinate files. Preserve additional files separately.'); return null;
    }
    const bytes = utf8(text), token = generation;
    const artifact = { id: identifier('artifact'), kind, filename, original_filename: originalFilename,
      byte_count: bytes.byteLength, sha256: null, included: false, omission_reason: null };
    if (bytes.byteLength > MAX_TEXT_BYTES || embeddedBytes() + bytes.byteLength > MAX_TOTAL_BYTES) {
      artifact.omission_reason = 'Embedded coordinate size limit exceeded; preserve this file separately.';
      warning('A coordinate file exceeds the record size limit. Its metadata is recorded; save the file separately.');
    } else { artifact.text = text; artifact.included = true; }
    state.artifacts.push(artifact);
    track((async () => {
      artifact.sha256 = await sha256(bytes);
      if (token !== generation) return;
      if (!artifact.sha256) warning('Coordinate checksums are unavailable in this browser. Preserve the original files separately.');
      if (artifact.included) {
        try { sessionStorage.setItem(ART_KEY + artifact.id, artifact.text); }
        catch (_) { warning('Coordinate text is kept in this tab only. Export the session before refreshing.'); }
      }
      schedulePersist();
    })());
    return artifact.id;
  }
  function captureFile(file) {
    if (stopped()) return null;
    if (!file || typeof file.text !== 'function') return null;
    if (fileIds.has(file)) return fileIds.get(file);
    if (state.artifacts.length >= MAX_ARTIFACTS) {
      warning('The record reached 1,000 coordinate files. Preserve additional files separately.'); return null;
    }
    const id = identifier('artifact'), token = generation;
    const artifact = { id, kind: 'monomer_xyz', filename: `monomer_${state.artifacts.filter(a => a.kind === 'monomer_xyz').length + 1}.xyz`,
      original_filename: file.name, byte_count: file.size, sha256: null, included: false, omission_reason: null };
    state.artifacts.push(artifact); fileIds.set(file, id);
    if (file.size > 32 * 1024 * 1024) {
      artifact.omission_reason = 'Input XYZ exceeds the embedded size limit; preserve the original file separately.';
      warning('The XYZ is too large to embed. Its metadata is recorded; preserve the original file separately.');
    } else track((async () => { try {
      const bytes = new Uint8Array(await file.arrayBuffer()); if (token !== generation) return;
      artifact.byte_count = bytes.byteLength;
      artifact.sha256 = await sha256(bytes); if (token !== generation) return;
      let text;
      try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); }
      catch (_) {
        artifact.omission_reason = 'Input is not valid UTF-8 text; preserve the original XYZ bytes separately.';
        warning('The XYZ encoding cannot be embedded as text. Its checksum is recorded; preserve the original file.');
        schedulePersist(); return;
      }
      if (bytes.byteLength > MAX_TEXT_BYTES || embeddedBytes() + bytes.byteLength > MAX_TOTAL_BYTES) {
        artifact.omission_reason = 'Total embedded coordinate size limit exceeded; preserve the original file separately.';
        warning('The record has reached its coordinate size limit. Preserve additional files separately.');
      } else {
        artifact.included = true; artifact.text = text;
        try { sessionStorage.setItem(ART_KEY + id, text); }
        catch (_) { warning('The XYZ is kept in this tab only. Export before refreshing.'); }
      }
      if (!artifact.sha256) warning('Coordinate checksums are unavailable in this browser. Preserve the original files separately.');
      schedulePersist();
    } catch (_) {
      if (token !== generation) return;
      artifact.included = false; delete artifact.text;
      artifact.omission_reason = 'Input XYZ could not be read; preserve or reselect the original file.';
      warning('The XYZ could not be recorded. Preserve or reselect the original file.');
      schedulePersist();
    } })());
    schedulePersist(); return id;
  }
  function captureSelectedFile() {
    const file = byId('monomerFile')?.files?.[0];
    const id = captureFile(file); state.current_monomer_id = id;
    if (id) state.last_recorded_monomer_id = id;
    note('monomer_selected', { monomer_id: id, original_filename: file?.name ?? null,
      byte_count: file?.size ?? null, last_modified: file?.lastModified ?? null });
  }
  function load() {
    let restored = false, corrupt = false;
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (saved?.format === FORMAT && Array.isArray(saved.events) && Array.isArray(saved.artifacts)
          && saved.events.length <= MAX_EVENTS && saved.artifacts.length <= MAX_ARTIFACTS && typeof saved.session_id === 'string'
          && saved.events.every((e, i) => e && e.id === i + 1 && typeof e.at === 'string' && typeof e.type === 'string'
            && e.data && typeof e.data === 'object' && !Array.isArray(e.data))
          && saved.artifacts.every(a => a && typeof a.id === 'string' && typeof a.filename === 'string'
            && ['monomer_xyz', 'built_pdb'].includes(a.kind) && typeof a.included === 'boolean'
            && Number.isFinite(a.byte_count) && a.byte_count >= 0)
          && saved.source_versions && Array.isArray(saved.limitations)) {
        state = saved; restored = true;
        state.event_byte_count = state.events.reduce((sum, e) => sum + utf8(JSON.stringify(e)).byteLength, 0);
        if (state.events.length >= MAX_EVENTS || state.event_byte_count >= MAX_EVENT_BYTES) state.recording_stopped = true;
        state.artifacts.forEach(a => {
          const text = sessionStorage.getItem(ART_KEY + a.id);
          if (a.included && typeof text === 'string') a.text = text;
          else if (a.included) {
            a.included = false; a.omission_reason = 'Coordinate text was not retained after refresh; preserve the original exported file separately.';
            warning('Event history restored; some coordinate files were not retained. Keep or reselect the original files.');
          } else if (!a.omission_reason) {
            a.omission_reason = 'Coordinate capture was interrupted before completion; preserve or reselect the original file.';
            warning('A coordinate capture was interrupted. Keep or reselect the original file.');
          }
        });
      } else if (saved) corrupt = true;
    } catch (_) { state = null; restored = false; corrupt = true; }
    if (!state) state = fresh();
    if (corrupt) warning('The saved browser record could not be restored. A new record has started; retain previously exported files.');
    if (!byId('monomerFile')?.files?.[0]) {
      if (state.current_monomer_id) state.last_recorded_monomer_id = state.current_monomer_id;
      state.current_monomer_id = null;
    }
    observed = parameters();
    note(restored ? 'session_resumed' : 'session_started', { parameters: observed, recorder_version: VERSION });
  }
  function recordFormChange(event) {
    if (!event.target?.id || !parameterFields.some(field => byId(field) === event.target)) return;
    const after = parameters(), before = observed;
    observed = after;
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      note('form_changed', { field: event.target.id, source: event.isTrusted ? 'user' : 'script_event', before, after });
    }
  }
  function allowChatRequest(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) return {};
    return Object.fromEntries(['message', 'history', 'current', 'atom_count', 'page', 'ui_locale']
      .filter(key => Object.prototype.hasOwnProperty.call(body, key)).map(key => [key, body[key]]));
  }
  function allowChatResponse(body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) return {};
    return Object.fromEntries(['status', 'reply', 'questions', 'changes', 'candidate', 'issues', 'warnings',
      'can_apply', 'checks', 'request_id', 'model', 'prompt_version', 'version', 'format_normalizations', 'detail', 'error_code', 'error_fields', 'release']
      .filter(key => Object.prototype.hasOwnProperty.call(body, key)).map(key => [key, body[key]]));
  }
  async function readLimited(response, maxBytes) {
    const reader = response.body?.getReader();
    if (!reader) {
      const text = await response.text(); if (utf8(text).byteLength > maxBytes) throw new Error('Recording size limit'); return text;
    }
    const chunks = []; let size = 0;
    try {
      while (true) {
        const item = await reader.read(); if (item.done) break;
        size += item.value.byteLength;
        if (size > maxBytes) {
          // A cloned Response is a tee: waiting for cancellation may wait for the caller's branch.
          reader.cancel().catch(() => {}); throw new Error('Recording size limit');
        }
        chunks.push(item.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    chunks.forEach(chunk => { bytes.set(chunk, offset); offset += chunk.byteLength; });
    return new TextDecoder().decode(bytes);
  }
  function responseInfo(response) {
    return { http_status: response.status, content_type: (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase(),
      redirected: response.redirected };
  }
  async function recordResponse(response, context, parsedBody) {
    const meta = responseInfo(response), token = context.generation;
    if (token !== generation) return;
    if (stopped()) { inflight.delete(context.id); return; }
    let body = parsedBody || null, failure = null;
    if (parsedBody) { /* Reuse the UI JSON parse: no second giant coordinate buffer. */ }
    else if (!/^application\/(?:[a-z0-9.-]+\+)?json$/.test(meta.content_type)) failure = 'non_json_response';
    else try { body = JSON.parse(await readLimited(response, context.kind === 'build' ? 20 * 1024 * 1024 : 1024 * 1024)); }
    catch (error) { failure = error.message === 'Recording size limit' ? 'response_exceeds_recording_limit' : 'invalid_json'; }
    if (token !== generation) return;
    const elapsed = Date.now() - context.started;
    if (context.kind === 'status') {
      if (body && typeof body.version === 'string') state.source_versions.backend_version = body.version;
      if (body?.release) state.source_versions.release = clone(body.release);
      schedulePersist(); return;
    }
    inflight.delete(context.id);
    if (failure) {
      note(context.kind + '_failed', { [context.kind === 'chat' ? 'exchange_id' : 'build_id']: context.id,
        ...meta, error: failure, elapsed_ms: elapsed });
      if (failure === 'response_exceeds_recording_limit') warning('A response exceeded the recording limit. Save its coordinate output separately.');
      return;
    }
    if (context.kind === 'chat') {
      const result = allowChatResponse(body);
      ['version', 'prompt_version', 'model'].forEach((key, index) => {
        if (typeof result[key] === 'string') state.source_versions[['backend_version', 'prompt_version', 'model_configured'][index]] = result[key];
      });
      note(response.ok ? 'chat_response' : 'chat_failed', { exchange_id: context.id, ...meta, response: result, elapsed_ms: elapsed });
    } else {
      const result = { build_id: context.id, ...meta, elapsed_ms: elapsed, status: body?.status ?? null,
        message: typeof body?.message === 'string' ? body.message : null, pdb_artifact_id: null };
      if (response.ok && body?.status === 'success') {
        result.artifact_ids = {};
        // Hash every returned artifact, even when its text exceeds embedding quotas.
        for (const ext of ['json', 'xyz', 'cif', 'pdb', 'mst', 'xml']) {
          if (typeof body[ext] === 'string') result.artifact_ids[ext] =
            addTextArtifact('built_' + ext, body[ext], `build_${context.ordinal}.${ext}`);
        }
        result.pdb_artifact_id = result.artifact_ids.pdb || null;
        for (const key of ['protocol','release','sampling','contacts','template_sha256',
                          'atom_count','copy_count','atoms_per_monomer','copies_per_strand',
                          'strand_count','strand_phase_deg','pdb_unavailable_reason']) {
          if (body[key] !== undefined) result[key] = clone(body[key]);
        }
        if (body.release) state.source_versions.release = clone(body.release);
      }
      note(response.ok && body?.status === 'success' ? 'build_response' : 'build_failed', result);
    }
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async function(input, init) {
    let url, method, body;
    try {
      url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, location.href);
      method = String(init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
      body = init?.body;
    } catch (_) { return originalFetch(input, init); }
    const kind = url.origin === location.origin && !url.search && !url.hash
      ? url.pathname === '/api/assistant/chat' && method === 'POST' ? 'chat'
        : url.pathname === '/api/build' && method === 'POST' ? 'build'
          : url.pathname === '/api/assistant/status' && method === 'GET' ? 'status' : null : null;
    if (!kind) return originalFetch(input, init);
    if (stopped()) return originalFetch(input, init);
    const context = { kind, id: identifier(kind), started: Date.now(), generation, ordinal: ++counter };
    try {
      if (kind === 'chat') {
        const text = typeof body === 'string' ? body : input instanceof Request ? await input.clone().text() : null;
        const request = text ? allowChatRequest(JSON.parse(text)) : {};
        note('chat_request', { exchange_id: context.id, request }); inflight.add(context.id);
      } else if (kind === 'build') {
        const values = {}, data = body instanceof FormData ? body : input instanceof Request ? await input.clone().formData() : null;
        if (data) formFields.forEach(field => { if (typeof data.get(field) === 'string') values[field] = data.get(field); });
        const monomer = data?.get('file'), monomerId = captureFile(monomer);
        note('build_request', { build_id: context.id, parameters: parameters(), form_fields: values, monomer_id: monomerId });
        inflight.add(context.id);
      }
    } catch (_) {
      state.event_capture_complete = false;
      warning('One request could not be recorded; the modeling request will still proceed.');
    }
    try {
      const response = await originalFetch(input, init);
      try {
        if (kind === 'build') {
          const parse = response.json.bind(response);
          response.json = async () => {
            try { const data = await parse(); track(recordResponse(response, context, data)); return data; }
            catch (error) { inflight.delete(context.id); note('build_failed', {build_id: context.id, error: 'invalid_json'}); throw error; }
          };
        } else track(recordResponse(response.clone(), context));
      }
      catch (_) {
        state.event_capture_complete = false;
        warning('One response could not be recorded. Keep the original coordinate file separately.');
      }
      return response;
    } catch (error) {
      if (context.generation === generation && kind !== 'status') {
        inflight.delete(context.id);
        note(kind + '_failed', { [kind === 'chat' ? 'exchange_id' : 'build_id']: context.id,
          error: error.name === 'AbortError' ? 'aborted_or_timed_out' : 'network_error', elapsed_ms: Date.now() - context.started });
      }
      throw error;
    }
  };

  async function snapshot() {
    // Tasks spawned by response parsing can themselves schedule checksum work.
    while (tasks.size) await Promise.all(Array.from(tasks));
    return { ...clone(state), exported_at: now(), current_parameters: parameters(),
      export_summary: { event_count: state.events.length, artifact_count: state.artifacts.length,
        pending_request_count: inflight.size, embedded_coordinate_bytes: embeddedBytes(),
        complete_event_capture: state.event_capture_complete !== false && state.events.length < MAX_EVENTS,
        notes: 'Allowlisted application response fields are retained; provider raw envelopes and arbitrary extra keys are not recorded. proposal_ready marks frontend acceptance; parameters_applied marks confirmed form updates. Build success is server-reported, not physical validation.' } };
  }
  async function exportRecord() {
    exportsInProgress++;
    if (exportButton) exportButton.disabled = true;
    try {
      note('session_exported', { parameters: parameters() });
      const record = await snapshot(), json = JSON.stringify(record, null, 2);
      const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
      const anchor = document.createElement('a'); anchor.href = url;
      anchor.download = `HeliCraft-session-${state.started_at.slice(0, 10)}-${state.session_id.slice(-8)}.json`;
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); persist(); return record;
    } finally { exportsInProgress--; if (exportButton && !exportsInProgress) exportButton.disabled = false; }
  }
  function newSession(force = false) {
    if (inflight.size || tasks.size || exportsInProgress) {
      if (statusNode) statusNode.textContent = 'Wait for requests and coordinate recording to finish before starting a new record.';
      return false;
    }
    if (!force && !confirm('Export the current record before starting a new one. Your model and Jack conversation will stay unchanged. Start a new record?')) return false;
    generation++; clearTimeout(persistTimer); tasks.clear();
    state.artifacts.forEach(a => { try { sessionStorage.removeItem(ART_KEY + a.id); } catch (_) {} });
    state = fresh(); observed = parameters(); fileIds = new WeakMap(); inflight.clear(); counter = 0; storageWarning = '';
    note('session_started', { parameters: observed, recorder_version: VERSION });
    if (byId('monomerFile')?.files?.[0]) captureSelectedFile(); persist(); return true;
  }

  load();
  const panel = document.createElement('div'); panel.id = 'hc-session-record';
  panel.style.cssText = 'margin-top:14px;padding:12px;border:1px solid #334155;border-radius:8px;font-size:12px;line-height:1.5;';
  const label = document.createElement('strong'); label.textContent = 'Modeling session record';
  statusNode = document.createElement('p'); statusNode.id = 'hc-session-status'; statusNode.setAttribute('role', 'status');
  statusNode.style.cssText = 'margin:6px 0;';
  const info = document.createElement('p'); info.textContent = 'Includes dialogue, parameter changes and coordinates. Export before closing this tab.';
  info.style.cssText = 'margin:6px 0;color:#94a3b8;';
  function smallButton(id, text, handler) {
    const button = document.createElement('button'); button.type = 'button'; button.id = id; button.textContent = text;
    button.style.cssText = 'width:auto;margin:6px 6px 0 0;padding:7px 10px;border:1px solid #475569;border-radius:6px;background:#1e293b;color:#e2e8f0;cursor:pointer;font-size:12px;';
    button.addEventListener('click', handler); return button;
  }
  exportButton = smallButton('hc-session-export', 'Export session', () => { exportRecord().catch(() => warning('The record could not be downloaded. Keep this tab open and try again.')); });
  panel.append(label, statusNode, info, exportButton, smallButton('hc-session-new', 'New session record', () => newSession()));
  form.append(panel); updateStatus();
  form.addEventListener('input', recordFormChange);
  form.addEventListener('change', recordFormChange);
  form.addEventListener('reset', () => setTimeout(() => {
    const before = observed, after = parameters(); observed = after;
    state.current_monomer_id = captureFile(byId('monomerFile')?.files?.[0]);
    note('form_reset', { before, after, current_monomer_id: state.current_monomer_id });
  }, 0));
  byId('monomerFile')?.addEventListener('change', captureSelectedFile);
  if (byId('monomerFile')?.files?.[0]) captureSelectedFile();
  window.addEventListener('pagehide', persist);
  window.HeliCraftSessionRecord = Object.freeze({ version: VERSION, sessionId: () => state.session_id, note(type, data, ownerSessionId = null) {
    try {
      if (type === 'proposal_ready' && ownerSessionId && ownerSessionId !== state.session_id) return null;
      if (type === 'parameters_applied') observed = parameters();
      const safe = type === 'parameters_applied' && data?.proposal
        ? { ...data, proposal: allowChatResponse(data.proposal) } : data;
      return note(type, safe);
    } catch (_) {
      state.event_capture_complete = false;
      warning('One operation could not be recorded. Keep this tab open and export the available record.');
      return null;
    }
  }, snapshot, exportRecord, newSession });
})();
