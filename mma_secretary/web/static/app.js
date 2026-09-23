const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

const state = { view: "archives", boot: null, sort: "seq", catId: null };

const titles = {
  archives: ["Турниры", "Сохраните текущие данные, начните пустой турнир или откройте другую копию."],
  setup: ["Реквизиты", "Название турнира, судьи, возрасты, дивизионы и веса"],
  people: ["Участники", "Добавьте заявку вручную или загрузите таблицу. Отчество программа отрежет сама."],
  weigh: ["Взвешивание", "Впишите фактический вес и нажмите «Записать». Запятая и точка оба подходят."],
  cats: ["Категории", "Разбейте список по возрасту, дивизиону и весу. Кто не попал — будет в жёлтом списке, а не пропадёт."],
  brackets: ["Сетки", "Выберите категорию и нажмите на пару, чтобы записать победителя. Он сам пойдёт дальше."],
  bouts: ["Бои", "Все пары турнира по порядку. Здесь же можно поставить номер ринга."],
  results: ["Итоги", "Места, очки команд и мандатная комиссия считаются автоматически."],
  docs: ["Документы", "Откройте форму и в браузере нажмите Ctrl+P — так получается PDF."],
};

const KIND_RU = {
  empty: "пусто",
  walkover: "без боя",
  final: "финал",
  round_robin: "круговая",
  single_elim: "олимпийская",
};
const ROUND_RU = {
  "авто": "без боя",
  "без боя": "без боя",
  "круг": "круг",
  "1/32": "1/32 финала",
  "1/16": "1/16 финала",
  "1/8": "1/8 финала",
  "1/4": "1/4 финала",
  "1/2": "1/2 финала",
  "финал": "финал",
  "за бронзу": "за бронзу",
};

function kindRu(v) { return KIND_RU[v] || v || "—"; }
function roundRu(v) { return ROUND_RU[v] || v || "—"; }
function statusClass(s) {
  if (s === "допущен" || s === "взвешен") return "ok";
  if (s === "снят" || s === "не явился") return "bad";
  if (s === "заявлен") return "warn";
  return "";
}

async function api(path, opts={}) {
  $("#save-dot").textContent = "сохранение…";
  $("#save-dot").className = "busy";
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers||{}) },
    ...opts,
    body: opts.body && typeof opts.body !== "string" && !(opts.body instanceof FormData)
      ? JSON.stringify(opts.body) : opts.body,
  });
  $("#save-dot").textContent = "сохранено";
  $("#save-dot").className = "saved";
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch {}
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("json")) return res.json();
  return res;
}

function toast(msg, kind="ok") {
  const n = document.createElement("div");
  n.textContent = msg;
  n.style.cssText = `position:fixed;right:18px;bottom:18px;background:${kind==="ok"?"#16324f":"#c0122a"};color:#fff;padding:12px 16px;border-radius:8px;z-index:50;font-weight:600`;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 2800);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

function openModal(title, html) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = html;
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }
$("#modal-close").onclick = closeModal;
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") closeModal(); });

$$("#nav button").forEach(b => b.onclick = () => show(b.dataset.view));
$("#btn-undo").onclick = async () => {
  try { const r = await api("/api/undo", { method: "POST", body: {} }); toast("Отменено"); show(state.view); }
  catch (e) { toast(e.message, "err"); }
};
$("#btn-backup").onclick = () => { location.href = "/api/export"; };
$("#file-import").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  await fetch("/api/import", { method: "POST", body: fd });
  toast("Турнир загружен");
  await boot(); show(state.view);
};

async function boot() {
  state.boot = await api("/api/bootstrap");
  $("#brand-sub").textContent = state.boot.tournament.name || "турнир";
}

async function show(view) {
  state.view = view;
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#page-title").textContent = titles[view][0];
  $("#page-hint").textContent = titles[view][1];
  $("#view").innerHTML = "<p>Загрузка…</p>";
  try { await views[view](); } catch (e) { $("#view").innerHTML = `<div class="warn-box">${esc(e.message)}</div>`; }
}

function resultForm(b, methodsHtml, onDone) {
  if (!b.blue || !b.red) return;
  openModal("Кто победил" + (b.bout_no ? ` · бой № ${b.bout_no}` : ""), `
    <p>${esc(roundRu(b.round_title || b.round_code))}</p>
    <div class="pick">
      <button class="btn blue wide" id="pick-blue" type="button">Синий угол<br>${esc(b.blue.name)}</button>
      <button class="btn red wide" id="pick-red" type="button">Красный угол<br>${esc(b.red.name)}</button>
    </div>
    <label class="field">Как победил
      <select id="w-m">${methodsHtml}</select>
    </label>
    ${b.winner_entry_id || b.winner ? `<button class="btn sec" id="w-clr" type="button">Сбросить результат</button>` : ""}
  `);
  const send = async (entryId) => {
    await api(`/api/bouts/${b.id}/result`, { method:"POST", body:{ winner_entry_id: entryId, method: $("#w-m").value }});
    closeModal(); onDone();
  };
  $("#pick-blue").onclick = () => send(b.blue.id);
  $("#pick-red").onclick = () => send(b.red.id);
  const clr = $("#w-clr");
  if (clr) clr.onclick = async () => { await api(`/api/bouts/${b.id}/clear`, { method:"POST", body:{} }); closeModal(); onDone(); };
}

async function renderArchives() {
  const t = state.boot.tournament;
  let saves = [];
  let apiOk = true;
  try { saves = await api("/api/saves"); } catch { apiOk = false; }
  $("#view").innerHTML = `
    <div class="card">
      <p style="margin:0 0 8px">Сейчас открыто: <b>${esc(t.name || "без названия")}</b>${t.date ? " · " + esc(t.date) : ""}</p>
      ${apiOk ? "" : `<div class="warn-box">Сервер старый и не умеет копии. Закройте чёрное окно, запустите start.bat заново, затем обновите страницу.</div>`}
      <div class="add-row" style="margin-bottom:12px">
        <input id="save-name" placeholder="Название копии, например Калининград 14.09.2024">
        <button class="btn" id="save-now" type="button">Сохранить этот турнир</button>
        <button class="btn sec" id="new-now" type="button">Начать с нуля</button>
      </div>
      ${saves.length ? `<table class="data"><thead><tr><th>Название</th><th>Когда сохранили</th><th>Участников</th><th></th></tr></thead>
      <tbody>${saves.map(s => `<tr>
        <td><b>${esc(s.name)}</b></td>
        <td>${esc((s.saved_at || "").replace("T", " ").replace("+00:00",""))}</td>
        <td>${s.participants}</td>
        <td>
            <button class="btn sm" data-load="${esc(s.id)}" type="button">Открыть</button>
            <button class="btn sm danger" data-forget="${esc(s.id)}" type="button">Удалить</button>
        </td>
      </tr>`).join("")}</tbody></table>` : `<p style="color:#5c6570;margin:0">Сохранённых копий пока нет. Нажмите «Сохранить этот турнир», чтобы оставить учебный список с Excel.</p>`}
    </div>`;
  $("#save-name").value = t.name || "";
  $("#save-now").onclick = async () => {
    try {
      const r = await api("/api/saves", { method: "POST", body: { name: $("#save-name").value } });
      toast("Сохранено: " + r.name);
      show("archives");
    } catch (e) { toast(e.message, "err"); }
  };
  $("#new-now").onclick = async () => {
    if (!confirm("Начать с нуля? Текущий список и сетки пропадут. Справочник весов останется. Если нужно — сначала нажмите «Сохранить этот турнир».")) return;
    await api("/api/tournament/new", { method: "POST", body: {} });
    toast("Пустой турнир");
    await boot();
    show("archives");
  };
  $("#view").onclick = async (e) => {
    if (e.target.dataset.load) {
      if (!confirm("Открыть эту копию? То, что сейчас на экране, заменится. Сначала сохраните, если оно ещё нужно.")) return;
      await api("/api/saves/" + encodeURIComponent(e.target.dataset.load) + "/load", { method: "POST", body: {} });
      toast("Турнир открыт");
      await boot();
      show("archives");
    }
    if (e.target.dataset.forget && confirm("Удалить только сохранённую копию? Открытый турнир не тронется.")) {
      await api("/api/saves/" + encodeURIComponent(e.target.dataset.forget), { method: "DELETE" });
      show("archives");
    }
  };
}

const views = {
  async archives() { await renderArchives(); },
  async setup() {
    const t = state.boot.tournament;
    $("#view").innerHTML = `
      <div class="card">
        <h2>О турнире</h2>
        <div class="catalogs">
          <label class="field">Название<input id="t-name" value="${esc(t.name)}"></label>
          <label class="field">Вид спорта<input id="t-kind" value="${esc(t.kind)}"></label>
          <label class="field">Город<input id="t-city" value="${esc(t.city)}"></label>
          <label class="field">Дата<input id="t-date" type="date" value="${esc(t.date||"")}"></label>
          <label class="field">Главный судья<input id="t-ref" value="${esc(t.chief_referee)}"></label>
          <label class="field">Главный секретарь<input id="t-sec" value="${esc(t.chief_secretary)}"></label>
          <label class="field">Сколько рингов<input id="t-rings" type="number" min="1" value="${t.rings||1}"></label>
          <label class="field">Третье место
            <select id="t-bronze">
              <option value="0">два третьих места</option>
              <option value="1">отдельный бой за бронзу</option>
            </select>
          </label>
          <label class="field"><span><input type="checkbox" id="t-walk" ${t.award_walkover?"checked":""}> очки одиночке (n=1)</span></label>
        </div>
        <button class="btn" id="t-save" type="button">Сохранить реквизиты</button>
      </div>
      <div class="card">
        <h2>Справочники</h2>
        <div class="catalogs">
          <div>
            <h3>Возрастные группы</h3>
            <div id="ages"></div>
            <div class="add-row" style="margin-top:10px"><input id="age-label" placeholder="2007-2008"><button class="btn sec" id="age-add" type="button">Добавить</button></div>
          </div>
          <div>
            <h3>Дивизионы</h3>
            <div id="divs"></div>
            <div class="add-row" style="margin-top:10px"><input id="div-code" placeholder="А"><button class="btn sec" id="div-add" type="button">Добавить</button></div>
          </div>
          <div>
            <h3>Весовые категории, кг</h3>
            <div id="wts"></div>
            <div class="add-row" style="margin-top:10px"><input id="wt-kg" placeholder="52,2"><button class="btn sec" id="wt-add" type="button">Добавить</button></div>
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Очки за места</h2>
        <p class="hint-inline">Сколько очков команда получает за это место. Обычно правят только числа справа.</p>
        <div id="pts"></div>
        <button class="btn" id="pts-save" type="button">Сохранить очки</button>
      </div>`;
    $("#t-bronze").value = t.bronze_bout ? "1" : "0";
    $("#t-save").onclick = async () => {
      state.boot.tournament = await api("/api/tournament", { method: "PUT", body: {
        name: $("#t-name").value, kind: $("#t-kind").value, date: $("#t-date").value,
        city: $("#t-city").value, chief_referee: $("#t-ref").value, chief_secretary: $("#t-sec").value,
        rings: +$("#t-rings").value, bronze_bout: +$("#t-bronze").value,
        two_bronzes: +$("#t-bronze").value ? 0 : 1,
        award_walkover: $("#t-walk").checked ? 1 : 0,
      }});
      $("#brand-sub").textContent = state.boot.tournament.name;
      toast("Сохранено");
    };
    renderCatalogs();
    $("#age-add").onclick = async () => { await api("/api/age-groups", { method: "POST", body: { label: $("#age-label").value } }); await boot(); renderCatalogs(); };
    $("#div-add").onclick = async () => { await api("/api/divisions", { method: "POST", body: { code: $("#div-code").value } }); await boot(); renderCatalogs(); };
    $("#wt-add").onclick = async () => { await api("/api/weights", { method: "POST", body: { limit_kg: $("#wt-kg").value } }); await boot(); renderCatalogs(); };
    $("#pts-save").onclick = savePoints;
  },

  async people() {
    const list = await api("/api/participants?sort=" + state.sort);
    $("#view").innerHTML = `
      <div class="toolbar">
        <div class="stat"><b>${list.length}</b><span>в списке</span></div>
        <input id="q" placeholder="Найти по фамилии или клубу" style="max-width:280px">
        <select id="sort">
          <option value="seq">по номеру</option>
          <option value="team">команда → год → жребий</option>
          <option value="weight">по весу</option>
          <option value="year_weight">год → вес</option>
          <option value="alpha">по алфавиту</option>
          <option value="draw">по жребию</option>
        </select>
        <button class="btn" id="p-add" type="button">Добавить участника</button>
        <label class="btn sec">Загрузить Excel<input type="file" id="p-imp" accept=".xlsx,.xlsm,.csv" hidden></label>
        <a class="btn sec" href="/api/export/participants.xlsx">Скачать список</a>
        <button class="btn sec" id="p-demo" type="button">Учебный список (14 человек)</button>
      </div>
      <div class="table-wrap">
        <table class="data" id="ptable">
          <thead><tr><th>№</th><th>Жребий</th><th>ФИО</th><th>Организация</th><th>Разряд</th><th>Год</th><th>Тренер</th><th>Вес</th><th>Статус</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>`;
    $("#sort").value = state.sort;
    $("#sort").onchange = () => { state.sort = $("#sort").value; show("people"); };
    const tbody = $("#ptable tbody");
    const draw = (items) => {
      tbody.innerHTML = items.map(p => `<tr>
        <td>${p.seq??""}</td><td>${p.draw_number??""}</td>
        <td><b>${esc(p.name)}</b></td><td>${esc(p.organization)}</td>
        <td>${esc(p.rank)}</td><td>${p.birth_year??""}</td><td>${esc(p.coach)}</td>
        <td>${p.weight ?? "—"}</td><td><span class="badge ${statusClass(p.status)}">${esc(p.status)}</span></td>
        <td class="actions"><button class="btn sm sec" data-edit="${p.id}" type="button">Изменить</button>
            <button class="btn sm danger" data-del="${p.id}" type="button">Удалить</button></td>
      </tr>`).join("") || `<tr><td colspan="10">Список пуст. Добавьте человека или загрузите Excel.</td></tr>`;
    };
    draw(list);
    $("#q").oninput = () => {
      const q = $("#q").value.toLowerCase();
      draw(list.filter(p => `${p.name} ${p.organization} ${p.coach}`.toLowerCase().includes(q)));
    };
    tbody.onclick = async (e) => {
      const del = e.target.dataset.del, ed = e.target.dataset.edit;
      if (del && confirm("Удалить участника?")) { await api("/api/participants/"+del, { method:"DELETE" }); show("people"); }
      if (ed) personForm(list.find(p => p.id == ed));
    };
    $("#p-add").onclick = () => personForm(null);
    $("#p-imp").onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      const fd = new FormData(); fd.append("file", f);
      const r = await fetch("/api/participants/import", { method:"POST", body: fd }).then(x=>x.json());
      toast(`Загружено: ${r.added}`); show("people");
    };
    $("#p-demo").onclick = async () => { await api("/api/demo", { method:"POST", body:{} }); toast("Учебный список загружен"); show("people"); };
  },

  async weigh() {
    const list = await api("/api/participants?sort=alpha");
    const left = list.filter(p => p.weight == null).length;
    $("#view").innerHTML = `
      <div class="toolbar">
        <div class="stat"><b>${left}</b><span>ещё без веса</span></div>
        <div class="stat"><b>${list.length - left}</b><span>уже взвешены</span></div>
      </div>
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>ФИО</th><th>Организация</th><th>Год</th><th>Вес, кг</th><th>Статус</th><th></th></tr></thead>
          <tbody>${list.map(p => `<tr>
            <td><b>${esc(p.name)}</b></td><td>${esc(p.organization)}</td><td>${p.birth_year??""}</td>
            <td><input data-w="${p.id}" value="${p.weight ?? ""}" inputmode="decimal" style="width:110px"></td>
            <td><select data-st="${p.id}">
              ${["заявлен","взвешен","допущен","снят","не явился"].map(s => `<option ${s===p.status?"selected":""}>${s}</option>`).join("")}
            </select></td>
            <td class="actions"><button class="btn sm" data-save="${p.id}" type="button">Записать</button>
                <button class="btn sm sec" data-hist="${p.id}" type="button">История</button></td>
          </tr>`).join("")}</tbody>
        </table>
      </div>`;
    $("#view").onclick = async (e) => {
      const id = e.target.dataset.save || e.target.dataset.hist;
      if (e.target.dataset.save) {
        const w = $(`input[data-w="${id}"]`).value;
        const st = $(`select[data-st="${id}"]`).value;
        try { await api(`/api/participants/${id}/weigh`, { method:"POST", body:{ weight:w, status:st } }); toast("Вес записан"); }
        catch (err) { toast(err.message, "err"); }
      }
      if (e.target.dataset.hist) {
        const h = await api(`/api/participants/${id}/weights`);
        openModal("История веса", h.length ? `<ul>${h.map(x=>`<li>${esc(x.recorded_at)} — ${x.weight} кг</li>`).join("")}</ul>` : "<p>записей нет</p>");
      }
    };
  },

  async cats() {
    const cats = await api("/api/categories");
    $("#view").innerHTML = `
      <div class="toolbar">
        <button class="btn" id="do-class" type="button">Разбить на категории</button>
        <span>После взвешивания нажмите эту кнопку. Старые сетки и результаты боёв соберутся заново.</span>
      </div>
      <div id="unplaced"></div>
      ${cats.length ? `<div class="table-wrap"><table class="data">
        <thead><tr><th>Возраст</th><th>Дивизион</th><th>Вес</th><th>Человек</th><th>Вид сетки</th><th></th></tr></thead>
        <tbody>${cats.map(c => `<tr>
          <td>${esc(c.age_label)}</td><td>${esc(c.division_code)}</td>
          <td>до ${esc(c.weight_label)} кг</td><td><b>${c.n}</b></td>
          <td>${esc(c.bracket_title || kindRu(c.bracket_kind))}</td>
          <td class="actions">
            <button class="btn sm" data-open="${c.id}" type="button">Открыть сетку</button>
            <button class="btn sm sec" data-redraw="${c.id}" type="button">Новый жребий</button>
          </td>
        </tr>`).join("")}</tbody>
      </table></div>` : `<div class="empty">Категорий ещё нет. Сначала загрузите участников и нажмите «Разбить на категории».</div>`}`;
    $("#do-class").onclick = async () => {
      if (cats.length && !confirm("Собрать категории заново? Результаты боёв сбросятся.")) return;
      const r = await api("/api/classify", { method:"POST", body:{} });
      const box = $("#unplaced");
      if (r.unplaced.length) {
        box.innerHTML = `<div class="warn-box"><b>Не удалось разместить: ${r.unplaced.length}</b><ul>${
          r.unplaced.map(u => `<li>${esc(u.participant.name)} — ${esc(u.reason)}</li>`).join("")
        }</ul></div>`;
      } else {
        toast("Категории собраны: " + r.categories.length);
        show("cats");
      }
    };
    $("#view").onclick = async (e) => {
      if (e.target.dataset.open) { state.catId = +e.target.dataset.open; show("brackets"); }
      if (e.target.dataset.redraw && confirm("Пережеребить только эту категорию?")) {
        await api(`/api/categories/${e.target.dataset.redraw}/redraw`, { method:"POST", body:{} });
        toast("Жребий обновлён");
        show("cats");
      }
    };
  },

  async brackets() {
    const cats = await api("/api/categories");
    if (!cats.length) {
      $("#view").innerHTML = `<div class="empty">Сначала откройте «Категории» и нажмите «Разбить на категории».</div>`;
      return;
    }
    if (!state.catId) state.catId = cats[0].id;
    const d = await api("/api/categories/" + state.catId);
    const methods = (state.boot.methods||[]).map(m => `<option>${m}</option>`).join("");
    const title = d.category.bracket_title || kindRu(d.category.bracket_kind);
    $("#view").innerHTML = `
      <div class="toolbar">
        <select id="cat-sel" style="max-width:420px">${cats.map(c =>
          `<option value="${c.id}" ${c.id===state.catId?"selected":""}>до ${esc(c.weight_label)} кг · ${esc(c.age_label)} · ${esc(c.division_code)} · ${c.n} чел. · ${esc(c.bracket_title || kindRu(c.bracket_kind))}</option>`
        ).join("")}</select>
        <button class="btn sec" id="br-redraw" type="button">Новый жребий</button>
      </div>
      <div class="card">
        <h2>${esc(d.category.age_label)} · дивизион ${esc(d.category.division_code)} · до ${esc(d.category.weight_label)} кг · ${esc(title)}</h2>
        <div class="chips">${d.entries.map(e =>
          `<span class="chip"><b>${e.control_number}.</b> ${esc(e.name)} <span style="color:#5c6570">${esc(e.organization)}</span></span>`
        ).join("")}</div>
        <div class="bracket-wrap" id="br"></div>
      </div>`;
    $("#cat-sel").onchange = () => { state.catId = +$("#cat-sel").value; show("brackets"); };
    $("#br-redraw").onclick = async () => {
      if (!confirm("Пережеребить эту категорию? Результаты боёв сбросятся.")) return;
      await api(`/api/categories/${state.catId}/redraw`, { method:"POST", body:{} });
      show("brackets");
    };
    renderBracket($("#br"), d, methods);
  },

  async bouts() {
    const list = await api("/api/bouts");
    const methods = (state.boot.methods||[]).map(m => `<option>${m}</option>`).join("");
    $("#view").innerHTML = list.length ? `
      <div class="table-wrap"><table class="data">
        <thead><tr><th>№</th><th>Категория</th><th>Тур</th><th>Синий угол</th><th>Красный угол</th><th>Победитель</th><th>Ринг</th><th></th></tr></thead>
        <tbody>${list.map(b => `<tr>
          <td><b>${b.bout_no??""}</b></td>
          <td>до ${esc(b.weight_label)} · ${esc(b.division_code)}</td>
          <td>${esc(b.round_title || roundRu(b.round_code))}</td>
          <td class="blue">${b.blue?esc(b.blue.name):"—"}</td>
          <td class="red">${b.red?esc(b.red.name):"—"}</td>
          <td>${b.winner?esc(b.winner.name):(b.blue&&b.red?"ещё не записан":"ждём пару")}</td>
          <td><input data-ring="${b.id}" value="${b.ring??""}" style="width:64px"></td>
          <td class="actions">${b.blue&&b.red?`<button class="btn sm" data-res="${b.id}" type="button">${b.winner?"Исправить":"Записать"}</button>`:""}</td>
        </tr>`).join("")}</tbody>
      </table></div>` : `<div class="empty">Боёв нет. Сначала соберите категории.</div>`;
    $("#view").onclick = (e) => {
      if (!e.target.dataset.res) return;
      const b = list.find(x => x.id == e.target.dataset.res);
      resultForm(b, methods, () => show("bouts"));
    };
    $$("input[data-ring]").forEach(inp => inp.onchange = () => {
      api(`/api/bouts/${inp.dataset.ring}/schedule`, { method:"POST", body:{ ring: inp.value? +inp.value: null }});
    });
  },

  async results() {
    const [places, teams, man] = await Promise.all([api("/api/placements"), api("/api/teams"), api("/api/mandate")]);
    const whead = man.weights.map(w => `<th>${esc(w)}</th>`).join("");
    $("#view").innerHTML = `
      <div class="grid two">
        <div class="card" style="padding:0;overflow:auto">
          <h2 style="padding:16px 16px 0">Личные места</h2>
          <table class="data"><thead><tr><th>Категория</th><th>Место</th><th>ФИО</th><th>Организация</th><th>Очки</th></tr></thead>
          <tbody>${places.map(p => `<tr><td>до ${esc(p.weight_label)} · ${esc(p.division_code)}</td>
            <td><b>${p.place}</b></td><td>${esc(p.name)}</td><td>${esc(p.organization)}</td><td>${p.points}</td></tr>`).join("")
            || `<tr><td colspan="5">Мест ещё нет — запишите результаты боёв.</td></tr>`}</tbody></table>
        </div>
        <div class="card" style="padding:0;overflow:auto">
          <h2 style="padding:16px 16px 0">Командный зачёт</h2>
          <table class="data"><thead><tr><th>Место</th><th>Организация</th><th>Очки</th><th>Представитель</th></tr></thead>
          <tbody>${teams.map(s => `<tr><td><b>${s.place}</b></td><td>${esc(s.organization)}</td><td>${s.points}</td>
            <td><input data-org="${esc(s.organization)}" value="${esc(s.representative)}" placeholder="ФИО"></td></tr>`).join("")
            || `<tr><td colspan="4">Пока пусто.</td></tr>`}</tbody></table>
        </div>
      </div>
      <div class="card" style="overflow:auto">
        <h2>Мандатная комиссия</h2>
        <table class="data">
          <thead><tr><th>Организация</th>${whead}<th>Итого</th></tr></thead>
          <tbody>${man.rows.map(r => `<tr><td>${esc(r.organization)}</td>${man.weights.map(w=>`<td>${r.cells[w]||""}</td>`).join("")}<td><b>${r.total}</b></td></tr>`).join("")}
          <tr><th>Итого</th>${man.weights.map(w=>`<th>${man.col_totals[w]||0}</th>`).join("")}<th>${man.grand_total}</th></tr></tbody>
        </table>
        <p style="color:#5c6570;margin:12px 0 0">${Object.entries(man.titles).map(([k,v])=>`${esc(k)}: ${v}`).join(" · ")}</p>
      </div>`;
    $$("input[data-org]").forEach(inp => inp.onchange = () => {
      api("/api/teams/rep", { method:"POST", body:{ organization: inp.dataset.org, representative: inp.value }});
    });
  },

  async docs() {
    const items = [
      ["/print/weigh-in", "Протокол взвешивания", "Список с весом и жребием"],
      ["/print/mandate", "Мандатная комиссия", "Клубы по весовым категориям"],
      ["/print/pairs", "Список пар", "Кто с кем в первом круге"],
      ["/print/corners", "Бои по углам", "Синий и красный угол, ринг"],
      ["/print/brackets", "Сетки", "Все категории"],
      ["/print/personal", "Личное первенство", "Места и очки"],
      ["/print/scorecards", "Судейские записки", "По одному листу на бой"],
      ["/print/teams", "Командный протокол", "Сумма очков клубов"],
      ["/print/medals", "Призёры", "1–3 места"],
      ["/print/certificates", "Грамоты", "Печать пачкой"],
      ["/print/report", "Итоговый отчёт", "Всё сразу"],
      ["/api/export/report.xlsx", "Файл Excel", "Мандат, команды, места"],
    ];
    $("#view").innerHTML = `
      <div class="docs">${items.map(([h,t,s]) => `<a href="${h}" target="_blank">${esc(t)}<small>${esc(s)}</small></a>`).join("")}</div>
      <p style="margin-top:16px;color:#5c6570">Резервная копия всего турнира — кнопка «Сохранить копию» слева внизу.</p>`;
  },
};

function placeLabel(from, to) {
  from = Number(from); to = Number(to);
  if (from === to) {
    if (from === 1) return "1-е место";
    if (from === 2) return "2-е место";
    if (from === 3) return "3-е место";
    return from + "-е место";
  }
  if (to >= 32) return from + "-е и ниже";
  return from + "–" + to + " места";
}

function renderCatalogs() {
  const b = state.boot;
  const chips = (items, html) => items.length
    ? `<div class="chip-list">${items.map(html).join("")}</div>`
    : `<p style="color:#5c6570;margin:0">пока нет</p>`;
  $("#ages").innerHTML = chips(b.age_groups, g =>
    `<span class="chip">${esc(g.label)} <button type="button" data-del-age="${g.id}" aria-label="Удалить">×</button></span>`);
  $("#divs").innerHTML = chips(b.divisions, d =>
    `<span class="chip">${esc(d.code)} <button type="button" data-del-div="${d.id}" aria-label="Удалить">×</button></span>`);
  $("#wts").innerHTML = chips(b.weights, w =>
    `<span class="chip">до ${esc(w.label)} <button type="button" data-del-wt="${w.id}" aria-label="Удалить">×</button></span>`);
  $("#pts").innerHTML = `<table class="data pts-table">
    <thead><tr><th>Место</th><th>Очки</th></tr></thead>
    <tbody>${b.point_rules.map((p,i) => `<tr>
      <td>${esc(placeLabel(p.place_from, p.place_to))}</td>
      <td>
        <input class="pts-num" data-pp="${i}" value="${p.points}" inputmode="numeric">
        <input type="hidden" data-pf="${i}" value="${p.place_from}">
        <input type="hidden" data-pt="${i}" value="${p.place_to}">
      </td>
    </tr>`).join("")}</tbody>
  </table>`;
  $("#ages").onclick = async (e) => { if (e.target.dataset.delAge) { await api("/api/age-groups/"+e.target.dataset.delAge,{method:"DELETE"}); await boot(); renderCatalogs(); } };
  $("#divs").onclick = async (e) => { if (e.target.dataset.delDiv) { await api("/api/divisions/"+e.target.dataset.delDiv,{method:"DELETE"}); await boot(); renderCatalogs(); } };
  $("#wts").onclick = async (e) => { if (e.target.dataset.delWt) { await api("/api/weights/"+e.target.dataset.delWt,{method:"DELETE"}); await boot(); renderCatalogs(); } };
}

async function savePoints() {
  const n = state.boot.point_rules.length;
  const rules = [];
  for (let i=0;i<n;i++) rules.push({
    place_from: +$(`input[data-pf="${i}"]`).value,
    place_to: +$(`input[data-pt="${i}"]`).value,
    points: +$(`input[data-pp="${i}"]`).value,
  });
  state.boot.point_rules = await api("/api/points", { method:"PUT", body: rules });
  toast("Очки обновлены");
}

function personForm(p) {
  const v = (k, d="") => p ? (p[k] ?? d) : d;
  openModal(p ? "Участник" : "Новый участник", `
    <label class="field">Фамилия и имя<input id="f-name" value="${esc(v("name"))}"></label>
    <label class="field">Город, организация<input id="f-org" value="${esc(v("organization"))}"></label>
    <div class="grid two">
      <label class="field">Разряд или дивизион<input id="f-rank" value="${esc(v("rank"))}" placeholder="КМС или А"></label>
      <label class="field">Год рождения<input id="f-year" value="${esc(v("birth_year"))}"></label>
    </div>
    <label class="field">Тренер<input id="f-coach" value="${esc(v("coach"))}"></label>
    <div class="grid two">
      <label class="field">Вес, кг<input id="f-w" value="${esc(v("weight"))}"></label>
      <label class="field">Номер жребия, если уже есть<input id="f-draw" value="${esc(v("draw_number"))}"></label>
    </div>
    <button class="btn" id="f-ok" type="button">Сохранить</button>
  `);
  $("#f-ok").onclick = async () => {
    const body = {
      name: $("#f-name").value, organization: $("#f-org").value, rank: $("#f-rank").value,
      birth_year: $("#f-year").value, coach: $("#f-coach").value, weight: $("#f-w").value,
      draw_number: $("#f-draw").value,
    };
    const r = p ? await api("/api/participants/"+p.id, { method:"PUT", body }) : await api("/api/participants", { method:"POST", body });
    if (r.duplicate_warning) toast("Похожий участник уже есть", "err");
    closeModal(); show("people");
  };
}

function renderBracket(el, d, methods) {
  const byRound = {};
  d.bouts.forEach(b => { (byRound[b.round_code] ||= []).push(b); });
  const order = ["1/32","1/16","1/8","1/4","круг","1/2","финал","за бронзу","без боя","авто"];
  const cols = order.filter(k => byRound[k]);
  const who = (eid) => d.entries.find(e => e.id === eid);
  const nameOf = (e) => e ? `${e.control_number}. ${e.name}` : "ещё нет пары";
  el.innerHTML = `<div class="cols">${cols.map(code => `
    <div class="col">
      <div class="col-title">${esc(roundRu(code))}</div>
      ${byRound[code].sort((a,b)=>a.slot-b.slot).map(b => {
        if (b.is_bye) {
          const p = who(b.blue_entry_id);
          const label = (b.round_code === "авто" || b.round_code === "без боя") ? "1-е место без боя" : "проход дальше";
          return `<div class="match"><header>${esc(label)}</header><div class="p">${esc(nameOf(p))}</div></div>`;
        }
        const bl = who(b.blue_entry_id), rd = who(b.red_entry_id);
        const cls = (eid) => !b.winner_entry_id ? "" : (eid===b.winner_entry_id ? "win" : "lose");
        const ready = bl && rd;
        return `<div class="match ${ready?"clickable":""}" data-bout="${b.id}">
          <header><span>${b.bout_no ? "бой № "+b.bout_no : "пара"}</span><span>${ready ? "нажмите, чтобы записать" : ""}</span></header>
          <div class="p blue-row ${cls(b.blue_entry_id)}"><span>${esc(nameOf(bl))}</span><span class="corner">СИНИЙ</span></div>
          <div class="p red-row ${cls(b.red_entry_id)}"><span>${esc(nameOf(rd))}</span><span class="corner">КРАСНЫЙ</span></div>
        </div>`;
      }).join("")}
    </div>`).join("")}</div>`;
  el.onclick = (e) => {
    const node = e.target.closest("[data-bout]");
    if (!node) return;
    const b = d.bouts.find(x => x.id == node.dataset.bout);
    if (!b || !b.blue_entry_id || !b.red_entry_id) return;
    resultForm({
      ...b,
      blue: who(b.blue_entry_id),
      red: who(b.red_entry_id),
    }, methods, () => show("brackets"));
  };
}

boot().then(() => show("archives"));
