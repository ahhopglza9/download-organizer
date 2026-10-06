// 입력창 화면. Python 쪽 Api(main.py)를 window.pywebview.api 로 부릅니다.
(function () {
  const $ = (id) => document.getElementById(id);
  const fileEl = $("file-name");
  const pendingEl = $("pending");
  const queryEl = $("query");
  const statusEl = $("status");
  const listEl = $("results");
  const pickEl = $("pick");

  let results = [];
  let selected = 0;
  let seq = 0;            // 늦게 도착한 이전 검색 결과를 버리기 위한 번호
  let resultsSeq = 0;     // 지금 보이는 결과가 몇 번째 검색의 결과인지
  let searching = null;   // 진행 중인 검색 (Enter가 기다릴 수 있도록)
  let shownId = null;     // 지금 화면에 보이는 파일의 번호 (Python Api.state().id)
  let debounce = null;
  let busy = false;       // 옮기는 중에는 다시 누르지 못하게

  const api = () => window.pywebview.api;

  function setStatus(text, kind) {
    statusEl.textContent = text || "";
    if (kind) statusEl.dataset.kind = kind;
    else delete statusEl.dataset.kind;
  }

  function idleStatus() {
    const q = queryEl.value.trim();
    if (q && results.length === 0) {
      setStatus("비슷한 폴더가 없어요. 다른 말로 입력해 보세요.");
    } else {
      setStatus("");
    }
  }

  function render() {
    listEl.replaceChildren(...results.map((r, i) => {
      const li = document.createElement("li");
      li.className = "row";
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === selected));
      li.title = r.path;
      const name = document.createElement("span");
      name.className = "row-name";
      name.textContent = r.name;
      const where = document.createElement("span");
      where.className = "row-where";
      where.textContent = r.location;
      if (r.remembered) {
        const tag = document.createElement("span");
        tag.className = "row-tag";
        tag.textContent = "전에 고름";
        li.append(name, tag, where);
      } else {
        li.append(name, where);
      }
      li.addEventListener("mousedown", (e) => e.preventDefault()); // 입력칸 포커스 유지
      li.addEventListener("click", () => move(i));
      li.addEventListener("mouseenter", () => { selected = i; markSelected(); });
      return li;
    }));
  }

  function markSelected() {
    [...listEl.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === selected)));
  }

  async function search() {
    const q = queryEl.value.trim();
    const mine = ++seq;
    if (!q) {
      results = [];
      resultsSeq = mine;
      render();
      idleStatus();
      return;
    }
    const found = await api().search(q);
    if (mine !== seq) return;
    results = found;
    resultsSeq = mine;
    selected = 0;
    render();
    idleStatus();
  }

  function startSearch() {
    debounce = null;
    searching = search();
    return searching;
  }

  // 다음 파일로. 그사이 화면에 다른 파일이 떴으면 Python 쪽에서 무시합니다.
  const nextFile = () => api().next_file(shownId);

  // 옮기기 결과 처리 (추천에서 골랐든, 직접 골랐든 같음)
  function afterMove(res, row) {
    if (res.ok) {
      row?.classList.add("moved");
      setStatus(`${res.folder} 폴더로 옮겼어요.`, "ok");
      setTimeout(nextFile, 900);
    } else {
      setStatus(res.error, "error");
      if (res.gone) setTimeout(nextFile, 1600);
      else busy = false;
    }
  }

  async function move(i) {
    if (busy || !results[i]) return;
    busy = true;
    const res = await api().move(results[i].path, queryEl.value.trim());
    afterMove(res, listEl.children[i]);
  }

  // "다른 폴더 고르기": Windows 폴더 선택 창에서 고른 폴더로 옮기고, 검색어를 기억합니다.
  async function pickFolder() {
    if (busy) return;
    busy = true;
    const res = await api().pick_folder(queryEl.value.trim());
    if (res.cancelled) {
      busy = false;
      queryEl.focus();
      return;
    }
    afterMove(res, null);
  }

  // newFile이 false면 대기 개수만 바꾸고 입력 내용은 그대로 둡니다.
  async function refresh(newFile) {
    const s = await api().state();
    if (!s.file) return;
    fileEl.textContent = s.file;
    fileEl.title = s.file;
    pendingEl.textContent = s.pending > 0 ? `대기 중인 파일 ${s.pending}개` : "";
    if (!newFile) return;
    shownId = s.id;
    busy = false;
    seq++;
    queryEl.value = "";
    results = [];
    render();
    idleStatus();
    queryEl.focus();
  }

  queryEl.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(startSearch, 150);
  });

  queryEl.addEventListener("keydown", async (e) => {
    if (e.key === "ArrowDown" && results.length) {
      selected = (selected + 1) % results.length;
      markSelected();
      e.preventDefault();
    } else if (e.key === "ArrowUp" && results.length) {
      selected = (selected - 1 + results.length) % results.length;
      markSelected();
      e.preventDefault();
    } else if (e.key === "Enter") {
      e.preventDefault();
      // 입력 직후나 검색 중에 누른 Enter: 마지막 입력의 검색이 끝날 때까지 기다린 뒤, 그 결과로 옮깁니다.
      if (debounce) {
        clearTimeout(debounce);
        await startSearch();
      } else if (searching) {
        await searching;
      }
      if (resultsSeq === seq && results.length) move(selected);
    } else if (e.key === "Escape") {
      if (!busy) nextFile();
      e.preventDefault();
    }
  });

  pickEl.addEventListener("mousedown", (e) => e.preventDefault()); // 입력칸 포커스 유지
  pickEl.addEventListener("click", pickFolder);
  document.addEventListener("keydown", (e) => {
    if (view !== "popup") return;
    if (e.ctrlKey && (e.key === "o" || e.key === "O")) {
      e.preventDefault();
      pickFolder();
    }
  });

  // ---- 설정 화면 ----
  const popupEl = $("popup");
  const settingsEl = $("settings");
  const rootsEl = $("roots");
  const autostartEl = $("autostart");
  const memoryCountEl = $("memory-count");
  const clearEl = $("clear-memory");
  const addRootEl = $("add-root");
  const saveEl = $("save");
  const cancelEl = $("cancel");
  const settingsStatusEl = $("settings-status");
  let view = "popup";
  let firstRun = false;
  let confirmClear = false;

  function rootRow(r) {
    const li = document.createElement("li");
    li.className = "root";
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = r.checked;
    box.value = r.path;
    const name = document.createElement("span");
    name.className = "root-name";
    name.textContent = r.label;
    const where = document.createElement("span");
    where.className = "root-path";
    where.textContent = r.path;
    where.title = r.path;
    label.append(box, name, where);
    li.append(label);
    return li;
  }

  function setMemoryCount(n) {
    memoryCountEl.textContent = `고른 폴더 기억 ${n}개`;
    clearEl.hidden = n === 0;
    clearEl.textContent = "모두 지우기";
    confirmClear = false;
  }

  async function showSettings() {
    const s = await api().get_settings();
    firstRun = s.first_run;
    rootsEl.replaceChildren(...s.roots.map(rootRow));
    autostartEl.checked = s.autostart;
    setMemoryCount(s.memory_count);
    saveEl.textContent = firstRun ? "시작하기" : "저장";
    cancelEl.hidden = firstRun;
    settingsStatusEl.textContent = "";
    popupEl.hidden = true;
    settingsEl.hidden = false;
    view = "settings";
    saveEl.focus();
  }

  function closeSettings(hasFile) {
    if (view !== "settings") return;
    settingsEl.hidden = true;
    popupEl.hidden = false;
    view = "popup";
    if (hasFile) {
      refresh(false);
      queryEl.focus();
    }
  }

  addRootEl.addEventListener("click", async () => {
    const r = await api().add_root();
    if (!r) return;
    const existing = [...rootsEl.querySelectorAll("input")].find((b) => b.value.toLowerCase() === r.path.toLowerCase());
    if (existing) existing.checked = true;
    else rootsEl.append(rootRow({ ...r, checked: true }));
  });

  clearEl.addEventListener("click", async () => {
    if (!confirmClear) {
      confirmClear = true;
      clearEl.textContent = "정말 지울까요? 한 번 더 누르면 지워요";
      return;
    }
    setMemoryCount(await api().clear_memory());
  });

  saveEl.addEventListener("click", async () => {
    const roots = [...rootsEl.querySelectorAll("input:checked")].map((b) => b.value);
    const res = await api().save_settings(roots, autostartEl.checked);
    if (!res.ok) {
      settingsStatusEl.textContent = res.error;
      return;
    }
    closeSettings(res.has_file);
  });

  async function cancelSettings() {
    if (firstRun) return;
    const res = await api().close_settings();
    closeSettings(res.has_file);
  }

  cancelEl.addEventListener("click", cancelSettings);
  document.addEventListener("keydown", (e) => {
    if (view === "settings" && e.key === "Escape") {
      e.preventDefault();
      cancelSettings();
    }
  });

  window.app = { refresh, focusInput: () => queryEl.focus(), showSettings, closeSettings };
  window.addEventListener("pywebviewready", async () => {
    const s = await api().state();
    if (s.settings_open) showSettings();
    else refresh(true);
  });
  window.addEventListener("focus", () => { if (view === "popup") queryEl.focus(); });
})();
