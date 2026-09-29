const SQ_PAGE = document.body.dataset.page || 'index';

/* =========================================================
   API CONFIG
   Point this at your FastAPI backend. Override by setting
   window.SQ_API_BASE before this script runs, if needed.
   ========================================================= */
const API_BASE = window.SQ_API_BASE || 'https://sq-git.onrender.com';
const REGISTRATION_FORM_URL = window.SQ_REGISTRATION_URL || 'https://forms.gle/wtEbCgdcDPB3EC8S9';

/* =========================================================
   SUBJECT / LEVEL META (static, matches backend's VALID_SUBJECTS)
   ========================================================= */
const SUBJECTS = [
  {key:'chemistry',  name:'Chemistry',   icon:'🧪', c:'--c-chemistry',   cd:'--c-chemistry-d'},
  {key:'physics',    name:'Physics',     icon:'⚛️', c:'--c-physics',     cd:'--c-physics-d'},
  {key:'botany',     name:'Botany',      icon:'🌿', c:'--c-botany',      cd:'--c-botany-d'},
  {key:'zoology',    name:'Zoology',     icon:'🐾', c:'--c-zoology',     cd:'--c-zoology-d'},
  {key:'commerce',   name:'Commerce',    icon:'💼', c:'--c-commerce',    cd:'--c-commerce-d'},
  {key:'accounts',   name:'Accounts',    icon:'📒', c:'--c-accounts',    cd:'--c-accounts-d'},
  {key:'mathematics',name:'Mathematics', icon:'📐', c:'--c-mathematics', cd:'--c-mathematics-d'},
  {key:'nutrition',  name:'Nutrition',   icon:'🍎', c:'--c-nutrition',   cd:'--c-nutrition-d'},
];
const LEVEL_META = {
  1:{label:'Foundation', diff:'Easy'},
  2:{label:'Building',   diff:'Easy-Med'},
  3:{label:'Application',diff:'Medium'},
  4:{label:'Challenge',  diff:'Hard'},
  5:{label:'Mastery',    diff:'Expert'},
};
// Levels beyond 5 have no named tier — fall back to a plain "Level N" label,
// cycling through the same 5 difficulty tags so the UI still shows *some*
// sense of escalating difficulty without needing new admin-side config.
function levelMeta(lvl){
  if(LEVEL_META[lvl]) return LEVEL_META[lvl];
  const cycled = LEVEL_META[((lvl - 1) % 5) + 1];
  return {label:`Level ${lvl}`, diff:cycled.diff};
}
function currentThemeIconInfo(){
  const key = (STATE.user && STATE.user.theme) || 'classic';
  if(key === 'classic') return null;
  const t = DYNAMIC_THEMES.find(t=>t.key===key);
  if(!t || !t.icon_count) return null;
  return {key, count: t.icon_count};
}
const AVATARS = ['🦊','🐼','🦉','🐯','🐸','🐨','🦁','🐵','🐢','🦄'];

/* =========================================================
   STATE
   ========================================================= */
let STATE = {
  token: localStorage.getItem('sq_token') || null,
  user: null,          // {userid, name, role, avatar, grade, board}
  progress: {},        // subjectKey -> {unlocked_level, xp, stars:{level:n}}
  isAdmin: false,
  selectedAvatar: AVATARS[0],
  quiz: null,           // active timed quiz session
  currentSubject: null,
  currentToc: null,
  adminSubject: 'chemistry',
  pendingResetToken: null,
  firstAttemptLedger: {}, // questionKey -> {correct, points, subject, level, answeredAt}
};

function escapeHtml(s){
  const div = document.createElement('div');
  div.textContent = s == null ? '' : s;
  return div.innerHTML;
}
function subjMeta(key){
  const hardcoded = SUBJECTS.find(s=>s.key===key);
  if(hardcoded) return hardcoded;
  const dynamic = (STATE.subjectMeta || {})[key];
  return {
    key, name: dynamic ? dynamic.name : key, icon: dynamic ? (dynamic.icon || '📘') : '📘',
    c: '--c-generic', cd: '--c-generic-d',
  };
}
function goto(id){
  const pageFor = {
    'screen-admin-login':'admin.html',
    'screen-admin':'admin.html',
    'screen-performance':'performance.html',
    'screen-toc':'toc.html',
  };
  if(id === 'screen-quiz' && SQ_PAGE !== 'index'){
    try{ localStorage.setItem('sq_quiz_redirect', JSON.stringify({...STATE.quiz, timerId:null})); }catch(e){}
    window.location.href='index.html';
    return;
  }
  const target = document.getElementById(id);
  if(!target && pageFor[id]){
    if(id === 'screen-admin-login' || id === 'screen-admin'){
      window.location.href = pageFor[id];
      return;
    }
    if(id === 'screen-performance'){
      window.location.href = pageFor[id];
      return;
    }
    if(id === 'screen-toc'){
      window.location.href = pageFor[id];
      return;
    }
  }
  if(!target){
    // Cross-page navigation back to the main student shell.
    if(SQ_PAGE !== 'index'){
      if(id === 'screen-home' || id === 'screen-auth' || id === 'screen-map' || id === 'screen-quiz' || id === 'screen-force-reset'){
        window.location.href = 'index.html';
        return;
      }
    }
    console.warn('Screen not found:', id);
    return;
  }
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  target.classList.add('active');
  document.body.classList.toggle('admin-active', id === 'screen-admin');
  document.body.classList.toggle('map-active', id === 'screen-map');
  document.body.classList.toggle('performance-active', id === 'screen-performance');
  window.scrollTo(0,0);
}
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 1800);
}

/* =========================================================
   API HELPER
   ========================================================= */
async function api(path, {method='GET', body=null, isForm=false, auth=true} = {}){
  const headers = {};
  if(!isForm) headers['Content-Type'] = 'application/json';
  if(auth && STATE.token) headers['Authorization'] = `Bearer ${STATE.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });

  let data = null;
  try{ data = await res.json(); }catch(e){ /* no body */ }

  if(!res.ok){
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    if(res.status === 401){ handleAuthExpired(); }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}
function handleAuthExpired(){
  STATE.token = null; STATE.user = null; STATE.progress = {};
  localStorage.removeItem('sq_token');
  localStorage.removeItem('sq_user');
  localStorage.removeItem('sq_progress');
}

/* =========================================================
   AUTH
   ========================================================= */
function renderAvatarPicker(){
  const row = document.getElementById('admin-avatar-row');
  if(!row) return;
  row.innerHTML = AVATARS.map(a=>`<button type="button" class="avatar-opt ${a===STATE.selectedAvatar?'sel':''}" onclick="pickAvatar('${a}')">${a}</button>`).join('');
}
function pickAvatar(a){ STATE.selectedAvatar = a; renderAvatarPicker(); }

async function loginUser(){
  const userid = document.getElementById('login-userid').value.trim();
  const password = document.getElementById('login-password').value;
  if(!userid || !password){ toast('Enter your user ID and password'); return; }
  try{
    const data = await api('/api/auth/login', {method:'POST', body:{userid, password}, auth:false});
    if(data.role !== 'student'){
      toast('This is an admin account — use "Admin / teacher login" instead');
      return;
    }
    await onLoginSuccess(data);
    document.getElementById('login-password').value = '';
    if(data.must_reset_password){
      goto('screen-force-reset');
      return;
    }
    await loadMyProgress();
    enterHome();
  }catch(err){
    toast(err.message || 'Incorrect user ID or password');
  }
}
async function submitForceReset(){
  const p1 = document.getElementById('force-reset-password').value;
  const p2 = document.getElementById('force-reset-password-confirm').value;
  if(!p1 || p1.length < 6){ toast('Password must be at least 6 characters'); return; }
  if(p1 !== p2){ toast('Passwords do not match'); return; }
  try{
    await api('/api/auth/set-password', {method:'POST', body:{new_password: p1}});
    STATE.user.must_reset_password = false;
    document.getElementById('force-reset-password').value = '';
    document.getElementById('force-reset-password-confirm').value = '';
    toast('Password set — welcome!');
    await loadMyProgress();
    enterHome();
  }catch(err){
    toast(err.message || 'Could not set password');
  }
}
async function loadAllSubjectMeta(){
  // Admin needs every subject across every grade, not just one grade's
  // worth — unlike loadMyProgress()'s student-scoped version of this.
  try{
    const allSubjects = await api('/api/subjects', {auth:false});
    STATE.subjectMeta = {};
    STATE.allGradeSubjectKeys = allSubjects.map(s => s.key);
    allSubjects.forEach(s => { STATE.subjectMeta[s.key] = {name:s.name, icon:s.icon}; });
  }catch(err){
    STATE.subjectMeta = {};
    STATE.allGradeSubjectKeys = [];
  }
}
async function adminLogin(){
  const userid = document.getElementById('admin-userid').value.trim();
  const password = document.getElementById('admin-pw').value;
  if(!userid || !password){ toast('Enter the admin user ID and password'); return; }
  try{
    const data = await api('/api/auth/login', {method:'POST', body:{userid, password}, auth:false});
    if(data.role !== 'admin'){
      toast('That account is not an admin account');
      return;
    }
    await onLoginSuccess(data);
    STATE.isAdmin = true;
    document.getElementById('admin-pw').value = '';
    populateSubjectSelect('qf-subject');
    document.getElementById('admin-section').innerHTML = '<p class="empty-note">Choose at least one filter above, then hit Search.</p>';
    renderAvatarPicker();
    await renderAdminStudentList();
    await renderAdminThemeList();
    await renderAdminSubjectCaps();
    await renderAdminGradeSubjectList();
    goto('screen-admin');
  }catch(err){
    toast(err.message || 'Incorrect admin user ID or password');
  }
}
async function onLoginSuccess(data){
  STATE.token = data.access_token;
  STATE.user = {userid:data.userid, name:data.name, role:data.role, avatar:data.avatar, grade:data.grade, board:data.board, theme:data.theme || 'classic', account_tier:data.account_tier || 'silver'};
  localStorage.setItem('sq_token', STATE.token);
  localStorage.setItem('sq_user', JSON.stringify(STATE.user));
  await loadThemes();
  applyTheme(STATE.user.theme);
}
async function openGuestFormModal(){
  const gradeSelect = document.getElementById('guest-grade');
  gradeSelect.innerHTML = '<option>Loading…</option>';
  try{
    const grades = await api('/api/grades', {auth:false});
    if(grades.length === 0){
      gradeSelect.innerHTML = '<option value="">No grades configured yet</option>';
      toast('No grades are set up yet — ask your admin to configure grade/subject mappings');
    } else {
      grades.sort((a,b) => parseInt(a) - parseInt(b));
      gradeSelect.innerHTML = grades.map(g => `<option value="${g}">Grade ${g}</option>`).join('');
    }
  }catch(err){
    gradeSelect.innerHTML = '<option value="">Could not load grades</option>';
  }
  await onGuestGradeChange();
  document.getElementById('guest-form-modal').classList.add('active');
}
async function onGuestGradeChange(){
  const grade = document.getElementById('guest-grade').value;
  const subjectSelect = document.getElementById('guest-subject');
  if(!grade){ subjectSelect.innerHTML = ''; return; }
  subjectSelect.innerHTML = '<option>Loading…</option>';
  try{
    const subjects = await api(`/api/subjects?grade=${encodeURIComponent(grade)}`, {auth:false});
    subjectSelect.innerHTML = subjects.map(s => `<option value="${s.key}">${s.icon||''} ${s.name}</option>`).join('');
  }catch(err){
    subjectSelect.innerHTML = '<option value="">Could not load subjects</option>';
  }
}
function closeGuestFormModal(){
  document.getElementById('guest-form-modal').classList.remove('active');
}
async function startGuestSession(){
  const grade = document.getElementById('guest-grade').value;
  const subject = document.getElementById('guest-subject').value;
  if(!grade || !subject){ toast('Please pick a grade and subject'); return; }
  try{
    const data = await api('/api/auth/guest', {method:'POST', auth:false, body:{grade, subject}});
    await onLoginSuccess(data);
    closeGuestFormModal();
    await loadMyProgress();
    enterHome();
    toast(`Welcome! Your guest ID is ${data.userid} — save it to mention when you register.`);
  }catch(err){
    toast(err.message || 'Could not start a demo session — please try again.');
  }
}
function openRegistrationCta(){
  document.getElementById('registration-guest-id').textContent = STATE.user.userid;
  document.getElementById('registration-modal').classList.add('active');
}
function closeRegistrationCta(){
  document.getElementById('registration-modal').classList.remove('active');
}
function goToRegistrationForm(){
  window.open(REGISTRATION_FORM_URL, '_blank');
  closeRegistrationCta();
}

/* ---------- theme picker ---------- */
// Dynamic themes fetched from the backend (admin-uploaded) plus the
// permanent built-in Classic look, which needs no image at all.
let DYNAMIC_THEMES = []; // [{key, name, icon_count}, ...] — refreshed each time the picker opens
const LEGACY_GRADIENT_KEYS = ['garden','racetrack','space','ocean']; // built-in fallback look, used until/unless a real image is uploaded for that key

async function loadThemes(){
  try{ DYNAMIC_THEMES = await api('/api/themes', {auth:false}); }
  catch(err){ DYNAMIC_THEMES = []; }
}
function applyTheme(theme){
  document.body.classList.remove(...LEGACY_GRADIENT_KEYS.map(k=>`theme-${k}`));
  document.body.style.removeProperty('--theme-outer-bg');
  document.body.style.removeProperty('--theme-home-bg');
  if(!theme || theme === 'classic') return;

  // Fallback gradient look for the 4 original keys, shown until a real
  // image exists for them (or forever, for any brand-new custom key that
  // doesn't match one of these — in which case there's just no fallback and
  // the background stays blank until an image is uploaded for it).
  if(LEGACY_GRADIENT_KEYS.includes(theme)) document.body.classList.add(`theme-${theme}`);

  // A real uploaded image (a row that actually exists in DYNAMIC_THEMES,
  // fetched fresh via loadThemes() before this runs) wins over the gradient
  // fallback. Themes with no upload yet — e.g. a legacy key nobody has
  // uploaded art for — correctly keep showing just the gradient instead of
  // pointing at an image URL that would 404.
  const hasRealUpload = DYNAMIC_THEMES.some(t => t.key === theme);
  if(!hasRealUpload) return;

  const bgUrl = `${API_BASE}/api/themes/${encodeURIComponent(theme)}/background`;
  document.body.style.setProperty('--theme-outer-bg', `url('${bgUrl}') center/cover no-repeat`);
  document.body.style.setProperty('--theme-home-bg', `url('${bgUrl}') center/cover no-repeat`);
}
async function openThemeModal(){
  await loadThemes();
  const grid = document.getElementById('theme-grid');
  const current = (STATE.user && STATE.user.theme) || 'classic';
  const options = [{key:'classic', name:'Classic'}, ...DYNAMIC_THEMES];
  grid.innerHTML = options.map(t=>{
    const thumb = t.key === 'classic'
      ? `<span class="t-icon">⭐</span>`
      : `<img class="t-thumb" src="${API_BASE}/api/themes/${encodeURIComponent(t.key)}/background" alt="">`;
    return `<button class="theme-opt ${t.key===current?'selected':''}" onclick="selectTheme('${t.key}')">
      ${thumb}
      <span class="t-name">${t.name}</span>
    </button>`;
  }).join('');
  document.getElementById('theme-modal').classList.add('active');
}
function closeThemeModal(){ document.getElementById('theme-modal').classList.remove('active'); }
async function selectTheme(theme){
  applyTheme(theme); // instant feedback, even before the save round-trip finishes
  if(STATE.user) STATE.user.theme = theme;
  try{
    await api('/api/auth/set-theme', {method:'POST', body:{theme}});
    closeThemeModal();
  }catch(err){
    toast(err.message || 'Could not save theme');
  }
}

function logout(){
  STATE.token = null; STATE.user = null; STATE.progress = {};
  localStorage.removeItem('sq_token');
  localStorage.removeItem('sq_user');
  localStorage.removeItem('sq_progress');
  applyTheme('classic');
  goto('screen-auth');
}
function adminLogout(){
  STATE.token = null; STATE.user = null; STATE.isAdmin = false;
  localStorage.removeItem('sq_token');
  localStorage.removeItem('sq_user');
  localStorage.removeItem('sq_progress');
  window.location.href='index.html';
}

/* ---------- forgot / reset password ---------- */
function openForgotModal(){
  document.getElementById('forgot-step-request').classList.remove('hidden');
  document.getElementById('forgot-step-reset').classList.add('hidden');
  document.getElementById('forgot-userid').value = '';
  document.getElementById('forgot-modal').classList.add('active');
}
function closeForgotModal(){ document.getElementById('forgot-modal').classList.remove('active'); }

async function requestPasswordReset(){
  const userid = document.getElementById('forgot-userid').value.trim();
  if(!userid){ toast('Enter your user ID'); return; }
  try{
    const data = await api('/api/auth/forgot-password', {method:'POST', body:{userid}, auth:false});
    toast(data.message || 'If that account exists, a reset link was sent');
    if(data.reset_token){
      // Dev/demo mode (no SMTP configured on the backend): the API returned
      // the token directly so the flow can be tested without an email server.
      STATE.pendingResetToken = data.reset_token;
      document.getElementById('forgot-step-request').classList.add('hidden');
      document.getElementById('forgot-step-reset').classList.remove('hidden');
      document.getElementById('forgot-dev-note').textContent =
        'Dev mode: no email server is configured, so you can reset your password right here.';
    } else {
      closeForgotModal();
    }
  }catch(err){
    toast(err.message || 'Something went wrong');
  }
}
async function submitPasswordReset(){
  const newPassword = document.getElementById('forgot-new-password').value;
  if(!newPassword || newPassword.length < 6){ toast('Password must be at least 6 characters'); return; }
  try{
    await api('/api/auth/reset-password', {method:'POST', body:{token: STATE.pendingResetToken, new_password: newPassword}, auth:false});
    toast('Password updated — you can log in now');
    closeForgotModal();
  }catch(err){
    toast(err.message || 'Could not reset password');
  }
}
/* =========================================================
   FIRST-ATTEMPT QUESTION POINTS
   A question can earn points only the first time this student answers it.
   Retakes/re-attends never add question points again.
   ========================================================= */
function firstAttemptStorageKey(){
  const uid = String(STATE.user?.userid || STATE.user?.email || 'guest');
  return `sq_first_attempts_${uid}`;
}
function questionProgressKey(q){
  if(q == null) return '';
  const id = q.question_id ?? q.id ?? q.questionId;
  if(id != null && String(id).trim()) return `id:${String(id).trim()}`;
  const raw = [q.subject||STATE.quiz?.subject||'', q.level||STATE.quiz?.level||'', q.chapter||'', q.topic||'', q.question||''].map(v=>String(v).trim().toLowerCase()).join('|');
  return `fp:${raw}`;
}
function loadFirstAttemptLedger(){
  try{
    const raw=localStorage.getItem(firstAttemptStorageKey());
    STATE.firstAttemptLedger = raw ? (JSON.parse(raw)||{}) : {};
  }catch(e){ STATE.firstAttemptLedger={}; }
}
function saveFirstAttemptLedger(){
  try{ localStorage.setItem(firstAttemptStorageKey(), JSON.stringify(STATE.firstAttemptLedger||{})); }catch(e){}
}
function registerQuestionFirstAttempt(q, wasCorrect){
  const key=questionProgressKey(q);
  if(!key) return {isFirstAttempt:true, points:wasCorrect?10:0};
  if(STATE.firstAttemptLedger[key]) return {isFirstAttempt:false, points:0};
  const entry={correct:!!wasCorrect, points:wasCorrect?10:0, subject:q.subject||STATE.quiz?.subject||'', level:Number(q.level||STATE.quiz?.level||0), answeredAt:new Date().toISOString()};
  STATE.firstAttemptLedger[key]=entry;
  saveFirstAttemptLedger();
  return {isFirstAttempt:true, points:entry.points};
}
function firstAttemptStatsForQuiz(quiz){
  const subject=quiz?.subject||'';
  const level=Number(quiz?.level||0);
  const entries=Object.values(STATE.firstAttemptLedger||{}).filter(e=>String(e.subject||subject)===String(subject) && Number(e.level||level)===level);
  return {
    total:entries.length,
    correct:entries.filter(e=>e.correct).length,
    points:entries.reduce((n,e)=>n+Number(e.points||0),0),
  };
}

/* =========================================================
   HOME / PROGRESS
   ========================================================= */
async function loadMyProgress(){
  const rows = await api('/api/progress');
  let savedLocal = {};
  try{ savedLocal = JSON.parse(localStorage.getItem('sq_progress') || '{}') || {}; }catch(e){}
  const map = {};
  rows.forEach(r => {
    const local = savedLocal[r.subject] || {};
    const serverStars = r.stars || {};
    const localStars = local.stars || {};
    const mergedStars = {...localStars, ...serverStars};
    Object.keys(serverStars).forEach(k => {
      mergedStars[k] = Math.max(Number(localStars[k] || 0), Number(serverStars[k] || 0));
    });
    const isPremium = String(STATE.user?.account_tier || '').toLowerCase() === 'premium';
    const serverMax = Number(r.max_level || 0);
    // Premium accounts can use every configured level. Keep the normal
    // five-level roadmap as the minimum, while preserving a larger server
    // configured maximum when one exists.
    const effectiveMax = isPremium ? Math.max(serverMax, 5) : serverMax;
    map[r.subject] = {
      ...local,
      ...r,
      unlocked_level: isPremium ? Math.max(Number(r.unlocked_level || 1), effectiveMax) : Number(r.unlocked_level || local.unlocked_level || 1),
      max_level: effectiveMax,
      xp: Math.max(Number(local.xp || 0), Number(r.xp || 0)),
      stars: mergedStars,
      enrolled:r.enrolled,
    };
  });
  STATE.progress = map;
  try{ localStorage.setItem('sq_progress', JSON.stringify(STATE.progress)); }catch(e){}

  // Full grade-appropriate subject list (name/icon), so newly admin-created
  // subjects (e.g. "Science" for grade 8) render correctly even though
  // they're not in the hardcoded SUBJECTS array. Falls back to every subject
  // if the account has no grade set.
  try{
    const gradeParam = STATE.user.grade ? `?grade=${encodeURIComponent(STATE.user.grade)}` : '';
    const allSubjects = await api(`/api/subjects${gradeParam}`, {auth:false});
    STATE.subjectMeta = {};
    STATE.allGradeSubjectKeys = allSubjects.map(s => s.key);
    allSubjects.forEach(s => { STATE.subjectMeta[s.key] = {name:s.name, icon:s.icon}; });
  }catch(err){
    STATE.subjectMeta = {};
    STATE.allGradeSubjectKeys = [];
  }

  // Needed so renderPath() knows the current theme's icon_count before the
  // student ever opens the theme picker (e.g. resuming a session that
  // already had a theme picked).
  await loadThemes();
}
function totalXp(){
  return Object.values(STATE.progress).reduce((sum,s)=>sum+(s.xp||0), 0);
}
function updateMathTocHomeButton(){
  const btn = document.getElementById('math-toc-home-btn');
  if(!btn) return;
  const board = String(STATE.user?.board || '').toLowerCase();
  const grade = String(STATE.user?.grade || '');
  const hasMath = !!(STATE.progress && STATE.progress.mathematics);
  btn.style.display = (board === 'cbse' && grade === '11' && hasMath) ? 'block' : 'none';
}

function enterHome(){
  const u = STATE.user;
  document.getElementById('home-avatar').textContent = u.avatar || '🦊';
  document.getElementById('home-name').textContent = u.name;
  document.getElementById('home-sub').textContent = `Grade ${u.grade || '—'} · ${u.board || '—'}`;
  document.getElementById('home-xp').textContent = totalXp();
  const banner = document.getElementById('guest-banner');
  if(u.account_tier === 'guest'){
    banner.style.display = 'block';
    document.getElementById('guest-banner-id').textContent = u.userid;
  } else {
    banner.style.display = 'none';
  }
  renderSubjectGrid();
  updateMathTocHomeButton();
  goto('screen-home');
}
function renderSubjectGrid(){
  const grid = document.getElementById('subject-grid');
  const isGuest = STATE.user.account_tier === 'guest';
  const allKeys = (STATE.allGradeSubjectKeys && STATE.allGradeSubjectKeys.length)
    ? STATE.allGradeSubjectKeys
    : Object.keys(STATE.progress);

  // Guests see every subject for their grade — locked ones prompt
  // registration instead of disappearing, since that's a conversion nudge.
  // Silver/Premium students only ever see subjects their admin enrolled
  // them in — hidden, not locked, since that's a deliberate admin choice,
  // not a sales funnel.
  const visibleKeys = isGuest ? allKeys : allKeys.filter(k => STATE.progress[k] && STATE.progress[k].enrolled);

  if(visibleKeys.length === 0){
    grid.innerHTML = '<p class="empty-note">You\'re not enrolled in any subjects yet — ask your admin/teacher to add some.</p>';
    return;
  }

  grid.innerHTML = visibleKeys.map(key=>{
    const s = subjMeta(key);
    const sp = STATE.progress[key];
    const isLocked = isGuest && (!sp || !sp.enrolled);
    if(isLocked){
      return `<button class="subj-card" style="background:linear-gradient(155deg, #8a8a92, #5f5f68);opacity:0.75;" onclick="openRegistrationCta()">
        <div class="icon">🔒</div>
        <div>
          <div class="name">${s.name}</div>
          <div class="prog">Register to unlock</div>
        </div>
      </button>`;
    }
    const totalLevels = sp.max_level || 5;
    const doneLevels = Object.keys(sp.stars).length;
    const pct = Math.round((doneLevels/totalLevels)*100);
    return `<button class="subj-card" style="background:linear-gradient(155deg, var(${s.c}), var(${s.cd}));" onclick="openSubject('${key}')">
      <div class="icon">${s.icon}</div>
      <div>
        <div class="name">${s.name}</div>
        <div class="prog">Level ${sp.unlocked_level} of ${totalLevels}</div>
        <div class="bar"><i style="width:${pct}%"></i></div>
      </div>
    </button>`;
  }).join('');
}



/* =========================================================
   MOUNTAIN PERFORMANCE DASHBOARD
   Uses the existing /api/progress/performance endpoint.
   ========================================================= */

function performanceZone(score){
  if(score === null || score === undefined){
    return {key:'not-enrolled',name:'Not Enrolled',message:'No evaluation available yet.'};
  }
  score = Number(score);
  if(score >= 90) return {key:'outstanding',name:'Outstanding',message:'You are at the summit. Keep challenging yourself!'};
  if(score >= 80) return {key:'excellent',name:'Excellent',message:'You are climbing strongly toward the summit.'};
  if(score >= 70) return {key:'good',name:'Good',message:'A solid climb. Keep building your skills.'};
  if(score >= 60) return {key:'developing',name:'Developing',message:'Your progress is growing. Keep practising regularly.'};
  return {key:'needs',name:'Needs Improvement',message:'This is your practice zone. Keep climbing!'};
}

function mountainPosition(score){
  score = Number(score);
  if(!Number.isFinite(score)) return 95;

  const points = [
    {score:0,pos:95},{score:40,pos:80},{score:60,pos:62},
    {score:70,pos:43},{score:80,pos:25},{score:90,pos:8},{score:100,pos:2}
  ];

  for(let i=0;i<points.length-1;i++){
    const a=points[i], b=points[i+1];
    if(score>=a.score && score<=b.score){
      const ratio=(score-a.score)/(b.score-a.score);
      return a.pos+(b.pos-a.pos)*ratio;
    }
  }
  return score<0 ? 95 : 2;
}

function openPerformance(){
  if(!STATE.user || STATE.user.account_tier === 'guest'){
    toast('Performance dashboard is available after registration.');
    return;
  }
  if(SQ_PAGE !== 'performance'){ window.location.href='performance.html'; return; }
  goto('screen-performance');
  loadPerformanceDashboard();
}

async function loadPerformanceDashboard(){

  const container=document.getElementById('perf-subjects');
  if(!container) return;

  container.innerHTML='<div class="perf-subject-card" style="padding:25px;text-align:center;">Loading your learning journey...</div>';

  try{

    const d=await api('/api/progress/performance');
    const overall=Number(d.overall_score||0);
    const zone=performanceZone(overall);

    const scoreEl=document.getElementById('mountain-overall');
    const zoneEl=document.getElementById('mountain-zone');
    const messageEl=document.getElementById('mountain-message');
    const climber=document.getElementById('student-climber');

    if(scoreEl) scoreEl.textContent=`${overall}%`;
    if(zoneEl) zoneEl.textContent=zone.name;
    if(messageEl) messageEl.textContent=zone.message;

    if(climber){
      climber.style.top=`${mountainPosition(overall)}%`;
      climber.textContent=STATE.user?.avatar || '🧗';
    }

    const subtitle=document.getElementById('perf-subtitle');
    if(subtitle){
      subtitle.textContent=`Grade ${d.student?.grade || STATE.user?.grade || '—'} · ${d.student?.board || STATE.user?.board || '—'}`;
    }

    document.getElementById('perf-subject-count').textContent=d.enrolled_subjects||0;
    document.getElementById('perf-mastered').textContent=d.mastered_subjects||0;
    document.getElementById('perf-practice').textContent=d.needs_practice||0;

    renderMountainSubjects(d.subjects||[]);
    renderMountainTable(d.performance_table||[]);

  }catch(err){

    console.error('Performance dashboard error:',err);

    container.innerHTML=`
      <div class="perf-subject-card" style="padding:25px;text-align:center;">
        <b>Could not load performance</b>
        <div style="margin-top:7px;font-size:11px;color:var(--muted);">
          ${escapeHtml(err.message||'Please try again.')}
        </div>
      </div>
    `;
  }
}

function renderMountainSubjects(subjects){

  const container=document.getElementById('perf-subjects');

  if(!subjects.length){
    container.innerHTML=`
      <div class="perf-subject-card" style="grid-column:1/-1;padding:25px;text-align:center;">
        <div style="font-size:38px;">🏔️</div>
        <b>Your mountain journey starts here</b>
        <div style="margin-top:7px;font-size:11px;color:var(--muted);">
          Complete a level to see your subject performance.
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML=subjects.map(s=>{

    const enrolled=!!s.enrolled;
    const score=(s.score===null || s.score===undefined) ? null : Number(s.score);
    const zone=performanceZone(score);
    const safeScore=score===null ? 0 : Math.max(0,Math.min(100,score));
    const meta=subjMeta(s.key);
    const colorVariable=meta?.c||'--c-generic';
    const chapters=s.chapters||[];

    let details='';

    if(enrolled){

      if(chapters.length){

        details=chapters.map(c=>`
          <div class="perf-detail-row">
            <span>${escapeHtml(c.name||'Chapter')}</span>
            <b>${Number(c.score||0)}%</b>
          </div>
        `).join('');

      }else{

        details=`
          <div style="font-size:11px;color:var(--muted);padding:5px 0;">
            Complete levels to see chapter performance.
          </div>
        `;
      }

    }else{

      details=`
        <div style="font-size:11px;color:var(--muted);padding:5px 0;">
          This subject is not enrolled.
        </div>
      `;
    }

    return `
      <div class="perf-subject-card">

        <div class="perf-subject-head">

          <div class="perf-subject-icon"
               style="background:linear-gradient(145deg,var(${colorVariable}),rgba(23,19,53,.75));">
            ${s.icon||'📘'}
          </div>

          <div class="perf-subject-main">
            <b>${escapeHtml(s.name||s.key||'Subject')}</b>
            <span>${enrolled ? zone.name : 'Not enrolled'}</span>
          </div>

          <div class="perf-subject-score">
            ${enrolled && score!==null ? `${score}%` : '—'}
          </div>

        </div>

        <div class="perf-subject-bar">
          <i style="width:${safeScore}%;background:var(${colorVariable});"></i>
        </div>

        <div class="perf-subject-details">
          ${details}
        </div>

      </div>
    `;

  }).join('');
}

function renderMountainTable(rows){

  const body=document.getElementById('perf-table-body');
  if(!body) return;

  if(!rows.length){
    body.innerHTML=`
      <tr>
        <td colspan="6" style="text-align:center;padding:25px;color:var(--muted);">
          Complete a level to see your progress here.
        </td>
      </tr>
    `;
    return;
  }

  body.innerHTML=rows.map(r=>{

    const starsCount=Math.max(0,Math.min(5,Number(r.stars||0)));
    const stars=`${'★'.repeat(starsCount)}${'☆'.repeat(5-starsCount)}`;
    const score=r.completed ? Number(r.score||0) : null;

    let status='Not attempted';

    if(r.completed){
      if(score>=90) status='Outstanding';
      else if(score>=80) status='Excellent';
      else if(score>=70) status='Good';
      else if(score>=60) status='Developing';
      else status='Needs improvement';
    }

    return `
      <tr>
        <td><b>${escapeHtml(r.subject||'Subject')}</b></td>
        <td>Level ${r.level}</td>
        <td class="stars">${stars}</td>
        <td class="score">${r.completed ? `${score}%` : '—'}</td>
        <td>${status}</td>
        <td>${Number(r.xp||0)}</td>
      </tr>
    `;

  }).join('');
}

/* =========================================================
   LEVEL MAP
   ========================================================= */
async function openSubject(key){
  STATE.currentSubject = key;
  const s = subjMeta(key);
  const grade = String(STATE.user?.grade || '');
  const board = String(STATE.user?.board || '').toLowerCase();
  const tocSubject = String(key || '').toLowerCase();

  // The Student Quiz Board roadmap is generated from the question table.
  if(board === 'cbse' && grade === '11' && tocSubject === 'mathematics'){
    await openTableOfContent('cbse', 11, 'mathematics');
    return;
  }

  const prog = STATE.progress[key];
  document.getElementById('map-title').textContent = s.name;
  const displayUnlocked = String(STATE.user?.account_tier || '').toLowerCase() === 'premium'
    ? prog.max_level
    : prog.unlocked_level;
  document.getElementById('map-sub').textContent = `${s.icon} ${prog.max_level} levels · Level ${displayUnlocked} unlocked`;
  document.getElementById('map-xp').textContent = prog.xp;
  const mapScreen = document.getElementById('screen-map');
  const theme = (STATE.user && STATE.user.theme) || 'classic';
  if(theme === 'classic'){
    mapScreen.style.background = `linear-gradient(180deg, var(${s.c}), var(${s.cd}) 60%, #1a1440)`;
  } else {
    mapScreen.style.background = '';
  }
  renderPath(key);
  goto('screen-map');
}

async function loadQuestionTableForSubject(subject){
  // The backend requires `level` on /api/questions, so build the roadmap by
  // reading every supported quiz level and merging the returned question rows.
  // No syllabus/TOC JSON is used here — the question table is the source of truth.
  const levels = [1,2,3,4,5];
  const results = await Promise.all(levels.map(async level => {
    try {
      const qs = await api(`/api/questions?subject=${encodeURIComponent(subject)}&level=${level}`);
      return { level, questions: Array.isArray(qs) ? qs : [], locked: false };
    } catch (err) {
      // The student API may intentionally reject levels above the student's
      // current unlock/demo cap. That must not prevent the rest of the
      // question-table roadmap from loading.
      const message = String(err?.message || '').toLowerCase();
      const locked = message.includes('locked') || message.includes('level') && message.includes('unlock');
      if (locked) return { level, questions: [], locked: true };
      console.warn(`Could not load level ${level}:`, err);
      return { level, questions: [], locked: false };
    }
  }));
  const seen = new Set();
  const merged = [];
  results.flatMap(r => r.questions || []).forEach(q => {
    const key = q.question_id ?? q.id ?? `${q.subject}|${q.chapter}|${q.topic}|${q.question}`;
    if(seen.has(String(key))) return;
    seen.add(String(key));
    merged.push(q);
  });
  return merged;
}

function normalizeQuestionLevel(q){
  const direct = Number(q.level);
  if(Number.isFinite(direct) && direct > 0) return direct;
  const stage = String(q.stage || '').trim().toLowerCase();
  const map = {foundation:1,beginner:1,intermediate:2,advanced:3,application:4,mastery:5,expert:5};
  return map[stage] || null;
}

function buildQuestionToc(subject, questions, board, grade){
  const groups = new Map();
  questions.forEach(q => {
    const qSubject = String(q.subject || subject).trim() || subject;
    const world = String(q.world || q.unit || 'General').trim() || 'General';
    const chapter = String(q.chapter || 'Uncategorized').trim() || 'Uncategorized';
    const topic = String(q.topic || 'General').trim() || 'General';
    const level = normalizeQuestionLevel(q);
    if(!groups.has(qSubject)) groups.set(qSubject, new Map());
    const worlds = groups.get(qSubject);
    if(!worlds.has(world)) worlds.set(world, new Map());
    const chapters = worlds.get(world);
    if(!chapters.has(chapter)) chapters.set(chapter, new Map());
    const topics = chapters.get(chapter);
    if(!topics.has(topic)) topics.set(topic, []);
    if(level) topics.get(topic).push({...q, __level:level});
  });
  const subjects = [...groups.entries()].map(([subjectName, worlds]) => ({
    subject: subjectName,
    worlds: [...worlds.entries()].map(([world, chapters]) => ({
      world,
      chapters: [...chapters.entries()].map(([chapter, topics]) => ({
        chapter,
        topics: [...topics.entries()].map(([topic, qs]) => ({topic, questions: qs}))
      }))
    }))
  }));
  return {board, grade, subject, subjects};
}

function tocStageMeta(level){
  const fallback = {1:{stage:'Foundation',icon:'🌱'},2:{stage:'Intermediate',icon:'📘'},3:{stage:'Advanced',icon:'🚀'},4:{stage:'Application',icon:'🧠'},5:{stage:'Mastery',icon:'🏆'}};
  return fallback[Number(level)] || {stage:`Level ${level}`,icon:'⭐'};
}

function loadQuestionAvailability(questions){
  STATE.tocQuestionCache = {};
  questions.forEach(q => {
    const chapter = String(q.chapter || 'Uncategorized').trim().toLowerCase();
    const level = normalizeQuestionLevel(q);
    if(!level) return;
    if(!STATE.tocQuestionCache[chapter]) STATE.tocQuestionCache[chapter] = {};
    (STATE.tocQuestionCache[chapter][level] ||= []).push({...q, __level:level});
  });
  return STATE.tocQuestionCache;
}

function getAvailableLevels(chapterName){
  const row = STATE.tocQuestionCache?.[String(chapterName).trim().toLowerCase()] || {};
  return Object.keys(row).map(Number).filter(Boolean).sort((a,b)=>a-b);
}

function renderQuestionGroupedTable(toc){
  const rows=[];
  toc.subjects.forEach(subjectGroup=>{
    const subjectRows = subjectGroup.worlds.reduce((n,w)=>n+w.chapters.reduce((m,c)=>m+Math.max(1,c.topics.length),0),0);
    let subjectFirst=true;
    subjectGroup.worlds.forEach(worldGroup=>{
      const worldRows = worldGroup.chapters.reduce((n,c)=>n+Math.max(1,c.topics.length),0);
      let worldFirst=true;
      worldGroup.chapters.forEach(chapterGroup=>{
        const chapterRows=Math.max(1,chapterGroup.topics.length);
        const chapterLevels=[...new Set(chapterGroup.topics.flatMap(t=>t.questions.map(q=>q.__level)))].sort((a,b)=>a-b);
        const chapterOptions=chapterLevels.length ? chapterLevels.map(l=>{const m=tocStageMeta(l); const count=chapterGroup.topics.reduce((n,t)=>n+t.questions.filter(q=>q.__level===l).length,0); return `<option value="${l}">${m.icon} Level ${l} · ${m.stage} (${count})</option>`}).join('') : '<option value="">No questions</option>';
        const chapterBadges=chapterLevels.map(l=>{const m=tocStageMeta(l);const count=chapterGroup.topics.reduce((n,t)=>n+t.questions.filter(q=>q.__level===l).length,0);return `<span class="toc-level-badge">${m.icon} L${l} · ${count}</span>`}).join('');
        let chapterFirst=true;
        chapterGroup.topics.forEach(topicGroup=>{
          rows.push(`<tr>
            ${subjectFirst?`<td class="toc-subject-cell" rowspan="${subjectRows}">${escapeHtml(subjectGroup.subject)}</td>`:''}
            ${worldFirst?`<td class="toc-world-cell" rowspan="${worldRows}">${escapeHtml(worldGroup.world)}</td>`:''}
            ${chapterFirst?`<td class="toc-chapter-cell" rowspan="${chapterRows}"><div class="toc-chapter-name">${escapeHtml(chapterGroup.chapter)}</div><input type="checkbox" class="toc-chapter-check" data-chapter="${escapeHtml(chapterGroup.chapter)}" ${chapterLevels.length?'':'disabled'}></td>`:''}
            <td class="toc-topic-cell">${escapeHtml(topicGroup.topic)}<span>${topicGroup.questions.length} question${topicGroup.questions.length===1?'':'s'}</span></td>
            ${chapterFirst?`<td class="toc-level-cell" rowspan="${chapterRows}"><select class="toc-level-select" data-chapter="${escapeHtml(chapterGroup.chapter)}" ${chapterLevels.length?'':'disabled'}>${chapterOptions}</select><div class="toc-level-badges">${chapterBadges||'<span class="toc-level-badge empty">No question data</span>'}</div></td><td class="toc-start-cell" rowspan="${chapterRows}"><button class="toc-start-btn" ${chapterLevels.length?'':'disabled'} onclick="startSingleChapterFromRow(this)">Start</button></td>`:''}
          </tr>`);
          subjectFirst=false; worldFirst=false; chapterFirst=false;
        });
      });
    });
  });
  return rows.join('');
}

function collectSelectedChapters(){
  return [...document.querySelectorAll('.toc-chapter-check:checked')].map(x=>x.dataset.chapter).filter(Boolean);
}

function updateTocSelectionUI(){
  const selected=collectSelectedChapters(); const note=document.getElementById('toc-selection-note');
  if(note) note.textContent=selected.length?`${selected.length} chapter${selected.length===1?'':'s'} selected`:'No chapters selected';
}

function toggleAllTocChapters(checked){
  document.querySelectorAll('.toc-chapter-check:not(:disabled)').forEach(x=>x.checked=checked);
  refreshGlobalLevelOptions(); updateTocSelectionUI();
}

function getSelectedLevel(){ const value=document.getElementById('toc-global-level')?.value||''; return value?Number(value):null; }

function refreshGlobalLevelOptions(){
  const selected=collectSelectedChapters(); const select=document.getElementById('toc-global-level'); if(!select) return;
  const source=selected.length?selected:Object.keys(STATE.tocQuestionCache||{});
  const levels=[...new Set(source.flatMap(ch=>getAvailableLevels(ch)))].sort((a,b)=>a-b);
  select.innerHTML=levels.length?levels.map(l=>{const m=tocStageMeta(l);return `<option value="${l}">${m.icon} Level ${l} · ${escapeHtml(m.stage)}</option>`}).join(''):'<option value="">No levels available</option>';
}

function onTocChapterSelectionChanged(){refreshGlobalLevelOptions();updateTocSelectionUI();}

function startSingleChapterFromRow(button){
  const row=button.closest('tr'); const chapter=row.querySelector('.toc-level-select')?.dataset.chapter; const level=Number(row.querySelector('.toc-level-select')?.value||0);
  if(!chapter||!level){toast('No question level is available for this chapter');return;} startConfiguredQuiz([chapter],level);
}

function getQuizMinutes(){return Number(document.getElementById('toc-time-limit')?.value||20);}

function quizSessionKey(subject, level, chapters){
  const ch = [...new Set((chapters||[]).filter(Boolean).map(String))].sort();
  return `sq_quiz_${String(subject||'').toLowerCase()}_${Number(level)||0}_${ch.join('|').toLowerCase()}`;
}
function saveQuizSession(){
  const q=STATE.quiz; if(!q) return;
  const copy={...q,timerId:null};
  try{ localStorage.setItem(quizSessionKey(q.subject,q.level,q.chapters||[]),JSON.stringify(copy)); }catch(e){console.warn('Could not save quiz session',e);}
}
function loadQuizSession(subject,level,chapters){
  try{const raw=localStorage.getItem(quizSessionKey(subject,level,chapters)); return raw?JSON.parse(raw):null;}catch(e){return null;}
}
function clearQuizSession(q=STATE.quiz){
  if(!q) return;
  try{localStorage.removeItem(quizSessionKey(q.subject,q.level,q.chapters||[]));}catch(e){}
}
function hasSavedQuiz(subject,level,chapters){
  const q=loadQuizSession(subject,level,chapters);
  return !!(q && Array.isArray(q.questions) && q.questions.length && !q.levelComplete);
}

function questionsForMinutes(pool,minutes){
  const count=Math.max(1,Math.min(60,Number(minutes)||5));
  return pool.slice(0,count);
}

function beginQuizFromPool({subject,level,chapters,allQuestions,minutes,resume=false}){
  const clean=[...new Set((chapters||[]).filter(Boolean))];
  if(resume){
    const saved=loadQuizSession(subject,level,clean);
    if(saved){
      STATE.quiz=saved;
      STATE.quiz.timerId=null;
      if(!STATE.quiz.deadline || STATE.quiz.deadline<=Date.now()){
        STATE.quiz.finished=false;
        finishQuizBatch(true);
        return;
      }
      startQuizTimerFromDeadline(); renderQuestion(); goto('screen-quiz'); return;
    }
  }
  const shuffled=[...(allQuestions||[])].sort(()=>Math.random()-0.5);
  if(!shuffled.length){toast('No questions are available for the selected chapter(s) and level');return;}
  const batchSize=Math.min(shuffled.length,Math.max(1,Number(minutes)||5));
  STATE.quiz={
    subject,level:Number(level),chapter:clean.length===1?clean[0]:null,chapters:clean,
    allQuestions:shuffled, batchStart:0, batchSize, questions:questionsForMinutes(shuffled,minutes),
    idx:0,correct:0,batchCorrect:0,totalCorrect:0,hearts:5,failed:false,
    durationMinutes:Number(minutes)||5,plannedSeconds:(Number(minutes)||5)*60,
    startedAt:Date.now(),deadline:null,timerId:null,finished:false,levelComplete:false
  };
  startQuizTimer(minutes); saveQuizSession(); renderQuestion(); goto('screen-quiz');
}

function buildTimedQuestionSet(chapters,level,minutes){
  const pool=[];
  chapters.forEach(chapter=>{
    const byLevel=STATE.tocQuestionCache?.[String(chapter).trim().toLowerCase()]?.[level]||[];
    byLevel.forEach(q=>pool.push({...q,__chapter:chapter,__level:level}));
  });
  const shuffled=[...pool].sort(()=>Math.random()-0.5);
  return {selected:questionsForMinutes(shuffled,minutes),available:pool.length,allQuestions:shuffled};
}

let PENDING_QUIZ_LAUNCH=null;
function openQuizLaunchModal(config){
  PENDING_QUIZ_LAUNCH=config;
  const saved=hasSavedQuiz(config.subject,config.level,config.chapters||[]);
  document.getElementById('quiz-launch-title').textContent=`Level ${config.level}`;
  document.getElementById('quiz-launch-note').textContent=saved
    ? 'A saved attempt is available. Resume it to continue with the remaining questions, or retake the level from the beginning.'
    : 'Choose the time for this attempt. The time directly sets the number of questions: 1 minute = 1 question.';
  document.getElementById('quiz-time-picker').style.display=saved?'none':'block';
  document.getElementById('quiz-resume-actions').style.display=saved?'flex':'none';
  document.getElementById('quiz-launch-modal').classList.add('active');
}
function closeQuizLaunchModal(){PENDING_QUIZ_LAUNCH=null;document.getElementById('quiz-launch-modal').classList.remove('active');}
function confirmQuizLaunch(minutes){
  const c=PENDING_QUIZ_LAUNCH; if(!c) return;
  closeQuizLaunchModal();
  if(c.type==='map') loadAndStartMapQuiz(c.subject,c.level,minutes);
  else beginQuizFromPool({...c,minutes});
}
function resumeSavedQuiz(){
  const c=PENDING_QUIZ_LAUNCH; if(!c) return;
  closeQuizLaunchModal();
  const saved=loadQuizSession(c.subject,c.level,c.chapters||[]);
  if(saved){STATE.quiz=saved;STATE.quiz.timerId=null;startQuizTimerFromDeadline();renderQuestion();goto('screen-quiz');}
}
function retakeSavedQuiz(){
  const c=PENDING_QUIZ_LAUNCH; if(!c) return;
  const ok = confirm('Restart this level from the beginning? Your saved position for this attempt will be cleared.');
  if(!ok) return;
  closeQuizLaunchModal();
  const saved=loadQuizSession(c.subject,c.level,c.chapters||[]);
  if(saved){
    try{ localStorage.removeItem(quizSessionKey(c.subject,c.level,c.chapters||[])); }catch(e){}
  }
  if(c.type==='map') loadAndStartMapQuiz(c.subject,c.level,c.minutes||savedDefaultMinutes(c.subject,c.level,c.chapters||[]),true);
  else beginQuizFromPool({...c,minutes:c.minutes||savedDefaultMinutes(c.subject,c.level,c.chapters||[]),resume:false});
}
function savedDefaultMinutes(subject,level,chapters){
  const q=loadQuizSession(subject,level,chapters); return Number(q?.durationMinutes||5);
}

function startConfiguredQuiz(chapters,level){
  chapters=[...new Set(chapters)].filter(Boolean);
  if(!chapters.length){toast('Select at least one chapter');return;}
  if(!level){toast('Choose a quiz level');return;}
  const minutes=getQuizMinutes();
  const pack=buildTimedQuestionSet(chapters,Number(level),minutes);
  if(!pack.allQuestions.length){toast('No questions are available for the selected chapter(s) and level');return;}
  const subject=STATE.currentSubject||'mathematics';
  if(hasSavedQuiz(subject,Number(level),chapters)){
    openQuizLaunchModal({type:'toc',subject,level:Number(level),chapters,allQuestions:pack.allQuestions,minutes});
  }else{
    beginQuizFromPool({type:'toc',subject,level:Number(level),chapters,allQuestions:pack.allQuestions,minutes});
  }
}

async function openTableOfContent(board,grade,subject){
  if(SQ_PAGE !== 'toc'){
    try{ localStorage.setItem('sq_toc_request', JSON.stringify({board,grade,subject})); }catch(e){}
    window.location.href='toc.html';
    return;
  }
  const wrap=document.getElementById('toc-wrap'); wrap.innerHTML='<div class="toc-empty">Loading questions…</div>';
  try{
    const questions=await loadQuestionTableForSubject(subject); loadQuestionAvailability(questions); const toc=buildQuestionToc(subject,questions,board,grade); STATE.currentToc=toc;
    document.getElementById('toc-title').textContent=subject||'Table of Content'; document.getElementById('toc-subtitle').textContent=`${String(board||'').toUpperCase()} · Grade ${grade} · Question Bank`; document.getElementById('toc-xp').textContent=totalXp();
    const table=renderQuestionGroupedTable(toc); const allLevels=[...new Set(questions.map(normalizeQuestionLevel).filter(Boolean))].sort((a,b)=>a-b);
    const levelOptions=allLevels.length?allLevels.map(l=>{const m=tocStageMeta(l);return `<option value="${l}">${m.icon} Level ${l} · ${escapeHtml(m.stage)}</option>`}).join(''):'<option value="">No levels available</option>';
    wrap.innerHTML=`<div class="toc-hero"><div class="eyebrow">📚 Student Quiz Board · Question Bank</div><h2>${escapeHtml(subject)}</h2><p>This learning roadmap is generated only from published question data: subject, world/unit, chapter and topic are grouped directly from the questions table.</p></div><div class="toc-map-launch"><button class="toc-action-btn toc-action-map" onclick="openSubjectLevelMap('${escapeHtml(subject)}')">🎮 Open Gamified Level Map</button></div><div class="toc-controls"><div class="toc-control-row"><div class="toc-control"><label>Quiz level</label><select id="toc-global-level">${levelOptions}</select></div><div class="toc-control"><label>Quiz time</label><select id="toc-time-limit"><option value="5">5 minutes</option><option value="20" selected>20 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes (max)</option></select></div></div><div class="toc-actions"><button class="toc-action-btn toc-action-secondary" onclick="toggleAllTocChapters(true)">Select all</button><button class="toc-action-btn toc-action-secondary" onclick="toggleAllTocChapters(false)">Clear</button><button class="toc-action-btn toc-action-primary" onclick="startSelectedTocQuiz()">▶ Start selected chapters</button><span class="toc-selection-note" id="toc-selection-note">No chapters selected</span></div></div><div class="toc-table-card"><table class="toc-table"><thead><tr><th>Subject</th><th>World / Unit</th><th>Chapter</th><th>Topic</th><th>Available levels · questions</th><th class="toc-start-cell">Start</th></tr></thead><tbody>${table||'<tr><td colspan="6"><div class="toc-status">No questions are available for this subject.</div></td></tr>'}</tbody></table></div>`;
    document.querySelectorAll('.toc-chapter-check').forEach(x=>x.addEventListener('change',onTocChapterSelectionChanged)); refreshGlobalLevelOptions(); goto('screen-toc');
  }catch(err){wrap.innerHTML=`<div class="toc-empty">Could not load questions. ${escapeHtml(err.message||'')}</div>`;goto('screen-toc');}
}


function startSelectedTocQuiz(){
  const chapters=collectSelectedChapters();
  if(!chapters.length){toast('Select one or more chapters first');return;}
  const level=getSelectedLevel(); startConfiguredQuiz(chapters,level);
}

function selectTocTime(minutes){
  const select=document.getElementById('toc-time-limit');
  if(select) select.value=String(minutes);
}

function openSubjectLevelMap(key){
  if(SQ_PAGE !== 'index'){
    try{ localStorage.setItem('sq_map_request', String(key||'')); }catch(e){}
    window.location.href='index.html';
    return;
  }
  const s = subjMeta(key);
  const prog = STATE.progress[key];
  document.getElementById('map-title').textContent = s.name;
  const displayUnlocked = String(STATE.user?.account_tier || '').toLowerCase() === 'premium'
    ? prog.max_level
    : prog.unlocked_level;
  document.getElementById('map-sub').textContent = `${s.icon} ${prog.max_level} levels · Level ${displayUnlocked} unlocked`;
  document.getElementById('map-xp').textContent = prog.xp;
  const mapScreen = document.getElementById('screen-map');
  const theme = (STATE.user && STATE.user.theme) || 'classic';
  mapScreen.style.background = theme === 'classic'
    ? `linear-gradient(180deg, var(${s.c}), var(${s.cd}) 60%, #1a1440)` : '';
  renderPath(key);
  goto('screen-map');
}

function renderPath(key){
  const s = subjMeta(key);
  const prog = STATE.progress[key];
  const wrap = document.getElementById('path-wrap');
  const iconInfo = currentThemeIconInfo();
  const isGuest = STATE.user.account_tier === 'guest';
  const isPremium = String(STATE.user?.account_tier || '').toLowerCase() === 'premium';
  let html = '';
  for(let lvl=prog.max_level; lvl>=1; lvl--){
    const meta = levelMeta(lvl);
    const isConceptLevel = lvl > 5;
    const isGuestBeyondCap = isGuest && lvl > prog.demo_level_cap;
    const stars = prog.stars[lvl] || 0;
    // Levels 1-5 (and a guest's whole demo range) stay strictly sequential.
    // For a non-guest past level 5, every concept-tier level is playable at
    // once — 'done' if already cleared, otherwise the same 'unlocked' look
    // as the single frontier node, just without the pulse (since several
    // can be available simultaneously here, not just one "next" step).
    let state;
    if(isPremium){
      // Premium users have unrestricted access to every configured level.
      state = stars > 0 ? 'done' : 'unlocked';
    } else if(isGuest || !isConceptLevel){
      state = lvl < prog.unlocked_level ? 'done' : (lvl === prog.unlocked_level ? 'unlocked' : 'locked');
    } else {
      state = prog.unlocked_level >= 6 ? (stars > 0 ? 'done' : 'unlocked') : 'locked';
    }
    const hasIcon = iconInfo && state !== 'locked';
    let bg = '';
    let inner;
    if(isGuestBeyondCap){
      bg = '';
      inner = `<span class="lock">🔒</span>`;
    } else if(hasIcon){
      const iconIdx = (lvl - 1) % iconInfo.count;
      const iconUrl = `${API_BASE}/api/themes/${encodeURIComponent(iconInfo.key)}/icons/${iconIdx}`;
      bg = `background-image:url('${iconUrl}');background-size:cover;background-position:center;`;
      inner = `<span class="node-badge">${lvl}</span>`;
    } else {
      bg = state==='locked' ? '' : `background:linear-gradient(155deg, var(${s.c}), var(${s.cd}));`;
      inner = state==='locked'
        ? `<span class="lock">🔒</span>`
        : `<span class="num">${lvl}</span><span class="tag">${meta.diff}</span>`;
    }
    // Always show the 3-star progress indicator for an available level.
    // Filled stars come from the latest merged progress; empty stars mean
    // the level has not earned those stars yet. Locked levels keep the
    // indicator hidden.
    const visibleStars = Math.max(0, Math.min(5, Number(stars) || 0));
    let starsHtml = state!=='locked'
      ? `<div class="stars-row" aria-label="${visibleStars} of 5 stars">${[1,2,3,4,5].map(i=>`<span>${i<=visibleStars?'⭐':'☆'}</span>`).join('')}</div>` : '';
    // A concept level's real topic name (e.g. "Newton's Laws") wins over the
    // generic "Level N" fallback, once the admin has tagged questions with one.
    const conceptLabel = isConceptLevel && prog.level_labels && prog.level_labels[String(lvl)];
    const label = isGuestBeyondCap ? '🔒 Register to unlock' : (conceptLabel || meta.label);
    const pulses = state==='unlocked' && !isGuestBeyondCap && !isConceptLevel;
    const clickAction = isGuestBeyondCap
      ? 'openRegistrationCta()'
      : (state!=='locked' ? `startLevel('${key}',${lvl})` : `toast('Complete Level 5 first')`);
    html += `<div class="level-node-wrap">
      <span class="level-label">${label}</span>
      <button class="level-node ${isGuestBeyondCap?'locked':state} ${pulses?'pulse':''} ${hasIcon&&!isGuestBeyondCap?'has-icon':''}" style="${bg}" onclick="${clickAction}">
        ${inner}
      </button>
      ${starsHtml}
    </div>`;
  }
  wrap.innerHTML = html;
}

/* =========================================================
   QUIZ FLOW
   ========================================================= */
async function startChapterLevel(subject, level, chapter){
  // Compatibility entry point for any existing button handlers.
  await startConfiguredQuiz([chapter], Number(level));
}

async function startLevel(subject, level){
  const saved=hasSavedQuiz(subject,level,[]);
  openQuizLaunchModal({type:'map',subject,level,chapters:[],minutes:savedDefaultMinutes(subject,level,[])});
}
async function loadAndStartMapQuiz(subject,level,minutes,forceRetake=false){
  let qs;
  try{qs=await api(`/api/questions?subject=${encodeURIComponent(subject)}&level=${level}`);}
  catch(err){if(err.message==='REGISTRATION_REQUIRED'){openRegistrationCta();return;} toast(err.message||'Could not load questions');return;}
  if(!qs.length){toast('No questions have been added for this level yet');return;}
  beginQuizFromPool({subject,level,chapters:[],allQuestions:qs,minutes,resume:false});
}
function exitQuiz(){
  if(confirm('Save your current position and leave? You can resume this attempt later.')){
    saveQuizSession(); stopQuizTimer();
    if(STATE.quiz && (STATE.quiz.chapter || STATE.quiz.chapters?.length)) openTableOfContent('cbse',STATE.user.grade,'mathematics');
    else goto('screen-map');
  }
}
function stopQuizTimer(){if(STATE.quiz?.timerId){clearInterval(STATE.quiz.timerId);STATE.quiz.timerId=null;}}
function startQuizTimerFromDeadline(){
  stopQuizTimer(); if(!STATE.quiz)return;
  updateQuizTimer(); STATE.quiz.timerId=setInterval(updateQuizTimer,1000);
}
function updateQuizTimer(){
  const quiz=STATE.quiz, el=document.getElementById('quiz-timer'); if(!quiz||!el||!quiz.deadline)return;
  const remaining=Math.max(0,quiz.deadline-Date.now()), totalSeconds=Math.ceil(remaining/1000);
  el.textContent=`${String(Math.floor(totalSeconds/60)).padStart(2,'0')}:${String(totalSeconds%60).padStart(2,'0')}`;
  el.style.background=remaining<=60000?'#ffe0df':'#fff3cf'; el.style.color=remaining<=60000?'#a62d2d':'#7a5b12';
  if(remaining<=0&&!quiz.finished){quiz.finished=true;stopQuizTimer();saveQuizSession();finishQuizBatch(true);}
}
function startQuizTimer(minutes){
  stopQuizTimer(); if(!STATE.quiz)return;
  STATE.quiz.deadline=Date.now()+Math.max(1,Number(minutes)||5)*60*1000;
  STATE.quiz.finished=false; updateQuizTimer(); STATE.quiz.timerId=setInterval(updateQuizTimer,1000);
}

function renderHearts(){
  const h = document.getElementById('quiz-hearts');
  h.innerHTML = Array.from({length:5}).map((_,i)=> i < STATE.quiz.hearts ? '❤️' : '🤍').join('');
}
function renderQuestion(){
  const quiz = STATE.quiz;
  const q = quiz.questions[quiz.idx];
  const s = subjMeta(quiz.subject);
  document.getElementById('screen-quiz').style.background = '#FBF7EC';
  document.getElementById('quiz-progress').style.width = `${((quiz.idx + 1)/quiz.questions.length)*100}%`;
  renderHearts();
  updateQuizTimer();
  document.getElementById('q-difficulty').textContent = levelMeta(quiz.level).diff;
  document.getElementById('q-difficulty').style.background = `var(${s.c})`;
  document.getElementById('q-difficulty').style.color = '#fff';
  document.getElementById('q-board').textContent = q.board;
  document.getElementById('q-text').textContent = q.question;
  const hintToggle = document.getElementById('hint-toggle');
  const hintText = document.getElementById('hint-text');
  hintText.style.display = 'none';
  hintText.textContent = q.hint || '';
  hintToggle.style.display = q.hint ? 'block' : 'none';
  hintToggle.textContent = '💡 Show a hint';
  const letters = ['A','B','C','D'];
  const optWrap = document.getElementById('q-options');
  optWrap.innerHTML = q.options.map((o,i)=>`<button class="opt" data-i="${i}" onclick="selectOption(${i})"><span class="letter">${letters[i]}</span><span>${escapeHtml(o)}</span></button>`).join('');
  document.getElementById('quiz-continue').style.display = 'none';
  document.getElementById('explain-card').classList.remove('show');
}
function toggleHint(){
  const hintText = document.getElementById('hint-text');
  const isHidden = hintText.style.display === 'none';
  hintText.style.display = isHidden ? 'block' : 'none';
  document.getElementById('hint-toggle').textContent = isHidden ? '💡 Hide hint' : '💡 Show a hint';
}
function selectOption(i){
  const quiz = STATE.quiz;
  const q = quiz.questions[quiz.idx];
  const btns = document.querySelectorAll('#q-options .opt');
  btns.forEach(b=>b.classList.add('disabled'));
  btns.forEach(b=>b.onclick=null);
  const wasCorrect = (i === q.correct);
  const firstAttempt = registerQuestionFirstAttempt(q, wasCorrect);
  quiz.firstAttemptAnswered = Number(quiz.firstAttemptAnswered||0) + (firstAttempt.isFirstAttempt ? 1 : 0);
  quiz.firstAttemptCorrect = Number(quiz.firstAttemptCorrect||0) + (firstAttempt.isFirstAttempt && wasCorrect ? 1 : 0);
  quiz.firstAttemptPoints = Number(quiz.firstAttemptPoints||0) + Number(firstAttempt.points||0);
  quiz.batchFirstAttemptAnswered = Number(quiz.batchFirstAttemptAnswered||0) + (firstAttempt.isFirstAttempt ? 1 : 0);
  quiz.batchFirstAttemptCorrect = Number(quiz.batchFirstAttemptCorrect||0) + (firstAttempt.isFirstAttempt && wasCorrect ? 1 : 0);
  quiz.batchFirstAttemptPoints = Number(quiz.batchFirstAttemptPoints||0) + Number(firstAttempt.points||0);
  if(wasCorrect){
    quiz.correct++; quiz.batchCorrect++; quiz.totalCorrect++;
    btns[i].classList.add('correct');
    toast('Correct! ⚡ +10 XP');
  } else {
    btns[i].classList.add('wrong');
    btns[q.correct].classList.add('correct');
    quiz.hearts--;
    toast('Not quite');
  }
  if(q.explanation){
    document.getElementById('explain-ico').textContent = wasCorrect ? '✅' : '💡';
    document.getElementById('explain-label').textContent = wasCorrect ? 'Nice — here\'s why' : 'Here\'s why';
    document.getElementById('explain-text').textContent = q.explanation;
    document.getElementById('explain-card').classList.add('show');
  }
  document.getElementById('quiz-continue').style.display = 'block';
  document.getElementById('quiz-continue').textContent = (quiz.hearts<=0) ? 'See result' : (quiz.idx===quiz.questions.length-1 ? 'Finish level' : 'Continue');
}
function nextQuestion(){
  const quiz=STATE.quiz;
  if(quiz.hearts<=0){finishQuizBatch(false,true);return;}
  quiz.idx++;
  if(quiz.idx>=quiz.questions.length){finishQuizBatch(false,false);return;}
  saveQuizSession(); renderQuestion();
}

async function finishQuizBatch(timeUp=false,outOfHearts=false){
  const quiz=STATE.quiz; if(!quiz)return;
  if(quiz.finished && !timeUp && !outOfHearts)return;
  quiz.finished=true; stopQuizTimer(); saveQuizSession();
  const batchTotal=Math.max(1,quiz.questions.length), batchCorrect=Number(quiz.batchCorrect||0);
  const nextStart=Number(quiz.batchStart||0)+batchTotal;
  const levelComplete=nextStart>=Number(quiz.allQuestions?.length||batchTotal);
  if(!levelComplete){
    document.getElementById('result-emoji').textContent=timeUp?'⏰':(outOfHearts?'💔':'🎉');
    document.getElementById('result-title').textContent=timeUp?"Time's up!":'Batch finished!';
    document.getElementById('result-sub').textContent=`Batch ${Math.floor((quiz.batchStart||0)/quiz.batchSize)+1} finished · ${batchCorrect}/${batchTotal} correct · ${quiz.allQuestions.length-nextStart} questions remaining`;
    document.getElementById('result-stars').textContent='⭐'.repeat(batchCorrect>=batchTotal?5:batchCorrect>=Math.ceil(batchTotal*.9)?4:batchCorrect>=Math.ceil(batchTotal*.8)?3:batchCorrect>=Math.ceil(batchTotal*.7)?2:batchCorrect>=Math.ceil(batchTotal*.5)?1:0);
    document.getElementById('result-correct').textContent=`${batchCorrect}/${batchTotal}`;
    document.getElementById('result-xp').textContent=`+${batchCorrect*10}`;
    document.getElementById('result-actions').innerHTML=`
      <button class="btn-primary btn-gold" onclick="continueQuizLevel()">▶ Continue Level</button>
      <button class="result-action-secondary" onclick="retestCurrentBatch()">🔄 Retake This Batch</button>
      <button class="result-action-secondary" onclick="saveAndExitBatch()">💾 Resume Later</button>
      <button class="result-action-secondary" onclick="openResultProgress()">📊 Track Progress</button>`;
    document.getElementById('result-overlay').classList.add('active'); return;
  }
  quiz.levelComplete=true; clearQuizSession(quiz);
  const total=Math.max(1,quiz.allQuestions?.length||batchTotal), totalCorrect=Number(quiz.totalCorrect||quiz.correct||0), scorePct=Math.round((totalCorrect/total)*100);
  let result=null;
  try{result=await api('/api/progress/attempt',{method:'POST',body:{
      subject:quiz.subject, level:quiz.level,
      correct_count:totalCorrect, total_questions:total,
      out_of_hearts:!!outOfHearts,
      first_attempt_correct:Number(quiz.firstAttemptCorrect||0),
      first_attempt_total:Number(quiz.firstAttemptAnswered||0),
      first_attempt_points:Number(quiz.firstAttemptPoints||0),
      question_points:Number(quiz.firstAttemptPoints||0),
      first_attempt_answers:Object.entries(STATE.firstAttemptLedger||{})
        .filter(([key,e])=>String(e.subject||'')===String(quiz.subject) && Number(e.level||0)===Number(quiz.level) && String(key).startsWith('id:'))
        .map(([key,e])=>({question_id:Number(String(key).slice(3)),correct:!!e.correct}))
    }});}catch(err){console.warn('Progress save unavailable; showing local level result:',err);}  
  // Calculate the completion result locally first. The API may return a
  // stale/partial progress object (or zero stars) while the student has
  // already completed the level in this browser session. Never let that
  // response hide the result or the Next Level action.
  const localPassed = !outOfHearts && scorePct >= 50;
  const localStars = outOfHearts ? 0 : (scorePct >= 100 ? 5 : scorePct >= 90 ? 4 : scorePct >= 80 ? 3 : scorePct >= 70 ? 2 : scorePct >= 50 ? 1 : 0);
  const passed = result?.passed === true || (result?.passed == null && localPassed) || (result?.passed !== false && localPassed);
  const serverStars = Number(result?.stars || 0);
  const stars = Math.max(serverStars, localStars);
  const xpGained = Math.max(Number(result?.xp_gained || 0), totalCorrect * 10);
  // Merge the completed level with the server response. Never let a stale
  // server snapshot move the unlock frontier backwards.
  const serverProgress = result?.progress || {};
  const current = STATE.progress[quiz.subject] || {};
  const mergedStars = {...(current.stars || {}), ...(serverProgress.stars || {})};
  if(stars > Number(mergedStars[String(quiz.level)] || 0)){
    mergedStars[String(quiz.level)] = stars;
  }
  const serverUnlocked = Number(serverProgress.unlocked_level || 0);
  const currentUnlocked = Number(current.unlocked_level || 1);
  const nextUnlocked = passed
    ? Math.max(currentUnlocked, serverUnlocked, Number(quiz.level) + 1)
    : Math.max(currentUnlocked, serverUnlocked || 1);

  const premiumUser = String(STATE.user?.account_tier || '').toLowerCase() === 'premium';
  const effectiveMaxLevel = premiumUser
    ? Math.max(Number(serverProgress.max_level || 0), Number(current.max_level || 0), 5)
    : Number(serverProgress.max_level || current.max_level || 5);
  STATE.progress[quiz.subject] = {
    ...current,
    ...serverProgress,
    unlocked_level: premiumUser ? Math.max(nextUnlocked, effectiveMaxLevel) : nextUnlocked,
    stars: mergedStars,
    xp: Math.max(Number(serverProgress.xp ?? 0), Number(current.xp ?? 0), Number(xpGained || 0)),
    max_level: effectiveMaxLevel
  };
  try{ localStorage.setItem('sq_progress', JSON.stringify(STATE.progress)); }catch(e){}

  // Refresh the roadmap immediately after a successful level completion.
  if(STATE.currentSubject === quiz.subject){
    renderPath(quiz.subject);
    const p = STATE.progress[quiz.subject];
    const s = subjMeta(quiz.subject);
    document.getElementById('map-sub').textContent =
      `${s.icon} ${p.max_level} levels · Level ${p.unlocked_level} unlocked`;
    document.getElementById('map-xp').textContent = p.xp || 0;
  }
  document.getElementById('result-emoji').textContent=outOfHearts?'💔':(passed?(stars>=5?'🏆':'🎉'):'📘');
  document.getElementById('result-title').textContent=timeUp?"Time's up!":'Level finished!';
  document.getElementById('result-sub').textContent=`Level ${quiz.level} complete · ${quiz.correct}/${total} correct · ${stars} star${stars===1?'':'s'} obtained`;
  document.getElementById('result-stars').textContent='⭐'.repeat(stars)+'☆'.repeat(Math.max(0,5-stars));
  document.getElementById('result-correct').textContent=`${totalCorrect}/${total}`; document.getElementById('result-xp').textContent=`+${xpGained}`;
  const nextLevel = Number(quiz.level) + 1;
  const progressAfter = STATE.progress[quiz.subject] || {};
  const availableMax = premiumUser ? Math.max(Number(progressAfter.max_level || 0), 5) : Number(progressAfter.max_level || 0);
  // A Premium user can always move to the next configured level after a
  // passed level, even if the server returned an outdated max_level.
  const canGoNext = passed && (premiumUser ? nextLevel <= availableMax : nextLevel <= availableMax);
  document.getElementById('result-actions').innerHTML=`
    ${canGoNext ? `<button class="btn-primary btn-gold" onclick="goToNextGamifiedLevel()">▶ Next Level ${nextLevel}</button>` : ''}
    <button class="result-action-secondary" onclick="openResultProgress()">📊 Track Progress</button>
    <button class="result-action-secondary" onclick="retestFinishedLevel()">🔄 Take Retest</button>
    <button class="result-action-secondary" onclick="exploreOtherLevels()">🧭 Explore Other Levels</button>
    <button class="result-action-secondary" onclick="backHomeFromResult()">🏠 Back Home</button>`;
  document.getElementById('result-overlay').classList.add('active');
}

function goToNextGamifiedLevel(){
  const quiz = STATE.quiz;
  if(!quiz || !quiz.subject) return;
  const next = Number(quiz.level) + 1;
  const p = STATE.progress[quiz.subject] || {};
  const premiumUser = String(STATE.user?.account_tier || '').toLowerCase() === 'premium';
  const availableMax = premiumUser ? Math.max(Number(p.max_level || 0), 5) : Number(p.max_level || next);
  if(next > availableMax){
    document.getElementById('result-overlay').classList.remove('active');
    goto('screen-map');
    return;
  }
  if(premiumUser) p.max_level = availableMax;
  p.unlocked_level = Math.max(Number(p.unlocked_level || 1), next);
  document.getElementById('result-overlay').classList.remove('active');
  renderPath(quiz.subject);
  loadAndStartMapQuiz(quiz.subject, next, quiz.durationMinutes || 5, false);
}

function continueQuizLevel(){
  const q=STATE.quiz; if(!q)return;
  document.getElementById('result-overlay').classList.remove('active');
  q.batchStart=(q.batchStart||0)+q.questions.length; q.questions=q.allQuestions.slice(q.batchStart,q.batchStart+q.batchSize); q.idx=0; q.batchCorrect=0; q.hearts=5; q.finished=false; startQuizTimer(q.durationMinutes); saveQuizSession(); renderQuestion(); goto('screen-quiz');
}
function retestCurrentBatch(){
  const q=STATE.quiz; if(!q)return;
  if(!confirm('Restart this batch from the beginning? Your answers from this batch will be cleared.')) return;
  document.getElementById('result-overlay').classList.remove('active');
  q.questions=q.allQuestions.slice(q.batchStart,q.batchStart+q.batchSize);
  q.idx=0;q.batchCorrect=0;q.hearts=5;q.finished=false;
  startQuizTimer(q.durationMinutes);saveQuizSession();renderQuestion();goto('screen-quiz');
}
function saveAndExitBatch(){const q=STATE.quiz;if(q){q.batchStart=(q.batchStart||0)+q.questions.length;q.questions=q.allQuestions.slice(q.batchStart,q.batchStart+q.batchSize);q.idx=0;q.batchCorrect=0;q.hearts=5;q.finished=false;saveQuizSession();}document.getElementById('result-overlay').classList.remove('active');if(q?.chapters?.length)openTableOfContent('cbse',STATE.user?.grade||11,'mathematics');else goto('screen-map');}

function closeResult(){
  document.getElementById('result-overlay').classList.remove('active');
  goto('screen-home');
}

function openResultProgress(){
  document.getElementById('result-overlay').classList.remove('active');
  openPerformance();
}

function retestFinishedLevel(){
  const quiz=STATE.quiz;
  if(!quiz||!quiz.level){goto('screen-home');return;}
  if(!confirm('Restart this level from the beginning? This will start a completely new attempt.')) return;
  document.getElementById('result-overlay').classList.remove('active');
  clearQuizSession(quiz);
  if(quiz.chapters?.length){
    const pack=buildTimedQuestionSet(quiz.chapters,quiz.level,quiz.durationMinutes||5);
    beginQuizFromPool({subject:quiz.subject,level:quiz.level,chapters:quiz.chapters,allQuestions:pack.allQuestions,minutes:quiz.durationMinutes||5}); return;
  }
  loadAndStartMapQuiz(quiz.subject,quiz.level,quiz.durationMinutes||5,true);
}

function exploreOtherLevels(){
  const quiz = STATE.quiz;
  document.getElementById('result-overlay').classList.remove('active');
  if(quiz?.subject){
    openTableOfContent('cbse', STATE.user?.grade || 11, quiz.subject);
  }else{
    goto('screen-home');
  }
}

function backHomeFromResult(){
  document.getElementById('result-overlay').classList.remove('active');
  goto('screen-home');
}

/* =========================================================
   ADMIN — student accounts
   ========================================================= */
async function addStudent(){
  const userid = document.getElementById('new-stu-userid').value.trim();
  const email = document.getElementById('new-stu-email').value.trim();
  const password = document.getElementById('new-stu-password').value;
  const name = document.getElementById('new-stu-name').value.trim();
  const grade = document.getElementById('new-stu-grade').value;
  const board = document.getElementById('new-stu-board').value;
  const accountTier = document.getElementById('new-stu-tier').value;
  const requireReset = document.getElementById('new-stu-force-reset').checked;
  if(!userid || !email || !password || !name){ toast('Fill in user ID, email, password and name'); return; }
  if(password.length < 6){ toast('Password must be at least 6 characters'); return; }
  try{
    await api('/api/admin/students', {method:'POST', body:{
      userid, email, password, name, grade, board, avatar: STATE.selectedAvatar,
      account_tier: accountTier, require_password_reset: requireReset,
    }});
    ['new-stu-userid','new-stu-email','new-stu-password','new-stu-name'].forEach(i=>document.getElementById(i).value='');
    await renderAdminStudentList();
    toast('Student account created');
  }catch(err){
    toast(err.message || 'Could not create student');
  }
}
async function deleteStudent(id){
  if(!confirm('Remove this student account and their progress?')) return;
  try{
    await api(`/api/admin/students/${id}`, {method:'DELETE'});
    await renderAdminStudentList();
  }catch(err){
    toast(err.message || 'Could not remove student');
  }
}
let EXPANDED_GUEST_IDS = new Set();
let EXPANDED_ENROLLMENT_IDS = new Set();
let ENROLLMENT_CACHE = {}; // student id -> [{subject,name,icon,enrolled}, ...], fetched on demand

async function renderAdminStudentList(){
  const wrap = document.getElementById('admin-student-list');
  if(!wrap) return;
  let students;
  try{ students = await api('/api/admin/students'); }
  catch(err){ toast(err.message || 'Could not load students'); return; }
  if(students.length===0){ wrap.innerHTML = '<p class="empty-note">No student accounts yet — add one above.</p>'; return; }

  const tierColors = {guest:'#948c68', silver:'#7a7a8c', premium:'#C98A0A'};
  wrap.innerHTML = students.map(u=>{
    const isGuest = u.account_tier === 'guest';
    const isOpen = EXPANDED_GUEST_IDS.has(u.id);
    const enrollOpen = EXPANDED_ENROLLMENT_IDS.has(u.id);
    const tierBadge = `<span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.04em;color:#fff;background:${tierColors[u.account_tier]||'#888'};margin-left:6px;">${escapeHtml(u.account_tier||'—')}</span>`;
    const enrollmentList = ENROLLMENT_CACHE[u.id];
    const enrollmentPanel = (!isGuest && enrollOpen) ? `
      <div style="flex-basis:100%;margin-top:14px;padding-top:14px;border-top:1px solid var(--paper-line);">
        <label style="display:block;font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#948c68;margin-bottom:8px;">Enrolled subjects</label>
        ${enrollmentList ? `
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px;">
          ${enrollmentList.map(e => `
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;background:var(--paper-line);padding:6px 10px;border-radius:20px;cursor:pointer;">
              <input type="checkbox" class="enroll-check-${u.id}" value="${e.subject}" ${e.enrolled?'checked':''} style="width:auto;">
              ${e.icon||''} ${escapeHtml(e.name)}
            </label>`).join('')}
        </div>
        <button class="btn-primary" onclick="saveEnrollment('${u.id}')">Save enrollment</button>
        <p class="msg-note" id="enroll-status-${u.id}"></p>
        ` : '<p class="empty-note">Loading…</p>'}
      </div>` : '';
    return `
    <div class="user-row" style="flex-wrap:wrap;">
      <div class="av">${u.avatar || '🦊'}</div>
      <div class="meta"><b>${escapeHtml(u.name)}</b>${tierBadge}<span>${escapeHtml(u.userid)}${u.email ? ' · '+escapeHtml(u.email) : ''}${u.grade ? ' · Grade '+u.grade : ''}${u.board ? ' · '+u.board : ''}</span></div>
      ${isGuest ? `<button onclick="toggleGuestUpgrade('${u.id}')">${isOpen?'Close':'Upgrade'}</button>` : `<button onclick="toggleEnrollmentPanel('${u.id}')">${enrollOpen?'Close':'Subjects'}</button>`}
      <button onclick="deleteStudent('${u.id}')">Remove</button>
      ${isGuest && isOpen ? `
      <div style="flex-basis:100%;margin-top:14px;padding-top:14px;border-top:1px solid var(--paper-line);">
        <div class="field"><label>Set password</label><input type="password" id="upgrade-pw-${u.id}" placeholder="At least 6 characters"></div>
        <div class="field"><label>Email</label><input type="email" id="upgrade-email-${u.id}" placeholder="e.g. student@gmail.com"></div>
        <div class="field"><label>Account tier</label>
          <select id="upgrade-tier-${u.id}"><option value="silver">Silver</option><option value="premium">Premium</option></select>
        </div>
        <button class="btn-primary" onclick="submitGuestUpgrade('${u.id}')">Confirm upgrade</button>
        <p class="msg-note" id="upgrade-status-${u.id}"></p>
      </div>` : ''}
      ${enrollmentPanel}
    </div>`;
  }).join('');
}
async function toggleEnrollmentPanel(id){
  if(EXPANDED_ENROLLMENT_IDS.has(id)){
    EXPANDED_ENROLLMENT_IDS.delete(id);
    renderAdminStudentList();
    return;
  }
  EXPANDED_ENROLLMENT_IDS.add(id);
  delete ENROLLMENT_CACHE[id];
  renderAdminStudentList(); // show "Loading…" immediately
  try{
    ENROLLMENT_CACHE[id] = await api(`/api/admin/students/${id}/enrollment`);
  }catch(err){
    toast(err.message || 'Could not load enrollment');
    EXPANDED_ENROLLMENT_IDS.delete(id);
  }
  renderAdminStudentList();
}
async function saveEnrollment(id){
  const statusEl = document.getElementById(`enroll-status-${id}`);
  const checked = Array.from(document.querySelectorAll(`.enroll-check-${id}:checked`)).map(el => el.value);
  try{
    ENROLLMENT_CACHE[id] = await api(`/api/admin/students/${id}/enrollment`, {method:'PUT', body:{enrolled_subjects: checked}});
    statusEl.textContent = 'Saved.';
    toast('Enrollment updated');
  }catch(err){
    statusEl.textContent = err.message || 'Could not save enrollment';
  }
}
function toggleGuestUpgrade(id){
  if(EXPANDED_GUEST_IDS.has(id)) EXPANDED_GUEST_IDS.delete(id);
  else EXPANDED_GUEST_IDS.add(id);
  renderAdminStudentList();
}
async function submitGuestUpgrade(id){
  const statusEl = document.getElementById(`upgrade-status-${id}`);
  const password = document.getElementById(`upgrade-pw-${id}`).value;
  const email = document.getElementById(`upgrade-email-${id}`).value.trim();
  const accountTier = document.getElementById(`upgrade-tier-${id}`).value;
  if(!password || password.length < 6){ statusEl.textContent = 'Password must be at least 6 characters.'; return; }
  try{
    await api(`/api/admin/students/${id}/upgrade`, {method:'PUT', body:{
      password, account_tier: accountTier, email: email || undefined, require_password_reset: true,
    }});
    toast('Guest upgraded successfully');
    EXPANDED_GUEST_IDS.delete(id);
    await renderAdminStudentList();
  }catch(err){
    statusEl.textContent = err.message || 'Could not upgrade this account.';
  }
}

/* =========================================================
   ADMIN — bulk question upload from Excel
   ========================================================= */
function downloadExcelTemplate(){
  const sample = [
    {Subject:'chemistry', Level:1, Grade:'', Board:'CBSE', Question:'Which is the SI unit of amount of substance?',
     OptionA:'Mole', OptionB:'Gram', OptionC:'Litre', OptionD:'Atom', Correct:'A',
     Explanation:'Mole is the SI base unit for amount of substance.',
     World:'', Chapter:'', Topic:'', Stage:'', CognitiveSkill:'', QuestionType:'mcq', TimeLimit:'', Hint:'',
     Status:'published', Version:1},
    {Subject:'physics', Level:6, Grade:'8', Board:'CBSE', Question:'What is the SI unit of force?',
     OptionA:'Newton', OptionB:'Joule', OptionC:'Watt', OptionD:'Pascal', Correct:'A',
     Explanation:"Force is measured in Newtons, named after Sir Isaac Newton.",
     World:'Mechanics', Chapter:'Forces', Topic:"Newton's Laws", Stage:'1', CognitiveSkill:'Remember',
     QuestionType:'mcq', TimeLimit:30, Hint:'Think about F = ma', Status:'published', Version:1},
  ];
  const ws = XLSX.utils.json_to_sheet(sample);
  ws['!cols'] = [13,7,7,9,38,15,15,15,15,9,30,13,13,16,8,13,11,9,22,11,8].map(w=>({wch:w}));
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Questions');
  XLSX.writeFile(wb, 'question_upload_template.xlsx');
}
async function handleExcelUpload(evt){
  const file = evt.target.files[0];
  if(!file) return;
  const statusEl = document.getElementById('excel-upload-status');
  statusEl.textContent = 'Uploading…';
  const form = new FormData();
  form.append('file', file);
  try{
    const result = await api('/api/admin/questions/upload', {method:'POST', body:form, isForm:true});
    statusEl.textContent = `Added ${result.added} question${result.added===1?'':'s'}${result.skipped ? `, skipped ${result.skipped} invalid row${result.skipped===1?'':'s'}` : ''}.`;
    if(result.errors && result.errors.length){
      statusEl.textContent += ' See console for row-level details.';
      console.warn('Excel upload issues:', result.errors);
    }
    toast(`${result.added} question${result.added===1?'':'s'} added`);
    await searchAdminQuestions(true);
  }catch(err){
    statusEl.textContent = err.message || 'Could not read that file — please check it is a valid Excel file.';
  }
  document.getElementById('admin-excel-file').value = '';
}

/* =========================================================
   ADMIN — free-demo level caps per subject
   ========================================================= */
async function renderAdminSubjectCaps(){
  const wrap = document.getElementById('admin-subject-cap-list');
  if(!wrap) return;
  let subjects;
  try{ subjects = await api('/api/admin/subjects'); }
  catch(err){ wrap.innerHTML = `<p class="empty-note">${err.message || 'Could not load subjects'}</p>`; return; }
  wrap.innerHTML = subjects.map(s => `
    <div class="user-row">
      <div class="av">${s.icon || '📘'}</div>
      <div class="meta"><b>${escapeHtml(s.name)}</b><span>${escapeHtml(s.key)}</span></div>
      <input type="number" min="1" max="1000" id="subj-cap-${s.key}" value="${s.demo_level_cap}"
             style="width:64px;padding:8px;border-radius:8px;border:1.5px solid var(--paper-line);text-align:center;">
      <button onclick="saveSubjectCap('${s.key}')">Save</button>
      <button onclick="deleteSubject('${s.key}')">Remove</button>
    </div>`).join('');
}
async function saveSubjectCap(key){
  const input = document.getElementById(`subj-cap-${key}`);
  const cap = parseInt(input.value, 10);
  if(!cap || cap < 1){ toast('Enter a valid level number'); return; }
  try{
    await api(`/api/admin/subjects/${encodeURIComponent(key)}`, {method:'PUT', body:{demo_level_cap: cap}});
    toast(`${key} demo cap set to ${cap}`);
  }catch(err){
    toast(err.message || 'Could not save that cap');
  }
}
async function createSubject(){
  const statusEl = document.getElementById('new-subj-status');
  const key = document.getElementById('new-subj-key').value.trim().toLowerCase();
  const name = document.getElementById('new-subj-name').value.trim();
  const icon = document.getElementById('new-subj-icon').value.trim();
  const cap = parseInt(document.getElementById('new-subj-cap').value, 10) || 5;
  if(!key || !name){ statusEl.textContent = 'Enter a key and display name.'; return; }
  try{
    await api('/api/admin/subjects', {method:'POST', body:{key, name, icon: icon || undefined, demo_level_cap: cap}});
    statusEl.textContent = `"${name}" added.`;
    toast('Subject added');
    ['new-subj-key','new-subj-name','new-subj-icon'].forEach(id=>document.getElementById(id).value='');
    document.getElementById('new-subj-cap').value = '5';
    await renderAdminSubjectCaps();
    await renderAdminGradeSubjectList();
  }catch(err){
    statusEl.textContent = err.message || 'Could not add that subject.';
  }
}
async function deleteSubject(key){
  if(!confirm(`Delete the "${key}" subject? This also removes it from every grade mapping.`)) return;
  try{
    await api(`/api/admin/subjects/${encodeURIComponent(key)}`, {method:'DELETE'});
    toast('Subject deleted');
    await renderAdminSubjectCaps();
    await renderAdminGradeSubjectList();
  }catch(err){
    toast(err.message || 'Could not delete that subject');
  }
}

/* =========================================================
   ADMIN — grade \u2192 subject mapping
   ========================================================= */
async function addGradeBand(){
  const input = document.getElementById('new-grade-band');
  const grade = input.value.trim();
  if(!grade){ toast('Enter a grade'); return; }
  try{
    await api(`/api/admin/grade-subjects/${encodeURIComponent(grade)}`, {method:'PUT', body:{subject_keys: []}});
    input.value = '';
    toast(`Grade ${grade} added — now pick its subjects below`);
    await renderAdminGradeSubjectList();
  }catch(err){
    toast(err.message || 'Could not add that grade');
  }
}
async function renderAdminGradeSubjectList(){
  const wrap = document.getElementById('admin-grade-subject-list');
  if(!wrap) return;
  let mappings, allSubjects;
  try{
    [mappings, allSubjects] = await Promise.all([
      api('/api/admin/grade-subjects'),
      api('/api/admin/subjects'),
    ]);
  }catch(err){
    wrap.innerHTML = `<p class="empty-note">${err.message || 'Could not load grade mappings'}</p>`;
    return;
  }
  if(mappings.length === 0){
    wrap.innerHTML = '<p class="empty-note">No grade bands configured yet — every grade currently sees every subject. Add a grade above to start restricting.</p>';
    return;
  }
  wrap.innerHTML = mappings.map(m => {
    const selectedKeys = new Set(m.subjects.map(s => s.key));
    return `
    <div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--paper-line);">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <b>Grade ${escapeHtml(m.grade)}</b>
        <button onclick="deleteGradeBand('${m.grade}')">Remove grade</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
        ${allSubjects.map(s => `
          <label style="display:flex;align-items:center;gap:6px;font-size:13px;background:var(--paper-line);padding:6px 10px;border-radius:20px;cursor:pointer;">
            <input type="checkbox" class="grade-subj-${m.grade}" value="${s.key}" ${selectedKeys.has(s.key)?'checked':''} style="width:auto;">
            ${s.icon||''} ${escapeHtml(s.name)}
          </label>`).join('')}
      </div>
      <button class="btn-primary" onclick="saveGradeSubjects('${m.grade}')">Save Grade ${escapeHtml(m.grade)}</button>
    </div>`;
  }).join('');
}
async function saveGradeSubjects(grade){
  const checked = Array.from(document.querySelectorAll(`.grade-subj-${grade}:checked`)).map(el => el.value);
  try{
    await api(`/api/admin/grade-subjects/${encodeURIComponent(grade)}`, {method:'PUT', body:{subject_keys: checked}});
    toast(`Grade ${grade} updated`);
  }catch(err){
    toast(err.message || 'Could not save');
  }
}
async function deleteGradeBand(grade){
  if(!confirm(`Remove grade ${grade}'s subject mapping? It will fall back to showing every subject.`)) return;
  try{
    await api(`/api/admin/grade-subjects/${encodeURIComponent(grade)}`, {method:'DELETE'});
    toast('Grade mapping removed');
    await renderAdminGradeSubjectList();
  }catch(err){
    toast(err.message || 'Could not remove that grade');
  }
}

/* =========================================================
   ADMIN — visual theme management
   ========================================================= */
async function uploadTheme(){
  const statusEl = document.getElementById('theme-upload-status');
  const key = document.getElementById('new-theme-key').value.trim().toLowerCase();
  const name = document.getElementById('new-theme-name').value.trim();
  const bgInput = document.getElementById('new-theme-bg');
  const iconsInput = document.getElementById('new-theme-icons');
  const bgFile = bgInput.files[0];

  if(!key || !name){ statusEl.textContent = 'Enter a theme key and display name.'; return; }
  if(!bgFile){ statusEl.textContent = 'Choose a background image.'; return; }

  const form = new FormData();
  form.append('key', key);
  form.append('name', name);
  form.append('background', bgFile);
  for(const f of iconsInput.files) form.append('icons', f);

  statusEl.textContent = 'Uploading…';
  try{
    const theme = await api('/api/admin/themes', {method:'POST', body:form, isForm:true});
    statusEl.textContent = `"${theme.name}" added successfully${theme.icon_count ? ` with ${theme.icon_count} icon${theme.icon_count===1?'':'s'}` : ''}.`;
    toast(`Theme "${theme.name}" added`);
    document.getElementById('new-theme-key').value = '';
    document.getElementById('new-theme-name').value = '';
    bgInput.value = '';
    iconsInput.value = '';
    await renderAdminThemeList();
  }catch(err){
    statusEl.textContent = err.message || 'Could not upload that theme.';
    toast(err.message || 'Theme upload failed');
  }
}
let EXPANDED_THEME_KEYS = new Set(); // which theme cards are currently showing their edit panel

async function renderAdminThemeList(){
  const wrap = document.getElementById('admin-theme-list');
  if(!wrap) return;
  let themes;
  try{ themes = await api('/api/admin/themes'); }
  catch(err){ wrap.innerHTML = `<p class="empty-note">${err.message || 'Could not load themes'}</p>`; return; }
  if(!themes.length){ wrap.innerHTML = '<p class="empty-note">No themes uploaded yet — add one above.</p>'; return; }

  wrap.innerHTML = themes.map(t => {
    const isOpen = EXPANDED_THEME_KEYS.has(t.key);
    const iconThumbs = Array.from({length: t.icon_count}, (_, i) => `
      <div style="position:relative;display:inline-block;margin:0 6px 6px 0;">
        <img src="${API_BASE}/api/themes/${encodeURIComponent(t.key)}/icons/${i}" alt=""
             style="width:52px;height:52px;border-radius:8px;object-fit:cover;display:block;">
        <button onclick="deleteThemeIcon('${t.key}', ${i})" title="Remove this icon"
                style="position:absolute;top:-6px;right:-6px;width:20px;height:20px;border-radius:50%;background:#E15554;color:#fff;font-size:12px;line-height:1;border:2px solid var(--paper);cursor:pointer;">✕</button>
      </div>`).join('');

    return `
    <div class="user-row" style="flex-wrap:wrap;">
      <img src="${API_BASE}/api/themes/${encodeURIComponent(t.key)}/background" alt=""
           style="width:44px;height:44px;border-radius:10px;object-fit:cover;flex-shrink:0;">
      <div class="meta"><b>${escapeHtml(t.name)}</b><span>${escapeHtml(t.key)} · ${t.icon_count} icon${t.icon_count===1?'':'s'}</span></div>
      <button onclick="toggleThemeEdit('${t.key}')">${isOpen ? 'Close' : 'Edit'}</button>
      <button onclick="deleteTheme('${t.key}')">Remove</button>
      ${isOpen ? `
      <div style="flex-basis:100%;margin-top:14px;padding-top:14px;border-top:1px solid var(--paper-line);">
        <div class="field"><label>Display name</label><input id="edit-theme-name-${t.key}" value="${escapeHtml(t.name)}"></div>
        <div class="field"><label>Replace background image (optional)</label><input type="file" id="edit-theme-bg-${t.key}" accept="image/*"></div>
        <button class="btn-primary" onclick="saveThemeEdit('${t.key}')">Save changes</button>
        <p class="msg-note" id="edit-theme-status-${t.key}"></p>

        <div style="margin-top:16px;">
          <label style="display:block;font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#948c68;margin-bottom:8px;">Character icons</label>
          <div>${iconThumbs || '<p class="empty-note">No icons yet.</p>'}</div>
        </div>
        <div class="field" style="margin-top:10px;"><label>Add more icons</label><input type="file" id="edit-theme-add-icons-${t.key}" accept="image/*" multiple></div>
        <button class="btn-primary" onclick="addIconsToExistingTheme('${t.key}')">Add icons</button>
        <p class="msg-note" id="edit-theme-icons-status-${t.key}"></p>
      </div>` : ''}
    </div>`;
  }).join('');
}
function toggleThemeEdit(key){
  if(EXPANDED_THEME_KEYS.has(key)) EXPANDED_THEME_KEYS.delete(key);
  else EXPANDED_THEME_KEYS.add(key);
  renderAdminThemeList();
}
async function saveThemeEdit(key){
  const statusEl = document.getElementById(`edit-theme-status-${key}`);
  const name = document.getElementById(`edit-theme-name-${key}`).value.trim();
  const bgInput = document.getElementById(`edit-theme-bg-${key}`);
  const form = new FormData();
  if(name) form.append('name', name);
  if(bgInput.files[0]) form.append('background', bgInput.files[0]);
  statusEl.textContent = 'Saving…';
  try{
    const theme = await api(`/api/admin/themes/${encodeURIComponent(key)}`, {method:'PUT', body:form, isForm:true});
    statusEl.textContent = `"${theme.name}" updated successfully.`;
    toast('Theme updated');
    bgInput.value = '';
    await renderAdminThemeList();
  }catch(err){
    statusEl.textContent = err.message || 'Could not save changes.';
    toast(err.message || 'Update failed');
  }
}
async function addIconsToExistingTheme(key){
  const statusEl = document.getElementById(`edit-theme-icons-status-${key}`);
  const input = document.getElementById(`edit-theme-add-icons-${key}`);
  if(!input.files.length){ statusEl.textContent = 'Choose at least one icon image.'; return; }
  const form = new FormData();
  for(const f of input.files) form.append('icons', f);
  statusEl.textContent = 'Uploading…';
  try{
    const theme = await api(`/api/admin/themes/${encodeURIComponent(key)}/icons`, {method:'POST', body:form, isForm:true});
    statusEl.textContent = `Now ${theme.icon_count} icon${theme.icon_count===1?'':'s'} added successfully.`;
    toast('Icons added');
    input.value = '';
    await renderAdminThemeList();
  }catch(err){
    statusEl.textContent = err.message || 'Could not add icons.';
    toast(err.message || 'Icon upload failed');
  }
}
async function deleteThemeIcon(key, index){
  if(!confirm('Remove this icon?')) return;
  try{
    await api(`/api/admin/themes/${encodeURIComponent(key)}/icons/${index}`, {method:'DELETE'});
    toast('Icon removed');
    await renderAdminThemeList();
  }catch(err){
    toast(err.message || 'Could not remove icon');
  }
}
async function deleteTheme(key){
  if(!confirm(`Delete the "${key}" theme? Students using it will fall back to Classic.`)) return;
  try{
    await api(`/api/admin/themes/${encodeURIComponent(key)}`, {method:'DELETE'});
    EXPANDED_THEME_KEYS.delete(key);
    toast('Theme deleted');
    await renderAdminThemeList();
  }catch(err){
    toast(err.message || 'Could not delete theme');
  }
}

/* =========================================================
   ADMIN — question bank browser (see searchAdminQuestions above)
   ========================================================= */
async function deleteQuestion(id){
  if(!confirm('Delete this question permanently from the bank?')) return;
  try{
    await api(`/api/admin/questions/${id}`, {method:'DELETE'});
    await searchAdminQuestions(true);
    toast('Question deleted');
  }catch(err){
    toast(err.message || 'Could not delete question');
  }
}
let STATE_editingQuestionId = null;

function openAddModal(){
  STATE_editingQuestionId = null;
  document.getElementById('add-modal-title').textContent = 'Add a question';
  document.getElementById('add-modal-submit-btn').textContent = 'Save question';
  ['new-qtext','new-optA','new-optB','new-optC','new-optD','new-expl','new-topic','new-hint','new-grade'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('new-level').value = 1;
  document.getElementById('new-correct').value = '0';
  populateSubjectSelect('new-subject');
  document.getElementById('add-modal').classList.add('active');
}
function openEditModal(q){
  STATE_editingQuestionId = q.id;
  document.getElementById('add-modal-title').textContent = `Edit question #${q.id}`;
  document.getElementById('add-modal-submit-btn').textContent = 'Save changes';
  populateSubjectSelect('new-subject', q.subject);
  document.getElementById('new-level').value = q.level;
  document.getElementById('new-grade').value = q.grade || '';
  document.querySelectorAll('input[name="new-board"]').forEach(r => r.checked = (r.value === q.board));
  document.getElementById('new-qtext').value = q.question;
  document.getElementById('new-optA').value = q.option_a;
  document.getElementById('new-optB').value = q.option_b;
  document.getElementById('new-optC').value = q.option_c;
  document.getElementById('new-optD').value = q.option_d;
  document.getElementById('new-correct').value = String(q.correct);
  document.getElementById('new-expl').value = q.explanation || '';
  document.getElementById('new-topic').value = q.topic || '';
  document.getElementById('new-hint').value = q.hint || '';
  document.getElementById('add-modal').classList.add('active');
}
function closeAddModal(){
  document.getElementById('add-modal').classList.remove('active');
  STATE_editingQuestionId = null;
}
async function submitQuestionForm(){
  const subject = document.getElementById('new-subject').value;
  const level = parseInt(document.getElementById('new-level').value);
  const grade = document.getElementById('new-grade').value.trim();
  const board = document.querySelector('input[name="new-board"]:checked').value;
  const qtext = document.getElementById('new-qtext').value.trim();
  const a = document.getElementById('new-optA').value.trim();
  const b = document.getElementById('new-optB').value.trim();
  const c = document.getElementById('new-optC').value.trim();
  const d = document.getElementById('new-optD').value.trim();
  const correct = parseInt(document.getElementById('new-correct').value);
  const expl = document.getElementById('new-expl').value.trim();
  const topic = document.getElementById('new-topic').value.trim();
  const hint = document.getElementById('new-hint').value.trim();
  if(!subject){ toast('Choose a subject'); return; }
  if(!qtext || !a || !b || !c || !d){ toast('Fill in the question and all 4 options'); return; }
  const body = {
    level, board, question: qtext,
    option_a:a, option_b:b, option_c:c, option_d:d, correct, explanation: expl,
    topic: topic || undefined, hint: hint || undefined, grade: grade || undefined,
  };
  try{
    if(STATE_editingQuestionId){
      await api(`/api/admin/questions/${STATE_editingQuestionId}`, {method:'PUT', body});
      toast('Question updated');
    } else {
      await api('/api/admin/questions', {method:'POST', body:{subject, ...body}});
      toast('Question added to the bank');
    }
    closeAddModal();
    await searchAdminQuestions(true);
  }catch(err){
    toast(err.message || 'Could not save question');
  }
}

/* ---------- admin tabs ---------- */
function switchAdminTab(tabId){
  document.querySelectorAll('.admin-tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.admin-tab-btn').forEach(el => el.classList.toggle('active', el.dataset.tab === tabId));
  document.getElementById(tabId).classList.add('active');
}

/* ---------- question search (replaces the old "load everything" browser) ---------- */
function populateSubjectSelect(selectId, selected){
  const sel = document.getElementById(selectId);
  if(!sel) return;
  const keys = (STATE.allGradeSubjectKeys && STATE.allGradeSubjectKeys.length) ? STATE.allGradeSubjectKeys : SUBJECTS.map(s=>s.key);
  const includeAny = selectId === 'qf-subject';
  sel.innerHTML = (includeAny ? '<option value="">Any</option>' : '') + keys.map(key => {
    const meta = subjMeta(key) || {name: key, icon: '📘'};
    return `<option value="${key}">${meta.icon || ''} ${escapeHtml(meta.name || key)}</option>`;
  }).join('');
  if(selected) sel.value = selected;
}
async function searchAdminQuestions(quiet){
  const filters = {
    subject: document.getElementById('qf-subject').value,
    grade: document.getElementById('qf-grade').value.trim(),
    level: document.getElementById('qf-level').value,
    question_id: document.getElementById('qf-id').value,
    status: document.getElementById('qf-status').value,
    topic: document.getElementById('qf-topic').value.trim(),
    search: document.getElementById('qf-search').value.trim(),
  };
  const hasAnyFilter = Object.values(filters).some(v => v);
  const wrap = document.getElementById('admin-section');
  if(!hasAnyFilter){
    if(!quiet) toast('Pick at least one filter first');
    wrap.innerHTML = '<p class="empty-note">Choose at least one filter above, then hit Search.</p>';
    return;
  }
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k,v]) => { if(v) params.set(k, v); });
  let results;
  try{ results = await api(`/api/admin/questions?${params.toString()}`); }
  catch(err){ toast(err.message || 'Search failed'); return; }

  if(!results.length){ wrap.innerHTML = '<p class="empty-note">No questions match those filters.</p>'; return; }
  const letters = ['A','B','C','D'];
  wrap.innerHTML = `<p class="msg-note" style="margin-bottom:10px;">${results.length} result${results.length===1?'':'s'}${results.length===50?' (showing first 50 — narrow your filters for more precision)':''}</p>` +
    results.map(q => {
      const opts = [q.option_a, q.option_b, q.option_c, q.option_d];
      const meta = subjMeta(q.subject);
      return `<div class="q-row">
        <div class="optlist" style="margin-bottom:4px;">#${q.id} · ${meta ? meta.icon+' '+escapeHtml(meta.name) : escapeHtml(q.subject)} · Level ${q.level}${q.grade ? ' · Grade '+escapeHtml(q.grade) : ''} · ${q.status}</div>
        <div class="qtxt">${escapeHtml(q.question)}</div>
        <div class="optlist">${opts.map((o,i)=> i===q.correct ? `<b>${letters[i]}. ${escapeHtml(o)} ✓</b>` : `${letters[i]}. ${escapeHtml(o)}`).join('<br>')}</div>
        ${q.explanation ? `<div class="optlist" style="margin-top:6px;font-style:italic;">💡 ${escapeHtml(q.explanation)}</div>` : ''}
        <div class="qactions">
          <button onclick='openEditModal(${JSON.stringify(q).replace(/'/g,"&apos;")})'>Edit</button>
          <button class="del-btn" onclick="deleteQuestion(${q.id})">Delete</button>
        </div>
      </div>`;
    }).join('');
}
function clearAdminQuestionFilters(){
  ['qf-grade','qf-level','qf-id','qf-topic','qf-search'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('qf-subject').value = '';
  document.getElementById('qf-status').value = '';
  document.getElementById('admin-section').innerHTML = '<p class="empty-note">Choose at least one filter above, then hit Search.</p>';
}

/* =========================================================
   INIT — resume a session if a token is already stored
   ========================================================= */
renderAvatarPicker();
(async function init(){
  // Admin, performance and TOC are now separate pages. They reuse the same
  // shared API/session code but initialize only the UI that exists on that page.
  if(SQ_PAGE === 'admin'){
    if(!STATE.token){ goto('screen-admin-login'); return; }
    try{
      const me = await api('/api/auth/me');
      STATE.user = {userid:me.userid,name:me.name,role:me.role,avatar:me.avatar,grade:me.grade,board:me.board,theme:me.theme||'classic',account_tier:me.account_tier||'silver'};
      if(me.role !== 'admin'){ window.location.href='index.html'; return; }
      STATE.isAdmin=true;
      localStorage.setItem('sq_user',JSON.stringify(STATE.user));
      await loadThemes(); applyTheme(STATE.user.theme);
      goto('screen-admin');
      try{
        await renderAdminSubjRow();
        await searchAdminQuestions(true);
        renderAvatarPicker();
        await renderAdminStudentList();
        await renderAdminThemeList();
        await renderAdminSubjectCaps();
        await renderAdminGradeSubjectList();
      }catch(panelErr){ console.error('Admin panel failed to fully load:',panelErr); }
    }catch(err){
      localStorage.removeItem('sq_token'); localStorage.removeItem('sq_user');
      goto('screen-admin-login');
    }
    return;
  }

  if(!STATE.token){
    if(SQ_PAGE === 'index') goto('screen-auth');
    else window.location.href='index.html';
    return;
  }

  try{
    const cachedUser = JSON.parse(localStorage.getItem('sq_user') || 'null');
    const cachedProgress = JSON.parse(localStorage.getItem('sq_progress') || 'null');
    if(cachedUser) STATE.user=cachedUser;
    if(cachedProgress) STATE.progress=cachedProgress;
  }catch(e){}

  try{
    const me = await api('/api/auth/me');
    STATE.user={userid:me.userid,name:me.name,role:me.role,avatar:me.avatar,grade:me.grade,board:me.board,theme:me.theme||'classic',account_tier:me.account_tier||'silver'};
    localStorage.setItem('sq_user',JSON.stringify(STATE.user));
    await loadThemes(); applyTheme(STATE.user.theme);

    if(me.role === 'admin'){
      if(SQ_PAGE !== 'admin'){ window.location.href='admin.html'; return; }
      STATE.isAdmin=true; goto('screen-admin'); return;
    }

    await loadMyProgress();

    if(SQ_PAGE === 'performance'){
      if(STATE.user.account_tier === 'guest'){ window.location.href='index.html'; return; }
      goto('screen-performance'); await loadPerformanceDashboard(); return;
    }

    if(SQ_PAGE === 'toc'){
      let req=null; try{ req=JSON.parse(localStorage.getItem('sq_toc_request')||'null'); }catch(e){}
      if(req) localStorage.removeItem('sq_toc_request');
      const subject=req?.subject || (STATE.user.board?.toLowerCase()==='cbse' && String(STATE.user.grade)==='11' ? 'mathematics' : Object.keys(STATE.progress)[0]);
      if(subject) await openTableOfContent(req?.board || STATE.user.board || 'cbse', req?.grade || STATE.user.grade || 11, subject);
      return;
    }

    // Main student shell.
    const pendingQuiz = (()=>{try{const q=JSON.parse(localStorage.getItem('sq_quiz_redirect')||'null');localStorage.removeItem('sq_quiz_redirect');return q;}catch(e){return null;}})();
    if(pendingQuiz){
      STATE.quiz=pendingQuiz;
      STATE.quiz.timerId=null;
      if(STATE.quiz.deadline && STATE.quiz.deadline>Date.now()) startQuizTimerFromDeadline();
      else if(STATE.quiz.deadline) { STATE.quiz.finished=true; finishQuizBatch(true); return; }
      renderQuestion(); goto('screen-quiz'); return;
    }
    const pendingMap = localStorage.getItem('sq_map_request');
    if(pendingMap){ localStorage.removeItem('sq_map_request'); if(STATE.progress[pendingMap]){ openSubjectLevelMap(pendingMap); return; } }
    enterHome();
  }catch(err){
    console.warn('Session validation failed:',err);
    if(SQ_PAGE === 'index' && STATE.user){ enterHome(); return; }
    window.location.href='index.html';
  }
})();
