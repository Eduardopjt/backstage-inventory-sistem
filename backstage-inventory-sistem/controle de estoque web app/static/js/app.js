// App principal - BACKSTAGE Profissional

let currentUser = null;
let accountInfo = null;
let allItems = [];
let allMovements = [];
let allCategories = [];
let locChart = null;
let typeChart = null;
let messageTimer = null;

// ==================== INICIALIZAÇÃO ====================
async function init() {
  try {
    const userRes = await fetch("/api/user");
    if (userRes.status === 401) {
      window.location.href = "/login";
      return;
    }
    currentUser = await userRes.json();

    const accountRes = await fetch("/api/account");
    if (!accountRes.ok) {
      throw new Error("Não foi possível carregar os dados da conta");
    }
    accountInfo = await accountRes.json();

    document.getElementById("userInfo").textContent = `${currentUser.account_name} · ${currentUser.username}`;
    document.getElementById("currentAccount").textContent = currentUser.account_name;
    document.getElementById("currentUsername").textContent = currentUser.username;
    document.getElementById("currentPlan").textContent = accountInfo.plan;

    setupEventListeners();
    await loadCategories();
    await loadLocations();
    updatePlanUI();
    loadDashboard();
  } catch (error) {
    console.error("Erro ao inicializar:", error);
    window.location.href = "/login";
  }
}

function showMessage(message, type = "success") {
  clearMessage();
  const alertEl = document.getElementById("appMessage");
  if (!alertEl) return;
  alertEl.textContent = message;
  alertEl.className = `app-message ${type}`;
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "×";
  closeBtn.addEventListener("click", clearMessage);
  alertEl.appendChild(closeBtn);
  messageTimer = setTimeout(clearMessage, 5000);
}

function clearMessage() {
  const alertEl = document.getElementById("appMessage");
  if (!alertEl) return;
  alertEl.className = "app-message hidden";
  alertEl.textContent = "";
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
}

// ==================== NAVEGAÇÃO ====================
function setupEventListeners() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const page = btn.dataset.page;
      changePage(page, e);
    });
  });

  document.getElementById("logoutBtn").addEventListener("click", () => {
    window.location.href = "/logout";
  });

  document.getElementById("upgradePlanBtn").addEventListener("click", upgradePlan);

  // Event listeners para páginas
  document.getElementById("addItemBtn").addEventListener("click", () => openItemModal());
  document.getElementById("addCategoryBtn").addEventListener("click", addCategory);
  document.getElementById("changePasswordBtn").addEventListener("click", () => openChangePasswordModal());
  document.getElementById("reportSupplierBtn").addEventListener("click", generateSupplierReport);
  document.getElementById("reportLocationBtn").addEventListener("click", generateLocationReport);
  document.getElementById("exportCSVBtn").addEventListener("click", exportCSV);
  document.getElementById("exportPDFBtn").addEventListener("click", exportPDF);

  // Modais
  document.querySelectorAll(".modal-close").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.target.closest(".modal").classList.add("hidden");
    });
  });

  window.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal")) {
      e.target.classList.add("hidden");
    }
  });

  // Filtros
  document.getElementById("searchInput").addEventListener("input", loadItems);
  document.getElementById("categoryFilter").addEventListener("change", loadItems);
  document.getElementById("dateStart").addEventListener("change", loadHistorico);
  document.getElementById("dateEnd").addEventListener("change", loadHistorico);
  document.getElementById("searchMovement").addEventListener("input", filterMovements);
  document.getElementById("movementTypeFilter").addEventListener("change", renderMovements);

  // Forms
  document.getElementById("itemForm").addEventListener("submit", saveItem);
  document.getElementById("movementForm").addEventListener("submit", saveMovement);
  document.getElementById("changePasswordForm").addEventListener("submit", saveNewPassword);
}

function changePage(page, e) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById(`${page}-page`).classList.add("active");
  if (e) e.target.classList.add("active");

  switch (page) {
    case "items":
      loadItems();
      break;
    case "historico":
      loadHistorico();
      break;
    case "dashboard":
      loadDashboard();
      break;
  }
}

// ==================== DASHBOARD ====================
async function loadDashboard() {
  const [itemsRes, balancoRes] = await Promise.all([fetch("/api/items"), fetch("/api/balanco")]);
  allItems = await itemsRes.json();
  const balanco = await balancoRes.json();

  const totalQty = balanco.total_quantity;
  const lowCount = Array.isArray(balanco.low_stock) ? balanco.low_stock.length : 0;
  const totalValue = balanco.total_value || 0;

  document.getElementById("kpi-items").textContent = balanco.total_items;
  document.getElementById("kpi-quantity").textContent = totalQty;
  document.getElementById("kpi-low").textContent = lowCount;
  document.getElementById("kpi-value").textContent = `R$ ${totalValue.toFixed(2)}`;

  const lowStockList = document.getElementById("lowStockList");
  lowStockList.innerHTML = "";
  allItems
    .filter((item) => item.quantity <= (item.min_quantity || 5))
    .forEach((item) => {
      const div = document.createElement("div");
      div.className = "low-stock-item";
      div.innerHTML = `<strong>${item.name}</strong> <span>${item.quantity} / ${item.min_quantity}</span>`;
      lowStockList.appendChild(div);
    });

  updateCharts(balanco.movement_types || {});
}

async function updateCharts(movementTypes = {}) {
  const locations = {};
  allItems.forEach((item) => {
    const loc = item.location || "Sem local";
    locations[loc] = (locations[loc] || 0) + item.quantity;
  });

  const locCtx = document.getElementById("locChart").getContext("2d");
  if (locChart) locChart.destroy();
  locChart = new Chart(locCtx, {
    type: "bar",
    data: {
      labels: Object.keys(locations),
      datasets: [
        {
          label: "Quantidade",
          data: Object.values(locations),
          backgroundColor: "#667eea",
        },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });

  const movementValues = [
    movementTypes.ENTRADA || 0,
    movementTypes.SAIDA || 0,
    movementTypes.AJUSTE || 0,
  ];

  const typeCtx = document.getElementById("typeChart").getContext("2d");
  if (typeChart) typeChart.destroy();
  typeChart = new Chart(typeCtx, {
    type: "pie",
    data: {
      labels: ["Entrada", "Saída", "Ajuste"],
      datasets: [
        {
          data: movementValues,
          backgroundColor: ["#10b981", "#f59e0b", "#8b5cf6"],
        },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

// ==================== ITENS ====================
async function loadItems() {
  const search = document.getElementById("searchInput").value;
  const category = document.getElementById("categoryFilter").value;
  let url = "/api/items";
  const params = new URLSearchParams();
  if (search) params.set("q", search);
  if (category) params.set("category", category);
  if (params.toString()) url += `?${params.toString()}`;

  const res = await fetch(url);
  allItems = await res.json();
  renderItems();
}

function renderItems() {
  const tbody = document.getElementById("itemsTableBody");
  tbody.innerHTML = "";

  if (allItems.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Nenhum item encontrado. Adicione um novo item para começar.</td></tr>`;
    return;
  }

  allItems.forEach((item) => {
    const tr = document.createElement("tr");
    if (item.quantity <= (item.min_quantity || 5)) tr.classList.add("low-stock-row");

    tr.innerHTML = `
      <td>${item.name}</td>
      <td>${item.sku || "-"}</td>
      <td>${item.category || "-"}</td>
      <td>${item.quantity}</td>
      <td>${item.min_quantity || 0}</td>
      <td>${item.location || "-"}</td>
      <td>
        <div class="action-buttons">
          <button class="btn-sm btn-entrada" onclick="openMovementModal(${item.id}, 'entrada')">+E</button>
          <button class="btn-sm btn-saida" onclick="openMovementModal(${item.id}, 'saida')">-S</button>
          <button class="btn-sm btn-ajuste" onclick="openMovementModal(${item.id}, 'ajuste')">A</button>
          <button class="btn-sm btn-edit" onclick="editItem(${item.id})">Edit</button>
          <button class="btn-sm btn-delete" onclick="deleteItem(${item.id})">Del</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function openItemModal(itemId = null) {
  if (!itemId && accountInfo && accountInfo.limits.max_items !== null && accountInfo.item_count >= accountInfo.limits.max_items) {
    showMessage("Limite do plano atingido. Faça upgrade para PRO.", "error");
    return;
  }

  const modal = document.getElementById("itemModal");
  const quantityField = document.getElementById("itemQuantity");
  const quantityLabel = document.getElementById("itemQuantityLabel");
  const quantityNote = document.getElementById("itemQuantityNote");

  if (itemId) {
    const item = allItems.find((i) => i.id === itemId);
    document.getElementById("itemModalTitle").textContent = "Editar Item";
    document.getElementById("itemId").value = itemId;
    document.getElementById("itemName").value = item.name;
    document.getElementById("itemSKU").value = item.sku || "";
    document.getElementById("itemCategory").value = item.category || "";
    document.getElementById("itemDescription").value = item.description || "";
    quantityField.value = item.quantity;
    quantityField.disabled = true;
    quantityLabel.textContent = "Quantidade Atual";
    quantityNote.classList.remove("hidden");
    document.getElementById("itemMinQuantity").value = item.min_quantity || 0;
    document.getElementById("itemLocation").value = item.location || "";
    await loadLocations();
  } else {
    document.getElementById("itemModalTitle").textContent = "Novo Item";
    document.getElementById("itemForm").reset();
    document.getElementById("itemId").value = "";
    quantityField.disabled = false;
    quantityLabel.textContent = "Quantidade";
    quantityNote.classList.add("hidden");
    document.getElementById("itemLocation").value = "";
    await loadLocations();
  }
  modal.classList.remove("hidden");
}

async function saveItem(e) {
  e.preventDefault();
  const itemId = document.getElementById("itemId").value;
  const quantityValue = parseInt(document.getElementById("itemQuantity").value);
  const minQuantityValue = parseInt(document.getElementById("itemMinQuantity").value);
  const data = {
    name: document.getElementById("itemName").value,
    sku: document.getElementById("itemSKU").value,
    category: document.getElementById("itemCategory").value,
    description: document.getElementById("itemDescription").value,
    min_quantity: isNaN(minQuantityValue) ? 0 : minQuantityValue,
    location: document.getElementById("itemLocation").value,
  };
  if (!itemId) {
    data.quantity = isNaN(quantityValue) ? 0 : quantityValue;
  }

  try {
    let res;
    if (itemId) {
      res = await fetch(`/api/items/${itemId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    } else {
      res = await fetch("/api/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    }

    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
    } else {
      document.getElementById("itemModal").classList.add("hidden");
      await loadItems();
      await refreshAccountInfo();
      showMessage(`Item ${itemId ? "atualizado" : "criado"} com sucesso.`, "success");
    }
  } catch (error) {
    console.error("Erro ao salvar item:", error);
    showMessage("Erro ao salvar item", "error");
  }
}

async function deleteItem(itemId) {
  if (!confirm("Tem certeza que deseja deletar este item?")) return;
  try {
    await fetch(`/api/items/${itemId}`, { method: "DELETE" });
    await loadItems();
    await refreshAccountInfo();
    showMessage("Item removido com sucesso.", "success");
  } catch (error) {
    showMessage("Erro ao deletar item", "error");
  }
}

function editItem(itemId) {
  openItemModal(itemId);
}

// ==================== MOVIMENTAÇÕES ====================
function openMovementModal(itemId, type) {
  const modal = document.getElementById("movementModal");
  document.getElementById("movementItemId").value = itemId;
  document.getElementById("movementType").value = type;
  document.getElementById("movementTitle").textContent =
    type === "entrada" ? "Entrada" : type === "saida" ? "Saída" : "Ajuste";

  // Show/hide fields based on type
  document.getElementById("supplierGroup").style.display =
    type === "entrada" ? "flex" : "none";
  document.getElementById("priceGroup").style.display =
    type === "entrada" ? "flex" : "none";
  document.getElementById("destinationGroup").style.display =
    type === "saida" ? "flex" : "none";

  document.getElementById("movementForm").reset();
  modal.classList.remove("hidden");
}

async function saveMovement(e) {
  e.preventDefault();
  const itemId = document.getElementById("movementItemId").value;
  const type = document.getElementById("movementType").value;
  const quantity = parseInt(document.getElementById("movementQuantity").value);
  const supplier = document.getElementById("movementSupplier").value;
  const price = document.getElementById("movementPrice").value;
  const destination = document.getElementById("movementDestination").value;
  const observation = document.getElementById("movementObservation").value;

  if (isNaN(quantity) || quantity <= 0) {
    showMessage("Quantidade deve ser maior que zero.", "error");
    return;
  }

  if (type === "saida" && !destination.trim()) {
    showMessage("Destino é obrigatório para saída", "error");
    return;
  }

  const data = {
    quantity,
    observation,
    ...(type === "entrada" && { supplier, unit_price: price ? parseFloat(price) : null }),
    ...(type === "saida" && { destination }),
  };

  try {
    const endpoint =
      type === "entrada"
        ? `/api/items/${itemId}/entrada`
        : type === "saida"
        ? `/api/items/${itemId}/saida`
        : `/api/items/${itemId}/ajuste`;

    console.log("Enviando movimento:", { endpoint, data });

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    const result = await res.json();
    console.log("Resposta do servidor:", result);
    
    if (result.error) {
      showMessage("Erro: " + result.error, "error");
    } else {
      document.getElementById("movementModal").classList.add("hidden");
      loadItems();
      loadDashboard();
      showMessage("Movimentação registrada com sucesso.", "success");
    }
  } catch (error) {
    console.error("Erro na movimentação:", error);
    showMessage("Erro ao registrar movimentação: " + error.message, "error");
  }
}

// ==================== HISTÓRICO ====================
async function loadHistorico() {
  const start = document.getElementById("dateStart").value;
  const end = document.getElementById("dateEnd").value;
  let url = "/api/balanco/movements";
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (params.toString()) url += `?${params.toString()}`;

  const res = await fetch(url);
  allMovements = await res.json();
  renderMovements();
}

function renderMovements() {
  const tbody = document.getElementById("movementTableBody");
  tbody.innerHTML = "";

  const term = document.getElementById("searchMovement").value.toLowerCase();
  const typeFilter = document.getElementById("movementTypeFilter").value;

  const filtered = allMovements.filter((mov) => {
    const matchesType = !typeFilter || mov.type === typeFilter;
    const matchesSearch =
      mov.item_name.toLowerCase().includes(term) ||
      mov.type.toLowerCase().includes(term) ||
      (mov.observation || "").toLowerCase().includes(term) ||
      (mov.supplier || "").toLowerCase().includes(term) ||
      (mov.destination || "").toLowerCase().includes(term);
    return matchesType && matchesSearch;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">Nenhuma movimentação encontrada para os filtros selecionados.</td></tr>`;
    return;
  }

  filtered.forEach((mov) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${new Date(mov.timestamp).toLocaleString("pt-BR")}</td>
      <td>${mov.item_name}</td>
      <td>${mov.type}</td>
      <td>${mov.quantity}</td>
      <td>${mov.supplier || mov.destination || "-"}</td>
      <td>${mov.observation || "-"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function filterMovements() {
  renderMovements();
}

// ==================== CATEGORIAS ====================
async function loadCategories() {
  const res = await fetch("/api/categories");
  allCategories = await res.json();

  // Atualizar selects
  document.getElementById("itemCategory").innerHTML = '<option value="">Sem categoria</option>';
  document.getElementById("categoryFilter").innerHTML = '<option value="">Todas as categorias</option>';

  allCategories.forEach((cat) => {
    const opt1 = document.createElement("option");
    opt1.value = cat.name;
    opt1.textContent = cat.name;
    document.getElementById("itemCategory").appendChild(opt1);

    const opt2 = document.createElement("option");
    opt2.value = cat.name;
    opt2.textContent = cat.name;
    document.getElementById("categoryFilter").appendChild(opt2);
  });

  renderCategories();
}

async function addCategory() {
  const name = document.getElementById("newCategoryName").value.trim();
  const color = document.getElementById("newCategoryColor").value;

  if (!name) {
    showMessage("Digite um nome para a categoria", "error");
    return;
  }

  try {
    const res = await fetch("/api/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color }),
    });

    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
    } else {
      document.getElementById("newCategoryName").value = "";
      await loadCategories();
      await refreshAccountInfo();
      showMessage("Categoria adicionada com sucesso.", "success");
    }
  } catch (error) {
    showMessage("Erro ao adicionar categoria", "error");
  }
}

function renderCategories() {
  const list = document.getElementById("categoriesList");
  list.innerHTML = "";

  allCategories.forEach((cat) => {
    const div = document.createElement("div");
    div.className = "category-item";
    div.innerHTML = `
      <div>
        <span class="category-color" style="background: ${cat.color}"></span>
        <span>${cat.name}</span>
      </div>
      <button class="btn-sm btn-delete" onclick="deleteCategory(${cat.id})">Del</button>
    `;
    list.appendChild(div);
  });
}

async function deleteCategory(catId) {
  if (!confirm("Tem certeza?")) return;
  try {
    await fetch(`/api/categories/${catId}`, { method: "DELETE" });
    await loadCategories();
    await refreshAccountInfo();
    showMessage("Categoria removida com sucesso.", "success");
  } catch (error) {
    showMessage("Erro ao deletar categoria", "error");
  }
}

// ==================== RELATÓRIOS ====================
async function generateSupplierReport() {
  const start = document.getElementById("dateStart")?.value || "";
  const end = document.getElementById("dateEnd")?.value || "";
  let url = "/api/balanco/suppliers";
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (params.toString()) url += `?${params.toString()}`;

  const res = await fetch(url);
  const suppliers = await res.json();

  let html = "<h3>Relatório por Fornecedor</h3>";
  html += "<table class='items-table'><thead><tr><th>Fornecedor</th><th>Qtd Total</th><th>Custo Total</th><th>Ticket Médio</th></tr></thead><tbody>";

  Object.entries(suppliers).forEach(([supplier, info]) => {
    const avg = info.total_qty ? (info.total_cost / info.total_qty).toFixed(2) : 0;
    html += `
      <tr>
        <td>${supplier}</td>
        <td>${info.total_qty}</td>
        <td>R$ ${info.total_cost.toFixed(2)}</td>
        <td>R$ ${avg}</td>
      </tr>
    `;
  });

  html += "</tbody></table>";
  document.getElementById("reportContent").innerHTML = html;
}

async function generateLocationReport() {
  const locations = {};
  allItems.forEach((item) => {
    const loc = item.location || "Sem local";
    if (!locations[loc]) locations[loc] = { qty: 0, items: 0 };
    locations[loc].qty += item.quantity;
    locations[loc].items += 1;
  });

  let html = "<h3>Relatório por Localização</h3>";
  html += "<table class='items-table'><thead><tr><th>Localização</th><th>Quantidade</th><th>Itens</th></tr></thead><tbody>";

  Object.entries(locations).forEach(([loc, info]) => {
    html += `<tr><td>${loc}</td><td>${info.qty}</td><td>${info.items}</td></tr>`;
  });

  html += "</tbody></table>";
  document.getElementById("reportContent").innerHTML = html;
}

function exportCSV() {
  let csv = "Nome,SKU,Categoria,Quantidade,Mínimo,Localização,Descrição\n";
  allItems.forEach((item) => {
    csv += `"${item.name}","${item.sku || ""}","${item.category || ""}",${item.quantity},${item.min_quantity || 0},"${item.location || ""}","${item.description || ""}"\n`;
  });

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `inventario-${new Date().toISOString().split("T")[0]}.csv`;
  a.click();
}

function exportPDF() {
  const w = window.open("", "_blank");
  let html = "<html><head><title>Inventário</title>";
  html += "<style>body{font-family:Arial}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;text-align:left}</style>";
  html += "</head><body><h1>Relatório de Inventário</h1>";
  html += `<p>Gerado em ${new Date().toLocaleString("pt-BR")}</p>`;
  html += "<table><thead><tr><th>Nome</th><th>Qtd</th><th>Min</th><th>Local</th><th>Categoria</th></tr></thead><tbody>";

  allItems.forEach((item) => {
    html += `<tr><td>${item.name}</td><td>${item.quantity}</td><td>${item.min_quantity || 0}</td><td>${item.location || "-"}</td><td>${item.category || "-"}</td></tr>`;
  });

  html += "</tbody></table></body></html>";
  w.document.write(html);
  w.document.close();
  setTimeout(() => w.print(), 300);
}

// ==================== LOCALIZAÇÕES ====================
async function loadLocations() {
  const res = await fetch("/api/locations");
  const locationsList = await res.json();

  const selectEl = document.getElementById("itemLocation");
  selectEl.innerHTML = '<option value="">-- Selecione ou digite --</option>';
  locationsList.forEach((loc) => {
    const opt = document.createElement("option");
    opt.value = loc;
    opt.textContent = loc;
    selectEl.appendChild(opt);
  });
}

// ==================== MUDAR SENHA ====================
function openChangePasswordModal() {
  document.getElementById("changePasswordModal").classList.remove("hidden");
  document.getElementById("changePasswordForm").reset();
}

async function refreshAccountInfo() {
  const res = await fetch("/api/account");
  if (!res.ok) return;
  accountInfo = await res.json();
  document.getElementById("currentPlan").textContent = accountInfo.plan;
  updatePlanUI();
}

function updatePlanUI() {
  const warning = document.getElementById("planWarning");
  const planLimitInfo = document.getElementById("planLimitInfo");
  const addItemBtn = document.getElementById("addItemBtn");
  const upgradeBtn = document.getElementById("upgradePlanBtn");

  if (!accountInfo) return;

  if (accountInfo.limits.max_items !== null) {
    const remaining = accountInfo.limits.max_items - accountInfo.item_count;
    planLimitInfo.textContent = `Plano ${accountInfo.plan.toUpperCase()}: ${accountInfo.item_count}/${accountInfo.limits.max_items} itens usados.`;

    if (remaining <= 0) {
      warning.textContent = "Você atingiu o limite de itens do plano gratuito. Faça upgrade para adicionar mais itens.";
      warning.classList.remove("hidden");
      addItemBtn.disabled = true;
      addItemBtn.textContent = "+ Novo Item (limite atingido)";
    } else if (remaining <= 5) {
      warning.textContent = `Faltam apenas ${remaining} itens para atingir o limite do plano gratuito.`;
      warning.classList.remove("hidden");
      addItemBtn.disabled = false;
      addItemBtn.textContent = "+ Novo Item";
    } else {
      warning.classList.add("hidden");
      addItemBtn.disabled = false;
      addItemBtn.textContent = "+ Novo Item";
    }
  } else {
    planLimitInfo.textContent = `Plano ${accountInfo.plan.toUpperCase()}: limite ilimitado.`;
    warning.classList.add("hidden");
    addItemBtn.disabled = false;
    addItemBtn.textContent = "+ Novo Item";
  }

  if (upgradeBtn) {
    upgradeBtn.style.display = accountInfo.plan === "pro" ? "none" : "inline-flex";
  }
}

async function upgradePlan() {
  try {
    const res = await fetch("/api/account/upgrade", { method: "POST" });
    const result = await res.json();
    if (result.success) {
      showMessage("Sua conta foi atualizada para PRO.", "success");
      await refreshAccountInfo();
    } else {
      showMessage("Não foi possível realizar o upgrade.", "error");
    }
  } catch (error) {
    showMessage("Erro ao tentar realizar o upgrade.", "error");
  }
}

async function saveNewPassword(e) {
  e.preventDefault();
  const currentPassword = document.getElementById("currentPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmPassword = document.getElementById("confirmPassword").value;

  if (!currentPassword || !newPassword || !confirmPassword) {
    showMessage("Todos os campos são obrigatórios", "error");
    return;
  }

  if (newPassword !== confirmPassword) {
    showMessage("Novas senhas não conferem", "error");
    return;
  }

  if (newPassword.length < 6) {
    showMessage("Nova senha deve ter pelo menos 6 caracteres", "error");
    return;
  }

  try {
    const res = await fetch("/api/user/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }),
    });

    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
    } else {
      document.getElementById("changePasswordModal").classList.add("hidden");
      showMessage("Senha alterada com sucesso.", "success");
    }
  } catch (error) {
    showMessage("Erro ao alterar senha", "error");
  }
}

// ==================== INICIAR ====================
init();
