import base64
import json
import os
import time
import urllib.parse
import urllib.request

import httpx
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

load_dotenv()

AGENT_ENDPOINT = os.getenv(
    "AGENT_ENDPOINT",
    "https://endpoint-a5e99572-5764-42b1-b2ff-e6beab2eca92.agentbase-runtime.aiplatform.vngcloud.vn/invocations",
)
IAM_TOKEN_URL = "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token"
CLIENT_ID = os.getenv("GREENNODE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GREENNODE_CLIENT_SECRET")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "KAN")
USER_ID = os.getenv("JIRA_EMAIL", "demo-user")

_token_cache: dict = {"token": None, "expires_at": 0.0}


def get_iam_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(
        IAM_TOKEN_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as f:
        token = json.load(f)["access_token"]
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 270
    return token


# __PROJECT_KEY__ is replaced server-side before serving
_CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jira Assistant</title>
  <script src="https://cdn.jsdelivr.net/npm/marked@9.1.6/marked.min.js"></script>
  <style>
    :root {
      --blue: #0052CC; --blue-h: #0065FF;
      --bg: #F4F5F7; --border: #DFE1E6;
      --muted: #6B778C; --dark: #172B4D; --red: #DE350B;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif;
      background: var(--bg); height: 100vh;
      display: flex; flex-direction: column; color: var(--dark);
    }

    /* ── Header ──────────────────────────────────────────── */
    .header {
      background: white; border-bottom: 1px solid var(--border);
      padding: 12px 20px; display: flex; align-items: center; gap: 12px; flex-shrink: 0;
    }
    .logo {
      width: 36px; height: 36px; background: var(--blue); border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      color: white; font-weight: 800; font-size: 18px; flex-shrink: 0;
    }
    .header-title { flex: 1; font-size: 16px; font-weight: 600; }

    /* ── Shared dropdown widget (project + session) ──────── */
    .dw { position: relative; }
    .dbtn {
      display: flex; align-items: center; gap: 6px;
      padding: 6px 10px 6px 12px;
      border: 1px solid var(--border); border-radius: 6px;
      background: white; cursor: pointer;
      font-size: 13px; color: var(--dark); font-family: inherit;
      max-width: 180px; white-space: nowrap;
    }
    .dbtn:hover { background: var(--bg); }
    .dbtn .dlabel { flex: 1; overflow: hidden; text-overflow: ellipsis; }
    .dmenu {
      display: none; position: absolute; right: 0; top: calc(100% + 4px);
      background: white; border: 1px solid var(--border);
      border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.12);
      min-width: 240px; z-index: 100; overflow: hidden;
    }
    .dmenu.open { display: block; }
    .dmenu-title {
      padding: 8px 14px 6px; font-size: 11px; font-weight: 600;
      color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em;
    }
    .ditem {
      display: flex; align-items: center; gap: 8px;
      padding: 9px 14px; cursor: pointer; font-size: 13px; color: var(--dark);
    }
    .ditem:hover { background: var(--bg); }
    .ditem.act { background: #E6EFFE; color: var(--blue); }
    .ditem .dname { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ditem .dmeta { font-size: 11px; color: var(--muted); flex-shrink: 0; }
    .ditem.act .dmeta { color: #4C9AFF; }
    .ditem .dact-btn {
      width: 20px; height: 20px; border-radius: 3px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; color: var(--muted); opacity: 0; cursor: pointer;
    }
    .ditem:hover .dact-btn { opacity: 1; }
    .dact-btn.edit:hover { background: #E6EFFE; color: var(--blue); }
    .dact-btn.del:hover  { background: #FFEBE6; color: var(--red); }
    .dmenu-add {
      padding: 9px 14px; font-size: 13px; color: var(--blue); cursor: pointer;
      border-top: 1px solid var(--border); display: flex; align-items: center; gap: 6px;
    }
    .dmenu-add:hover { background: #E6EFFE; }

    /* ── Quick actions ───────────────────────────────────── */
    .quick {
      background: white; border-bottom: 1px solid var(--border);
      padding: 8px 20px; display: flex; gap: 8px;
      overflow-x: auto; scrollbar-width: none; flex-shrink: 0;
    }
    .quick::-webkit-scrollbar { display: none; }
    .qbtn {
      white-space: nowrap; font-size: 12px; padding: 4px 12px; border-radius: 12px;
      border: 1px solid var(--blue); color: var(--blue);
      background: white; cursor: pointer; font-family: inherit;
    }
    .qbtn:hover { background: #E6EFFE; }

    /* ── Chat area ───────────────────────────────────────── */
    .chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
    .empty {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      color: var(--muted); text-align: center; gap: 8px; padding: 40px; min-height: 200px;
    }
    .empty .icon { font-size: 52px; }
    .empty h3 { font-size: 16px; color: var(--dark); margin-top: 4px; }
    .empty p { font-size: 13px; max-width: 320px; line-height: 1.5; }
    .msg { display: flex; gap: 10px; max-width: 88%; }
    .msg.user { align-self: flex-end; flex-direction: row-reverse; }
    .msg.bot  { align-self: flex-start; }
    .avatar {
      width: 32px; height: 32px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 700; flex-shrink: 0;
    }
    .msg.user .avatar { background: var(--blue); color: white; }
    .msg.bot  .avatar { background: var(--dark); color: white; }
    .bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; }
    .msg.user .bubble { background: var(--blue); color: white; border-bottom-right-radius: 4px; }
    .msg.bot  .bubble {
      background: white; color: var(--dark);
      border: 1px solid var(--border); border-bottom-left-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .bubble p { margin-bottom: 8px; } .bubble p:last-child { margin-bottom: 0; }
    .bubble ul, .bubble ol { margin: 6px 0 6px 20px; } .bubble li { margin-bottom: 3px; }
    .bubble code { background: rgba(0,0,0,0.07); padding: 2px 5px; border-radius: 4px; font-family: "SF Mono", Consolas, monospace; font-size: 12px; }
    .msg.user .bubble code { background: rgba(255,255,255,0.2); }
    .bubble pre { background: #1A2332; color: #E0E6ED; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
    .bubble pre code { background: none; padding: 0; font-size: 12px; }
    .bubble h1,.bubble h2,.bubble h3 { margin: 10px 0 4px; }
    .bubble table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }
    .bubble th,.bubble td { border: 1px solid var(--border); padding: 5px 9px; text-align: left; }
    .bubble th { background: var(--bg); font-weight: 600; }
    .bubble strong { font-weight: 600; }
    .dots { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); animation: bounce 1.2s infinite ease-in-out; }
    .dot:nth-child(2) { animation-delay: 0.15s; }
    .dot:nth-child(3) { animation-delay: 0.30s; }
    @keyframes bounce { 0%,80%,100%{transform:scale(0.7);opacity:0.4} 40%{transform:scale(1);opacity:1} }

    /* ── Input ───────────────────────────────────────────── */
    .input-wrap { background: white; border-top: 1px solid var(--border); padding: 14px 20px; flex-shrink: 0; }
    .input-row { display: flex; gap: 10px; align-items: flex-end; }
    textarea {
      flex: 1; border: 1px solid var(--border); border-radius: 8px;
      padding: 10px 14px; font-size: 14px; font-family: inherit;
      resize: none; outline: none; line-height: 1.5;
      max-height: 120px; overflow-y: auto; color: var(--dark);
    }
    textarea:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(0,82,204,0.12); }
    .send {
      background: var(--blue); color: white; border: none; border-radius: 8px;
      width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
      cursor: pointer; flex-shrink: 0; transition: background 0.15s;
    }
    .send:hover { background: var(--blue-h); }
    .send:disabled { background: var(--border); cursor: default; }

    /* ── Project modal ───────────────────────────────────── */
    .overlay {
      display: none; position: fixed; inset: 0;
      background: rgba(0,0,0,0.4); z-index: 200;
      align-items: center; justify-content: center;
    }
    .overlay.open { display: flex; }
    .modal {
      background: white; border-radius: 12px; padding: 24px;
      width: 460px; max-width: calc(100vw - 32px);
      box-shadow: 0 8px 32px rgba(0,0,0,0.16);
    }
    .modal-header {
      display: flex; align-items: center; margin-bottom: 20px;
    }
    .modal-header h2 { flex: 1; font-size: 16px; font-weight: 600; }
    .modal-close {
      width: 28px; height: 28px; border-radius: 6px;
      border: none; background: none; cursor: pointer;
      font-size: 16px; color: var(--muted); display: flex; align-items: center; justify-content: center;
    }
    .modal-close:hover { background: var(--bg); }
    .field { margin-bottom: 16px; }
    .field label { display: block; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
    .field input, .field textarea {
      width: 100%; border: 1px solid var(--border); border-radius: 6px;
      padding: 8px 12px; font-size: 14px; font-family: inherit; outline: none; color: var(--dark);
    }
    .field input:focus, .field textarea:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(0,82,204,0.12); }
    .field textarea { resize: vertical; min-height: 110px; line-height: 1.5; }
    .field .hint { font-size: 11px; color: var(--muted); margin-top: 4px; line-height: 1.4; }
    .modal-footer { display: flex; align-items: center; gap: 8px; margin-top: 20px; }
    .btn-del { padding: 8px 14px; border: 1px solid #FFBDAD; border-radius: 6px; background: white; color: var(--red); cursor: pointer; font-family: inherit; font-size: 13px; }
    .btn-del:hover { background: #FFEBE6; }
    .btn-cancel { padding: 8px 16px; border: 1px solid var(--border); border-radius: 6px; background: white; cursor: pointer; font-family: inherit; font-size: 14px; color: var(--dark); }
    .btn-cancel:hover { background: var(--bg); }
    .btn-save { padding: 8px 16px; border: none; border-radius: 6px; background: var(--blue); color: white; cursor: pointer; font-family: inherit; font-size: 14px; }
    .btn-save:hover { background: var(--blue-h); }
  </style>
</head>
<body>

<div class="header">
  <div class="logo">J</div>
  <div class="header-title">Jira Assistant</div>

  <!-- Project selector -->
  <div class="dw" id="pw">
    <button class="dbtn" id="pBtn" onclick="togglePMenu(event)">
      <span class="dlabel" id="pLabel">__PROJECT_KEY__</span>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="2,4 6,8 10,4"/></svg>
    </button>
    <div class="dmenu" id="pMenu">
      <div class="dmenu-title">Projects</div>
      <div id="pList"></div>
      <div class="dmenu-add" onclick="openProjectModal(null)">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Add project
      </div>
    </div>
  </div>

  <!-- Session selector -->
  <div class="dw" id="sw">
    <button class="dbtn" id="sBtn" onclick="toggleSMenu(event)">
      <span class="dlabel" id="sLabel">Session 1</span>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="2,4 6,8 10,4"/></svg>
    </button>
    <div class="dmenu" id="sMenu">
      <div class="dmenu-title">Sessions</div>
      <div id="sList"></div>
      <div class="dmenu-add" onclick="newSession()">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New session
      </div>
    </div>
  </div>
</div>

<div class="quick">
  <button class="qbtn" onclick="ask('How many open tasks are there?')">Open tasks</button>
  <button class="qbtn" onclick="ask('List all open tasks prioritized by urgency')">Priority list</button>
  <button class="qbtn" onclick="ask('Are there any overdue tasks?')">Overdue tasks</button>
  <button class="qbtn" onclick="ask('Which tasks are due before 2026-07-01?')">Due before July</button>
  <button class="qbtn" onclick="ask('Show workload summary per assignee')">Workload</button>
  <button class="qbtn" onclick="ask('Show current sprint tasks')">Sprint status</button>
  <button class="qbtn" onclick="ask('Estimate the ETA for the first task')">ETA estimate</button>
</div>

<div class="chat" id="chat"></div>

<div class="input-wrap">
  <div class="input-row">
    <textarea id="inp" rows="1" placeholder="Ask anything about your Jira project…"
      onkeydown="onKey(event)" oninput="resize(this)"></textarea>
    <button class="send" id="sendBtn" onclick="send()">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  </div>
</div>

<!-- Project add/edit modal -->
<div class="overlay" id="overlay" onclick="overlayClick(event)">
  <div class="modal">
    <div class="modal-header">
      <h2 id="modalTitle">Add Project</h2>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="field">
      <label>Project key *</label>
      <input id="fKey" type="text" placeholder="e.g. KAN" />
    </div>
    <div class="field">
      <label>Display name</label>
      <input id="fName" type="text" placeholder="e.g. Kanban Project" />
    </div>
    <div class="field">
      <label>Context / description</label>
      <textarea id="fDesc" placeholder="Help the assistant understand this project. Examples:&#10;- Team size: 3 developers&#10;- 1 story point ≈ 1 working day&#10;- Sprint length: 2 weeks&#10;- P1 = critical (fix same day), P2 = high, P3 = normal"></textarea>
      <div class="hint">This context is sent with every message so the assistant can give better ETA estimates and prioritisation advice.</div>
    </div>
    <div class="modal-footer">
      <button class="btn-del" id="fDelBtn" onclick="deleteEditingProject()" style="display:none">Delete project</button>
      <div style="flex:1"></div>
      <button class="btn-cancel" onclick="closeModal()">Cancel</button>
      <button class="btn-save" onclick="saveProject()">Save</button>
    </div>
  </div>
</div>

<script>
  const CHEVRON = '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="2,4 6,8 10,4"/></svg>';
  const PLUS    = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';

  // ── Project management ────────────────────────────────────────────────────

  let projects, activePkey;
  let _editingKey = null; // null = adding new, string = editing existing

  function _loadProjects() {
    const raw = localStorage.getItem('jira_projects');
    projects = raw ? JSON.parse(raw) : [];
    if (!projects.length) {
      projects = [{ key: '__PROJECT_KEY__', name: '__PROJECT_KEY__', description: '' }];
    }
    activePkey = localStorage.getItem('jira_active_pkey') || projects[0].key;
    if (!projects.find(p => p.key === activePkey)) activePkey = projects[0].key;
    _persistP();
  }

  function _persistP() {
    localStorage.setItem('jira_projects', JSON.stringify(projects));
    localStorage.setItem('jira_active_pkey', activePkey);
  }

  function getActiveProject() { return projects.find(p => p.key === activePkey); }

  function renderPMenu() {
    const list = document.getElementById('pList');
    list.innerHTML = '';
    for (const p of projects) {
      const label = p.name && p.name !== p.key ? p.key + ' · ' + p.name : p.key;
      const hasCtx = p.description ? ' ●' : '';
      const div = document.createElement('div');
      div.className = 'ditem' + (p.key === activePkey ? ' act' : '');
      div.innerHTML =
        '<span class="dname" title="' + (p.description || '') + '">' + label + '</span>' +
        '<span class="dmeta">' + hasCtx + '</span>' +
        '<span class="dact-btn edit" data-key="' + p.key + '" title="Edit">✎</span>';
      div.addEventListener('click', e => {
        const btn = e.target.closest('.dact-btn');
        if (btn) { e.stopPropagation(); openProjectModal(btn.dataset.key); }
        else { switchProject(p.key); }
      });
      list.appendChild(div);
    }
    const ap = getActiveProject();
    document.getElementById('pLabel').textContent =
      ap ? (ap.name && ap.name !== ap.key ? ap.key + ': ' + ap.name : ap.key) : '';
  }

  function togglePMenu(e) {
    e.stopPropagation();
    renderPMenu();
    document.getElementById('pMenu').classList.toggle('open');
    document.getElementById('sMenu').classList.remove('open');
  }

  function switchProject(key) {
    activePkey = key;
    _persistP();
    document.getElementById('pMenu').classList.remove('open');
    renderPMenu();
  }

  function openProjectModal(key) {
    document.getElementById('pMenu').classList.remove('open');
    _editingKey = key || null;
    const p = key ? projects.find(pr => pr.key === key) : null;
    document.getElementById('modalTitle').textContent = p ? 'Edit Project' : 'Add Project';
    document.getElementById('fKey').value = p ? p.key : '';
    document.getElementById('fKey').disabled = !!p;
    document.getElementById('fName').value = p ? (p.name !== p.key ? p.name : '') : '';
    document.getElementById('fDesc').value = p ? (p.description || '') : '';
    document.getElementById('fDelBtn').style.display = (p && projects.length > 1) ? '' : 'none';
    document.getElementById('overlay').classList.add('open');
    setTimeout(() => document.getElementById(p ? 'fName' : 'fKey').focus(), 50);
  }

  function closeModal() { document.getElementById('overlay').classList.remove('open'); }

  function overlayClick(e) {
    if (e.target === document.getElementById('overlay')) closeModal();
  }

  function saveProject() {
    const key = document.getElementById('fKey').value.trim().toUpperCase();
    if (!key) { document.getElementById('fKey').focus(); return; }
    const name = document.getElementById('fName').value.trim() || key;
    const desc = document.getElementById('fDesc').value.trim();

    if (_editingKey) {
      const p = projects.find(pr => pr.key === _editingKey);
      if (p) { p.name = name; p.description = desc; }
    } else {
      if (projects.find(p => p.key === key)) {
        document.getElementById('fKey').focus();
        document.getElementById('fKey').select();
        return;
      }
      projects.push({ key, name, description: desc });
      activePkey = key;
    }
    _persistP();
    closeModal();
    renderPMenu();
  }

  function deleteEditingProject() {
    if (!_editingKey || projects.length <= 1) return;
    projects = projects.filter(p => p.key !== _editingKey);
    if (activePkey === _editingKey) activePkey = projects[0].key;
    _persistP();
    closeModal();
    renderPMenu();
  }

  // ── Session management ────────────────────────────────────────────────────

  let sessions, activeSid;

  function _loadSessions() {
    const raw = localStorage.getItem('jira_sessions');
    sessions = raw ? JSON.parse(raw) : [];
    if (!sessions.length) {
      sessions = [{ id: crypto.randomUUID(), name: 'Session 1', created: Date.now(), messages: [] }];
    }
    activeSid = localStorage.getItem('jira_active_sid') || sessions[0].id;
    if (!sessions.find(s => s.id === activeSid)) activeSid = sessions[0].id;
    _persistS();
  }

  function _persistS() {
    localStorage.setItem('jira_sessions', JSON.stringify(sessions));
    localStorage.setItem('jira_active_sid', activeSid);
  }

  function getActiveSession() { return sessions.find(s => s.id === activeSid); }

  function renderSMenu() {
    const list = document.getElementById('sList');
    list.innerHTML = '';
    for (const s of sessions) {
      const turns = Math.floor(s.messages.length / 2);
      const div = document.createElement('div');
      div.className = 'ditem' + (s.id === activeSid ? ' act' : '');
      div.innerHTML =
        '<span class="dname">' + s.name + '</span>' +
        '<span class="dmeta">' + turns + ' turn' + (turns !== 1 ? 's' : '') + '</span>' +
        '<span class="dact-btn del" data-id="' + s.id + '" title="Delete">✕</span>';
      div.addEventListener('click', e => {
        const btn = e.target.closest('.dact-btn');
        if (btn) { e.stopPropagation(); _deleteSession(btn.dataset.id); }
        else { switchSession(s.id); }
      });
      list.appendChild(div);
    }
    const as = getActiveSession();
    document.getElementById('sLabel').textContent = as ? as.name : '';
  }

  function toggleSMenu(e) {
    e.stopPropagation();
    renderSMenu();
    document.getElementById('sMenu').classList.toggle('open');
    document.getElementById('pMenu').classList.remove('open');
  }

  function switchSession(id) {
    activeSid = id;
    _persistS();
    document.getElementById('sMenu').classList.remove('open');
    renderSMenu();
    renderChat();
  }

  function newSession() {
    const n = sessions.length + 1;
    const s = { id: crypto.randomUUID(), name: 'Session ' + n, created: Date.now(), messages: [] };
    sessions.push(s);
    activeSid = s.id;
    _persistS();
    document.getElementById('sMenu').classList.remove('open');
    renderSMenu();
    renderChat();
  }

  function _deleteSession(id) {
    if (sessions.length <= 1) return;
    sessions = sessions.filter(s => s.id !== id);
    if (activeSid === id) { activeSid = sessions[0].id; renderChat(); }
    _persistS();
    renderSMenu();
  }

  // ── Chat ──────────────────────────────────────────────────────────────────

  function renderChat() {
    const chat = document.getElementById('chat');
    chat.innerHTML = '';
    const s = getActiveSession();
    if (!s || !s.messages.length) {
      chat.innerHTML = '<div class="empty"><div class="icon">📋</div>' +
        '<h3>Ask me about your Jira project</h3>' +
        '<p>I can answer questions about tasks, deadlines, workload, ETA estimates, and more.</p></div>';
    } else {
      for (const m of s.messages) _appendBubble(m.role, m.content);
    }
  }

  function _appendBubble(role, content) {
    const chat = document.getElementById('chat');
    chat.querySelector('.empty')?.remove();
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    const av = document.createElement('div');
    av.className = 'avatar';
    av.textContent = role === 'user' ? 'U' : 'J';
    const b = document.createElement('div');
    b.className = 'bubble';
    if (role === 'bot') b.innerHTML = marked.parse(content);
    else b.textContent = content;
    d.append(av, b);
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
  }

  function _addMsgToSession(sid, role, content) {
    const s = sessions.find(x => x.id === sid);
    if (s) { s.messages.push({ role, content }); _persistS(); }
    if (sid === activeSid) _appendBubble(role, content);
    renderSMenu();
  }

  function showLoading() {
    const chat = document.getElementById('chat');
    chat.querySelector('.empty')?.remove();
    const d = document.createElement('div');
    d.id = 'loading'; d.className = 'msg bot';
    d.innerHTML = '<div class="avatar">J</div><div class="bubble"><div class="dots">' +
      '<div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>';
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
  }

  function hideLoading() { document.getElementById('loading')?.remove(); }

  // ── Input ─────────────────────────────────────────────────────────────────

  function resize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
  function onKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
  function ask(q) { document.getElementById('inp').value = q; send(); }

  async function send() {
    const inp = document.getElementById('inp');
    const btn = document.getElementById('sendBtn');
    const text = inp.value.trim();
    if (!text || btn.disabled) return;

    const reqSid = activeSid;  // capture before any await
    const proj   = getActiveProject();

    // Send project context only on the first message of each session.
    // Mark it now (before the fetch) so a rapid second send doesn't duplicate it.
    const reqSession = sessions.find(s => s.id === reqSid);
    const ctx = (!reqSession?.contextSent && proj?.description) ? proj.description : '';
    if (ctx && reqSession) { reqSession.contextSent = true; _persistS(); }

    inp.value = ''; inp.style.height = 'auto'; btn.disabled = true;

    _addMsgToSession(reqSid, 'user', text);
    showLoading();
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message:         text,
          session_id:      reqSid,
          project_key:     proj ? proj.key : '',
          project_context: ctx,
        }),
      });
      const data = await res.json();
      hideLoading();
      _addMsgToSession(reqSid, 'bot', data.error ? '⚠️ ' + data.error : data.message);
    } catch (e) {
      hideLoading();
      _addMsgToSession(reqSid, 'bot', '⚠️ Request failed: ' + e.message);
    } finally {
      btn.disabled = false;
      inp.focus();
    }
  }

  // Close dropdowns on outside click or Escape
  document.addEventListener('click', () => {
    document.getElementById('pMenu').classList.remove('open');
    document.getElementById('sMenu').classList.remove('open');
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.getElementById('pMenu').classList.remove('open');
      document.getElementById('sMenu').classList.remove('open');
      closeModal();
    }
  });

  // ── Boot ──────────────────────────────────────────────────────────────────
  _loadProjects();
  renderPMenu();
  _loadSessions();
  renderSMenu();
  renderChat();
</script>
</body>
</html>"""


async def health(request: Request):
    return JSONResponse({"status": "ok"})


async def index(request: Request):
    html = _CHAT_HTML.replace("__PROJECT_KEY__", PROJECT_KEY)
    return HTMLResponse(html)


async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id", "default-session")
    project_key = body.get("project_key", "")
    project_context = body.get("project_context", "")

    # Prepend project context so the LLM has it for ETA / prioritisation
    agent_message = message
    if project_context:
        agent_message = f"Project context: {project_context}\n\n{message}"

    agent_payload: dict = {"message": agent_message}
    if project_key:
        agent_payload["jira_config"] = {"project": project_key}

    try:
        token = get_iam_token()
    except Exception as e:
        return JSONResponse({"error": f"Auth failed: {e}"}, status_code=500)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                AGENT_ENDPOINT,
                json=agent_payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-GreenNode-AgentBase-Session-Id": session_id,
                    "X-GreenNode-AgentBase-User-Id": USER_ID,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            return JSONResponse({"error": data.get("error", "Unknown error")}, status_code=502)
        return JSONResponse({"message": data.get("message", "No response.")})
    except httpx.TimeoutException:
        return JSONResponse(
            {"error": "Request timed out. The agent is still thinking — try again."},
            status_code=504,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/health", health),
        Route("/chat", chat, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
