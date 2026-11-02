/* ---------- Backend contract (Flask) ----------
 POST /api/chat      {message, language, session_id|null} -> {text, intent, confidence, language, topic, chips[], session_id, title?}
 GET  /api/sessions  -> [{id, title}]
 GET  /api/sessions/<id> -> [{role:"user"|"bot", text, intent?, confidence?, language?}]
 If the backend is unreachable, a small demo reply is shown so the UI can be previewed. */
const API = "";
const $ = id => document.getElementById(id);
const root = document.documentElement;
let state = {lang:"auto", session:null, busy:false};
let sessions = [];

const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const LABEL = {python:"Python", java:"Java", c:"C"};
const INTENT = {explain:"Explanation", code:"Code request", debug:"Debugging", quiz:"Quiz", output:"Output prediction", compare:"Comparison",
  explain_concept:"Explanation", show_syntax:"Syntax", show_example:"Example", generate_code:"Code request", explain_code:"Code explanation",
  debug_code:"Debugging", predict_output:"Output prediction", compare_concepts:"Comparison", request_quiz:"Quiz", greeting:"Greeting",
  bot_capabilities:"Capabilities", follow_up:"Follow-up", clarification:"Clarification"};

function render(text, fb){
  const imgRe = /\[IMAGE:([^\|\]]+)\|([^\]]*)\]/g;
  const segments = [];
  let last = 0, imgMatch;
  while((imgMatch = imgRe.exec(text))){
    if(imgMatch.index > last) segments.push({type:"text", val:text.slice(last, imgMatch.index)});
    const src = "/static/" + imgMatch[1].trim();
    const alt = imgMatch[2].trim().replace(/"/g, "&quot;");
    segments.push({type:"img", val:'<img src="' + src + '" alt="' + alt + '" class="kb-image" onerror="this.style.display=\'none\'">'});
    last = imgRe.lastIndex;
  }
  if(last < text.length) segments.push({type:"text", val:text.slice(last)});
  if(segments.length === 0) segments.push({type:"text", val:text});

  return segments.map(seg => {
    if(seg.type === "img") return seg.val;
    const parts = []; let i = 0, m; const re = /```(\w*)\n?([\s\S]*?)```/g;
    const t = seg.val;
    while((m = re.exec(t))){ parts.push(para(t.slice(i, m.index))); parts.push(codeBox(m[1] || fb, m[2])); i = re.lastIndex; }
    parts.push(para(t.slice(i)));
    return parts.join("");
  }).join("");
}

function inl(s){
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?![*\w])/g, "$1<i>$2</i>")
    .replace(/`([^`]+)`/g, '<code class="in">$1</code>');
}

function para(t){
  t = t.trim(); if(!t) return "";
  return t.split(/\n{2,}/).map(block => {
    const out = []; let text = [], list = null, pre = [];
    const flushText = () => { if(text.length){ out.push("<p>" + text.map(inl).join("<br>") + "</p>"); text = []; } };
    const flushList = () => { if(list){ out.push("<" + list.t + ">" + list.items.map(x => "<li>" + inl(x) + "</li>").join("") + "</" + list.t + ">"); list = null; } };
    const flushPre  = () => {
      if(pre.length){
        const ind = Math.min(...pre.map(l => (l.match(/^[ \t]*/)[0]).length));
        out.push('<pre class="plainblock"><code>' + esc(pre.map(l => l.slice(ind)).join("\n")) + "</code></pre>"); pre = [];
      }
    };
    block.split("\n").forEach(line => {
      let m;
      if(/^( {4}|\t)\s*\S/.test(line)){ flushText(); flushList(); pre.push(line); return; }
      flushPre();
      if(/^\s*-{3,}\s*$/.test(line)){ flushText(); flushList(); out.push("<hr>"); }
      else if((m = line.match(/^(#{1,4})\s+(.*)$/))){ flushText(); flushList(); const n = Math.min(m[1].length + 1, 4); out.push("<h" + n + ' class="md-h">' + inl(m[2]) + "</h" + n + ">"); }
      else if((m = line.match(/^\s*[-*]\s+(.*)$/))){ flushText(); if(list && list.t !== "ul") flushList(); (list = list || {t:"ul", items:[]}).items.push(m[1]); }
      else if((m = line.match(/^\s*\d+\.\s+(.*)$/))){ flushText(); if(list && list.t !== "ol") flushList(); (list = list || {t:"ol", items:[]}).items.push(m[1]); }
      else { flushList(); text.push(line); }
    });
    flushPre(); flushText(); flushList();
    return out.join("");
  }).join("");
}
const ALIAS = {py:"python", python3:"python", h:"c"};
function highlight(code, key){ 
  try{ if(window.hljs) return hljs.highlight(code, {language:key, ignoreIllegals:true}).value; }catch(e){}
  return esc(code);
}
function codeBox(lang, code){
  const l = (lang||"").toLowerCase(), key = ALIAS[l] || l, known = !!LABEL[key];
  const name = LABEL[key] || (lang || "Code"), src = code.replace(/\n$/, "");
  return '<div class="codebox"><div class="codebar"><span>' + esc(name) + '</span><button type="button" data-copy>Copy</button></div><pre><code class="hljs' + (known ? " language-" + key : "") + '">' + (known ? highlight(src, key) : esc(src)) + "</code></pre></div>";
}

function scroll(){ const c = $("chat"); c.scrollTop = c.scrollHeight; }
function addUser(text){
  $("hello").hidden = true;
  const d = document.createElement("div"); d.className = "msg user";
  d.innerHTML = '<div class="bubble">' + esc(text) + "</div>";
  $("thread").appendChild(d); scroll();
}
function addBot(r){
  $("hello").hidden = true;
  const d = document.createElement("div"); d.className = "msg bot";

  // ── Out-of-scope card ────────────────────────────────────────────────────
  if(r.is_out_of_scope){
    const topics = Array.isArray(r.suggested_topics) ? r.suggested_topics
                 : Array.isArray(r.suggestions)      ? r.suggestions : [];
    const imgUrl  = r.oos_image_url || "/static/images/out_of_scope_guide.svg";
    const chipHtml = topics.map(t =>
      '<button class="sug-chip oos-chip" type="button">' + esc(t) + '</button>'
    ).join("");
    d.innerHTML =
      '<div class="oos-card">'
      + '<img src="' + esc(imgUrl) + '" alt="CodeTutor scope guide" class="oos-img">'
      + '<div class="oos-body">'
      +   '<div class="oos-msg">' + render(r.text || r.response || "", r.language) + '</div>'
      +   (chipHtml ? '<div class="sug-row oos-chips">' + chipHtml + '</div>' : '')
      + '</div>'
      + '</div>';
    $("thread").appendChild(d); scroll();
    return;
  }

  // ── Normal response ──────────────────────────────────────────────────────
  let tags = "";
  if(r.intent){
    tags = '<div class="tags"><span class="tag">Intent <b>' + esc(INTENT[r.intent] || r.intent) + "</b>"
      + (r.confidence != null ? " · " + Math.round(r.confidence * 100) + "%" : "") + "</span>"
      + (LABEL[r.language] ? '<span class="tag">Language <b>' + esc(LABEL[r.language] || r.language) + "</b></span>" : "") + "</div>";
  }
  const msgText = r.text || r.response || r.reply || "";
  d.innerHTML = '<div class="bubble">' + render(msgText, r.language) + "</div>" + tags;

  if(Array.isArray(r.suggestions) && r.suggestions.length){
    const chips = r.suggestions.map(s =>
      '<button class="sug-chip" type="button">' + esc(s) + '</button>'
    ).join("");
    d.innerHTML += '<div class="sug-row">' + chips + '</div>';
  }

  $("thread").appendChild(d); scroll();
  if(LABEL[r.language] && state.lang === "auto") root.dataset.lang = r.language;
}
function typing(on){
  const old = $("typing"); if(old) old.remove();
  if(!on) return;
  const d = document.createElement("div"); d.id = "typing"; d.className = "msg bot";
  d.innerHTML = '<div class="bubble"><div class="typing" aria-label="Tutor is typing"><span></span><span></span><span></span></div></div>';
  $("thread").appendChild(d); scroll();
}

async function send(text){
  text = text.trim(); if(!text || state.busy) return;
  state.busy = true; $("send").disabled = true;
  document.querySelectorAll(".sug-row").forEach(e => e.remove());
  addUser(text); $("input").value = ""; autosize(); typing(true);
  let r;
  try{
    const res = await fetch(API + "/api/chat", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({message:text, language:state.lang, session_id:state.session})});
    if(!res.ok) throw new Error(res.status);
    r = await res.json();
    if(r.session_id && !state.session){ state.session = r.session_id; sessions.unshift({id:r.session_id, title:r.title || text.slice(0,40)}); drawHist(); }
  }catch(e){
    r = demo(text);
  }
  typing(false); addBot(r);
  state.busy = false; $("send").disabled = !$("input").value.trim();
}

function demo(t){
  const l = /java\b/i.test(t) ? "java" : /\bc\b/i.test(t) ? "c" : "python";
  const code = {python:"for i in range(3):\n    print(i)", java:"for (int i = 0; i < 3; i++) {\n    System.out.println(i);\n}", c:"for (int i = 0; i < 3; i++) {\n    printf(\"%d\\n\", i);\n}"}[l];
  return {intent:"explain", confidence:0.93, language:l,
    text:"**Preview mode.** The Flask backend isn't connected yet, so this is a sample reply.\n\nA `for` loop repeats a block a set number of times:\n\n```" + l + "\n" + code + "\n```\n\nThis prints 0, 1 and 2."};
}

function setLang(l){
  state.lang = l;
  if(l === "auto") delete root.dataset.lang; else root.dataset.lang = l;
  document.querySelectorAll("#langs button").forEach(b => b.setAttribute("aria-pressed", b.dataset.lang === l));
  // Refresh quiz topic dropdown if the quiz panel is open
  if(location.hash === "#quiz") loadQuizTopics(l);
}
function drawHist(){
  const h = $("hist");
  if(!sessions.length){
    if(auth.user){
      h.innerHTML = "<h2>History</h2><p>No conversations yet. Start chatting and they will appear here.</p>";
    } else {
      h.innerHTML = "<h2>History</h2><p>Log in to save and view your conversation history.</p>";
    }
    return;
  }

  const pinned   = sessions.filter(s => s.pinned);
  const unpinned = sessions.filter(s => !s.pinned);

  let html = "<h2>History</h2>";
  if(pinned.length){
    html += '<div class="hist-section-label" style="font-size:11px;color:var(--muted);font-weight:600;padding:4px 10px 2px;letter-spacing:.03em">PINNED</div>';
    html += pinned.map(s => _histItem(s)).join("");
    if(unpinned.length){
      html += '<div class="hist-section-label" style="font-size:11px;color:var(--muted);font-weight:600;padding:8px 10px 2px;letter-spacing:.03em">RECENT</div>';
    }
  }
  html += unpinned.map(s => _histItem(s)).join("");
  h.innerHTML = html;
}

function _histItem(s){
  const active = s.id === state.session ? " active" : "";
  const pin    = s.pinned ? " pinned" : "";
  const dotsSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="2"></circle><circle cx="19" cy="12" r="2"></circle><circle cx="5" cy="12" r="2"></circle></svg>';
  
  return (
    '<div class="hist-item' + active + '" data-sid="' + esc(s.id) + '">' +
      '<button class="hist-title' + pin + '" data-id="' + esc(s.id) + '">' + esc(s.title) + '</button>' +
      '<button class="hist-dots" data-dots="' + esc(s.id) + '" aria-label="Options" title="Options">' + dotsSvg + '</button>' +
    '</div>'
  );
}

let _openMenu = null; 

function _closeMenu(){
  if(_openMenu){
    const item = $("hist").querySelector('.hist-item.menu-open');
    if(item) item.classList.remove("menu-open");
    _openMenu.remove();
    _openMenu = null;
  }
}

$("hist").addEventListener("click", e => {
  const titleBtn = e.target.closest(".hist-title");
  if(titleBtn){ _closeMenu(); openSession(titleBtn.dataset.id); return; }

  const dotsBtn = e.target.closest(".hist-dots");
  if(dotsBtn){
    e.stopPropagation();
    const sid = dotsBtn.dataset.dots;
    if(_openMenu && _openMenu.dataset.for === sid){ _closeMenu(); return; }
    _closeMenu();
    _showHistMenu(sid, dotsBtn);
    return;
  }
});

document.addEventListener("click", () => _closeMenu());

function _showHistMenu(sid, anchor){
  const s   = sessions.find(x => x.id === sid);
  const pin = s && s.pinned;

  const menu = document.createElement("div");
  menu.className   = "hist-menu";
  menu.dataset.for = sid;

  const renameIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
  const pinIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"></path></svg>';
  const deleteIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';

  menu.innerHTML =
    '<button data-action="rename"><span class="menu-icon">' + renameIcon + '</span> Rename</button>' +
    '<button data-action="pin"><span class="menu-icon">' + pinIcon + '</span> ' + (pin ? "Unpin" : "Pin") + '</button>' +
    '<hr class="menu-divider">' +
    '<button data-action="delete" class="danger"><span class="menu-icon">' + deleteIcon + '</span> Delete</button>';

  menu.addEventListener("click", async e => {
    const btn = e.target.closest("button[data-action]");
    if(!btn) return;
    e.stopPropagation();
    _closeMenu();
    const action = btn.dataset.action;
    if(action === "rename") _startRename(sid);
    if(action === "pin")    await _togglePin(sid, !pin);
    if(action === "delete") await _deleteSession(sid);
  });

  document.body.appendChild(menu);
  const rect = anchor.getBoundingClientRect();
  menu.style.top  = (rect.bottom + 4) + "px";
  menu.style.left = Math.max(4, rect.right - menu.offsetWidth - 4) + "px";

  _openMenu = menu;
  anchor.closest(".hist-item").classList.add("menu-open");
}

function _startRename(sid){
  const item      = $("hist").querySelector('[data-sid="' + CSS.escape(sid) + '"]');
  const titleBtn  = item && item.querySelector(".hist-title");
  if(!titleBtn) return;

  const currentTitle = titleBtn.textContent.replace(/^📌 /, "").trim();
  const input = document.createElement("input");
  input.type       = "text";
  input.className  = "hist-rename";
  input.value      = currentTitle;
  input.maxLength  = 60;

  titleBtn.replaceWith(input);
  input.focus();
  input.select();

  async function commit(){
    const newTitle = input.value.trim() || currentTitle;
    input.replaceWith(titleBtn);
    titleBtn.textContent = newTitle;
    const s = sessions.find(x => x.id === sid);
    if(s) s.title = newTitle;
    await fetch(API + "/api/sessions/" + encodeURIComponent(sid), {
      method: "PATCH",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({title: newTitle}),
    });
  }

  input.addEventListener("blur", commit);
  input.addEventListener("keydown", e => {
    if(e.key === "Enter"){ e.preventDefault(); input.blur(); }
    if(e.key === "Escape"){ input.value = currentTitle; input.blur(); }
  });
}

async function _togglePin(sid, pinned){
  await fetch(API + "/api/sessions/" + encodeURIComponent(sid), {
    method: "PATCH",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({pinned}),
  });
  await loadSessions();
}

async function _deleteSession(sid){
  const dlg = $("confirmDlg");
  dlg.querySelector(".dlg-title").textContent = "Delete conversation";
  dlg.querySelector(".dlg-msg").textContent   = "This conversation will be permanently deleted. This cannot be undone.";
  dlg.querySelector("#confirmOk").textContent = "Delete";
  dlg.showModal();

  await new Promise(resolve => {
    function onOk()     { cleanup(); resolve(true);  }
    function onCancel() { cleanup(); resolve(false); }
    function onBD(e){ if(e.target === dlg){ cleanup(); resolve(false); } }
    function cleanup(){
      $("confirmOk").removeEventListener("click", onOk);
      $("confirmCancel").removeEventListener("click", onCancel);
      dlg.removeEventListener("click", onBD);
      dlg.close();
      dlg.querySelector(".dlg-title").textContent = "Sign out";
      dlg.querySelector(".dlg-msg").textContent   = "Are you sure you want to sign out?";
      dlg.querySelector("#confirmOk").textContent = "Sign out";
    }
    $("confirmOk").addEventListener("click", onOk);
    $("confirmCancel").addEventListener("click", onCancel);
    dlg.addEventListener("click", onBD);
  }).then(async confirmed => {
    if(!confirmed) return;
    await fetch(API + "/api/sessions/" + encodeURIComponent(sid), {method:"DELETE"});
    if(state.session === sid){ state.session = null; $("thread").innerHTML = ""; $("hello").hidden = false; }
    await loadSessions();
  });
}
async function loadSessions(){
  try{ const r = await fetch(API + "/api/sessions"); sessions = r.ok ? (await r.json()).filter(s => s.kind !== "quiz") : []; }catch(e){ sessions = []; }
  drawHist();
}
async function loadMe(){
  try{
    const r = await fetch(API + "/api/me", {credentials:"same-origin"}); if(!r.ok) throw 0;
    const d = await r.json(); auth.available = true;
    auth.user = d && d.authenticated !== false && userName(d) ? d : null;
  }catch(e){ auth = {available:false, user:null}; }
  drawAccount();

  if(auth.user){
    await loadSessions();
  } else {
    state.session = null;
    sessions = [];
    drawHist();
  }
}
async function openSession(id){
  try{
    const r = await fetch(API + "/api/sessions/" + encodeURIComponent(id)); if(!r.ok) throw 0;
    const msgs = await r.json();
    goChat(); $("thread").innerHTML = ""; state.session = id;
    msgs.forEach(m => m.role === "user" ? addUser(m.text) : addBot(m));
    drawHist(); if(isMobile()) closeSidebar();
  }catch(e){ addBot({text:"Sorry, I could not load that conversation."}); }
}
function newChat(){
  state.session = null; $("thread").innerHTML = ""; $("hello").hidden = false;
  setLang(prefs.lang); goChat(); drawHist(); if(isMobile()) closeSidebar(); $("input").focus();
}
function autosize(){ const t = $("input"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 160) + "px"; }

$("input").addEventListener("input", () => { autosize(); $("send").disabled = !$("input").value.trim() || state.busy; });
$("input").addEventListener("keydown", e => { if(e.key === "Enter" && !e.shiftKey){ e.preventDefault(); send($("input").value); } });
$("send").addEventListener("click", () => send($("input").value));
$("langs").addEventListener("click", e => { const b = e.target.closest("button"); if(b) setLang(b.dataset.lang); });
$("starters").addEventListener("click", e => { const b = e.target.closest("button"); if(b) b.hasAttribute("data-quiz") ? openQuiz(b.dataset.quiz) : send(b.dataset.q); });
$("actions").addEventListener("click", e => { const b = e.target.closest("button"); if(!b) return; if(b.hasAttribute("data-quiz")){ openQuiz(); return; } const t = $("input"); t.value = b.dataset.p; t.focus(); autosize(); $("send").disabled = false; });

$("thread").addEventListener("click", e => {
  const b = e.target.closest("[data-copy]"); if(!b) return;
  const code = b.closest(".codebox").querySelector("code").textContent;
  navigator.clipboard.writeText(code).then(() => { b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1500); });
});

$("thread").addEventListener("click", e => {
  const chip = e.target.closest(".sug-chip"); if(!chip) return;
  send(chip.textContent.trim());
});
$("newChat").addEventListener("click", newChat);

// ── Sidebar toggle logic ──────────────────────────────────────────────────────
const isMobile = () => window.innerWidth <= 820;

function openSidebar(){
  if(isMobile()){
    $("side").classList.add("open");
  } else {
    $("app") || document.querySelector(".app").classList.remove("sidebar-closed");
    document.querySelector(".app").classList.remove("sidebar-closed");
  }
  $("sideToggle").setAttribute("aria-label", "Close sidebar");
  $("menu").setAttribute("aria-label", "Close sidebar");
}

function closeSidebar(){
  if(isMobile()){
    $("side").classList.remove("open");
  } else {
    document.querySelector(".app").classList.add("sidebar-closed");
  }
  $("sideToggle").setAttribute("aria-label", "Open sidebar");
  $("menu").setAttribute("aria-label", "Open sidebar");
}

function toggleSidebar(){
  const app = document.querySelector(".app");
  if(isMobile()){
    $("side").classList.contains("open") ? closeSidebar() : openSidebar();
  } else {
    app.classList.contains("sidebar-closed") ? openSidebar() : closeSidebar();
  }
}

// Hamburger in header (mobile only)
$("menu").addEventListener("click", toggleSidebar);
// Collapse button inside sidebar (all screen sizes)
$("sideToggle").addEventListener("click", toggleSidebar);
// Logo button in header — shown when sidebar is closed (all screen sizes)
$("headerLogoBtn").addEventListener("click", toggleSidebar);
// Profile pill in header — opens account dialog
$("profilePill").addEventListener("click", () => $("dlg").showModal());

// Close sidebar when tapping the dark backdrop on mobile
document.addEventListener("click", e => {
  const side = $("side");
  if(isMobile() && side.classList.contains("open") &&
     !side.contains(e.target) &&
     e.target !== $("menu") && !$("menu").contains(e.target)){
    closeSidebar();
  }
});

const PREF_KEY = "codetutor.prefs";
let prefs = {tags:true, wrap:false, lang:"auto"};
let auth = {available:false, user:null};
const QZ = {session:null, items:[], i:0, score:0, log:null, busy:false, lang:"auto", demo:false};
const userName = u => (u && (u.display_name || u.name || u.username || (u.email || "").split("@")[0])) || "";

function applyPrefs(){ root.classList.toggle("notags", !prefs.tags); root.classList.toggle("wrapcode", prefs.wrap); }
function syncPrefs(){ $("setTags").checked = prefs.tags; $("setWrap").checked = prefs.wrap; $("setLang").value = prefs.lang; }
function savePrefs(){ try{ localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); }catch(e){} applyPrefs(); }
$("setTags").addEventListener("change", e => { prefs.tags = e.target.checked; savePrefs(); });
$("setWrap").addEventListener("change", e => { prefs.wrap = e.target.checked; savePrefs(); });
$("setLang").addEventListener("change", e => { prefs.lang = e.target.value; savePrefs(); });

function drawAccount(){
  const u = auth.user, n = userName(u);
  const avatarEl = $("avatar");

  avatarEl.textContent = "";
  avatarEl.innerHTML   = "";

  if(u && u.picture){
    const img = document.createElement("img");
    img.src             = u.picture;
    img.alt             = n;
    img.referrerPolicy  = "no-referrer";
    img.style.cssText   = "width:100%;height:100%;border-radius:50%;object-fit:cover;display:block";
    img.onerror         = () => { avatarEl.textContent = n ? n[0].toUpperCase() : "?"; };
    avatarEl.appendChild(img);
  } else {
    avatarEl.textContent = n ? n[0].toUpperCase() : "?";
  }

  $("whoName").textContent = u ? n : "Guest";
  $("whoSub").textContent  = u ? "Signed in" : "Not signed in";
  $("greet").textContent   = u ? "Hello, " + n + "!" : "Hello there!";

  // ── Update header profile pill ────────────────────────────────────────────
  const profileAvatarEl = $("profileAvatar");
  profileAvatarEl.textContent = "";
  profileAvatarEl.innerHTML   = "";
  if(u && u.picture){
    const pImg = document.createElement("img");
    pImg.src            = u.picture;
    pImg.alt            = n;
    pImg.referrerPolicy = "no-referrer";
    pImg.onerror        = () => { profileAvatarEl.textContent = n ? n[0].toUpperCase() : "?"; };
    profileAvatarEl.appendChild(pImg);
  } else {
    profileAvatarEl.textContent = n ? n[0].toUpperCase() : "?";
  }
  $("profileName").textContent = u ? n.split(" ")[0] : "Guest";

  const rows = [["Status", u ? "Signed in" : "Not signed in"]];
  if(u){
    if(u.display_name || u.name) rows.push(["Display name", u.display_name || u.name]);
    if(u.username) rows.push(["Username", u.username]);
    if(u.email)    rows.push(["Email", u.email]);
  }
  $("acctRows").innerHTML = rows.map(r =>
    '<div class="row"><span>' + esc(r[0]) + "</span><span>" + esc(String(r[1])) + "</span></div>"
  ).join("");

  document.querySelectorAll("[data-auth]").forEach(b => {
    b.textContent = u ? "Sign out" : "Sign in";
    b.disabled    = !auth.available;
    b.title       = auth.available ? "" : "Login is not set up on the server yet";
  });
  $("acctMsg").textContent = auth.available
    ? ""
    : "Login is not set up on the server yet, so you are browsing as a guest.";
}
async function authAction(){
  if(!auth.available) return;
  if(!auth.user){ location.href = "/login"; return; }
  const dlg = $("confirmDlg");
  dlg.showModal();
  await new Promise(resolve => {
    function onOk()     { cleanup(); resolve(true);  }
    function onCancel() { cleanup(); resolve(false); }
    function onBackdrop(e){ if(e.target === dlg){ cleanup(); resolve(false); } }
    function cleanup(){
      $("confirmOk").removeEventListener("click", onOk);
      $("confirmCancel").removeEventListener("click", onCancel);
      dlg.removeEventListener("click", onBackdrop);
      dlg.close();
    }
    $("confirmOk").addEventListener("click", onOk);
    $("confirmCancel").addEventListener("click", onCancel);
    dlg.addEventListener("click", onBackdrop);
  }).then(async confirmed => {
    if(!confirmed) return;
    try{ const r = await fetch(API + "/api/logout", {method:"POST", credentials:"same-origin"}); if(!r.ok) throw 0; }
    catch(e){ $("acctMsg").textContent = "Could not sign out. Please try again."; return; }
    auth.user = null; sessions = []; state.session = null;
    $("thread").innerHTML = ""; $("hello").hidden = false;
    drawHist(); drawAccount();
    if($("dlg").open) $("dlg").close();
    await loadMe();
  });
}
document.querySelectorAll("[data-auth]").forEach(b => b.addEventListener("click", authAction));
$("who").addEventListener("click", () => { syncPrefs(); drawAccount(); $("dlg").showModal(); });
$("dlgClose").addEventListener("click", () => $("dlg").close());
$("dlg").addEventListener("click", e => { if(e.target === $("dlg")) $("dlg").close(); });

function goChat(){ if(location.hash === "#quiz") location.hash = "chat"; }

// ── Topic dropdown population ────────────────────────────────────────────────
// Pretty-prints a topic slug: "python_list" → "Python List"
function _topicLabel(slug){
  return slug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

let _quizTopicsCache = null;
async function loadQuizTopics(lang){
  if(!_quizTopicsCache){
    try{
      const r = await fetch(API + "/api/quiz/topics");
      _quizTopicsCache = r.ok ? await r.json() : {all:[], python:[], java:[], c:[]};
    }catch(e){
      _quizTopicsCache = {all:[], python:[], java:[], c:[]};
    }
  }
  const sel     = $("qtopic");
  const current = sel.value;   // preserve selection if possible
  sel.innerHTML = '<option value="">— All topics —</option>';

  const isAll = !lang || lang === "auto";

  if(isAll){
    // Grouped by language: C first, then Java, then Python
    const groups = [
      {label:"C",      key:"c"},
      {label:"Java",   key:"java"},
      {label:"Python", key:"python"},
    ];
    groups.forEach(({label, key}) => {
      const topics = (_quizTopicsCache[key] || []);
      if(!topics.length) return;
      const grp = document.createElement("optgroup");
      grp.label = label;
      topics.forEach(t => {
        const opt = document.createElement("option");
        opt.value       = t;
        opt.textContent = _topicLabel(t);
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    });
  } else {
    // Single language — flat list, no group header needed
    const topics = _quizTopicsCache[lang] || [];
    topics.forEach(t => {
      const opt = document.createElement("option");
      opt.value       = t;
      opt.textContent = _topicLabel(t);
      sel.appendChild(opt);
    });
  }

  // Re-select if the topic still exists in the new list
  if(current){
    const found = [...sel.options].find(o => o.value === current);
    if(found) sel.value = current;
  }
}

function openQuiz(topic){
  loadQuizTopics(state.lang).then(() => {
    // topic may be a display string like "Python lists" — try to match a slug
    if(topic){
      const slug = topic.toLowerCase().replace(/\s+/g, "_");
      const sel  = $("qtopic");
      // try exact slug match first, then partial
      const exact = [...sel.options].find(o => o.value === slug);
      if(exact) sel.value = exact.value;
      else {
        const partial = [...sel.options].find(o => o.value.includes(slug) || slug.includes(o.value));
        if(partial) sel.value = partial.value;
      }
    }
  });
  location.hash = "quiz";
}

function showView(){
  const q = location.hash === "#quiz";
  $("chat").hidden = q; $("composer").hidden = q; $("quiz").hidden = !q;
  if(isMobile()) closeSidebar();
  if(q){ loadQuizTopics(state.lang); $("qtopic").focus(); } else scroll();
}
function demoQuiz(){
  return {demo:true, language:"python", quiz:[
    {prompt:"What does this print?\n\n```python\nprint(len([1, 2, 3]))\n```", options:["2","3","[1, 2, 3]","Error"], answer:1, explanation:"`len()` counts the items in the list, and there are three."},
    {prompt:"Which keyword starts a function definition in Python?", options:["func","function","def","define"], answer:2, explanation:"Python uses `def` to define a function."}
  ]};
}
async function quizCall(message, allowDemo, quizTopic){
  try{
    const body = {message, language:state.lang, session_id:QZ.session, context:"quiz"};
    if(quizTopic) body.quiz_topic = quizTopic;
    const res = await fetch(API + "/api/chat", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(body)});
    if(!res.ok) throw 0; const r = await res.json(); if(r.session_id) QZ.session = r.session_id; return r;
  }catch(e){ return allowDemo ? demoQuiz() : {text:"Could not reach the server. Please try again."}; }
}
async function startQuiz(){
  if(QZ.busy) return;
  const topicSlug  = $("qtopic").value.trim();           // slug from dropdown, or ""
  // Build a human-readable message for the server (used as fallback for topic resolution)
  const topicLabel = topicSlug ? _topicLabel(topicSlug) : "the basics";
  const msg = "Quiz me on " + (state.lang !== "auto" ? LABEL[state.lang] + " " : "") + topicLabel;
  Object.assign(QZ, {session:null, items:[], i:0, score:0, log:null, busy:true});
  $("qbody").innerHTML = '<div class="typing" aria-label="Loading quiz"><span></span><span></span><span></span></div>';
  const r = await quizCall(msg, true, topicSlug || null); QZ.busy = false;
  QZ.lang = r.language || state.lang; QZ.demo = !!r.demo;
  if(Array.isArray(r.quiz) && r.quiz.length){ QZ.items = r.quiz; drawQ(); }
  else { QZ.log = [{role:"bot", text:r.text || r.reply || "", language:r.language}]; drawLog(); }
}

// ── Fill-in-the-blank exercises ───────────────────────────────────────────────

// FX holds exercise session state (parallel to QZ for quizzes)
const FX = {items:[], i:0, score:0, busy:false, type:"fill_in_blank"};

async function startExercise(){
  if(FX.busy) return;
  const lang = state.lang !== "auto" ? state.lang : null;  // respect active language tab
  Object.assign(FX, {items:[], i:0, score:0, busy:true, type:"mixed"});
  $("qbody").innerHTML = '<div class="typing" aria-label="Loading exercise"><span></span><span></span><span></span></div>';
  try{
    const res = await fetch(API + "/api/quiz/exercises", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({language: lang || ""}),
    });
    FX.busy = false;
    if(!res.ok){ $("qbody").innerHTML = '<div class="qcard"><p>Could not load exercises. Please try again.</p></div>'; return; }
    const data = await res.json();
    if(!Array.isArray(data.exercises) || !data.exercises.length){
      $("qbody").innerHTML = '<div class="qcard"><p>No exercises found for that selection.</p></div>'; return;
    }
    FX.items = data.exercises;
    drawFitb();
  }catch(e){
    FX.busy = false;
    $("qbody").innerHTML = '<div class="qcard"><p>Could not reach the server. Please try again.</p></div>';
  }
}

function drawFitb(){
  const it = FX.items[FX.i], b = $("qbody");
  if(!it){
    // Final score screen
    b.innerHTML = '<div class="qcard"><h2>Exercise complete 🎉</h2>'
      + '<p>You scored <b>' + FX.score + ' / ' + FX.items.length + '</b>.</p>'
      + '<button class="send" id="fitb-again" type="button">New exercise</button></div>';
    return;
  }
  const lang     = it.language || "text";
  const codeHtml = renderFitbCode(it.code, lang);

  let answerHtml;
  if(it.type === "fill_in_blank_mc"){
    // Multiple-choice options
    answerHtml = (it.options || []).map((o, k) =>
      '<button type="button" class="qopt fitb-opt" data-k="' + k + '" data-val="' + esc(String(o)) + '">'
      + esc(String(o)) + '</button>'
    ).join("");
  } else {
    // Free-text input
    answerHtml = '<div class="fitb-input-row">'
      + '<input id="fitb-ans" class="fitb-input" type="text" placeholder="Type your answer…" autocomplete="off" spellcheck="false" aria-label="Your answer">'
      + '<button class="send" id="fitb-submit" type="button">Submit</button>'
      + '</div>';
  }

  b.innerHTML = '<div class="qcard">'
    + '<div class="tags"><span class="tag">Exercise <b>' + (FX.i + 1) + ' of ' + FX.items.length + '</b></span>'
    + '</div>'
    + '<p class="qprompt">' + esc(it.question) + '</p>'
    + codeHtml
    + answerHtml
    + '<div id="fitb-fb"></div>'
    + '</div>';

  // Auto-focus the input for free-text
  const inp = $("fitb-ans");
  if(inp) inp.focus();
}

function renderFitbCode(code, lang){
  // Render code with ____ highlighted as a blank slot using existing codeBox()
  // Replace ____ with a visible placeholder, highlight, then restore styling
  const placeholder = "▓▓▓▓";
  const withHolder  = code.replace(/____/g, placeholder);
  const boxHtml     = codeBox(lang, withHolder);
  // After highlight.js runs, swap the escaped placeholder back to a styled blank
  return boxHtml.replace(
    new RegExp(esc(placeholder).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"),
    '<span class="fitb-blank">____</span>'
  );
}

function answerFitb(userAnswer){
  const it  = FX.items[FX.i];
  const ok  = it.answer.trim().toLowerCase() === userAnswer.trim().toLowerCase();
  if(ok) FX.score++;

  // Disable inputs
  document.querySelectorAll(".fitb-opt").forEach(b => { b.disabled = true; if(b.dataset.val === it.answer) b.classList.add("ok"); else if(b.dataset.val === userAnswer) b.classList.add("bad"); });
  const inp = $("fitb-ans");
  if(inp){ inp.disabled = true; inp.classList.add(ok ? "fitb-ok" : "fitb-bad"); }
  const subBtn = $("fitb-submit");
  if(subBtn) subBtn.disabled = true;

  const verdict = ok ? "✅ Correct!" : "❌ Not quite. The answer is <code class=\"in\">" + esc(it.answer) + "</code>";
  $("fitb-fb").innerHTML = '<div class="bubble qexp"><p><b>' + verdict + "</b></p>"
    + (it.explanation ? "<p>" + esc(it.explanation) + "</p>" : "")
    + '</div>'
    + '<button class="send" id="fitb-next" type="button">'
    + (FX.i + 1 < FX.items.length ? "Next exercise" : "See score")
    + "</button>";
}

// ── Quiz mode toggle ──────────────────────────────────────────────────────────
function setQuizMode(mode){
  // mode: "quiz" | "fitb"
  document.querySelectorAll(".qmode-tab").forEach(b => {
    const active = b.dataset.mode === mode;
    b.classList.toggle("active", active);
    b.setAttribute("aria-selected", active);
  });
  const isQuiz = mode === "quiz";
  $("panel-quiz").hidden = !isQuiz;
  $("panel-fitb").hidden =  isQuiz;
  $("qbody").innerHTML = "";
}
function drawQ(){
  const it = QZ.items[QZ.i], b = $("qbody");
  if(!it){
    b.innerHTML = '<div class="qcard"><h2>Quiz complete 🎉</h2><p>You scored <b>' + QZ.score + " / " + QZ.items.length + '</b>.</p><button class="send" id="qagain" type="button">New quiz</button></div>';
    return;
  }
  // Running score removed — shown only at the end
  b.innerHTML = '<div class="qcard">'
    + '<div class="tags"><span class="tag">Question <b>' + (QZ.i + 1) + " of " + QZ.items.length + "</b></span>"
    + (QZ.demo ? '<span class="tag">Preview</span>' : '')
    + '</div>'
    + '<div class="qprompt">' + render(it.prompt, QZ.lang) + "</div>"
    + it.options.map((o, k) => '<button type="button" class="qopt" data-k="' + k + '">' + esc(String(o)) + "</button>").join("")
    + '<div id="qfb"></div></div>';
}
function answerQ(k){
  const it = QZ.items[QZ.i], ans = typeof it.answer === "number" ? it.answer : it.options.indexOf(it.answer);
  document.querySelectorAll(".qopt").forEach(x => { x.disabled = true; const n = +x.dataset.k; if(n === ans) x.classList.add("ok"); else if(n === k) x.classList.add("bad"); });
  if(k === ans) QZ.score++;
  $("qfb").innerHTML = '<div class="bubble qexp"><p><b>' + (k === ans ? "Correct." : "Not quite.") + "</b></p>" + (it.explanation ? render(it.explanation, QZ.lang) : "") + '</div><button class="send" id="qnext" type="button">' + (QZ.i + 1 < QZ.items.length ? "Next question" : "See score") + "</button>";
}
function drawLog(){
  $("qbody").innerHTML = '<div class="thread">' + QZ.log.map(m => m.role === "user"
    ? '<div class="msg user"><div class="bubble">' + esc(m.text) + "</div></div>"
    : '<div class="msg bot"><div class="bubble">' + render(m.text, m.language || QZ.lang) + "</div></div>").join("")
    + '</div><div class="box qans"><input id="qans" placeholder="Type your answer…" aria-label="Your answer"><button class="send" id="qsendans" type="button">Answer</button></div>';
  $("qans").focus();
}
async function sendAns(){
  const t = $("qans").value.trim(); if(!t || QZ.busy) return;
  QZ.busy = true; QZ.log.push({role:"user", text:t}); drawLog();
  const r = await quizCall(t, false);
  QZ.log.push({role:"bot", text:r.text || r.reply || "", language:r.language}); QZ.busy = false; drawLog();
}
$("qbody").addEventListener("click", e => {
  const o = e.target.closest(".qopt:not(.fitb-opt)");
  if(o && !o.disabled) return answerQ(+o.dataset.k);
  if(e.target.closest("#qnext")){ QZ.i++; return drawQ(); }
  if(e.target.closest("#qagain")){ $("qbody").innerHTML = ""; return $("qtopic").focus(); }
  if(e.target.closest("#qsendans")) return sendAns();
  const c = e.target.closest("[data-copy]");
  if(c) navigator.clipboard.writeText(c.closest(".codebox").querySelector("code").textContent).then(() => { c.textContent = "Copied"; setTimeout(() => c.textContent = "Copy", 1500); });
});
$("qbody").addEventListener("keydown", e => { if(e.key === "Enter" && e.target.id === "qans"){ e.preventDefault(); sendAns(); } });
$("qstart").addEventListener("click", startQuiz);
$("qback").addEventListener("click", () => { location.hash = "chat"; });

// Exercise start button
$("fitb-start").addEventListener("click", startExercise);

// Exercise body event delegation (next, again, MC option click, free-text submit + Enter)
$("qbody").addEventListener("click", e => {
  // FITB next / again
  if(e.target.closest("#fitb-next")){ FX.i++; return drawFitb(); }
  if(e.target.closest("#fitb-again")){ Object.assign(FX,{items:[],i:0,score:0}); $("qbody").innerHTML=""; return; }
  // FITB submit (free-text)
  if(e.target.closest("#fitb-submit")){
    const inp = $("fitb-ans"); if(inp && inp.value.trim()) answerFitb(inp.value.trim()); return;
  }
  // FITB MC option
  const opt = e.target.closest(".fitb-opt");
  if(opt && !opt.disabled) return answerFitb(opt.dataset.val);
});
$("qbody").addEventListener("keydown", e => {
  if(e.key === "Enter" && e.target.id === "fitb-ans"){ e.preventDefault(); if(e.target.value.trim()) answerFitb(e.target.value.trim()); }
});

// Mode tabs
document.querySelectorAll(".qmode-tab").forEach(btn =>
  btn.addEventListener("click", () => setQuizMode(btn.dataset.mode))
);
window.addEventListener("hashchange", showView);

try{ Object.assign(prefs, JSON.parse(localStorage.getItem(PREF_KEY) || "{}")); }catch(e){}
applyPrefs(); syncPrefs(); if(prefs.lang !== "auto") setLang(prefs.lang);
showView(); loadMe();