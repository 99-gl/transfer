const importForm = document.querySelector('#import-form');
const previewButton = document.querySelector('#preview-button');
const commitButton = document.querySelector('#commit-button');
const importResult = document.querySelector('#import-result');
const searchForm = document.querySelector('#search-form');
const searchResult = document.querySelector('#search-result');
const detailResult = document.querySelector('#node-detail');
const connectionState = document.querySelector('#connection-state');

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setMessage(target, message, isError = false) {
  target.replaceChildren(element('div', `message${isError ? ' error' : ''}`, message));
}

function formData() {
  const data = new FormData();
  const file = document.querySelector('#excel-file').files[0];
  const sheet = document.querySelector('#sheet-name').value.trim();
  if (!file) throw new Error('请选择 Excel 文件。');
  data.append('file', file);
  if (sheet) data.append('sheet', sheet);
  return data;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || '请求失败，请检查服务状态。');
  }
  return response.json();
}

function renderChanges(payload, suffix = '') {
  importResult.replaceChildren();
  importResult.append(element('div', 'message', `${payload.nodes} 个节点、${payload.edges} 条关系${suffix}`));
  const changes = element('div', 'changes');
  const values = [
    ['新增节点', payload.changes.create_nodes],
    ['更新节点', payload.changes.update_nodes],
    ['删除节点', payload.changes.delete_nodes],
    ['新增关系', payload.changes.create_edges],
    ['更新关系', payload.changes.update_edges],
    ['删除关系', payload.changes.delete_edges],
  ];
  values.forEach(([label, value]) => {
    const item = element('div', 'change');
    item.append(element('span', '', label), element('strong', '', String(value)));
    changes.append(item);
  });
  importResult.append(changes);
}

importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  previewButton.disabled = true;
  commitButton.disabled = true;
  setMessage(importResult, '正在解析 Excel 并比对 Neo4j 数据...');
  try {
    const payload = await api('/api/imports/preview', { method: 'POST', body: formData() });
    renderChanges(payload, '，确认后将同步到图谱。');
    commitButton.disabled = false;
  } catch (error) {
    setMessage(importResult, error.message, true);
  } finally {
    previewButton.disabled = false;
  }
});

commitButton.addEventListener('click', async () => {
  commitButton.disabled = true;
  setMessage(importResult, '正在同步图谱...');
  try {
    const payload = await api('/api/imports/commit', { method: 'POST', body: formData() });
    renderChanges(payload, '，已完成同步。');
  } catch (error) {
    setMessage(importResult, error.message, true);
  }
});

function renderNodeDetail(node, edges = []) {
  detailResult.replaceChildren();
  const heading = element('div', 'message', `${node.name} (${node.type})`);
  const properties = element('dl', 'detail-grid');
  Object.entries(node.properties).forEach(([key, value]) => {
    properties.append(element('dt', '', key));
    properties.append(element('dd', '', Array.isArray(value) ? value.join(', ') : String(value ?? '')));
  });
  detailResult.append(heading, properties);
  if (edges.length) {
    const edgeList = element('div', 'edge-list');
    edgeList.append(element('strong', '', `关联关系 (${edges.length})`));
    edges.forEach((edge) => edgeList.append(element('div', 'edge-row', `${edge.relation}: ${edge.source_uuid} -> ${edge.target_uuid}`)));
    detailResult.append(edgeList);
  }
}

async function loadNode(uuid) {
  detailResult.replaceChildren(element('div', 'empty-state', '正在读取节点详情...'));
  try {
    const payload = await api(`/api/nodes/${encodeURIComponent(uuid)}`);
    renderNodeDetail(payload.node, payload.edges);
  } catch (error) {
    setMessage(detailResult, error.message, true);
  }
}

function renderSearch(payload) {
  searchResult.replaceChildren();
  if (!payload.nodes.length) {
    searchResult.append(element('div', 'empty-state', '没有找到匹配节点。'));
    return;
  }
  const selected = new Set(payload.matched_node_ids);
  searchResult.append(element('div', 'message', `命中 ${selected.size} 个节点，返回 ${payload.edges.length} 条直接关联关系。`));
  const list = element('div', 'result-list');
  payload.nodes.forEach((node) => {
    const row = element('div', 'node-row');
    const content = element('div');
    content.append(element('div', 'node-name', node.name));
    content.append(element('div', 'node-meta', `${node.type} · ${node.source_id}${selected.has(node.uuid) ? ' · 命中' : ' · 关联'}`));
    const button = element('button', '', '详情');
    button.type = 'button';
    button.addEventListener('click', () => loadNode(node.uuid));
    row.append(content, button);
    list.append(row);
  });
  searchResult.append(list);
}

searchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = document.querySelector('#search-query').value.trim();
  setMessage(searchResult, '正在查询图谱...');
  try {
    const payload = await api('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, include_neighbors: true }),
    });
    renderSearch(payload);
  } catch (error) {
    setMessage(searchResult, error.message, true);
  }
});

api('/healthcheck')
  .then(() => { connectionState.textContent = 'Neo4j 已连接'; })
  .catch(() => {
    connectionState.textContent = 'Neo4j 未连接';
    connectionState.classList.add('error');
  });
