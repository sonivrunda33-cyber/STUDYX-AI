(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const csrf = $('meta[name="csrf-token"]')?.content || '';
  const workspace = $('#workspaceContent');
  const page = workspace?.dataset.page || '';
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cache = { subjects: [], assignments: [], exams: [], notes: [], events: [] };

  const esc = (value = '') => String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const parseDate = value => value ? new Date(value) : null;
  const dateKey = value => {
    const d = value instanceof Date ? value : parseDate(value);
    return d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` : '';
  };
  const localInputDate = (date = new Date()) => `${dateKey(date)}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  const toISO = value => value ? new Date(value).toISOString() : null;
  const prettyDate = (value, options = { month: 'short', day: 'numeric' }) => {
    const date = parseDate(value);
    return date ? new Intl.DateTimeFormat(undefined, options).format(date) : 'No date';
  };
  const prettyTime = value => {
    const date = parseDate(value);
    return date ? new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date) : '';
  };
  const durationLabel = minutes => {
    const value = Math.max(0, Number(minutes) || 0);
    const hours = Math.floor(value / 60), rem = value % 60;
    return hours ? `${hours}h${rem ? ` ${rem}m` : ''}` : `${rem}m`;
  };
  const toast = (message, kind = '') => {
    const stack = $('#toastStack');
    if (!stack) return;
    const item = document.createElement('div');
    item.className = `toast ${kind}`;
    item.textContent = message;
    stack.append(item);
    setTimeout(() => item.remove(), 3800);
  };
  const api = async (path, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    if (!['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase())) headers.set('X-CSRF-Token', csrf);
    const response = await fetch(`/api${path}`, { ...options, headers, cache: 'no-store', credentials: 'same-origin' });
    const content = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) location.href = '/login';
      throw new Error(content.error || `Request failed (${response.status}).`);
    }
    return content;
  };
  const formData = form => {
    const result = Object.fromEntries(new FormData(form).entries());
    for (const key of Object.keys(result)) {
      if (key.endsWith('_at') && result[key]) result[key] = toISO(result[key]);
      else if (key === 'subject_id') result[key] = result[key] ? Number(result[key]) : null;
      else if (result[key] === '') result[key] = null;
    }
    return result;
  };
  const safeRequest = async (work, success) => {
    try { const result = await work(); if (success) toast(success); return result; }
    catch (error) { toast(error.message || 'Something went wrong. Please try again.', 'error'); trackUsage('ui_error', { page }); return null; }
  };
  function trackUsage(eventName, detail = {}, durationMs = null) {
    if (!workspace) return;
    api('/usage-events', { method: 'POST', keepalive: true, body: JSON.stringify({
      event_name: eventName, page, duration_ms: durationMs, detail,
    }) }).catch(() => {});
  }
  const empty = (title, copy, icon = '✳') => `<div class="empty-state"><span>${icon}</span><h3>${esc(title)}</h3><p>${esc(copy)}</p></div>`;
  const setHTML = (selector, html) => { const node = $(selector); if (node) node.innerHTML = html; };

  // Persist theme locally for an instant response, then on the account profile.
  function applyTheme(theme) {
    const mode = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = mode;
    document.body.dataset.theme = mode;
    localStorage.setItem('studyx-theme', mode);
    $$('[data-theme-icon]').forEach(node => node.textContent = mode === 'dark' ? '☀' : '◐');
  }
  const startTheme = (workspace ? document.documentElement.dataset.theme : localStorage.getItem('studyx-theme')) || 'light';
  applyTheme(startTheme);
  document.addEventListener('click', event => {
    const toggle = event.target.closest('[data-theme-toggle]');
    const set = event.target.closest('[data-set-theme]');
    if (!toggle && !set) return;
    event.preventDefault();
    const next = set ? set.dataset.setTheme : (document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    applyTheme(next);
    if (workspace) safeRequest(() => api('/preferences', { method: 'PATCH', body: JSON.stringify({ preferences: { theme_mode: next } }) }));
  });

  // Shared shell controls, mobile drawer and quick add.
  const quickAdd = $('#quickAdd');
  document.addEventListener('click', event => {
    if (event.target.closest('[data-global-create]')) quickAdd?.classList.add('is-open');
    if (event.target.closest('[data-close-quick]') || event.target === quickAdd) quickAdd?.classList.remove('is-open');
    const panelToggle = event.target.closest('[data-toggle-panel]');
    if (panelToggle) $(`#${CSS.escape(panelToggle.dataset.togglePanel)}`)?.classList.toggle('is-open');
    const menu = event.target.closest('#mobileMenu');
    if (menu) { $('#sidebar')?.classList.toggle('is-open'); $('#mobileScrim')?.classList.toggle('is-open'); }
    if (event.target.closest('#mobileScrim')) { $('#sidebar')?.classList.remove('is-open'); $('#mobileScrim')?.classList.remove('is-open'); }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault(); $('#globalSearch')?.focus();
    }
    if (event.key === 'Escape') {
      quickAdd?.classList.remove('is-open'); $('#eventModal')?.classList.remove('is-open');
      $('#sidebar')?.classList.remove('is-open'); $('#mobileScrim')?.classList.remove('is-open');
    }
  });
  if (workspace) {
    const pageStartedAt = performance.now();
    trackUsage('page_view', { page });
    document.addEventListener('click', event => {
      const control = event.target.closest('button, a');
      if (!control) return;
      const actionKey = [...control.attributes]
        .find(attribute => attribute.name.startsWith('data-'))?.name || '';
      trackUsage('control_click', { control: control.id || actionKey || control.tagName.toLowerCase() });
    }, { capture: true });
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        const duration = Math.max(0, Math.round(performance.now() - pageStartedAt));
        trackUsage('page_time', {}, duration);
      }
    });
  }
  $$('a[href^="/"]').forEach(link => link.addEventListener('click', () => {
    if (!reducedMotion && !link.target && !link.href.includes('#')) $('#pageLoader')?.classList.add('active');
  }));

  // Subtle pointer depth on 3D cards, disabled for touch and reduced motion.
  if (!reducedMotion && matchMedia('(pointer:fine)').matches) {
    let frame = 0;
    document.addEventListener('pointermove', event => {
      const card = event.target.closest('[data-tilt]');
      if (!card) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = card.getBoundingClientRect();
        const x = (event.clientX - box.left) / box.width - .5;
        const y = (event.clientY - box.top) / box.height - .5;
        card.style.transform = `perspective(900px) rotateX(${(-y * 5).toFixed(2)}deg) rotateY(${(x * 6).toFixed(2)}deg) translateY(-2px)`;
      });
    });
    document.addEventListener('pointerout', event => {
      const card = event.target.closest('[data-tilt]');
      if (card && !card.contains(event.relatedTarget)) card.style.transform = '';
    });
  }

  async function loadSubjects() {
    cache.subjects = await api('/subjects');
    $$('[data-subject-options]').forEach(select => {
      const keep = select.value;
      const first = select.options[0]?.outerHTML || '<option value="">Independent study</option>';
      select.innerHTML = first + cache.subjects.map(item => `<option value="${item.id}">${esc(item.name)}</option>`).join('');
      if (keep) select.value = keep;
    });
  }

  // Overview from saved activity only; no quiz-average metric is shown here.
  async function initDashboard() {
    const data = await api('/dashboard');
    const firstName = (data.profile.full_name || 'Student').split(' ')[0];
    const greeting = $('#todayGreeting');
    if (greeting) greeting.textContent = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date()).toUpperCase();
    const heading = $('.welcome-row h1');
    if (heading) heading.innerHTML = `Good day, <em>${esc(firstName)}.</em>`;
    const week = $('#metricWeek'); if (week) week.textContent = durationLabel(data.study.week_minutes);
    const weekHero = $('#heroWeekTime'); if (weekHero) weekHero.textContent = durationLabel(data.study.week_minutes);
    const assignments = $('#metricAssignments'); if (assignments) assignments.textContent = `${data.assignments.completed} / ${data.assignments.total}`;
    const assignFoot = $('#metricAssignmentFoot'); if (assignFoot) assignFoot.textContent = data.assignments.total ? `${Math.round((data.assignments.completed / data.assignments.total) * 100)}% completed` : 'No saved assignments yet';
    const sessions = $('#metricSessions'); if (sessions) sessions.textContent = data.study.session_count;
    const streak = $('#metricStreak'); if (streak) streak.textContent = `${data.study.streak_days} active study days`;
    const exam = $('#metricExam'); if (exam) exam.textContent = data.exams.next ? prettyDate(data.exams.next.exam_at, { month: 'short', day: 'numeric' }) : 'None yet';
    const examFoot = $('#metricExamFoot'); if (examFoot) examFoot.textContent = data.exams.next ? data.exams.next.title : 'Add a date when you know it';
    const taskProgress = $('#heroTaskProgress'); if (taskProgress) taskProgress.textContent = `${data.assignments.completed}/${data.assignments.total}`;
    $('#navAssignmentCount') && ($('#navAssignmentCount').textContent = String(data.assignments.upcoming.length));
    const notificationDot = $('#navNotificationDot'); if (notificationDot) notificationDot.style.display = data.unread_notifications ? 'block' : 'none';
    const topDot = $('#notificationDot'); if (topDot) topDot.style.display = data.unread_notifications ? 'block' : 'none';
    const goalTitle = $('#dashboardGoalTitle'), goalCopy = $('#dashboardGoalCopy');
    if (data.goal && goalTitle) { goalTitle.textContent = data.goal.title; goalCopy.textContent = `${durationLabel(data.goal.current_minutes)} of ${durationLabel(data.goal.target_minutes)} saved toward your goal.`; }
    const chart = $('#dashboardChart');
    if (chart) chart.innerHTML = data.study.by_day.map(day => {
      const height = Math.min(100, Math.max(day.minutes ? 7 : 2, (day.minutes / Math.max(60, ...data.study.by_day.map(x => x.minutes))) * 100));
      return `<div class="chart-day ${dateKey(day.date) === dateKey(new Date()) ? 'today' : ''}"><div><i style="height:${height}%" title="${day.minutes} minutes"></i></div><span>${esc(day.label)}</span></div>`;
    }).join('');
    const list = $('#dashboardUpcoming');
    if (list) list.innerHTML = data.assignments.upcoming.length ? data.assignments.upcoming.map(item => `<div class="data-row">${taskCheckbox(item)}<span class="row-date">${esc(prettyDate(item.due_at, { month: 'short', day: 'numeric' }))}</span><span class="row-copy"><b>${esc(item.title)}</b><small>${esc(item.subject || 'Independent')} · due ${esc(prettyTime(item.due_at))}</small></span><span class="status-pill priority-${esc(item.priority)}">${esc(item.priority)}</span></div>`).join('') : empty('A little breathing room.', 'Add an assignment when there is something you want to keep in sight.', '✓');
    const weekStart = new Date(); weekStart.setHours(0, 0, 0, 0); weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1);
    const weekEnd = new Date(weekStart); weekEnd.setDate(weekEnd.getDate() + 7);
    const events = await api(`/calendar-events?start=${encodeURIComponent(weekStart.toISOString())}&end=${encodeURIComponent(weekEnd.toISOString())}`);
    renderMiniCalendar(events);
    const eventList = $('#dashboardEvents');
    if (eventList) eventList.innerHTML = events.slice(0, 3).map(item => `<div class="mini-event"><i></i><span>${esc(prettyDate(item.starts_at))} · ${esc(item.title)}</span></div>`).join('') || '<small class="form-footnote">Your saved plans appear here.</small>';
  }
  function renderMiniCalendar(events = []) {
    const node = $('#dashboardMiniCalendar'); if (!node) return;
    const today = new Date(), first = new Date(today.getFullYear(), today.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7;
    const days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(day => `<span class="weekday">${day}</span>`).join('');
    const cells = Array.from({ length: 42 }, (_, index) => {
      const day = new Date(first.getFullYear(), first.getMonth(), 1 - offset + index), key = dateKey(day);
      const classes = [key === dateKey(today) ? 'today' : '', events.some(event => dateKey(event.starts_at) === key) ? 'has-event' : ''].filter(Boolean).join(' ');
      return `<span class="${classes}">${day.getDate()}</span>`;
    }).join('');
    node.innerHTML = days + cells;
  }

  // Calendar with one shared event stream for assignments, exams, revisions and study sessions.
  let calMonth = new Date(), calSelected = new Date(), calView = 'month', calendarEvents = [];
  function calendarRange() {
    const first = new Date(calMonth.getFullYear(), calMonth.getMonth(), 1);
    const mondayOffset = (first.getDay() + 6) % 7;
    const start = new Date(first); start.setDate(1 - mondayOffset); start.setHours(0, 0, 0, 0);
    const end = new Date(start); end.setDate(start.getDate() + 42); end.setHours(0, 0, 0, 0);
    return [start, end];
  }
  async function loadCalendar() {
    if (!$('#calendarGrid')) return;
    const [start, end] = calendarRange();
    calendarEvents = await api(`/calendar-events?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`);
    renderCalendar();
  }
  function renderCalendar() {
    const grid = $('#calendarGrid'); if (!grid) return;
    $('#calendarMonthTitle').textContent = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(calMonth);
    const first = new Date(calMonth.getFullYear(), calMonth.getMonth(), 1), mondayOffset = (first.getDay() + 6) % 7;
    let dates = Array.from({ length: 42 }, (_, index) => new Date(first.getFullYear(), first.getMonth(), 1 - mondayOffset + index));
    if (calView === 'week') {
      const selected = new Date(calSelected); selected.setHours(0, 0, 0, 0);
      const offset = (selected.getDay() + 6) % 7; const monday = new Date(selected); monday.setDate(selected.getDate() - offset);
      dates = Array.from({ length: 7 }, (_, index) => new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + index));
    }
    if (calView === 'agenda') {
      const chosenKey = dateKey(calSelected);
      const upcoming = calendarEvents.filter(item => dateKey(item.starts_at) >= chosenKey).slice(0, 21);
      grid.classList.add('agenda-grid');
      $('.calendar-weekdays')?.classList.add('agenda-hidden');
      grid.innerHTML = upcoming.length ? upcoming.map(item => `<div class="agenda-row ${item.status === 'done' ? 'is-done' : ''}" data-agenda-date="${esc(dateKey(item.starts_at))}">${item.assignment_id ? taskCheckbox({id: item.assignment_id, title: item.title, status: item.status}) : ''}<span class="row-date">${esc(prettyDate(item.starts_at, { weekday: 'short', day: 'numeric', month: 'short' }))}</span><span class="row-copy"><b>${esc(item.title)}</b><small>${esc(item.subject || item.event_type)} · ${esc(prettyTime(item.starts_at))}</small></span><span class="status-pill">${esc(item.status === 'done' ? 'Completed' : item.event_type)}</span></div>`).join('') : empty('Nothing is on the horizon yet.', 'Assignments, exams and study sessions saved to your account will appear here.', '▦');
      $('.calendar-grid')?.classList.toggle('agenda-grid', true);
      renderSelectedDay(); return;
    }
    grid.classList.remove('agenda-grid'); $('.calendar-weekdays')?.classList.remove('agenda-hidden');
    grid.innerHTML = dates.map(day => {
      const key = dateKey(day), dayEvents = calendarEvents.filter(item => dateKey(item.starts_at) === key);
      const classes = [day.getMonth() !== calMonth.getMonth() ? 'outside-month' : '', key === dateKey(new Date()) ? 'today' : '', key === dateKey(calSelected) ? 'selected' : ''].filter(Boolean).join(' ');
      const chips = dayEvents.slice(0, 2).map(item => `<div class="calendar-event-chip event-${esc(item.event_type)}" title="${esc(item.title)}">${esc(item.title)}</div>`).join('');
      return `<div class="calendar-cell ${classes}" data-calendar-date="${key}"><span class="calendar-day-number">${day.getDate()}</span>${chips}${dayEvents.length > 2 ? `<div class="calendar-more">+${dayEvents.length - 2} more</div>` : ''}</div>`;
    }).join('');
    renderSelectedDay();
  }
  function renderSelectedDay() {
    const key = dateKey(calSelected), title = $('#selectedDayTitle'), target = $('#selectedDayEvents');
    if (title) title.textContent = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'short', day: 'numeric' }).format(calSelected);
    if (!target) return;
    const events = calendarEvents.filter(item => dateKey(item.starts_at) === key);
    target.innerHTML = events.length ? events.map(item => `<div class="data-row ${item.status === 'done' ? 'is-done' : ''}">${item.assignment_id ? taskCheckbox({id: item.assignment_id, title: item.title, status: item.status}) : ''}<span class="row-date">${esc(prettyTime(item.starts_at) || 'ALL DAY')}</span><span class="row-copy"><b>${esc(item.title)}</b><small>${esc(item.subject || item.event_type)}${item.ends_at ? ` · until ${esc(prettyTime(item.ends_at))}` : ''}</small></span>${item.source_type === 'calendar' ? `<button class="icon-action" data-edit-event="${item.id}" aria-label="Edit event">✎</button><button class="icon-action" data-delete-event="${item.id}" aria-label="Delete event">×</button>` : ''}</div>`).join('') : empty('A clear day.', 'Add a study block or save an assignment to see it here.', '+');
  }
  document.addEventListener('click', async event => {
    const step = event.target.closest('[data-month-step]');
    if (step) { calMonth.setMonth(calMonth.getMonth() + Number(step.dataset.monthStep)); await loadCalendar(); }
    const cell = event.target.closest('[data-calendar-date]');
    if (cell) { calSelected = new Date(`${cell.dataset.calendarDate}T12:00:00`); if (calSelected.getMonth() !== calMonth.getMonth()) calMonth = new Date(calSelected); renderCalendar(); }
    const view = event.target.closest('[data-calendar-view]');
    if (view) { calView = view.dataset.calendarView; $$('[data-calendar-view]').forEach(button => button.classList.toggle('active', button === view)); renderCalendar(); }
    if (event.target.closest('[data-open-event]')) openEventModal();
    if (event.target.closest('[data-close-event]') || event.target.id === 'eventModal') $('#eventModal')?.classList.remove('is-open');
    const remove = event.target.closest('[data-delete-event]');
    if (remove && confirm('Delete this calendar event?')) await safeRequest(() => api(`/calendar-events/${remove.dataset.deleteEvent}`, { method: 'DELETE' }), 'Event deleted.');
    if (remove) await loadCalendar();
    const edit = event.target.closest('[data-edit-event]');
    if (edit) { const item = calendarEvents.find(row => row.id === Number(edit.dataset.editEvent)); if (item) openEventModal(item); }
    const agendaDate = event.target.closest('[data-agenda-date]');
    if (agendaDate) { calSelected = new Date(`${agendaDate.dataset.agendaDate}T12:00:00`); renderSelectedDay(); }
  });
  function openEventModal(item = null) {
    const modal = $('#eventModal'), form = $('#eventForm'); if (!modal || !form) return;
    form.reset();
    if (item) {
      form.dataset.editId = item.id;
      form.elements.title.value = item.title; form.elements.event_type.value = ['study','personal','reminder'].includes(item.event_type) ? item.event_type : 'study';
      form.elements.subject_id.value = item.subject_id || '';
      form.elements.starts_at.value = localInputDate(parseDate(item.starts_at));
      form.elements.ends_at.value = item.ends_at ? localInputDate(parseDate(item.ends_at)) : '';
      form.elements.details.value = item.details || '';
      $('#eventModalTitle').textContent = 'Edit calendar event';
    } else {
      delete form.dataset.editId; form.elements.starts_at.value = localInputDate(new Date(`${dateKey(calSelected)}T10:00:00`));
      form.elements.ends_at.value = localInputDate(new Date(`${dateKey(calSelected)}T11:00:00`));
      $('#eventModalTitle').textContent = 'Add a calendar event';
    }
    modal.classList.add('is-open');
  }
  $('#eventForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, data = formData(form);
    const id = form.dataset.editId;
    const saved = await safeRequest(() => api(`/calendar-events${id ? `/${id}` : ''}`, { method: id ? 'PATCH' : 'POST', body: JSON.stringify(data) }), id ? 'Calendar event updated.' : 'Saved to your calendar.');
    if (saved) { trackUsage('calendar_event_saved', { event_type: data.event_type }); form.reset(); $('#eventModal').classList.remove('is-open'); await loadCalendar(); }
  });

  // Timer state survives page refreshes; completed sessions are written once to SQLite.
  const timerStorageKey = `studyx-focus-timer:${csrf}`;
  let timer = { status: 'ready', planned: 35, elapsedMs: 0, startedMs: 0, startedAt: null, subjectId: null, ticker: null };
  const ringLength = 2 * Math.PI * 126;
  const timerTotal = () => timer.planned * 60000;
  const timerElapsed = () => timer.elapsedMs + (timer.status === 'running' ? Math.max(0, Date.now() - timer.startedMs) : 0);
  function stopTicker() { clearInterval(timer.ticker); timer.ticker = null; }
  function persistTimer() {
    try {
      if (timer.status === 'ready' || timer.status === 'complete') sessionStorage.removeItem(timerStorageKey);
      else sessionStorage.setItem(timerStorageKey, JSON.stringify({
        status: timer.status, planned: timer.planned, elapsedMs: timer.elapsedMs,
        startedMs: timer.startedMs, startedAt: timer.startedAt?.toISOString(), subjectId: timer.subjectId,
      }));
    } catch (_) { /* Timer remains usable when browser storage is disabled. */ }
  }
  function drawTimer() {
    const elapsed = Math.min(timerTotal(), timerElapsed()), remaining = Math.max(0, timerTotal() - elapsed);
    const minutes = Math.floor(remaining / 60000), seconds = Math.floor((remaining % 60000) / 1000);
    const display = $('#timerDisplay'); if (display) display.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    const progress = $('#focusRing .ring-progress'); if (progress) { progress.style.strokeDasharray = ringLength; progress.style.strokeDashoffset = ringLength * (elapsed / timerTotal()); }
    const status = $('#timerStatus'); if (status) status.textContent = timer.status === 'running' ? 'FOCUS IN PROGRESS' : timer.status === 'paused' ? 'PAUSED · TAKE YOUR TIME' : timer.status === 'saving' ? 'SAVING YOUR SESSION' : timer.status === 'complete' ? 'SESSION COMPLETE · SAVED' : 'READY WHEN YOU ARE';
    const busy = timer.status === 'saving', locked = timer.status === 'running' || timer.status === 'paused' || busy;
    const start = $('#timerStart'), stop = $('#timerStop'), reset = $('#timerReset');
    if (start) { start.disabled = busy; start.innerHTML = timer.status === 'running' ? 'Pause focus <span>Ⅱ</span>' : timer.status === 'paused' ? 'Resume focus <span>▶</span>' : timer.status === 'complete' ? 'Start another focus <span>▶</span>' : 'Start focus <span>▶</span>'; }
    if (stop) stop.disabled = !locked || busy;
    if (reset) reset.disabled = busy;
    $('#customMinutes') && ($('#customMinutes').disabled = locked);
    $('#focusSubject') && ($('#focusSubject').disabled = locked);
    $$('[data-focus-preset]').forEach(button => { button.disabled = locked; });
    if ($('#customMinutes') && document.activeElement !== $('#customMinutes')) $('#customMinutes').value = timer.planned;
  }
  function beginTicker() {
    stopTicker();
    timer.ticker = setInterval(() => {
      if (timerElapsed() >= timerTotal()) {
        timer.elapsedMs = timerTotal(); timer.startedMs = 0; timer.status = 'running';
        drawTimer(); persistTimer(); void saveFocusSession();
      } else drawTimer();
    }, 250);
  }
  function restoreTimer() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(timerStorageKey) || 'null');
      if (!saved || !['running', 'paused', 'saving'].includes(saved.status)) return;
      const planned = Number(saved.planned), elapsed = Number(saved.elapsedMs);
      const startedAt = saved.startedAt ? new Date(saved.startedAt) : null;
      if (!Number.isFinite(planned) || planned < 1 || planned > 720 || !Number.isFinite(elapsed) || !startedAt || Number.isNaN(startedAt.getTime())) {
        sessionStorage.removeItem(timerStorageKey); return;
      }
      timer = {
        status: saved.status === 'running' ? 'running' : 'paused',
        planned: Math.round(planned), elapsedMs: Math.max(0, elapsed),
        startedMs: Number(saved.startedMs) || 0, startedAt,
        subjectId: saved.subjectId ? Number(saved.subjectId) : null, ticker: null,
      };
      if (timer.status === 'running' && timer.startedMs > 0) beginTicker();
      else { timer.status = 'paused'; timer.startedMs = 0; }
      const subject = $('#focusSubject'); if (subject && timer.subjectId) subject.value = String(timer.subjectId);
    } catch (_) { timer.status = 'ready'; }
  }
  async function saveFocusSession() {
    if (!timer.startedAt || timer.status === 'saving') return;
    timer.elapsedMs = Math.min(timerTotal(), timerElapsed());
    timer.startedMs = 0; timer.status = 'saving'; stopTicker(); persistTimer(); drawTimer();
    const seconds = Math.max(1, Math.floor(timer.elapsedMs / 1000));
    const actual = Math.max(1, Math.min(720, Math.ceil(seconds / 60)));
    const endedAt = new Date();
    const payload = {
      planned_minutes: timer.planned, actual_minutes: actual,
      status: timer.elapsedMs >= timerTotal() ? 'completed' : 'stopped',
      started_at: timer.startedAt.toISOString(), ended_at: endedAt.toISOString(),
      subject_id: timer.subjectId,
    };
    const successMessage = payload.status === 'completed'
      ? 'Focus session complete and saved to your calendar.'
      : 'Focus session saved to your calendar.';
    const saved = await safeRequest(() => api('/focus-sessions', { method: 'POST', body: JSON.stringify(payload) }), successMessage);
    if (!saved) { timer.status = 'paused'; persistTimer(); drawTimer(); return; }
    trackUsage('focus_session_saved', { planned_minutes: timer.planned, actual_minutes: actual });
    try { await loadFocusHistory(); } catch (error) { toast(error.message, 'error'); }
    timer = payload.status === 'completed'
      ? { status: 'complete', planned: timer.planned, elapsedMs: timerTotal(), startedMs: 0, startedAt: null, subjectId: null, ticker: null }
      : { status: 'ready', planned: timer.planned, elapsedMs: 0, startedMs: 0, startedAt: null, subjectId: null, ticker: null };
    persistTimer(); drawTimer();
  }
  async function loadFocusHistory() {
    const list = $('#focusHistory'); if (!list) return;
    const rows = await api('/focus-sessions');
    list.innerHTML = rows.length ? rows.slice(0, 7).map(row => `<div class="data-row"><span class="row-date">${esc(prettyDate(row.started_at))}</span><span class="row-copy"><b>${esc(cache.subjects.find(subject => subject.id === row.subject_id)?.name || 'Independent study')}</b><small>${esc(prettyTime(row.started_at))} · ${row.status === 'stopped' ? 'finished early' : 'completed'}</small></span><span class="row-meta">${durationLabel(row.actual_minutes)}</span></div>`).join('') : empty('Your sessions begin here.', 'Start the timer or add study time you have already completed.', '◷');
  }
  $('#customMinutes')?.addEventListener('input', event => {
    if (timer.status !== 'ready') return;
    const requested = Number(event.target.value);
    if (Number.isFinite(requested) && requested > 0) timer.planned = Math.max(1, Math.min(720, Math.round(requested)));
    drawTimer();
  });
  $$('[data-focus-preset]').forEach(button => button.addEventListener('click', () => {
    if (!['ready', 'complete'].includes(timer.status)) return;
    timer.planned = Number(button.dataset.focusPreset); $('#customMinutes').value = timer.planned; drawTimer();
    $$('[data-focus-preset]').forEach(item => item.classList.toggle('active', item === button));
  }));
  $('#timerStart')?.addEventListener('click', () => {
    if (timer.status === 'saving') return;
    if (timer.status === 'running') {
      timer.elapsedMs = Math.min(timerTotal(), timerElapsed()); timer.startedMs = 0;
      timer.status = 'paused'; stopTicker(); persistTimer(); drawTimer(); return;
    }
    if (timer.status === 'paused') { timer.status = 'running'; timer.startedMs = Date.now(); }
    else {
      const requested = Number($('#customMinutes')?.value);
      timer.planned = Math.max(1, Math.min(720, Number.isFinite(requested) && requested > 0 ? Math.round(requested) : 35));
      timer.startedAt = new Date(); timer.elapsedMs = 0; timer.subjectId = $('#focusSubject')?.value ? Number($('#focusSubject').value) : null;
      timer.startedMs = Date.now(); timer.status = 'running';
    }
    persistTimer(); drawTimer(); beginTicker();
  });
  $('#timerStop')?.addEventListener('click', () => {
    if (timer.status !== 'running' && timer.status !== 'paused') return;
    void saveFocusSession();
  });
  $('#timerReset')?.addEventListener('click', () => {
    if (timer.status === 'saving') return;
    stopTicker(); timer.status = 'ready'; timer.elapsedMs = 0; timer.startedAt = null; timer.startedMs = 0; timer.subjectId = null;
    persistTimer(); drawTimer();
  });
  $('#manualSessionForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const data = formData(event.currentTarget); data.minutes = Number(data.minutes);
    const result = await safeRequest(() => api('/study-sessions', { method: 'POST', body: JSON.stringify(data) }), 'Study time saved to your calendar and progress.');
    if (result) { trackUsage('manual_study_time_saved', { minutes: data.minutes }); event.currentTarget.reset(); event.currentTarget.elements.started_at.value = localInputDate(); await loadFocusHistory(); }
  });

  // The input holds the real saved state; the adjacent icon makes the tick
  // visible consistently on mobile Safari, Android Chrome and desktop.
  function taskCheckbox(item) {
    const done = item.status === 'done';
    const label = `${done ? 'Reopen' : 'Complete'} ${item.title}`;
    return `<label class="task-toggle" title="${esc(label)}"><input type="checkbox" class="task-check" data-toggle-task="${item.id}" ${done ? 'checked' : ''} aria-label="${esc(label)}"><span class="task-box" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="m5 12 4.5 4.5L19 7"/></svg></span></label>`;
  }

  // Assignments and exams.
  async function loadAssignments() {
    cache.assignments = await api('/assignments');
    const filter = $('[data-assignment-filter].active')?.dataset.assignmentFilter || 'all';
    const items = cache.assignments.filter(item => filter === 'all' || item.status === filter);
    $('#assignmentCount') && ($('#assignmentCount').textContent = `${items.length} shown · ${cache.assignments.filter(item => item.status !== 'done').length} open`);
    const target = $('#assignmentList'); if (!target) return;
    target.innerHTML = items.length ? items.map(item => `<article class="task-row ${item.status === 'done' ? 'is-done' : ''}" data-task-id="${item.id}">${taskCheckbox(item)}<span class="task-main"><b>${esc(item.title)}</b><small>${esc(item.subject || 'Independent')} · due ${esc(prettyDate(item.due_at, { weekday: 'short', month: 'short', day: 'numeric' }))} at ${esc(prettyTime(item.due_at))} · ${item.estimated_minutes} min</small></span><span class="status-pill priority-${esc(item.priority)}">${esc(item.priority)}</span><button class="icon-action" data-delete-task="${item.id}" aria-label="Delete assignment">×</button></article>`).join('') : empty('Nothing to show yet.', 'Add an assignment to keep its due date visible in your calendar.', '✓');
  }
  $('#assignmentForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const data = formData(event.currentTarget); data.estimated_minutes = Number(data.estimated_minutes || 45);
    const result = await safeRequest(() => api('/assignments', { method: 'POST', body: JSON.stringify(data) }), 'Assignment saved and added to your calendar.');
    if (result) { trackUsage('assignment_created'); event.currentTarget.reset(); await loadAssignments(); }
  });
  document.addEventListener('click', async event => {
    const filter = event.target.closest('[data-assignment-filter]');
    if (filter) { $$('[data-assignment-filter]').forEach(button => button.classList.toggle('active', button === filter)); await loadAssignments(); }
    const remove = event.target.closest('[data-delete-task]');
    if (remove && confirm('Delete this assignment and its linked calendar entry?')) { await safeRequest(() => api(`/assignments/${remove.dataset.deleteTask}`, { method: 'DELETE' }), 'Assignment deleted.'); await loadAssignments(); }
  });
  // This works on BOTH the dashboard and assignments pages.
  document.addEventListener('change', async event => {
    const box = event.target.closest('input[data-toggle-task]');
    if (!box) return;
    const completed = box.checked;
    box.disabled = true;
    const result = await safeRequest(() => api(`/assignments/${Number(box.dataset.toggleTask)}`, {
      method: 'PATCH', body: JSON.stringify({status: completed ? 'done' : 'todo'})
    }), completed ? 'Task completed.' : 'Task reopened.');
    if (!result) { box.checked = !completed; box.disabled = false; return; }
    // The API response confirms the new status has been committed to SQLite.
    // Reload so dashboard, assignment filters, calendar and progress show
    // consistent saved values. On a failed request the old tick is restored.
    const returnedStatus = result.status;
    if (returnedStatus !== (completed ? 'done' : 'todo')) {
      box.checked = !completed;
      box.disabled = false;
      toast('Task did not update. Please try again.', 'error');
      return;
    }
    window.location.reload();
  });
  async function loadExams() {
    cache.exams = await api('/exams'); const target = $('#examList'); if (!target) return;
    target.innerHTML = cache.exams.length ? cache.exams.map(item => `<article class="exam-card"><div class="card-topline"><div><span class="eyebrow">${esc(item.subject || 'EXAM')}</span><h3>${esc(item.title)}</h3></div><span class="card-date"><b>${parseDate(item.exam_at)?.getDate() || '—'}</b>${esc(parseDate(item.exam_at)?.toLocaleDateString(undefined,{month:'short'}) || '')}</span></div><p class="card-subtitle">${esc(prettyDate(item.exam_at,{weekday:'long',month:'long',day:'numeric',year:'numeric'}))} · ${esc(prettyTime(item.exam_at))}${item.location ? ` · ${esc(item.location)}` : ''}</p><div class="topic-chips">${item.topics.map(topic => `<span>${esc(topic.title)}</span>`).join('') || '<span>Add topics when you are ready</span>'}</div><div class="card-topline" style="margin-top:15px"><small class="form-footnote">Saved to your calendar</small><button class="icon-action" data-delete-exam="${item.id}" aria-label="Delete exam">×</button></div></article>`).join('') : empty('No exam dates just yet.', 'Add an exam date and it will be saved to your calendar.', '⌑');
  }
  $('#examForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const data = formData(event.currentTarget); data.topics = (event.currentTarget.elements.topics.value || '').split('\n').map(value => value.trim()).filter(Boolean); delete data.topicsText;
    const result = await safeRequest(() => api('/exams', { method: 'POST', body: JSON.stringify(data) }), 'Exam saved and added to your calendar.');
    if (result) { event.currentTarget.reset(); await loadExams(); }
  });
  document.addEventListener('click', async event => {
    const remove = event.target.closest('[data-delete-exam]');
    if (remove && confirm('Delete this exam and its linked calendar entry?')) { await safeRequest(() => api(`/exams/${remove.dataset.deleteExam}`, { method: 'DELETE' }), 'Exam deleted.'); await loadExams(); }
  });

  // Subjects, notes, and quizzes.
  async function loadSubjectsPage() {
    cache.subjects = await api('/subjects'); const target = $('#subjectList'); if (!target) return;
    target.innerHTML = cache.subjects.length ? cache.subjects.map(subject => `<article class="subject-card"><div class="subject-top"><span class="subject-mark">${esc(subject.name.slice(0,1).toUpperCase())}</span><button class="icon-action" data-edit-subject="${subject.id}" aria-label="Rename subject">✎</button><button class="icon-action" data-delete-subject="${subject.id}" aria-label="Delete subject">×</button></div><h3>${esc(subject.name)}</h3><p>${esc(subject.category)} · difficulty ${subject.difficulty}/5</p><div style="margin-top:9px"><a class="button button-soft button-compact" href="/quizzes?subject_id=${subject.id}">Create course quiz ↗</a></div><div class="subject-meta"><span>Saved study time</span><b>${durationLabel(subject.study_minutes)}</b></div><div class="subject-progress"><i style="width:${Math.min(100, subject.target_hours ? (subject.study_minutes / (subject.target_hours * 60)) * 100 : 0)}%"></i></div></article>`).join('') : empty('Start with one subject.', 'Your sessions, notes and assignments can all stay connected to a class.', '⌑');
  }
  $('#subjectForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const data = formData(event.currentTarget); data.difficulty = Number(data.difficulty); data.target_hours = Number(data.target_hours);
    const result = await safeRequest(() => api('/subjects', { method: 'POST', body: JSON.stringify(data) }), 'Subject added.');
    if (result) { event.currentTarget.reset(); await loadSubjects(); await loadSubjectsPage(); }
  });
  document.addEventListener('click', async event => {
    const remove = event.target.closest('[data-delete-subject]');
    if (remove && confirm('Delete this subject? Existing study records will stay saved without a subject link.')) { await safeRequest(() => api(`/subjects/${remove.dataset.deleteSubject}`, { method: 'DELETE' }), 'Subject deleted.'); await loadSubjects(); await loadSubjectsPage(); }
    const edit = event.target.closest('[data-edit-subject]');
    if (edit) { const subject = cache.subjects.find(item => item.id === Number(edit.dataset.editSubject)); const name = prompt('Subject name', subject?.name || ''); if (name && subject) { await safeRequest(() => api(`/subjects/${subject.id}`, { method: 'PATCH', body: JSON.stringify({ name }) }), 'Subject updated.'); await loadSubjects(); await loadSubjectsPage(); } }
  });

  async function loadNotes() {
    cache.notes = await api('/notes'); const query = ($('#noteSearch')?.value || '').trim().toLowerCase();
    const items = cache.notes.filter(note => !query || `${note.title} ${note.content} ${note.tags.join(' ')}`.toLowerCase().includes(query));
    $('#noteCount') && ($('#noteCount').textContent = `${items.length} saved`);
    const target = $('#notesList'); if (!target) return;
    target.innerHTML = items.length ? items.map(note => `<article class="note-card"><span class="eyebrow">${esc(note.subject || 'STUDY NOTE')}</span><h3>${esc(note.title)}</h3><p>${esc(note.content)}</p><div class="tag-list">${note.tags.map(tag => `<span>${esc(tag)}</span>`).join('')}</div><div class="note-card-actions"><button class="icon-action" data-edit-note="${note.id}" aria-label="Edit note">✎</button><button class="icon-action" data-delete-note="${note.id}" aria-label="Delete note">×</button></div></article>`).join('') : empty(query ? 'No notes match that search.' : 'A good thought has a place.', 'Save a note in your own words and find it here when you need it.', '✎');
  }
  $('#noteForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, data = formData(form); data.tags = (form.elements.tags.value || '').split(',').map(tag => tag.trim()).filter(Boolean).slice(0,20);
    const id = form.dataset.editId;
    const result = await safeRequest(() => api(`/notes${id ? `/${id}` : ''}`, { method: id ? 'PATCH' : 'POST', body: JSON.stringify(data) }), id ? 'Note updated.' : 'Note saved.');
    if (result) { form.reset(); delete form.dataset.editId; await loadNotes(); }
  });
  $('#noteSearch')?.addEventListener('input', () => loadNotes().catch(error => toast(error.message, 'error')));
  document.addEventListener('click', async event => {
    const edit = event.target.closest('[data-edit-note]');
    if (edit) { const note = cache.notes.find(item => item.id === Number(edit.dataset.editNote)); const form = $('#noteForm'); if (note && form) { form.dataset.editId = note.id; form.elements.title.value = note.title; form.elements.subject_id.value = note.subject_id || ''; form.elements.content.value = note.content; form.elements.tags.value = note.tags.join(', '); $('#noteFormPanel').classList.add('is-open'); form.scrollIntoView({ behavior: 'smooth', block: 'center' }); } }
    const remove = event.target.closest('[data-delete-note]');
    if (remove && confirm('Delete this saved note?')) { await safeRequest(() => api(`/notes/${remove.dataset.deleteNote}`, { method: 'DELETE' }), 'Note deleted.'); await loadNotes(); }
  });

  function addQuizQuestion() {
    const builder = $('#quizQuestionBuilder'); if (!builder) return;
    const index = builder.children.length + 1;
    const card = document.createElement('div'); card.className = 'quiz-question-builder';
    card.innerHTML = `<div class="card-topline"><b>Question ${index}</b><button type="button" class="icon-action" data-remove-question aria-label="Remove question">×</button></div><label class="form-field"><span>Question</span><textarea data-question-prompt rows="2" maxlength="1500" required></textarea></label><div class="form-row">${[0,1,2,3].map(i => `<label class="form-field"><span>Option ${i+1} ${i<2?'':'· optional'}</span><input data-question-option maxlength="300" ${i<2?'required':''}></label>`).join('')}</div><label class="form-field"><span>Correct answer</span><select data-question-answer required><option value="">Select the correct option</option></select></label>`;
    const inputs = $$('[data-question-option]', card), select = $('[data-question-answer]', card);
    inputs.forEach((input, i) => input.addEventListener('input', () => { const value = input.value.trim(), was = select.value; select.innerHTML = '<option value="">Select the correct option</option>' + inputs.map(node => node.value.trim()).filter(Boolean).map(option => `<option>${esc(option)}</option>`).join(''); if ([...select.options].some(option => option.value === was)) select.value = was; }));
    builder.append(card);
  }
  $('#addQuizQuestion')?.addEventListener('click', addQuizQuestion);
  document.addEventListener('click', event => { if (event.target.closest('[data-remove-question]')) event.target.closest('.quiz-question-builder')?.remove(); });
  async function loadQuizzes() {
    const target = $('#quizList'); if (!target) return;
    const quizzes = await api('/quizzes');
    const activeCourse = $('#quizCourseFilter')?.value || '';
    const visible = activeCourse ? quizzes.filter(quiz => String(quiz.subject_id) === activeCourse) : quizzes;
    $('#quizCount') && ($('#quizCount').textContent = `${visible.length} quizzes`);
    target.innerHTML = visible.length ? visible.map(quiz => `<article class="quiz-card"><span class="eyebrow">${esc(cache.subjects.find(subject => subject.id === quiz.subject_id)?.name || 'PRACTICE')}</span><h3>${esc(quiz.title)}</h3><p class="card-subtitle">${quiz.question_count} questions · ${quiz.attempt_count} saved attempts</p>${quiz.latest_score !== null ? `<p class="card-subtitle">Latest attempt: ${quiz.latest_score}/${quiz.latest_total}</p>` : '<p class="card-subtitle">Not attempted yet</p>'}<div class="card-topline" style="margin-top:12px"><button class="button button-blue button-compact" data-take-quiz="${quiz.id}">Start quiz ↗</button><button class="icon-action" data-delete-quiz="${quiz.id}" aria-label="Delete quiz">×</button></div></article>`).join('') : empty('Make your own practice set.', 'Create a few questions from a class topic to check your recall.', '✦');
  }
  $('#quizCourseFilter')?.addEventListener('change', loadQuizzes);
  $('#quizForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget;
    const questions = $$('.quiz-question-builder', form).map(card => ({ prompt: $('[data-question-prompt]', card).value.trim(), options: $$('[data-question-option]', card).map(input => input.value.trim()).filter(Boolean), correct_answer: $('[data-question-answer]', card).value }));
    const data = { title: form.elements.title.value.trim(), subject_id: form.elements.subject_id.value ? Number(form.elements.subject_id.value) : null, questions };
    const result = await safeRequest(() => api('/quizzes', { method: 'POST', body: JSON.stringify(data) }), 'Quiz saved.');
    if (result) { form.reset(); $('#quizQuestionBuilder').innerHTML = ''; addQuizQuestion(); await loadQuizzes(); }
  });
  document.addEventListener('click', async event => {
    const take = event.target.closest('[data-take-quiz]');
    if (take) await startQuiz(Number(take.dataset.takeQuiz));
    const remove = event.target.closest('[data-delete-quiz]');
    if (remove && confirm('Delete this quiz and its attempt history?')) { await safeRequest(() => api(`/quizzes/${remove.dataset.deleteQuiz}`, { method: 'DELETE' }), 'Quiz deleted.'); await loadQuizzes(); }
  });
  async function startQuiz(id) {
    const target = $('#quizTakePanel'); if (!target) return;
    try {
      const quiz = await api(`/quizzes/${id}`);
      target.dataset.quizId = id; target.classList.add('is-open');
      target.innerHTML = `<div class="section-heading"><div><span class="eyebrow">TAKE A BREATH, THEN BEGIN</span><h2>${esc(quiz.title)}</h2><p>Choose one answer for each question. Your score is saved after you submit.</p></div><button class="icon-close" data-close-quiz>×</button></div><form id="quizAttemptForm" class="form-stack">${quiz.questions.map((question, index) => `<fieldset class="quiz-question"><legend>${index+1}. ${esc(question.prompt)}</legend>${question.options.map(option => `<label><input type="radio" name="q_${question.id}" value="${esc(option)}" required><span>${esc(option)}</span></label>`).join('')}</fieldset>`).join('')}<button class="button button-blue form-submit" type="submit">Submit answers ↗</button></form><div id="quizResult"></div>`;
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      $('#quizAttemptForm', target).addEventListener('submit', async submit => {
        submit.preventDefault(); const answers = Object.fromEntries([...new FormData(submit.currentTarget).entries()].map(([key, value]) => [key.replace(/^q_/, ''), value]));
        const result = await safeRequest(() => api(`/quizzes/${id}/attempts`, { method: 'POST', body: JSON.stringify({ answers }) }));
        if (result) { trackUsage('quiz_attempt_saved', { score: result.score, total: result.total_questions }); $('#quizResult', target).innerHTML = `<div class="quiz-result"><b>${result.score} / ${result.total_questions}</b><span>${Math.round(result.score/result.total_questions*100)}% correct · attempt saved</span></div>`; submit.currentTarget.querySelector('button[type="submit"]').disabled = true; await loadQuizzes(); }
      });
    } catch (error) { toast(error.message, 'error'); }
  }
  document.addEventListener('click', event => { if (event.target.closest('[data-close-quiz]')) $('#quizTakePanel')?.classList.remove('is-open'); });

  async function loadContactInbox() {
    const target = $('#contactInboxList'); if (!target) return;
    const rows = await api('/contact-messages');
    target.innerHTML = rows.length ? rows.map(item => `<article class="surface-card contact-inbox-card"><div class="card-topline"><b>${esc(item.name)}</b><small>${esc(prettyDate(item.created_at))}</small></div><small>${esc(item.email)} · ${item.email_sent ? 'Email sent' : 'Saved in database'}</small><p>${esc(item.message)}</p></article>`).join('') : empty('No messages yet.', 'Messages from your contact form will appear here.', '✉');
  }

  // Goals / revision / notification pages.
  async function loadGoals() {
    const target = $('#goalList'); if (!target) return;
    const goals = await api('/goals');
    target.innerHTML = goals.length ? goals.map(goal => `<article class="goal-card"><div class="card-topline"><span class="eyebrow">${esc(goal.period.toUpperCase())} · ${esc(prettyDate(goal.ends_on))}</span><div><button class="icon-action" data-complete-goal="${goal.id}" aria-label="${goal.completed ? 'Reopen goal' : 'Mark goal complete'}">${goal.completed ? '↺' : '✓'}</button><button class="icon-action" data-delete-goal="${goal.id}" aria-label="Delete goal">×</button></div></div><h3>${esc(goal.title)}</h3><p>${goal.completed ? 'This goal is complete.' : 'A small promise, kept over time.'}</p><div class="goal-numbers"><b>${durationLabel(goal.current_minutes)}</b><span>of ${durationLabel(goal.target_minutes)}</span></div><div class="goal-progress"><i style="width:${Math.min(100, Math.round(goal.current_minutes / goal.target_minutes * 100))}%"></i></div></article>`).join('') : empty('Choose a gentle goal.', 'Pick a small amount of study time that feels realistic for your week.', '◎');
  }
  $('#goalForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, data = formData(form); data.target_minutes = Number(data.target_minutes); const today = dateKey(new Date());
    const start = new Date(`${today}T12:00:00`), end = new Date(start);
    if (data.period === 'day') end.setDate(end.getDate()); else if (data.period === 'month') { start.setDate(1); end.setMonth(end.getMonth()+1,0); } else { const offset=(start.getDay()+6)%7; start.setDate(start.getDate()-offset); end.setTime(start.getTime()); end.setDate(start.getDate()+6); }
    data.starts_on = dateKey(start); data.ends_on = dateKey(end);
    const result = await safeRequest(() => api('/goals', { method: 'POST', body: JSON.stringify(data) }), 'Study goal saved.');
    if (result) { form.reset(); await loadGoals(); }
  });
  document.addEventListener('click', async event => {
    const complete = event.target.closest('[data-complete-goal]');
    if (complete) { const goals = await api('/goals'); const goal = goals.find(item => item.id === Number(complete.dataset.completeGoal)); if (goal) { await safeRequest(() => api(`/goals/${goal.id}`, { method: 'PATCH', body: JSON.stringify({ completed: !goal.completed }) }), 'Goal updated.'); await loadGoals(); } }
    const remove = event.target.closest('[data-delete-goal]');
    if (remove && confirm('Delete this goal?')) { await safeRequest(() => api(`/goals/${remove.dataset.deleteGoal}`, { method: 'DELETE' }), 'Goal deleted.'); await loadGoals(); }
  });
  async function loadRevisions() {
    const target = $('#revisionList'); if (!target) return;
    const rows = await api('/revision-plans');
    target.innerHTML = rows.length ? rows.map(item => `<article class="data-row revision-row ${item.status === 'done' ? 'is-done' : ''}"><button class="task-check ${item.status === 'done' ? 'done' : ''}" data-revision-status="${item.id}" aria-label="Toggle revision complete">✓</button><span class="row-copy"><b>${esc(item.title)}</b><small>${esc(item.subject || 'Independent study')} · ${esc(prettyDate(item.due_at,{weekday:'short',month:'short',day:'numeric'}))} at ${esc(prettyTime(item.due_at))}</small></span><span class="status-pill">${esc(item.status)}</span></article>`).join('') : empty('No revision reminders yet.', 'Schedule a topic to revisit, and it will appear in your calendar.', '↻');
  }
  $('#revisionForm')?.addEventListener('submit', async event => { event.preventDefault(); const result = await safeRequest(() => api('/revision-plans', { method: 'POST', body: JSON.stringify(formData(event.currentTarget)) }), 'Revision reminder saved to your calendar.'); if (result) { event.currentTarget.reset(); await loadRevisions(); } });
  document.addEventListener('click', async event => {
    const toggle = event.target.closest('[data-revision-status]');
    if (toggle) { const rows = await api('/revision-plans'); const row = rows.find(item => item.id === Number(toggle.dataset.revisionStatus)); if (row) { await safeRequest(() => api(`/revision-plans/${row.id}`, { method: 'PATCH', body: JSON.stringify({ status: row.status === 'done' ? 'scheduled' : 'done' }) }), 'Revision updated.'); await loadRevisions(); } }
  });
  async function loadNotifications() {
    const target = $('#notificationList'); if (!target) return;
    const rows = await api('/notifications');
    target.innerHTML = rows.length ? rows.map(item => `<article class="notification-row ${item.read ? '' : 'unread'}"><span class="notification-mark">${item.category === 'exam' ? '⌑' : '✓'}</span><span class="notification-copy"><b>${esc(item.title)}</b><p>${esc(item.message)}</p><small>${esc(prettyDate(item.created_at,{month:'short',day:'numeric',year:'numeric'}))} · ${esc(prettyTime(item.created_at))}</small></span>${item.read ? '' : `<button class="button button-soft button-compact" data-read-notification="${item.id}">Mark read</button>`}</article>`).join('') : empty('No reminders right now.', 'Notifications appear when you save new assignments and exams.', '♧');
  }
  $('#readAllNotifications')?.addEventListener('click', async () => { await safeRequest(() => api('/notifications/read-all', { method: 'POST', body: '{}' }), 'Notifications marked as read.'); await loadNotifications(); });
  document.addEventListener('click', async event => {
    const mark = event.target.closest('[data-read-notification]');
    if (mark) { await safeRequest(() => api(`/notifications/${mark.dataset.readNotification}`, { method: 'PATCH', body: JSON.stringify({ read: true }) })); await loadNotifications(); }
  });

  // Progress charts and profile/preferences.
  async function loadProgress() {
    const data = await api('/analytics');
    $('#progressTotalTime') && ($('#progressTotalTime').textContent = durationLabel(data.total_study_minutes));
    $('#progressSessionCount') && ($('#progressSessionCount').textContent = data.session_count);
    $('#progressTaskRatio') && ($('#progressTaskRatio').textContent = `${data.assignments.completed}/${data.assignments.total}`);
    const chart = $('#progressChart');
    if (chart) renderProgressChart(chart, data.daily);
    const subjects = $('#subjectProgress');
    const count = $('#progressCourseCount');
    if (count) count.textContent = `${data.by_subject.length} saved course${data.by_subject.length === 1 ? '' : 's'}`;
    if (subjects) subjects.innerHTML = data.by_subject.length ? data.by_subject.map(item => {
      const assignmentLabel = `${item.assignments_completed} / ${item.assignments_total} assignments done`;
      const targetLabel = item.target_minutes ? `${durationLabel(item.minutes)} / ${durationLabel(item.target_minutes)} studied` : `${durationLabel(item.minutes)} studied`;
      const progressLabel = item.progress_basis === 'combined' ? 'Study + assignments' : item.progress_basis === 'study_target' ? 'Study target' : item.progress_basis === 'assignments' ? 'Assignments' : 'Getting started';
      return `<div class="subject-time-row" data-progress-course="${item.id}"><b>${esc(item.name)}</b><span>${item.progress_percent}%</span><small class="course-progress-details">${esc(targetLabel)} · ${esc(assignmentLabel)}</small><div class="subject-progress" style="grid-column:1/-1" role="progressbar" aria-label="${esc(item.name)} ${esc(progressLabel)}" aria-valuenow="${item.progress_percent}" aria-valuemin="0" aria-valuemax="100"><i style="width:${item.progress_percent}%"></i></div></div>`;
    }).join('') : empty('No courses added yet.', 'Add a course and it will appear here immediately, even before your first study session.', '◷');
    const milestones = $('#progressAchievements');
    if (milestones) {
      const records = (await api('/progress')).filter(item => item.event_type.includes('assignment') || item.event_type.includes('focus') || item.event_type.includes('study'));
      milestones.innerHTML = records.length ? records.slice(0,8).map(item => `<div class="progress-achievement"><i>${item.event_type.includes('assignment') ? '✓' : '◷'}</i><span><b>${esc(item.title)}</b><small>${esc(item.event_type.replaceAll('_',' '))} · ${esc(prettyDate(item.created_at,{month:'short',day:'numeric'}))}</small></span></div>`).join('') : empty('Your learning trail starts here.', 'Completed assignments and saved study sessions will appear as you go.', '✦');
    }
  }
  function renderProgressChart(chart, daily) {
    const rows = Array.isArray(daily) ? daily : [];
    const values = rows.map(row => Math.max(0, Number(row.minutes) || 0));
    const peak = Math.max(60, ...values);
    const rawStep = peak / 4;
    const magnitude = 10 ** Math.floor(Math.log10(rawStep));
    const scaledStep = rawStep / magnitude;
    const step = (scaledStep <= 1 ? 1 : scaledStep <= 2 ? 2 : scaledStep <= 2.5 ? 2.5 : scaledStep <= 5 ? 5 : 10) * magnitude;
    const axisMax = Math.ceil(peak / step) * step;
    const width = Math.max(320, Math.round(chart.clientWidth || 900)), height = 310, left = 62, right = 18, top = 20, bottom = 48;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const x = index => left + (rows.length <= 1 ? plotWidth / 2 : (index / (rows.length - 1)) * plotWidth);
    const y = value => top + plotHeight - (value / axisMax) * plotHeight;
    const points = rows.map((row, index) => ({ row, value: values[index], x: x(index), y: y(values[index]) }));
    const hasStudy = values.some(value => value > 0);
    const dateLabel = value => {
      const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
      const date = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12) : null;
      return date && !Number.isNaN(date.getTime())
        ? new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date)
        : '';
    };
    const grid = Array.from({ length: Math.round(axisMax / step) + 1 }, (_, index) => {
      const value = axisMax - index * step, lineY = y(value);
      return `<g class="progress-chart-grid"><line x1="${left}" y1="${lineY}" x2="${width - right}" y2="${lineY}"/><text x="${left - 12}" y="${lineY + 4}" text-anchor="end">${Math.round(value)}</text></g>`;
    }).join('');
    const labelIndexes = [...new Set([0, 6, 12, 18, 24, rows.length - 1].filter(index => index >= 0 && index < rows.length))];
    const xLabels = labelIndexes.map(index => `<text class="progress-chart-x-label" x="${x(index)}" y="${height - 14}" text-anchor="${index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle'}">${dateLabel(rows[index].date)}</text>`).join('');
    const line = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
    const area = points.length ? `${line} L ${points.at(-1).x.toFixed(2)} ${y(0).toFixed(2)} L ${points[0].x.toFixed(2)} ${y(0).toFixed(2)} Z` : '';
    const marks = points.map(point => `<circle class="progress-chart-point" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="${point.value ? 4 : 2.5}"><title>${dateLabel(point.row.date)} · ${point.value} minutes</title></circle>`).join('');
    chart.innerHTML = `<svg class="progress-trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Study minutes for the last 30 days, from ${rows.length ? dateLabel(rows[0].date) : 'no date'} to ${rows.length ? dateLabel(rows.at(-1).date) : 'today'}">
      <defs><linearGradient id="studyTrendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="var(--blue)" stop-opacity=".28"/><stop offset="100%" stop-color="var(--blue)" stop-opacity="0"/></linearGradient></defs>
      ${grid}${hasStudy ? `<path class="progress-chart-area" d="${area}"/><path class="progress-chart-line" d="${line}"/>${marks}` : ''}${xLabels}
    </svg>${hasStudy ? '' : '<div class="progress-chart-empty"><b>Your study trend starts here</b><span>Complete a focus session to see your minutes appear across the month.</span></div>'}`;
  }
  async function loadRoadmaps() {
    const target = $('#roadmapList'); if (!target) return;
    const rows = await api('/roadmaps');
    target.innerHTML = rows.length ? rows.map(roadmap => `<article class="roadmap-card" data-roadmap-card="${roadmap.id}"><div class="roadmap-progress-top"><span class="eyebrow">${esc(roadmap.subject || 'INDEPENDENT LEARNING')} · ${esc(roadmap.status.toUpperCase())}</span><b>${roadmap.completion_rate}%</b></div><h2>${esc(roadmap.title)}</h2><p>${esc(roadmap.description || 'A sequence of small steps toward a learning goal.')}</p><div class="roadmap-bar"><i style="width:${roadmap.completion_rate}%"></i></div><div class="roadmap-progress-top"><span>${roadmap.completed_tasks} of ${roadmap.total_tasks} steps complete</span><button class="icon-action" data-edit-roadmap="${roadmap.id}" aria-label="Edit roadmap">✎</button></div><div class="roadmap-task-list">${roadmap.tasks.map(task => `<div class="roadmap-task ${task.status === 'done' ? 'done' : ''}"><button class="${task.status === 'done' ? 'done' : ''}" data-roadmap-task="${task.id}" aria-label="Toggle step complete">✓</button><span>${esc(task.title)}</span><small>${durationLabel(task.estimated_minutes)}</small><button class="icon-action" data-delete-roadmap-task="${task.id}" aria-label="Delete step">×</button></div>`).join('')}</div><form class="roadmap-task-add" data-add-roadmap-task="${roadmap.id}"><input name="title" maxlength="180" required placeholder="Add another step…"><button class="button button-soft button-compact" type="submit">＋</button></form><div class="roadmap-actions"><span>${roadmap.status === 'completed' ? 'A path completed.' : 'Keep it moving, one step at a time.'}</span><button class="icon-action" data-delete-roadmap="${roadmap.id}" aria-label="Delete roadmap">×</button></div></article>`).join('') : empty('Start with a learning goal.', 'Create a roadmap and break it into steps you can finish one at a time.', '◎');
  }
  $('#roadmapForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget;
    const data = formData(form); data.tasks = form.elements.tasks.value.split('\n').map(title => title.trim()).filter(Boolean).map(title => ({ title }));
    const result = await safeRequest(() => api('/roadmaps', { method: 'POST', body: JSON.stringify(data) }), 'Learning roadmap saved.');
    if (result) { form.reset(); await loadRoadmaps(); }
  });
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-add-roadmap-task]'); if (!form) return;
    event.preventDefault(); const data = { title: form.elements.title.value.trim() };
    const result = await safeRequest(() => api(`/roadmaps/${form.dataset.addRoadmapTask}/tasks`, { method: 'POST', body: JSON.stringify(data) }), 'Roadmap step added.');
    if (result) { form.reset(); await loadRoadmaps(); }
  });
  document.addEventListener('click', async event => {
    const toggle = event.target.closest('[data-roadmap-task]');
    if (toggle) {
      const card = toggle.closest('[data-roadmap-card]');
      const rows = await api('/roadmaps'), roadmap = rows.find(item => item.id === Number(card?.dataset.roadmapCard));
      const task = roadmap?.tasks.find(item => item.id === Number(toggle.dataset.roadmapTask));
      if (task) { const result = await safeRequest(() => api(`/roadmap-tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify({ status: task.status === 'done' ? 'todo' : 'done' }) }), 'Roadmap progress saved.'); if (result && task.status !== 'done') trackUsage('roadmap_step_completed'); await loadRoadmaps(); }
    }
    const edit = event.target.closest('[data-edit-roadmap]');
    if (edit) { const rows = await api('/roadmaps'), roadmap = rows.find(item => item.id === Number(edit.dataset.editRoadmap)); if (roadmap) { const title = prompt('Roadmap title', roadmap.title); if (title?.trim()) { await safeRequest(() => api(`/roadmaps/${roadmap.id}`, { method: 'PATCH', body: JSON.stringify({ title: title.trim() }) }), 'Roadmap updated.'); await loadRoadmaps(); } } }
    const removeTask = event.target.closest('[data-delete-roadmap-task]');
    if (removeTask && confirm('Remove this roadmap step?')) { await safeRequest(() => api(`/roadmap-tasks/${removeTask.dataset.deleteRoadmapTask}`, { method: 'DELETE' }), 'Roadmap step removed.'); await loadRoadmaps(); }
    const remove = event.target.closest('[data-delete-roadmap]');
    if (remove && confirm('Delete this roadmap and its steps? Saved progress history will remain.')) { await safeRequest(() => api(`/roadmaps/${remove.dataset.deleteRoadmap}`, { method: 'DELETE' }), 'Roadmap deleted.'); await loadRoadmaps(); }
  });
  async function loadProfile() {
    if (!$('#profileForm')) return;
    const data = await api('/profile');
    $('#profileNameInput').value = data.full_name; $('#profileCourseInput').value = data.course_name || ''; $('#profileImageInput').value = data.profile_image_url || '';
    $('#profileEmail').textContent = data.email; $('#profileCreated').textContent = prettyDate(data.created_at, { year:'numeric', month:'long', day:'numeric' });
  }
  $('#profileForm')?.addEventListener('submit', async event => { event.preventDefault(); const data = formData(event.currentTarget); const result = await safeRequest(() => api('/profile', { method: 'PATCH', body: JSON.stringify(data) }), 'Profile saved.'); if (result) { $$('.side-profile b').forEach(node => node.textContent = data.full_name); $('.side-profile .profile-avatar') && ($('.side-profile .profile-avatar').textContent = data.full_name[0].toUpperCase()); } });
  async function loadSettings() {
    if (!$('#reminderPreference')) return;
    const [prefs, status] = await Promise.all([api('/preferences'), api('/system-status')]);
    $('#reminderPreference').checked = prefs.reminders_enabled !== false;
    const badge = $('#aiConfigStatus'); if (badge) { badge.textContent = status.ai_configured ? 'Gemini key connected' : 'Gemini key not set'; badge.classList.add(status.ai_configured ? 'ready' : 'missing'); }
  }
  $('#reminderPreference')?.addEventListener('change', event => safeRequest(() => api('/preferences', { method: 'PATCH', body: JSON.stringify({ preferences: { reminders_enabled: event.target.checked } }) }), 'Preference saved.'));

  // AI tutor history is account-scoped; the API key stays server-side.
  async function loadChatHistory() {
    const target = $('#chatMessages'); if (!target) return;
    const history = await api('/assistant/history');
    if (!history.length) return;
    target.innerHTML = history.map(item => `<div class="chat-bubble ${item.role === 'user' ? 'user' : ''}">${esc(item.content)}</div>`).join('');
    target.scrollTop = target.scrollHeight;
  }
  $('#chatForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, question = form.elements.question.value.trim(); if (!question) return;
    const target = $('#chatMessages'); target.insertAdjacentHTML('beforeend', `<div class="chat-bubble user">${esc(question)}</div><div class="chat-bubble" data-thinking>StudyX is thinking…</div>`); target.scrollTop = target.scrollHeight;
    form.elements.question.value = ''; form.querySelector('button').disabled = true;
    try { const result = await api('/assistant', { method: 'POST', body: JSON.stringify({ question }) }); $('[data-thinking]')?.remove(); target.insertAdjacentHTML('beforeend', `<div class="chat-bubble">${esc(result.answer)}</div>`); target.scrollTop = target.scrollHeight; }
    catch (error) { $('[data-thinking]')?.remove(); target.insertAdjacentHTML('beforeend', `<div class="chat-bubble">${esc(error.message)}</div>`); }
    finally { form.querySelector('button').disabled = false; }
  });
  $$('#clearChat, [data-clear-chat]').forEach(button => button.addEventListener('click', async () => { await safeRequest(() => api('/assistant/history', { method: 'DELETE' }), 'Chat history cleared.'); const target = $('#chatMessages'); if (target) target.innerHTML = '<div class="assistant-welcome"><span>✧</span><h3>What are you working through?</h3></div>'; }));
  $$('[data-prompt]').forEach(button => button.addEventListener('click', () => { const input = $('#chatForm textarea'); if (input) { input.value = button.dataset.prompt; input.focus(); } }));

  // Draft timetable from saved assignments/exams; explicitly save suggested slots.
  let timetableDraft = [];
  $('#timetableForm')?.addEventListener('submit', async event => {
    event.preventDefault(); const form = event.currentTarget, values = formData(form); values.available_minutes = Number(values.available_minutes); values.start_hour = Number(values.start_hour); values.end_hour = Number(values.end_hour);
    const result = await safeRequest(() => api('/timetable/generate', { method: 'POST', body: JSON.stringify(values) }));
    if (!result) return;
    timetableDraft = result.slots;
    const target = $('#timetableSlots');
    target.innerHTML = result.slots.length ? result.slots.map((slot,index) => `<label class="timetable-slot"><input type="checkbox" data-save-slot="${index}" checked><i></i><span><b>${esc(slot.title)}</b><small>${esc(slot.subject || 'Study block')} · ${slot.minutes} min</small></span><time>${esc(slot.starts_at)}</time></label>`).join('') + '<button class="button button-blue timetable-save" id="saveTimetable">Save selected to calendar ↗</button>' : empty('No open work to place.', 'Add upcoming assignments or exam dates first, then build a draft.');
  });
  document.addEventListener('click', async event => {
    if (event.target.closest('#saveTimetable')) {
      const selected = $$('[data-save-slot]:checked').map(input => timetableDraft[Number(input.dataset.saveSlot)]).filter(Boolean);
      let saved = 0;
      for (const slot of selected) {
        const start = new Date(slot.starts_at), end = new Date(start.getTime() + Number(slot.minutes) * 60000);
        const result = await safeRequest(() => api('/calendar-events', { method: 'POST', body: JSON.stringify({ title: slot.title, event_type: 'study', starts_at: start.toISOString(), ends_at: end.toISOString(), details: 'Saved from your suggested StudyX timetable.' }) }));
        if (result) saved++;
      }
      if (saved) toast(`${saved} study block${saved === 1 ? '' : 's'} saved to your calendar.`);
    }
  });

  // Calendar-aware seven day planner.
  async function loadPlanner() {
    const target = $('#plannerTimeline'); if (!target) return;
    const start = new Date(); start.setHours(0,0,0,0); const end = new Date(start); end.setDate(end.getDate()+7);
    const rows = await api(`/calendar-events?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`);
    target.innerHTML = rows.length ? rows.map(item => `<div class="planner-slot"><time>${esc(prettyDate(item.starts_at,{weekday:'short',month:'short',day:'numeric'}))}<br>${esc(prettyTime(item.starts_at))}</time><i></i><span class="planner-slot-copy"><b>${esc(item.title)}</b><small>${esc(item.subject || item.event_type)}${item.ends_at ? ` · ${durationLabel((parseDate(item.ends_at)-parseDate(item.starts_at))/60000)}` : ''}</small></span></div>`).join('') : empty('A week with room to shape.', 'Your upcoming assignments, exams, revisions and study sessions appear here.', '▦');
  }

  // Contact form and search overlay.
  $('[data-contact-form]')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const status = $('[data-contact-status]', form);
    const button = $('button[type="submit"]', form);
    const data = formData(form);
    status.textContent = 'Saving your message…'; status.className = 'contact-status';
    button.disabled = true;
    try {
      const result = await api('/contact', {method: 'POST', body: JSON.stringify(data)});
      status.textContent = result.message || 'Your message was saved.';
      status.classList.add('success');
      form.reset();
    } catch (error) {
      status.textContent = error.message || 'Message not saved. Please try again.';
      status.classList.add('error');
    } finally { button.disabled = false; }
  });
  $$('[data-show-password]').forEach(button => button.addEventListener('click', () => {
    const input = button.closest('.form-field')?.querySelector('input[name="password"]');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
    button.textContent = input.type === 'password' ? 'Show' : 'Hide';
  }));
  const search = $('#globalSearch');
  if (search) {
    const panel = document.createElement('div'); panel.className = 'global-search-results'; panel.hidden = true; search.closest('.search-global').after(panel);
    let searchTimer;
    search.addEventListener('input', () => {
      clearTimeout(searchTimer); const query = search.value.trim().toLowerCase();
      if (query.length < 2) { panel.hidden = true; return; }
      searchTimer = setTimeout(async () => {
        try {
          const [assignments, exams, notes, subjects] = await Promise.all([api('/assignments'), api('/exams'), api('/notes'), api('/subjects')]);
          const items = [
            ...assignments.filter(item => item.title.toLowerCase().includes(query)).map(item => ({ title:item.title, sub:'Assignment', href:'/assignments' })),
            ...exams.filter(item => item.title.toLowerCase().includes(query)).map(item => ({ title:item.title, sub:'Exam', href:'/exams' })),
            ...notes.filter(item => `${item.title} ${item.content}`.toLowerCase().includes(query)).map(item => ({ title:item.title, sub:'Note', href:'/notes' })),
            ...subjects.filter(item => item.name.toLowerCase().includes(query)).map(item => ({ title:item.name, sub:'Subject', href:'/subjects' })),
          ].slice(0,8);
          panel.innerHTML = items.length ? items.map(item => `<a href="${item.href}"><b>${esc(item.title)}</b><small>${esc(item.sub)}</small></a>`).join('') : '<span>No matching saved items</span>';
          panel.hidden = false;
        } catch (_) { panel.hidden = true; }
      }, 220);
    });
    document.addEventListener('click', event => { if (!event.target.closest('.search-global') && !event.target.closest('.global-search-results')) panel.hidden = true; });
  }

  // Boot only APIs used by the current page. Data remains in the server database.
  async function boot() {
    if (!workspace) {
      if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
      return;
    }
    try { await loadSubjects(); } catch (error) { toast(error.message, 'error'); }
    try {
      const loaders = {
        dashboard: initDashboard,
        calendar: loadCalendar,
        focus: async () => { $('#manualSessionForm [name="started_at"]') && ($('#manualSessionForm [name="started_at"]').value = localInputDate()); restoreTimer(); drawTimer(); await loadFocusHistory(); },
        assignments: loadAssignments,
        exams: loadExams,
        subjects: loadSubjectsPage,
        notes: loadNotes,
        quizzes: async () => {
          if (!$('#quizQuestionBuilder').children.length) addQuizQuestion();
          const filter = $('#quizCourseFilter');
          if (filter) filter.innerHTML = '<option value="">All courses</option>' + cache.subjects.map(item => `<option value="${item.id}">${esc(item.name)}</option>`).join('');
          const requested = new URLSearchParams(location.search).get('subject_id');
          if (requested && cache.subjects.some(item => String(item.id) === requested)) {
            $('#quizForm').elements.subject_id.value = requested;
            if (filter) filter.value = requested;
            $('#quizFormPanel')?.classList.add('is-open');
          }
          await loadQuizzes();
        },
        contact_inbox: loadContactInbox,
        goals: loadGoals,
        roadmaps: loadRoadmaps,
        revision: loadRevisions,
        notifications: loadNotifications,
        progress: loadProgress,
        profile: loadProfile,
        settings: loadSettings,
        assistant: loadChatHistory,
        timetable: async () => { $('#timetableForm [name="date"]') && ($('#timetableForm [name="date"]').value = dateKey(new Date())); },
        planner: loadPlanner,
      };
      if (loaders[page]) await loaders[page]();
      if (page === 'dashboard') { /* Dashboard initializes its own saved event stream. */ }
    } catch (error) { toast(error.message || 'Could not load your saved study data.', 'error'); }
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  }
  boot();
})();
