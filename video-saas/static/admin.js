const loginView = document.getElementById('login-view');
const dashboard = document.getElementById('dashboard-view');
const loginError = document.getElementById('login-error');
const pageSize = 50;
let pageOffset = 0;
let filteredTotal = 0;

async function jsonResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Error(data.detail || `服务器错误 ${res.status}`);
  return data;
}
function filters() {
  return { q: document.getElementById('job-search').value.trim(), status: document.getElementById('job-status-filter').value };
}
function filterQuery() {
  const f = filters();
  const p = new URLSearchParams();
  if (f.q) p.set('q', f.q);
  if (f.status) p.set('status', f.status);
  return p;
}
function addEmptyRow(body, columns, label) {
  const tr = document.createElement('tr');
  const td = document.createElement('td');
  td.colSpan = columns;
  td.textContent = label;
  tr.appendChild(td);
  body.appendChild(tr);
}

async function loadDashboard() {
  try {
    const params = filterQuery();
    params.set('limit', String(pageSize));
    params.set('offset', String(pageOffset));
    const [metrics, result, userResult] = await Promise.all([
      fetch('/api/admin/summary'),
      fetch(`/api/admin/jobs?${params.toString()}`),
      fetch('/api/admin/users')
    ]);
    if (metrics.status === 401 || result.status === 401 || userResult.status === 401) {
      loginView.hidden = false;
      dashboard.hidden = true;
      return;
    }
    const stats = await jsonResponse(metrics);
    const data = await jsonResponse(result);
    const userData = await jsonResponse(userResult);
    loginView.hidden = true;
    dashboard.hidden = false;
    for (const [key, id] of [['total','total-count'],['completed','done-count'],['pending','pending-count'],['failed','failed-count'],['cancelled','cancelled-count'],['users','users-count']]) {
      document.getElementById(id).textContent = stats[key] ?? 0;
    }

    filteredTotal = data.total;
    document.getElementById('result-count').textContent = `显示 ${data.jobs.length} 条 / 共 ${filteredTotal} 条`;
    document.getElementById('page-info').textContent = `第 ${Math.floor(pageOffset / pageSize) + 1} 页`;
    document.getElementById('prev-page').disabled = pageOffset <= 0;
    document.getElementById('next-page').disabled = pageOffset + pageSize >= filteredTotal;
    document.getElementById('export-csv').href = `/api/admin/jobs/export.csv?${filterQuery().toString()}`;

    const body = document.getElementById('jobs-body');
    body.replaceChildren();
    if (!data.jobs.length) addEmptyRow(body, 5, '没有符合条件的任务');
    for (const job of data.jobs) {
      const tr = document.createElement('tr');
      const cols = [new Date(job.created_at * 1000).toLocaleString('zh-CN'), job.source_url,
        ({queued:'排队中',running:'处理中',done:'已完成',error:'失败',cancelled:'已取消'})[job.status] || job.status,
        `${job.progress}%`];
      cols.forEach((value, index) => {
        const td = document.createElement('td');
        td.textContent = value;
        if (index === 1) td.className = 'url-cell';
        tr.appendChild(td);
      });
      const td = document.createElement('td');
      if (job.status !== 'queued' && job.status !== 'running') {
        const button = document.createElement('button');
        button.className = 'small-button';
        button.textContent = '删除';
        button.addEventListener('click', async () => {
          if (!confirm('确定删除这条任务及其缓存文件？')) return;
          try { await jsonResponse(await fetch(`/api/admin/jobs/${job.id}`, { method: 'DELETE' })); await loadDashboard(); }
          catch (error) { alert(error.message); }
        });
        td.appendChild(button);
      } else td.textContent = '—';
      tr.appendChild(td);
      body.appendChild(tr);
    }

    const usersBody = document.getElementById('users-body');
    usersBody.replaceChildren();
    if (!userData.users.length) addEmptyRow(usersBody, 6, '暂无 Google 登录用户');
    for (const user of userData.users) {
      const tr = document.createElement('tr');
      const values = [user.email, user.name || '—', new Date(user.created_at * 1000).toLocaleString('zh-CN'),
        new Date(user.last_login * 1000).toLocaleString('zh-CN'), String(user.task_count || 0)];
      values.forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.appendChild(td); });
      const td = document.createElement('td');
      const state = document.createElement('span'); state.textContent = user.is_active ? '启用' : '已停用'; td.appendChild(state);
      const button = document.createElement('button'); button.className = 'small-button'; button.style.marginLeft = '8px';
      button.textContent = user.is_active ? '停用' : '启用';
      button.addEventListener('click', async () => {
        if (!confirm(`${user.is_active ? '停用' : '启用'}账号 ${user.email}？`)) return;
        try {
          await jsonResponse(await fetch(`/api/admin/users/${encodeURIComponent(user.id)}`, {
            method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({is_active: !user.is_active})
          }));
          await loadDashboard();
        } catch (error) { alert(error.message); }
      });
      td.appendChild(button); tr.appendChild(td); usersBody.appendChild(tr);
    }
  } catch (error) {
    if (!dashboard.hidden) alert(error.message);
  }
}

document.getElementById('admin-login-form').addEventListener('submit', async event => {
  event.preventDefault(); loginError.hidden = true;
  try {
    await jsonResponse(await fetch('/api/admin/login', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({password: document.getElementById('admin-password').value}) }));
    document.getElementById('admin-password').value = '';
    await loadDashboard();
  } catch (error) { loginError.textContent = error.message; loginError.hidden = false; }
});
document.getElementById('refresh-btn').addEventListener('click', loadDashboard);
document.getElementById('search-jobs-btn').addEventListener('click', () => { pageOffset = 0; loadDashboard(); });
document.getElementById('job-search').addEventListener('keydown', event => { if (event.key === 'Enter') { pageOffset = 0; loadDashboard(); } });
document.getElementById('prev-page').addEventListener('click', () => { pageOffset = Math.max(0, pageOffset - pageSize); loadDashboard(); });
document.getElementById('next-page').addEventListener('click', () => { if (pageOffset + pageSize < filteredTotal) { pageOffset += pageSize; loadDashboard(); } });
document.getElementById('logout-btn').addEventListener('click', async () => { await fetch('/api/admin/logout', {method:'POST'}); loginView.hidden = false; dashboard.hidden = true; });
loadDashboard();
