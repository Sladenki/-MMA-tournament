const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];

const state = {
  view: "setup",
  boot: null,
  sort: "seq",
  catId: null,
};

const titles = {
  setup: ["Реквизиты", "Название, судьи, возрасты, дивизионы и веса"],
  people: ["Участники", "Реестр, импорт, поиск и сортировки как в старом файле"],
  weigh: ["Взвешивание", "Фактический вес, допуск, история перевзвешивания"],
  cats: ["Категории", "Разбиение, отчёт «не размещены», жеребьёвка"],
  brackets: ["Сетки", "Клик по паре — внести победителя. Победители продвигаются сами"],
  bouts: ["Бои", "Сквозная нумерация, углы, ринг, характер победы"],
  results: ["Итоги", "Места, очки, командный зачёт, мандатная комиссия"],
  docs: ["Документы", "Печать в PDF из браузера, выгрузка XLSX"],
};

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
  n.style.cssText = `position:fixed;right:18px;bottom:18px;background:${kind==="ok"?"#1f1a17":"#9c1d1d"};color:#fff;padding:10px 14px;border-radius:6px;z-index:50`;
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
  try { const r = await api("/api/undo", { method: "POST", body: {} }); toast("Отменено: " + r.undone); show(state.view); }
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
  const fn = views[view];
  $("#view").innerHTML = "<p class='hint'>загрузка…</p>";
  try { await fn(); } catch (e) { $("#view").innerHTML = `<div class="warn-box">${esc(e.message)}</div>`; }
}

const views = {
  async setup() {
    const t = state.boot.tournament;
    $("#view").innerHTML = `
      <div class="grid two">
        <div class="card">
          <h2>Турнир</h2>
          <label class="field">Название<input id="t-name" value="${esc(t.name)}"></label>
          <label class="field">Вид<input id="t-kind" value="${esc(t.kind)}"></label>
          <div class="grid two">
            <label class="field">Дата<input id="t-date" type="date" value="${esc(t.date||"")}"></label>
            <label class="field">Город<input id="t-city" value="${esc(t.city)}"></label>
          </div>
          <label class="field">Главный судья<input id="t-ref" value="${esc(t.chief_referee)}"></label>
          <label class="field">Главный секретарь<input id="t-sec" value="${esc(t.chief_secretary)}"></label>
          <div class="grid two">
            <label class="field">Рингов<input id="t-rings" type="number" min="1" value="${t.rings||1}"></label>
            <label class="field">Бой за бронзу
              <select id="t-bronze"><option value="0">две бронзы</option><option value="1">играть за 3–4</option></select>
            </label>
          </div>
          <label class="field"><span><input type="checkbox" id="t-walk" ${t.award_walkover?"checked":""}> очки одиночке (n=1)</span></label>
          <button class="btn" id="t-save">Сохранить</button>
        </div>
        <div>
          <div class="card" style="margin-bottom:14px">
            <h2>Возрастные группы</h2>
            <div id="ages"></div>
            <div class="row"><input id="age-label" placeholder="2007-2008 или 2010+"><button class="btn tiny" id="age-add">Добавить</button></div>
          </div>
          <div class="card" style="margin-bottom:14px">
            <h2>Дивизионы</h2>
            <div id="divs"></div>
            <div class="row"><input id="div-code" placeholder="А"><button class="btn tiny" id="div-add">Добавить</button></div>
          </div>
          <div class="card">
            <h2>Весовые категории, кг</h2>
            <div id="wts"></div>
            <div class="row"><input id="wt-kg" placeholder="52,2"><button class="btn tiny" id="wt-add">Добавить</button></div>
          </div>
        </div>
      </div>
      <div class="card" style="margin-top:14px">
        <h2>Очки за места</h2>
        <div id="pts"></div>
        <button class="btn sec tiny" id="pts-save">Сохранить очки</button>
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
      toast("Реквизиты сохранены");
    };
    renderCatalogs();
    $("#age-add").onclick = async () => {
      await api("/api/age-groups", { method: "POST", body: { label: $("#age-label").value } });
      await boot(); renderCatalogs();
    };
    $("#div-add").onclick = async () => {
      await api("/api/divisions", { method: "POST", body: { code: $("#div-code").value } });
      await boot(); renderCatalogs();
    };
    $("#wt-add").onclick = async () => {
      await api("/api/weights", { method: "POST", body: { limit_kg: $("#wt-kg").value } });
      await boot(); renderCatalogs();
    };
    $("#pts-save").onclick = savePoints;
  },

  async people() {
    const list = await api("/api/participants?sort=" + state.sort);
    $("#view").innerHTML = `
      <div class="toolbar">
        <input id="q" placeholder="поиск…" style="max-width:240px">
        <select id="sort">
          <option value="seq">по номеру</option>
          <option value="team">команда → год → жребий</option>
          <option value="weight">вес</option>
          <option value="year_weight">год → вес</option>
          <option value="alpha">алфавит</option>
          <option value="draw">жребий</option>
        </select>
        <button class="btn" id="p-add">Добавить</button>
        <label class="btn sec file-btn">Импорт XLSX<input type="file" id="p-imp" accept=".xlsx,.xlsm,.csv" hidden></label>
        <a class="btn sec" href="/api/export/participants.xlsx">Скачать XLSX</a>
        <button class="btn sec" id="p-demo">Пример 14.09.2024</button>
      </div>
      <div class="card" style="padding:0;overflow:auto">
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
        <td>${p.weight ?? ""}</td><td><span class="badge">${esc(p.status)}</span></td>
        <td><button class="btn tiny sec" data-edit="${p.id}">изм.</button>
            <button class="btn tiny danger" data-del="${p.id}">×</button></td>
      </tr>`).join("");
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
      toast(`Импортировано: ${r.added}`); show("people");
    };
    $("#p-demo").onclick = async () => { await api("/api/demo", { method:"POST", body:{} }); toast("Загружен пример"); show("people"); };
  },

  async weigh() {
    const list = await api("/api/participants?sort=alpha");
    const left = list.filter(p => p.weight == null && p.status === "заявлен").length;
    $("#view").innerHTML = `
      <p class="hint">Без веса: <b>${left}</b>. Запятая и точка принимаются. Перевзвешивание пишется в историю.</p>
      <div class="card" style="padding:0;overflow:auto">
        <table class="data">
          <thead><tr><th>ФИО</th><th>Орг.</th><th>Год</th><th>Вес</th><th>Статус</th><th></th></tr></thead>
          <tbody>${list.map(p => `<tr>
            <td>${esc(p.name)}</td><td>${esc(p.organization)}</td><td>${p.birth_year??""}</td>
            <td><input data-w="${p.id}" value="${p.weight ?? ""}" style="width:80px"></td>
            <td><select data-st="${p.id}">
              ${["заявлен","взвешен","допущен","снят","не явился"].map(s => `<option ${s===p.status?"selected":""}>${s}</option>`).join("")}
            </select></td>
            <td><button class="btn tiny" data-save="${p.id}">записать</button>
                <button class="btn tiny sec" data-hist="${p.id}">история</button></td>
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
        openModal("История веса", h.length ? `<ul>${h.map(x=>`<li>${esc(x.recorded_at)} — ${x.weight} кг</li>`).join("")}</ul>` : "<p>пусто</p>");
      }
    };
  },

  async cats() {
    const cats = await api("/api/categories");
    $("#view").innerHTML = `
      <div class="toolbar">
        <button class="btn" id="do-class">Разбить на категории</button>
        <span class="hint">Пересобирает сетки. Результаты боёв будут сброшены.</span>
      </div>
      <div id="unplaced"></div>
      <div class="card" style="padding:0;overflow:auto">
        <table class="data">
          <thead><tr><th>Возраст</th><th>Див.</th><th>Вес</th><th>n</th><th>Сетка</th><th></th></tr></thead>
          <tbody>${cats.map(c => `<tr>
            <td>${esc(c.age_label)}</td><td>${esc(c.division_code)}</td>
            <td>до ${esc(c.weight_label)}</td><td>${c.n}</td><td>${esc(c.bracket_kind||"")}</td>
            <td>
              <button class="btn tiny sec" data-open="${c.id}">сетка</button>
              <button class="btn tiny" data-redraw="${c.id}">пережеребить</button>
            </td>
          </tr>`).join("")}</tbody>
        </table>
      </div>`;
    $("#do-class").onclick = async () => {
      if (cats.length && !confirm("Пересобрать категории и сетки?")) return;
      const r = await api("/api/classify", { method:"POST", body:{} });
      const box = $("#unplaced");
      if (r.unplaced.length) {
        box.innerHTML = `<div class="warn-box"><b>Не размещены (${r.unplaced.length})</b><ul>${
          r.unplaced.map(u => `<li>${esc(u.participant.name)} — ${esc(u.reason)}</li>`).join("")
        }</ul></div>`;
      } else box.innerHTML = `<p class="hint">Все взвешенные участники размещены.</p>`;
      toast("Категории собраны: " + r.categories.length);
      if (!r.unplaced.length) show("cats");
    };
    $("#view").onclick = async (e) => {
      if (e.target.dataset.open) { state.catId = +e.target.dataset.open; show("brackets"); }
      if (e.target.dataset.redraw && confirm("Пережеребить категорию?")) {
        await api(`/api/categories/${e.target.dataset.redraw}/redraw`, { method:"POST", body:{} });
        toast("Новый жребий записан в журнал");
        show("cats");
      }
    };
  },

  async brackets() {
    const cats = await api("/api/categories");
    if (!cats.length) { $("#view").innerHTML = "<p>Сначала разбейте участников на категории.</p>"; return; }
    if (!state.catId) state.catId = cats[0].id;
    const d = await api("/api/categories/" + state.catId);
    const methods = (state.boot.methods||[]).map(m => `<option>${m}</option>`).join("");
    $("#view").innerHTML = `
      <div class="toolbar">
        <select id="cat-sel">${cats.map(c => `<option value="${c.id}" ${c.id===state.catId?"selected":""}>${esc(c.age_label)} ${esc(c.division_code)} ${esc(c.weight_label)} (${c.n})</option>`).join("")}</select>
        <button class="btn sec" id="br-redraw">Пережеребить</button>
      </div>
      <div class="grid two">
        <div class="card">
          <h2>Участники (контр. №)</h2>
          <ol>${d.entries.map(e => `<li value="${e.control_number}">${esc(e.name)} <span class="hint">${esc(e.organization)}</span></li>`).join("")}</ol>
        </div>
        <div class="card">
          <h2>Сетка</h2>
          <div class="bracket-wrap" id="br"></div>
        </div>
      </div>`;
    $("#cat-sel").onchange = () => { state.catId = +$("#cat-sel").value; show("brackets"); };
    $("#br-redraw").onclick = async () => {
      await api(`/api/categories/${state.catId}/redraw`, { method:"POST", body:{} });
      show("brackets");
    };
    renderBracket($("#br"), d, methods);
  },

  async bouts() {
    const list = await api("/api/bouts");
    const methods = (state.boot.methods||[]).map(m => `<option>${m}</option>`).join("");
    $("#view").innerHTML = `
      <div class="card" style="padding:0;overflow:auto">
        <table class="data">
          <thead><tr><th>№</th><th>Категория</th><th>Тур</th><th>Синий</th><th>Красный</th><th>Победитель</th><th>Ринг</th><th></th></tr></thead>
          <tbody>${list.map(b => `<tr>
            <td>${b.bout_no??""}</td>
            <td>${esc(b.age_label)} ${esc(b.division_code)} ${esc(b.weight_label)}</td>
            <td>${esc(b.round_code)}</td>
            <td class="blue">${b.blue?esc(b.blue.name):"—"}</td>
            <td class="red">${b.red?esc(b.red.name):"—"}</td>
            <td>${b.winner?esc(b.winner.name):(b.blue&&b.red?"":"ожидание")}</td>
            <td><input data-ring="${b.id}" value="${b.ring??""}" style="width:48px"></td>
            <td>${b.blue&&b.red&&!b.winner?`<button class="btn tiny" data-res="${b.id}">результат</button>`:""}
                ${b.winner?`<button class="btn tiny sec" data-clr="${b.id}">сброс</button>`:""}</td>
          </tr>`).join("")}</tbody>
        </table>
      </div>`;
    $("#view").onclick = async (e) => {
      const id = e.target.dataset.res || e.target.dataset.clr;
      if (e.target.dataset.clr) { await api(`/api/bouts/${id}/clear`, { method:"POST", body:{} }); show("bouts"); }
      if (e.target.dataset.res) {
        const b = list.find(x => x.id == id);
        openModal("Результат боя № "+b.bout_no, `
          <p><span class="blue">${esc(b.blue.name)}</span> — <span class="red">${esc(b.red.name)}</span></p>
          <label class="field">Победитель
            <select id="w-id">
              <option value="${b.blue.id}">синий: ${esc(b.blue.name)}</option>
              <option value="${b.red.id}">красный: ${esc(b.red.name)}</option>
            </select>
          </label>
          <label class="field">Характер<select id="w-m">${methods}</select></label>
          <button class="btn" id="w-ok">Записать</button>`);
        $("#w-ok").onclick = async () => {
          await api(`/api/bouts/${id}/result`, { method:"POST", body:{ winner_entry_id:+$("#w-id").value, method:$("#w-m").value }});
          closeModal(); show("bouts");
        };
      }
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
          <h2 style="padding:12px 12px 0">Личные места</h2>
          <table class="data"><thead><tr><th>Кат.</th><th>Место</th><th>ФИО</th><th>Орг.</th><th>Очки</th></tr></thead>
          <tbody>${places.map(p => `<tr><td>${esc(p.age_label)} ${esc(p.division_code)} ${esc(p.weight_label)}</td>
            <td>${p.place}</td><td>${esc(p.name)}</td><td>${esc(p.organization)}</td><td>${p.points}</td></tr>`).join("")}</tbody></table>
        </div>
        <div class="card" style="padding:0;overflow:auto">
          <h2 style="padding:12px 12px 0">Команды</h2>
          <table class="data"><thead><tr><th>Место</th><th>Организация</th><th>Очки</th><th>Представитель</th></tr></thead>
          <tbody>${teams.map(s => `<tr><td>${s.place}</td><td>${esc(s.organization)}</td><td>${s.points}</td>
            <td><input data-org="${esc(s.organization)}" value="${esc(s.representative)}" style="width:140px"></td></tr>`).join("")}</tbody></table>
        </div>
      </div>
      <div class="card" style="margin-top:14px;overflow:auto">
        <h2>Мандатная комиссия</h2>
        <table class="data">
          <thead><tr><th>Организация</th>${whead}<th>Итого</th></tr></thead>
          <tbody>${man.rows.map(r => `<tr><td>${esc(r.organization)}</td>${man.weights.map(w=>`<td>${r.cells[w]||""}</td>`).join("")}<td>${r.total}</td></tr>`).join("")}
          <tr><th>Итого</th>${man.weights.map(w=>`<th>${man.col_totals[w]||0}</th>`).join("")}<th>${man.grand_total}</th></tr></tbody>
        </table>
        <p class="hint" style="padding-top:8px">${Object.entries(man.titles).map(([k,v])=>`${esc(k)}: ${v}`).join(" · ")}</p>
      </div>`;
    $$("input[data-org]").forEach(inp => inp.onchange = () => {
      api("/api/teams/rep", { method:"POST", body:{ organization: inp.dataset.org, representative: inp.value }});
    });
  },

  async docs() {
    const items = [
      ["/print/weigh-in", "Протокол взвешивания и жеребьёвки"],
      ["/print/mandate", "Протокол мандатной комиссии"],
      ["/print/pairs", "Список пар"],
      ["/print/corners", "Список боёв по углам"],
      ["/print/brackets", "Сетки"],
      ["/print/personal", "Личное первенство"],
      ["/print/scorecards", "Судейские записки"],
      ["/print/teams", "Командный протокол"],
      ["/print/medals", "Призёры"],
      ["/print/certificates", "Грамоты"],
      ["/print/report", "Итоговый отчёт"],
      ["/api/export/report.xlsx", "Выгрузка XLSX (мандат, команды, места)"],
      ["/api/export", "Весь турнир JSON (резервная копия)"],
    ];
    $("#view").innerHTML = `
      <p class="hint">Печатная форма открывается в новой вкладке — «Печать» браузера даёт PDF. Для мессенджера можно сохранить страницу как PDF или сделать снимок сетки.</p>
      <div class="docs grid two">${items.map(([h,t]) => `<a href="${h}" target="_blank">${esc(t)}</a>`).join("")}</div>`;
  },
};

function renderCatalogs() {
  const b = state.boot;
  $("#ages").innerHTML = b.age_groups.map(g =>
    `<div class="row" style="margin-bottom:6px"><span>${esc(g.label)} (${g.year_from}–${g.year_to})</span>
     <button class="btn tiny danger" data-del-age="${g.id}">×</button></div>`).join("") || "<p class='hint'>нет</p>";
  $("#divs").innerHTML = b.divisions.map(d =>
    `<div class="row" style="margin-bottom:6px"><span>${esc(d.code)}</span>
     <button class="btn tiny danger" data-del-div="${d.id}">×</button></div>`).join("") || "<p class='hint'>нет</p>";
  $("#wts").innerHTML = b.weights.map(w =>
    `<div class="row" style="margin-bottom:6px"><span>до ${esc(w.label)}</span>
     <button class="btn tiny danger" data-del-wt="${w.id}">×</button></div>`).join("") || "<p class='hint'>нет</p>";
  $("#pts").innerHTML = b.point_rules.map((p,i) =>
    `<div class="row" style="margin-bottom:6px">места <input data-pf="${i}" value="${p.place_from}" style="width:60px">–<input data-pt="${i}" value="${p.place_to}" style="width:60px">
     очки <input data-pp="${i}" value="${p.points}" style="width:60px"></div>`).join("");
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
    <label class="field">Фамилия имя<input id="f-name" value="${esc(v("name"))}"></label>
    <label class="field">Город, организация<input id="f-org" value="${esc(v("organization"))}"></label>
    <div class="grid two">
      <label class="field">Разряд / дивизион<input id="f-rank" value="${esc(v("rank"))}"></label>
      <label class="field">Год рождения<input id="f-year" value="${esc(v("birth_year"))}"></label>
    </div>
    <label class="field">Тренер<input id="f-coach" value="${esc(v("coach"))}"></label>
    <div class="grid two">
      <label class="field">Вес<input id="f-w" value="${esc(v("weight"))}"></label>
      <label class="field">Жребий (необяз.)<input id="f-draw" value="${esc(v("draw_number"))}"></label>
    </div>
    <button class="btn" id="f-ok">Сохранить</button>
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
  const order = ["1/32","1/16","1/8","1/4","круг","1/2","финал","за бронзу","авто"];
  const cols = order.filter(k => byRound[k]);
  const who = (eid) => d.entries.find(e => e.id === eid);
  el.innerHTML = `<div class="cols">${cols.map(code => `
    <div class="col"><div class="hint">${esc(code)}</div>
      ${byRound[code].sort((a,b)=>a.slot-b.slot).map(b => {
        if (b.is_bye) {
          const p = who(b.blue_entry_id);
          return `<div class="match"><header>проход</header><div class="p">${p?esc(p.control_number+". "+p.name):"—"}</div></div>`;
        }
        const bl = who(b.blue_entry_id), rd = who(b.red_entry_id);
        const cls = (eid) => !b.winner_entry_id ? "" : (eid===b.winner_entry_id ? "win" : "lose");
        return `<div class="match" data-bout="${b.id}">
          <header>бой ${b.bout_no||"—"}</header>
          <div class="p blue ${cls(b.blue_entry_id)}">${bl?esc(bl.control_number+". "+bl.name):"…"}</div>
          <div class="p red ${cls(b.red_entry_id)}">${rd?esc(rd.control_number+". "+rd.name):"…"}</div>
        </div>`;
      }).join("")}
    </div>`).join("")}</div>`;
  el.onclick = (e) => {
    const node = e.target.closest("[data-bout]");
    if (!node) return;
    const b = d.bouts.find(x => x.id == node.dataset.bout);
    if (!b || !b.blue_entry_id || !b.red_entry_id) return;
    const bl = who(b.blue_entry_id), rd = who(b.red_entry_id);
    openModal("Бой № "+(b.bout_no||""), `
      <label class="field">Победитель
        <select id="w-id">
          <option value="${bl.id}">синий: ${esc(bl.name)}</option>
          <option value="${rd.id}">красный: ${esc(rd.name)}</option>
        </select>
      </label>
      <label class="field">Характер<select id="w-m">${methods}</select></label>
      <div class="row">
        <button class="btn" id="w-ok">Записать</button>
        ${b.winner_entry_id?'<button class="btn sec" id="w-clr">Сбросить</button>':""}
      </div>`);
    $("#w-ok").onclick = async () => {
      await api(`/api/bouts/${b.id}/result`, { method:"POST", body:{ winner_entry_id:+$("#w-id").value, method:$("#w-m").value }});
      closeModal(); show("brackets");
    };
    const clr = $("#w-clr");
    if (clr) clr.onclick = async () => { await api(`/api/bouts/${b.id}/clear`, { method:"POST", body:{} }); closeModal(); show("brackets"); };
  };
}

boot().then(() => show("setup"));
