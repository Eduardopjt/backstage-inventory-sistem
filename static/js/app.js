// App principal - BACKSTAGE Profissional

let currentUser = null;
let allItems = [];
let allMovements = [];
let allCategories = [];
let allProjects = [];
let selectedProjectId = null;
let currentProjectAccessLevel = null;
let allTasks = [];
let projectChat = [];
let projectComments = [];
let projectRequests = [];
let purchaseRequests = [];
let warehouseRequests = [];
let romaneios = [];
let allTeamMembers = [];
let locChart = null;
let typeChart = null;
let notifications = [];
let roadmapChart = null;
let messageTimer = null;

// ==================== INICIALIZAÇÃO ====================
async function init() {
  try {
    const res = await fetch("/api/user");
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    
    if (!res.ok) {
      throw new Error(`Erro ao obter usuário: ${res.status} ${res.statusText}`);
    }
    
    currentUser = await res.json();
    if (!currentUser) {
      throw new Error("Dados de usuário inválidos");
    }
    
    if (document.getElementById("userInfo")) {
      document.getElementById("userInfo").textContent = `${currentUser.account_name} · ${currentUser.username}`;
    }
    if (document.getElementById("currentAccount")) {
      document.getElementById("currentAccount").textContent = currentUser.account_name;
    }
    if (document.getElementById("currentUsername")) {
      document.getElementById("currentUsername").textContent = currentUser.username;
    }
    if (document.getElementById("currentPlan")) {
      document.getElementById("currentPlan").textContent = currentUser.plan;
    }
    
    setupEventListeners();
    initializeSidebar();
    applyUserPermissions();
    
    try {
      await loadCategories();
    } catch (err) {
      console.warn("Aviso: Não foi possível carregar categorias", err);
    }
    
    try {
      await loadLocations();
    } catch (err) {
      console.warn("Aviso: Não foi possível carregar locais", err);
    }
    
    if (currentUser.role === "owner" || currentUser.role === "admin" || (currentUser.permissions || []).includes("team")) {
      try {
        await loadTeamMembers();
      } catch (err) {
        console.warn("Aviso: Não foi possível carregar membros da equipe", err);
      }
    }
    
    if (currentUser.role === "owner" || currentUser.role === "admin" || (currentUser.permissions || []).includes("dashboard")) {
      try {
        await loadDashboard();
      } catch (err) {
        console.warn("Aviso: Não foi possível carregar dashboard", err);
      }
    }
    
    const activeNav = document.querySelector(".nav-btn.active");
    if (activeNav && activeNav.classList.contains("hidden")) {
      const firstVisible = document.querySelector(".nav-btn:not(.hidden)");
      if (firstVisible) {
        changePage(firstVisible.dataset.page);
      }
    }
  } catch (error) {
    console.error("Erro crítico na inicialização:", error);
    showMessage(`Erro ao inicializar: ${error.message}`, "error");
    setTimeout(() => {
      window.location.href = "/login";
    }, 2000);
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

  // Event listeners para páginas
  document.getElementById("newProjectBtn").addEventListener("click", () => openProjectModal());
  document.getElementById("detailNewTaskBtn").addEventListener("click", () => openTaskModal());
  document.getElementById("detailQuickNewTaskBtn").addEventListener("click", () => openTaskModal());
  document.getElementById("detailQuickNewRequestBtn").addEventListener("click", () => selectProjectTab("detail-requests-tab"));
  document.getElementById("detailQuickNewCommentBtn").addEventListener("click", () => selectProjectTab("detail-comments-tab"));
  document.getElementById("detailQuickNewChatBtn").addEventListener("click", () => selectProjectTab("detail-chat-tab"));
  document.getElementById("backToProjectsBtn").addEventListener("click", () => changePage("projects"));
  document.getElementById("notificationBell").addEventListener("click", toggleNotificationsPanel);
  document.getElementById("closeNotificationPanel").addEventListener("click", toggleNotificationsPanel);
  const toggleBtn = document.getElementById("toggleBoardViewBtn");
  if (toggleBtn) toggleBtn.addEventListener("click", toggleBoardView);
  document.querySelectorAll(".project-tab-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".project-tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".detail-tab").forEach((tab) => tab.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
    });
  });
  window.addEventListener("click", (e) => {
    const notificationPanel = document.getElementById("notificationPanel");
    const notificationBell = document.getElementById("notificationBell");
    if (!notificationPanel || !notificationBell) return;
    if (!e.target.closest("#notificationPanel") && !e.target.closest("#notificationBell")) {
      notificationPanel.classList.add("hidden");
    }
  });
  document.getElementById("sendChatBtn").addEventListener("click", (e) => {
    e.preventDefault();
    saveProjectDiscussion("chat");
  });
  document.getElementById("sendCommentBtn").addEventListener("click", (e) => {
    e.preventDefault();
    saveProjectDiscussion("comment");
  });
  document.getElementById("sendRequestBtn").addEventListener("click", (e) => {
    e.preventDefault();
    saveProjectRequest();
  });
  document.getElementById("workspaceSendCommentBtn").addEventListener("click", (e) => {
    e.preventDefault();
    saveWorkspaceComment();
  });
  document.getElementById("workspaceStatusBtnPlanning").addEventListener("click", () => updateWorkspaceTaskStatus("planejamento"));
  document.getElementById("workspaceStatusBtnInProgress").addEventListener("click", () => updateWorkspaceTaskStatus("em progresso"));
  document.getElementById("workspaceStatusBtnDone").addEventListener("click", () => updateWorkspaceTaskStatus("concluído"));
  document.getElementById("clearTaskFiltersBtn").addEventListener("click", (e) => {
    e.preventDefault();
    clearTaskFilters();
  });
  document.getElementById("taskFilterSector").addEventListener("change", renderTasks);
  document.getElementById("taskFilterResponsible").addEventListener("change", renderTasks);
  document.getElementById("taskFilterPriority").addEventListener("change", renderTasks);
  document.getElementById("taskFilterStartDate").addEventListener("change", renderTasks);
  document.getElementById("taskFilterEndDate").addEventListener("change", renderTasks);
  document.getElementById("createRomaneioBtn").addEventListener("click", (e) => {
    e.preventDefault();
    saveRomaneio();
  });
  document.getElementById("romaneioProjectSelect").addEventListener("change", loadRomaneioRelatedRequests);
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
  document.getElementById("projectSearchInput").addEventListener("input", loadProjects);
  document.getElementById("projectStatusFilter").addEventListener("change", loadProjects);
  document.getElementById("dateStart").addEventListener("change", loadHistorico);
  document.getElementById("dateEnd").addEventListener("change", loadHistorico);
  document.getElementById("searchMovement").addEventListener("input", filterMovements);
  document.getElementById("movementTypeFilter").addEventListener("change", renderMovements);

  // Forms
  document.getElementById("itemForm").addEventListener("submit", saveItem);
  document.getElementById("movementForm").addEventListener("submit", saveMovement);
  document.getElementById("projectForm").addEventListener("submit", saveProject);
  document.getElementById("taskForm").addEventListener("submit", saveTask);
  document.getElementById("inviteMemberForm").addEventListener("submit", inviteTeamMember);
  document.getElementById("userPermissionsForm").addEventListener("submit", saveUserAccess);
  document.getElementById("changePasswordForm").addEventListener("submit", saveNewPassword);
}



function changePage(page, e) {
  const pageBtn = document.querySelector(`.nav-btn[data-page="${page}"]`);
  if (pageBtn && pageBtn.classList.contains("hidden")) {
    if (page !== "dashboard") {
      showMessage("Você não tem acesso a esta área.", "error");
      changePage("dashboard");
    }
    return;
  }
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
  const pageEl = document.getElementById(`${page}-page`);
  if (!pageEl) return;
  pageEl.classList.add("active");
  if (e) e.target.classList.add("active");

  switch (page) {
    case "projects":
      loadProjects();
      break;
    case "purchases":
      loadPurchases();
      break;
    case "romaneios":
      loadRomaneios();
      break;
    case "items":
      loadItems();
      break;
    case "configuracoes":
      loadCategories();
      if (currentUser.role === "owner" || currentUser.role === "admin" || (currentUser.permissions || []).includes("team")) {
        loadTeamMembers();
      }
      break;
    case "dashboard":
      loadDashboard();
      break;
  }
}

// ==================== DASHBOARD ====================
async function loadDashboard() {
  try {
    const [itemsRes, balancoRes, dashboardRes] = await Promise.all([fetch("/api/items"), fetch("/api/balanco"), fetch("/api/user/dashboard")]);
    if (itemsRes.ok) allItems = await itemsRes.json();
    const balanco = balancoRes.ok ? await balancoRes.json() : {total_items: 0, total_quantity: 0, low_stock: [], total_value: 0, movement_types: {}};
    const dashboardData = dashboardRes.ok ? await dashboardRes.json() : {};
    if (dashboardRes.ok) {
      renderNotifications(dashboardData);
    }

    const totalQty = balanco.total_quantity || 0;
    const lowCount = Array.isArray(balanco.low_stock) ? balanco.low_stock.length : 0;
    const totalValue = balanco.total_value || 0;

    document.getElementById("kpi-items").textContent = balanco.total_items || 0;
    document.getElementById("kpi-quantity").textContent = totalQty;
    document.getElementById("kpi-low").textContent = lowCount;
    document.getElementById("kpi-value").textContent = `R$ ${totalValue.toFixed(2)}`;

    const lowStockList = document.getElementById("lowStockList");
    lowStockList.innerHTML = "";
    (allItems || [])
      .filter((item) => item.quantity <= (item.min_quantity || 5))
      .forEach((item) => {
        const div = document.createElement("div");
        div.className = "low-stock-item";
        div.innerHTML = `<strong>${item.name}</strong> <span>${item.quantity} / ${item.min_quantity}</span>`;
        lowStockList.appendChild(div);
      });

    updateCharts(balanco.movement_types || {});
  } catch (err) {
    console.error("Error loading dashboard:", err);
  }
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

  const itemsRes = await fetch(url);
  let warehouseRes = null;

  try {
    warehouseRes = await fetch("/api/warehouse");
  } catch (err) {
    warehouseRes = null;
  }

  allItems = await itemsRes.json();
  if (warehouseRes && warehouseRes.ok) {
    warehouseRequests = await warehouseRes.json();
  } else {
    warehouseRequests = [];
  }

  renderItems();
  renderWarehouseRequests();
  await loadHistorico();
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
      loadItems();
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
    loadItems();
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
  if (!res.ok) {
    allMovements = [];
    renderMovements();
    return;
  }
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
      loadCategories();
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
    loadCategories();
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

// ==================== PROJETOS E TAREFAS ====================
async function loadProjects() {
  const search = document.getElementById("projectSearchInput").value.trim();
  const status = document.getElementById("projectStatusFilter").value;
  const res = await fetch("/api/projects");
  allProjects = await res.json();

  if (search || status) {
    allProjects = allProjects.filter((project) => {
      const matchesSearch = !search || project.name.toLowerCase().includes(search.toLowerCase()) || (project.description || "").toLowerCase().includes(search.toLowerCase());
      const matchesStatus = !status || project.status === status;
      return matchesSearch && matchesStatus;
    });
  }

  renderProjects();
}

function renderProjects() {
  const tbody = document.getElementById("projectsTableBody");
  tbody.innerHTML = "";

  if (allProjects.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">Nenhum projeto encontrado.</td></tr>`;
    return;
  }

  allProjects.forEach((project) => {
    const canEditProject = currentUser.role === "owner" || currentUser.role === "admin" || project.access_level === "edit";
    const accessBadge = project.access_level ? `<span class="badge badge-info">${project.access_level.toUpperCase()}</span>` : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${project.name} ${accessBadge}</td>
      <td>${project.status}</td>
      <td>${project.owner_name || "-"}</td>
      <td>${project.start_date || "-"}</td>
      <td>${project.due_date || "-"}</td>
      <td>
        <div class="action-buttons">
          <button class="btn-sm btn-entrada" onclick="openProjectDetails(${project.id})">Abrir</button>
          ${canEditProject ? `<button class="btn-sm btn-edit" onclick="editProject(${project.id})">Editar</button>` : ""}
          ${canEditProject ? `<button class="btn-sm btn-delete" onclick="deleteProject(${project.id})">Del</button>` : ""}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function openProjectDetails(projectId) {
  const loaded = await loadProjectDetails(projectId);
  if (loaded) {
    changePage("project-detail");
  }
}

async function selectProject(projectId) {
  selectedProjectId = projectId;
  const project = allProjects.find((project) => project.id === projectId);
  if (!project) return;
  document.getElementById("selectedProjectLabel").textContent = `Tarefas em ${project.name}`;
  await loadProjectTasks(projectId);
}

async function loadProjectDetails(projectId) {
  if (!projectId) return false;
  selectedProjectId = projectId;

  const projectRes = await fetch(`/api/projects/${projectId}`);
  const project = await projectRes.json();
  if (project.error) {
    showMessage(project.error, "error");
    return false;
  }

  currentProjectAccessLevel = project.access_level || "view";
  document.getElementById("detailProjectName").textContent = project.name;
  document.getElementById("detailProjectStatusTxt").textContent = project.description || "Abra um projeto para ver detalhes e interagir com as tarefas, chat, comentários e solicitações.";
  document.getElementById("detailProjectOwner").textContent = project.owner_name || "-";
  document.getElementById("detailProjectAccessLevel").textContent = currentProjectAccessLevel === "edit" ? "Acesso de edição" : "Visualização";
  document.getElementById("detailProjectAccessLevel").className = currentProjectAccessLevel === "edit" ? "access-label access-edit" : "access-label access-view";
  document.getElementById("detailProjectStartDate").textContent = project.start_date || "-";
  document.getElementById("detailProjectDueDate").textContent = project.due_date || "-";
  document.getElementById("detailProjectStatus").textContent = project.status || "-";
  document.getElementById("detailProjectDescription").textContent = project.description || "-";
  renderProjectMembers(project.members || []);
  updateProjectMetrics(project.metrics || {});
  renderProjectAlerts(project.alerts || []);
  renderProjectActivity(project.recent_activity || []);
  updateProjectDetailAccess();

  await Promise.all([
    loadProjectTasks(projectId),
    loadProjectDiscussions(projectId, "chat"),
    loadProjectDiscussions(projectId, "comment"),
    loadProjectRequests(projectId),
    loadProjectTimeline(projectId),
  ]);
  populateRequestApprovers(project.members || []);
  // restore user's view preference
  try { applyBoardView(localStorage.getItem('boardView') || 'kanban'); } catch (e) {}
  document.getElementById("detailAssemblyStart").textContent = project.assembly_start_date || "-";
  document.getElementById("detailAssemblyEnd").textContent = project.assembly_end_date || "-";
  document.getElementById("detailEventStart").textContent = project.event_start_date || "-";
  document.getElementById("detailEventEnd").textContent = project.event_end_date || "-";
  document.getElementById("detailDismantleStart").textContent = project.dismantle_start_date || "-";
  document.getElementById("detailDismantleEnd").textContent = project.dismantle_end_date || "-";
  document.getElementById("detailAssemblyAddress").textContent = project.assembly_address || "-";
  document.getElementById("detailEventAddress").textContent = project.event_address || "-";
  return true;
}

function updateProjectDetailAccess() {
  const canEditProject = currentUser.role === "owner" || currentUser.role === "admin" || currentProjectAccessLevel === "edit";
  const detailNewTaskBtn = document.getElementById("detailNewTaskBtn");
  if (detailNewTaskBtn) {
    detailNewTaskBtn.classList.toggle("hidden", !canEditProject);
  }
  const requestSection = document.getElementById("detail-requests-tab");
  if (requestSection) {
    requestSection.querySelector(".discussion-form").classList.toggle("hidden", false);
  }
}

function renderProjectMembers(members) {
  const list = document.getElementById("detailProjectMembersList");
  if (!list) return;
  list.innerHTML = "";
  if (!members || members.length === 0) {
    list.innerHTML = `<li class="small-note">Nenhum membro adicionado ao projeto.</li>`;
    return;
  }

  members.forEach((member) => {
    const li = document.createElement("li");
    li.textContent = `${member.username} (${member.access === "edit" ? "Edição" : "Visualização"})`;
    list.appendChild(li);
  });
}

function selectProjectTab(tabId) {
  document.querySelectorAll(".project-tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".detail-tab").forEach((tab) => tab.classList.remove("active"));
  const target = document.querySelector(`.project-tab-btn[data-tab="${tabId}"]`);
  if (target) target.classList.add("active");
  const tabEl = document.getElementById(tabId);
  if (tabEl) tabEl.classList.add("active");
}

function updateProjectMetrics(metrics) {
  document.getElementById("projectProgressValue").textContent = `${metrics.progress || 0}%`;
  document.getElementById("projectProgressBar").style.width = `${metrics.progress || 0}%`;
  document.getElementById("projectOpenTasksValue").textContent = metrics.open_tasks || 0;
  document.getElementById("projectOverdueTasksValue").textContent = metrics.overdue_tasks || 0;
  document.getElementById("projectRequestsValue").textContent = metrics.open_requests || 0;
}

function renderProjectAlerts(alerts) {
  const container = document.getElementById("projectAlertsList");
  if (!container) return;
  container.innerHTML = "";
  if (!alerts || alerts.length === 0) {
    container.innerHTML = `<div class="small-note">Nenhum aviso no momento.</div>`;
    return;
  }
  alerts.forEach((alert) => {
    const item = document.createElement("div");
    item.className = "activity-item";
    item.innerHTML = `<strong>${alert.message}</strong><small>${alert.type === "due_soon" ? "Vence em breve" : alert.type === "requests" ? "Solicitação pendente" : "Atrasado"}</small>`;
    container.appendChild(item);
  });
}

function renderProjectActivity(activity) {
  const container = document.getElementById("detailActivityList") || document.getElementById("projectActivityList");
  if (!container) return;
  container.innerHTML = "";
  if (!activity || activity.length === 0) {
    container.innerHTML = `<div class="small-note">Nenhuma atividade registrada.</div>`;
    return;
  }
  activity.forEach((item) => {
    const div = document.createElement("div");
    div.className = "activity-item";
    const dateValue = item.date || new Date(item.created_at).toLocaleDateString("pt-BR");
    div.innerHTML = `
      <strong>${item.title}</strong>
      <small>${item.detail || "Atualização"} • ${dateValue}</small>
    `;
    container.appendChild(div);
  });
}

function toggleNotificationsPanel() {
  const panel = document.getElementById("notificationPanel");
  if (!panel) return;
  panel.classList.toggle("hidden");
}

function renderNotifications(dashboardData) {
  const panel = document.getElementById("notificationPanel");
  const list = document.getElementById("notificationList");
  const countBadge = document.getElementById("notificationCount");
  if (!panel || !list || !countBadge) return;

  notifications = [];
  const alerts = dashboardData.alerts || [];
  const reminders = dashboardData.reminders || [];

  alerts.forEach((alert) => {
    notifications.push({
      type: alert.type,
      title: alert.message,
      subtitle: alert.due_date ? `Vence em ${alert.due_date}` : "Ação necessária",
    });
  });

  reminders.slice(0, 6).forEach((reminder) => {
    notifications.push({
      type: "reminder",
      title: reminder.title,
      subtitle: reminder.note || (reminder.due_date ? `Vence em ${reminder.due_date}` : "Lembrete pendente"),
    });
  });

  const count = notifications.length;
  countBadge.textContent = count;
  countBadge.classList.toggle("hidden", count === 0);
  list.innerHTML = "";

  if (!notifications.length) {
    list.innerHTML = `<div class="notification-empty">Você está tudo em dia. Sem notificações recentes.</div>`;
    return;
  }

  notifications.slice(0, 6).forEach((note) => {
    const item = document.createElement("div");
    item.className = "notification-item";
    item.innerHTML = `
      <strong>${note.title}</strong>
      <small>${note.subtitle}</small>
    `;
    list.appendChild(item);
  });
}

async function loadProjectTimeline(projectId) {
  if (!projectId) return;
  try {
    const res = await fetch(`/api/projects/${projectId}/timeline`);
    const timeline = await res.json();
    if (timeline.error) return;
    renderProjectTimeline(timeline);
  } catch (error) {
    console.warn("Falha ao carregar linha do tempo do projeto:", error);
  }
}

function renderProjectTimeline(timeline) {
  const container = document.getElementById("projectTimelineList");
  if (!container) return;
  container.innerHTML = "";

  if (!timeline || timeline.length === 0) {
    container.innerHTML = `<div class="small-note">Nenhum evento programado para este projeto.</div>`;
    if (roadmapChart) {
      roadmapChart.destroy();
      roadmapChart = null;
    }
    return;
  }

  timeline.forEach((event) => {
    const div = document.createElement("div");
    div.className = "timeline-event";
    div.innerHTML = `
      <strong>${event.title}</strong>
      <small>${event.detail || "Evento"} • ${event.date ? new Date(event.date).toLocaleDateString("pt-BR") : "Sem data"}</small>
    `;
    container.appendChild(div);
  });

  renderRoadmapChart(timeline);
}

function renderRoadmapChart(timeline) {
  const ctx = document.getElementById("roadmapChart");
  if (!ctx) return;
  const labels = timeline.map((item) => item.date ? new Date(item.date).toLocaleDateString("pt-BR") : item.title);
  const dataValues = timeline.map((_, index) => index + 1);

  if (roadmapChart) roadmapChart.destroy();
  roadmapChart = new Chart(ctx.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Eventos do roadmap",
          data: dataValues,
          fill: false,
          borderColor: "#667eea",
          backgroundColor: "#667eea",
          tension: 0.3,
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => `${timeline[context.dataIndex].title} — ${timeline[context.dataIndex].detail || "Evento"}`,
          },
        },
      },
      scales: {
        y: { display: false },
      },
    },
  });
}

function renderTaskBoard() {
  const board = document.getElementById("taskBoard");
  if (!board) return;
  board.innerHTML = "";
  const statuses = [
    { key: "planejamento", label: "Planejamento" },
    { key: "pendente", label: "Pendentes" },
    { key: "em progresso", label: "Em Progresso" },
    { key: "concluído", label: "Concluído" },
    { key: "outros", label: "Outros" },
  ];

  statuses.forEach((status) => {
    const column = document.createElement("div");
    column.className = "board-column";
    column.dataset.status = status.key;
    column.innerHTML = `<h4>${status.label}</h4>`;
    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      try { event.dataTransfer.dropEffect = 'move'; } catch(e) {}
      column.classList.add("drag-over");
    });
    column.addEventListener("dragleave", () => {
      column.classList.remove("drag-over");
    });
    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("drag-over");
      const taskId = event.dataTransfer.getData("text/plain");
      if (taskId) {
        await quickUpdateTaskStatus(parseInt(taskId, 10), status.key);
      }
    });

    const tasks = status.key === "outros"
      ? allTasks.filter((task) => !["planejamento", "pendente", "em progresso", "concluído"].includes(task.status))
      : allTasks.filter((task) => task.status === status.key);
    if (!tasks.length) {
      const empty = document.createElement("div");
      empty.className = "small-note";
      empty.textContent = "Nenhuma tarefa.";
      column.appendChild(empty);
    } else {
      tasks.forEach((task) => {
        const card = document.createElement("div");
        card.className = "board-task-card";
        card.draggable = true;
        card.addEventListener("dragstart", (event) => {
          try { event.dataTransfer.setData("text/plain", String(task.id)); } catch(e) {}
          try { event.dataTransfer.effectAllowed = 'move'; } catch(e) {}
          card.classList.add('dragging');
        });
        card.addEventListener('dragend', () => { card.classList.remove('dragging'); });
        const assignedNames = (task.assignees && task.assignees.length) ? task.assignees.map(a => a.username).join(', ') : (task.assigned_name || 'Sem responsável');
        card.innerHTML = `
          <div class="task-card-header">
            <strong>${task.name}</strong>
            <span>${task.priority}</span>
          </div>
          <div>${assignedNames}</div>
          <div class="task-card-meta">
            <span>${task.sector || 'Sem setor'}</span>
            <small>${task.due_date || "Sem prazo"}</small>
          </div>
          <div class="task-card-actions">
            <button class="btn-sm btn-primary" onclick="quickUpdateTaskStatus(${task.id}, 'planejamento')">Planejamento</button>
            <button class="btn-sm btn-secondary" onclick="quickUpdateTaskStatus(${task.id}, 'em progresso')">Em Progresso</button>
            <button class="btn-sm btn-entrada" onclick="quickUpdateTaskStatus(${task.id}, 'concluído')">Concluir</button>
            <button class="btn-sm btn-secondary" onclick="openTaskWorkspace(${task.id})">Workspace</button>
          </div>
        `;
        // ensure interactive buttons don't interfere with dragging
        Array.from(card.querySelectorAll('button')).forEach(b => b.draggable = false);
        column.appendChild(card);
      });
    }
    board.appendChild(column);
  });
}

function toggleBoardView() {
  const board = document.getElementById('taskBoard');
  const table = document.getElementById('detailTasksTableBody');
  if (!board || !table) return;
  const current = localStorage.getItem('boardView') || 'kanban';
  const next = current === 'kanban' ? 'list' : 'kanban';
  localStorage.setItem('boardView', next);
  applyBoardView(next);
}

function applyBoardView(mode) {
  const board = document.getElementById('taskBoard');
  const table = document.getElementById('detailTasksTableBody');
  if (!board || !table) return;
  if (mode === 'list') {
    board.classList.add('hidden');
    table.closest('table').classList.remove('hidden');
  } else {
    board.classList.remove('hidden');
    table.closest('table').classList.add('hidden');
  }
}

async function quickUpdateTaskStatus(taskId, status) {
  try {
    await fetch(`/api/tasks/${taskId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (selectedProjectId) {
      await loadProjectDetails(selectedProjectId);
    }
    showMessage("Status da tarefa atualizado.", "success");
  } catch (error) {
    showMessage("Erro ao atualizar status da tarefa.", "error");
  }
}

async function loadProjectDiscussions(projectId, kind) {
  if (!projectId) return;
  let url = `/api/projects/${projectId}/discussions`;
  if (kind) url += `?kind=${kind}`;
  const res = await fetch(url);
  const discussions = await res.json();
  if (kind === "chat") {
    projectChat = discussions;
  } else {
    projectComments = discussions;
  }
  renderProjectDiscussions(kind);
}

function renderProjectDiscussions(kind) {
  const listId = kind === "chat" ? "chatList" : "commentsList";
  const container = document.getElementById(listId);
  const items = kind === "chat" ? projectChat : projectComments;
  if (!container) return;
  container.innerHTML = "";

  if (!items || items.length === 0) {
    container.innerHTML = `<div class="empty-row">Nenhuma ${kind === "chat" ? "mensagem de chat" : "comentário"} encontrada.</div>`;
    return;
  }

  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = "discussion-item";
    div.innerHTML = `
      <div class="discussion-item-header">
        <strong>${item.author_name || "Usuário"}</strong>
        <span>${new Date(item.created_at).toLocaleString("pt-BR")}</span>
      </div>
      <p>${item.message}</p>
    `;
    container.appendChild(div);
  });
}

async function saveProjectDiscussion(kind) {
  if (!selectedProjectId) {
    showMessage("Selecione um projeto primeiro.", "error");
    return;
  }
  const textareaId = kind === "chat" ? "chatMessage" : "commentMessage";
  const message = document.getElementById(textareaId).value.trim();
  if (!message) {
    showMessage("Digite uma mensagem antes de enviar.", "error");
    return;
  }

  try {
    const res = await fetch(`/api/projects/${selectedProjectId}/discussions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, message }),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }
    document.getElementById(textareaId).value = "";
    await loadProjectDiscussions(selectedProjectId, kind);
    showMessage(`${kind === "chat" ? "Chat enviado" : "Comentário publicado"} com sucesso.`, "success");
  } catch (error) {
    showMessage("Erro ao enviar mensagem.", "error");
  }
}

async function loadProjectRequests(projectId) {
  if (!projectId) return;
  const res = await fetch(`/api/projects/${projectId}/requests`);
  projectRequests = await res.json();
  renderProjectRequests();
}

function renderProjectRequests() {
  const container = document.getElementById("requestsList");
  container.innerHTML = "";
  if (!projectRequests || projectRequests.length === 0) {
    container.innerHTML = `<div class="empty-row">Nenhuma solicitação encontrada.</div>`;
    return;
  }

  projectRequests.forEach((request) => {
    const moduleLabel = request.type === "compra" ? "Compras" : request.type === "material" ? "Almoxarifado" : "Projeto";
    const isApprover = request.approver_id && Number(request.approver_id) === Number(currentUser.id);
    const canManageRequest = currentUser.role === "owner" || currentUser.role === "admin" || currentProjectAccessLevel === "edit" || isApprover;
    const actionLabel = request.status === "aberta" ? "Aprovar" : request.status === "aprovada" ? "Atender" : request.status === "atendida" ? "Cancelar" : null;
    const actionStatus = request.status === "aberta" ? "aprovada" : request.status === "aprovada" ? "atendida" : request.status === "atendida" ? "cancelada" : null;
    const actionButtonHtml = canManageRequest && actionStatus
      ? `<div class="request-actions"><button class="btn-sm btn-primary" onclick="updateProjectRequestStatus(${request.id}, '${actionStatus}')">${actionLabel}</button></div>`
      : "";

    const approverText = request.approver_name ? `<p class="detail-small"><strong>Responsável:</strong> ${request.approver_name}</p>` : "";

    const div = document.createElement("div");
    div.className = "discussion-item";
    div.innerHTML = `
      <div class="discussion-item-header">
        <strong>${request.title} (${request.type || "Solicitação"})</strong>
        <span>${request.status || "aberta"} · ${new Date(request.created_at).toLocaleString("pt-BR")}</span>
      </div>
      <p>${request.description || "Sem descrição."}</p>
      <p class="detail-small"><strong>Módulo:</strong> ${moduleLabel}</p>
      ${approverText}
      ${actionButtonHtml}
    `;
    container.appendChild(div);
  });
}

let currentWorkspaceTaskId = null;

async function openTaskWorkspace(taskId) {
  if (!taskId) return;
  try {
    const res = await fetch(`/api/tasks/${taskId}/workspace`);
    const data = await res.json();
    if (data.error) { showMessage(data.error, 'error'); return; }
    currentWorkspaceTaskId = taskId;
    const task = data.task || {};
    document.getElementById('workspaceTaskTitle').textContent = task.name || 'Tarefa';
    document.getElementById('workspaceTaskStatus').textContent = task.status || '-';
    document.getElementById('workspaceTaskPriority').textContent = task.priority || '-';
    document.getElementById('workspaceTaskSector').textContent = task.sector || '-';
    document.getElementById('workspaceTaskDueDate').textContent = task.due_date || '-';
    document.getElementById('workspaceTaskAssignees').textContent = (data.assignees || []).map(a => a.username).join(', ') || '-';
    document.getElementById('workspaceTaskDescription').textContent = task.description || '';
    // render comments
    const commentsList = document.getElementById('workspaceCommentsList');
    commentsList.innerHTML = '';
    (data.comments || []).forEach(c => {
      const div = document.createElement('div');
      div.className = 'discussion-item';
      div.innerHTML = `<div class="discussion-item-header"><strong>${c.author}</strong><span>${new Date(c.created_at).toLocaleString('pt-BR')}</span></div><p>${c.message}</p>`;
      commentsList.appendChild(div);
    });
    const checklist = document.getElementById('workspaceChecklistList');
    checklist.innerHTML = '';
    (data.checklist || []).forEach(ch => {
      const li = document.createElement('li');
      li.textContent = `${ch.label} ${ch.checked ? '(✔)' : ''}`;
      checklist.appendChild(li);
    });
    document.getElementById('taskWorkspaceModal').classList.remove('hidden');
  } catch (error) {
    showMessage('Erro ao abrir workspace da tarefa.', 'error');
  }
}

async function saveWorkspaceComment() {
  if (!currentWorkspaceTaskId) return showMessage('Nenhuma tarefa aberta.', 'error');
  const message = document.getElementById('workspaceCommentMessage').value.trim();
  if (!message) return showMessage('Digite um comentário.', 'error');
  try {
    const res = await fetch(`/api/tasks/${currentWorkspaceTaskId}/comments`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message })
    });
    const data = await res.json();
    if (data.error) return showMessage(data.error, 'error');
    document.getElementById('workspaceCommentMessage').value = '';
    await openTaskWorkspace(currentWorkspaceTaskId);
    showMessage('Comentário publicado.', 'success');
  } catch (error) {
    showMessage('Erro ao publicar comentário.', 'error');
  }
}

async function updateWorkspaceTaskStatus(status) {
  if (!currentWorkspaceTaskId) return;
  try {
    await quickUpdateTaskStatus(currentWorkspaceTaskId, status);
    await openTaskWorkspace(currentWorkspaceTaskId);
  } catch (e) {
    showMessage('Erro ao atualizar status.', 'error');
  }
}

function populateRequestApprovers(members) {
  const sel = document.getElementById('requestApprover');
  if (!sel) return;
  sel.innerHTML = '<option value="">Responsável pelo setor</option>';
  (members || []).forEach(m => {
    const id = m.user_id || m.id || m.userId || null;
    const name = m.username || m.name || m.user_name || '';
    if (id) {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = name;
      sel.appendChild(opt);
    }
  });
}

async function updateProjectRequestStatus(requestId, status) {
  try {
    const res = await fetch(`/api/projects/${selectedProjectId}/requests/${requestId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao atualizar solicitação.", "error");
      return;
    }
    await loadProjectRequests(selectedProjectId);
    showMessage("Solicitação atualizada.", "success");
  } catch (error) {
    showMessage("Erro ao atualizar solicitação.", "error");
  }
}

async function loadPurchases() {
  const res = await fetch("/api/purchases");
  purchaseRequests = await res.json();
  renderPurchases();
}

function renderPurchases() {
  const tbody = document.getElementById("purchasesTableBody");
  tbody.innerHTML = "";
  if (!purchaseRequests || purchaseRequests.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Nenhuma solicitação de compra encontrada.</td></tr>`;
    return;
  }

  const canManage = currentUser.role === "owner" || currentUser.role === "admin";
  purchaseRequests.forEach((request) => {
    const actionLabel = request.status === "aberta" ? "Aprovar" : request.status === "aprovada" ? "Atender" : request.status === "atendida" ? "Cancelar" : "Detalhes";
    const actionStatus = request.status === "aberta" ? "aprovada" : request.status === "aprovada" ? "atendida" : request.status === "atendida" ? "cancelada" : request.status;
    const actions = canManage && actionStatus !== request.status
      ? `<button class="btn-sm btn-primary" onclick="updatePurchaseStatus(${request.id}, '${actionStatus}')">${actionLabel}</button>`
      : "";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${request.id}</td>
      <td>${request.project_name || "-"}</td>
      <td>${request.title}</td>
      <td>${request.requester_name || "-"}</td>
      <td>${request.status || "aberta"}</td>
      <td>${new Date(request.created_at).toLocaleDateString("pt-BR")}</td>
      <td>${actions}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadWarehouse() {
  const res = await fetch("/api/warehouse");
  warehouseRequests = await res.json();
  renderWarehouseRequests();
}

function renderWarehouseRequests() {
  const tbody = document.getElementById("warehouseTableBody");
  tbody.innerHTML = "";
  if (!warehouseRequests || warehouseRequests.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">Nenhuma solicitação de material encontrada.</td></tr>`;
    return;
  }

  const canManage = currentUser.role === "owner" || currentUser.role === "admin";
  warehouseRequests.forEach((request) => {
    const actionLabel = request.status === "aberta" ? "Aprovar" : request.status === "aprovada" ? "Atender" : request.status === "atendida" ? "Cancelar" : "Detalhes";
    const actionStatus = request.status === "aberta" ? "aprovada" : request.status === "aprovada" ? "atendida" : request.status === "atendida" ? "cancelada" : request.status;
    const actions = canManage && actionStatus !== request.status
      ? `<button class="btn-sm btn-primary" onclick="updateWarehouseStatus(${request.id}, '${actionStatus}')">${actionLabel}</button>`
      : "";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${request.id}</td>
      <td>${request.project_name || "-"}</td>
      <td>${request.title}</td>
      <td>${request.requester_name || "-"}</td>
      <td>${request.status || "aberta"}</td>
      <td>${new Date(request.created_at).toLocaleDateString("pt-BR")}</td>
      <td>${actions}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadRomaneios() {
  const [projectsRes, purchasesRes, warehouseRes, romaneiosRes] = await Promise.all([
    fetch("/api/projects"),
    fetch("/api/purchases"),
    fetch("/api/warehouse"),
    fetch("/api/romaneios"),
  ]);

  allProjects = await projectsRes.json();
  purchaseRequests = await purchasesRes.json();
  warehouseRequests = await warehouseRes.json();
  romaneios = await romaneiosRes.json();

  renderRomaneioProjectOptions();
  renderRomaneioRequestOptions();
  renderRomaneios();
}

function renderRomaneioProjectOptions() {
  const projectSelect = document.getElementById("romaneioProjectSelect");
  projectSelect.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Selecione um projeto";
  projectSelect.appendChild(defaultOption);

  allProjects.forEach((project) => {
    const opt = document.createElement("option");
    opt.value = project.id;
    opt.textContent = project.name;
    projectSelect.appendChild(opt);
  });
}

function renderRomaneioRequestOptions(projectId = null) {
  const purchaseSelect = document.getElementById("romaneioPurchaseSelect");
  const warehouseSelect = document.getElementById("romaneioWarehouseSelect");
  purchaseSelect.innerHTML = '<option value="">Nenhuma</option>';
  warehouseSelect.innerHTML = '<option value="">Nenhuma</option>';

  const filteredPurchases = projectId
    ? purchaseRequests.filter((request) => request.project_id === Number(projectId))
    : purchaseRequests;
  const filteredWarehouse = projectId
    ? warehouseRequests.filter((request) => request.project_id === Number(projectId))
    : warehouseRequests;

  filteredPurchases.forEach((request) => {
    const opt = document.createElement("option");
    opt.value = request.id;
    opt.textContent = `${request.title} (${request.project_name || "Projeto"})`;
    purchaseSelect.appendChild(opt);
  });

  filteredWarehouse.forEach((request) => {
    const opt = document.createElement("option");
    opt.value = request.id;
    opt.textContent = `${request.title} (${request.project_name || "Projeto"})`;
    warehouseSelect.appendChild(opt);
  });
}

function renderRomaneios() {
  const tbody = document.getElementById("romaneiosTableBody");
  tbody.innerHTML = "";
  if (!romaneios || romaneios.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Nenhum romaneio criado.</td></tr>`;
    return;
  }

  const canManage = currentUser.role === "owner" || currentUser.role === "admin";
  romaneios.forEach((item) => {
    const actionLabel = item.status === "aberto" ? "Concluir" : item.status === "concluído" ? "Cancelar" : "Detalhes";
    const actionStatus = item.status === "aberto" ? "concluído" : item.status === "concluído" ? "cancelado" : item.status;
    const actions = canManage && actionStatus !== item.status
      ? `<button class="btn-sm btn-primary" onclick="updateRomaneioStatus(${item.id}, '${actionStatus}')">${actionLabel}</button>`
      : "";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.id}</td>
      <td>${item.project_name || "-"}</td>
      <td>${item.name}</td>
      <td>${item.purchase_title || "-"}</td>
      <td>${item.warehouse_title || "-"}</td>
      <td>${item.status || "aberto"}</td>
      <td>${new Date(item.created_at).toLocaleDateString("pt-BR")}</td>
      <td>${actions}</td>
    `;
    tbody.appendChild(tr);
  });
}

function loadRomaneioRelatedRequests() {
  const projectId = document.getElementById("romaneioProjectSelect").value;
  renderRomaneioRequestOptions(projectId);
}

async function updatePurchaseStatus(purchaseId, status) {
  try {
    const res = await fetch(`/api/purchases/${purchaseId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao atualizar status da compra.", "error");
      return;
    }
    await loadPurchases();
    showMessage("Status da compra atualizado.", "success");
  } catch (error) {
    showMessage("Erro ao atualizar status da compra.", "error");
  }
}

async function updateWarehouseStatus(warehouseId, status) {
  try {
    const res = await fetch(`/api/warehouse/${warehouseId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao atualizar status do almoxarifado.", "error");
      return;
    }
    await loadWarehouse();
    showMessage("Status do almoxarifado atualizado.", "success");
  } catch (error) {
    showMessage("Erro ao atualizar status do almoxarifado.", "error");
  }
}

async function updateRomaneioStatus(romaneioId, status) {
  try {
    const res = await fetch(`/api/romaneios/${romaneioId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao atualizar status do romaneio.", "error");
      return;
    }
    await loadRomaneios();
    showMessage("Status do romaneio atualizado.", "success");
  } catch (error) {
    showMessage("Erro ao atualizar status do romaneio.", "error");
  }
}

async function saveRomaneio() {
  const projectId = document.getElementById("romaneioProjectSelect").value;
  const purchaseId = document.getElementById("romaneioPurchaseSelect").value;
  const warehouseId = document.getElementById("romaneioWarehouseSelect").value;
  const name = document.getElementById("romaneioName").value.trim();
  const note = document.getElementById("romaneioNote").value.trim();

  if (!projectId) {
    showMessage("Selecione um projeto para criar o romaneio.", "error");
    return;
  }
  if (!name) {
    showMessage("Informe o nome do romaneio.", "error");
    return;
  }

  try {
    const res = await fetch("/api/romaneios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, purchase_id: purchaseId || null, warehouse_id: warehouseId || null, name, note }),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }
    document.getElementById("romaneioName").value = "";
    document.getElementById("romaneioNote").value = "";
    document.getElementById("romaneioPurchaseSelect").value = "";
    document.getElementById("romaneioWarehouseSelect").value = "";
    showMessage("Romaneio criado com sucesso.", "success");
    loadRomaneios();
  } catch (error) {
    showMessage("Erro ao criar romaneio.", "error");
  }
}

async function saveProjectRequest() {
  if (!selectedProjectId) {
    showMessage("Selecione um projeto primeiro.", "error");
    return;
  }

  const type = document.getElementById("requestType").value;
  const title = document.getElementById("requestTitle").value.trim();
  const description = document.getElementById("requestDescription").value.trim();

  if (!title) {
    showMessage("Informe um título para a solicitação.", "error");
    return;
  }

  const approverId = document.getElementById("requestApprover").value || null;
  try {
    const res = await fetch(`/api/projects/${selectedProjectId}/requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, title, description, approver_id: approverId }),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }
    document.getElementById("requestTitle").value = "";
    document.getElementById("requestDescription").value = "";
    document.getElementById("requestApprover").value = "";
    await loadProjectRequests(selectedProjectId);
    showMessage("Solicitação criada com sucesso.", "success");
  } catch (error) {
    showMessage("Erro ao criar solicitação.", "error");
  }
}

function populateProjectAccessSelectors(selectedMembers = []) {
  const editorsSelect = document.getElementById("projectEditorUsers");
  const viewersSelect = document.getElementById("projectViewerUsers");
  if (!editorsSelect || !viewersSelect) return;

  editorsSelect.innerHTML = "";
  viewersSelect.innerHTML = "";

  allTeamMembers.forEach((member) => {
    const editorOption = document.createElement("option");
    editorOption.value = member.id;
    editorOption.textContent = member.username;

    const viewerOption = document.createElement("option");
    viewerOption.value = member.id;
    viewerOption.textContent = member.username;

    const selectedMember = selectedMembers.find((m) => m.user_id === member.id);
    if (selectedMember?.access === "edit") {
      editorOption.selected = true;
    } else if (selectedMember?.access === "view") {
      viewerOption.selected = true;
    }

    editorsSelect.appendChild(editorOption);
    viewersSelect.appendChild(viewerOption);
  });
}

async function openProjectModal(projectId = null) {
  const modal = document.getElementById("projectModal");
  document.getElementById("projectForm").reset();
  document.getElementById("projectId").value = "";
  document.getElementById("projectStatus").value = "planejamento";

  if (!allTeamMembers.length) {
    try {
      await loadTeamMembers();
    } catch (err) {
      console.warn("Could not load team members:", err);
      allTeamMembers = [];
    }
  }

  if (projectId) {
    const res = await fetch(`/api/projects/${projectId}`);
    const project = await res.json();
    if (project.error) {
      showMessage(project.error, "error");
      return;
    }

    document.getElementById("projectModalTitle").textContent = "Editar Projeto";
    document.getElementById("projectId").value = projectId;
    document.getElementById("projectName").value = project.name;
    document.getElementById("projectDescription").value = project.description || "";
    document.getElementById("projectStatus").value = project.status || "planejamento";
    document.getElementById("projectStartDate").value = project.start_date || "";
    document.getElementById("projectDueDate").value = project.due_date || "";
    document.getElementById("projectAssemblyStartDate").value = project.assembly_start_date || "";
    document.getElementById("projectAssemblyEndDate").value = project.assembly_end_date || "";
    document.getElementById("projectEventStartDate").value = project.event_start_date || "";
    document.getElementById("projectEventEndDate").value = project.event_end_date || "";
    document.getElementById("projectDismantleStartDate").value = project.dismantle_start_date || "";
    document.getElementById("projectDismantleEndDate").value = project.dismantle_end_date || "";
    document.getElementById("projectAssemblyAddress").value = project.assembly_address || "";
    document.getElementById("projectEventAddress").value = project.event_address || "";
    populateProjectAccessSelectors(project.members || []);
  } else {
    document.getElementById("projectModalTitle").textContent = "Novo Projeto";
    document.getElementById("projectAssemblyStartDate").value = "";
    document.getElementById("projectAssemblyEndDate").value = "";
    document.getElementById("projectEventStartDate").value = "";
    document.getElementById("projectEventEndDate").value = "";
    document.getElementById("projectDismantleStartDate").value = "";
    document.getElementById("projectDismantleEndDate").value = "";
    document.getElementById("projectAssemblyAddress").value = "";
    document.getElementById("projectEventAddress").value = "";
    populateProjectAccessSelectors([]);
  }

  modal.classList.remove("hidden");
}

async function saveProject(e) {
  e.preventDefault();
  const projectId = document.getElementById("projectId").value;
  const data = {
    name: document.getElementById("projectName").value.trim(),
    description: document.getElementById("projectDescription").value.trim(),
    status: document.getElementById("projectStatus").value,
    start_date: document.getElementById("projectStartDate").value || null,
    due_date: document.getElementById("projectDueDate").value || null,
    assembly_start_date: document.getElementById("projectAssemblyStartDate").value || null,
    assembly_end_date: document.getElementById("projectAssemblyEndDate").value || null,
    event_start_date: document.getElementById("projectEventStartDate").value || null,
    event_end_date: document.getElementById("projectEventEndDate").value || null,
    dismantle_start_date: document.getElementById("projectDismantleStartDate").value || null,
    dismantle_end_date: document.getElementById("projectDismantleEndDate").value || null,
    assembly_address: document.getElementById("projectAssemblyAddress").value.trim() || null,
    event_address: document.getElementById("projectEventAddress").value.trim() || null,
  };

  if (!data.name) {
    showMessage("Nome do projeto é obrigatório.", "error");
    return;
  }

  const editorSelect = document.getElementById("projectEditorUsers");
  const viewerSelect = document.getElementById("projectViewerUsers");
  const editors = editorSelect ? Array.from(editorSelect.selectedOptions).map((opt) => parseInt(opt.value, 10)) : [];
  const viewers = viewerSelect ? Array.from(viewerSelect.selectedOptions).map((opt) => parseInt(opt.value, 10)) : [];

  const memberMap = new Map();
  viewers.forEach((userId) => {
    if (userId) {
      memberMap.set(userId, { user_id: userId, access: "view" });
    }
  });
  editors.forEach((userId) => {
    if (userId) {
      memberMap.set(userId, { user_id: userId, access: "edit" });
    }
  });
  data.members = Array.from(memberMap.values());

  try {
    const endpoint = projectId ? `/api/projects/${projectId}` : "/api/projects";
    const method = projectId ? "PUT" : "POST";
    const res = await fetch(endpoint, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }
    document.getElementById("projectModal").classList.add("hidden");
    await loadProjects();
    showMessage(`Projeto ${projectId ? "atualizado" : "criado"} com sucesso.`, "success");
  } catch (error) {
    showMessage("Erro ao salvar projeto", "error");
  }
}

function editProject(projectId) {
  openProjectModal(projectId);
}

async function deleteProject(projectId) {
  if (!confirm("Deseja realmente excluir este projeto?")) return;
  try {
    await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
    if (selectedProjectId === projectId) {
      selectedProjectId = null;
      document.getElementById("selectedProjectLabel").textContent = "Selecione um projeto para ver as tarefas";
      document.getElementById("tasksTableBody").innerHTML = "";
    }
    await loadProjects();
    showMessage("Projeto removido.", "success");
  } catch (error) {
    showMessage("Erro ao deletar projeto", "error");
  }
}

async function loadProjectTasks(projectId) {
  if (!projectId) return;
  const res = await fetch(`/api/projects/${projectId}/tasks`);
  allTasks = await res.json();
  populateTaskFilterOptions(allTasks);
  renderTasks();
  renderTaskBoard();
}

function getFilteredTasks(tasks) {
  const sector = document.getElementById("taskFilterSector").value;
  const responsible = document.getElementById("taskFilterResponsible").value;
  const priority = document.getElementById("taskFilterPriority").value;
  const startDate = document.getElementById("taskFilterStartDate").value;
  const endDate = document.getElementById("taskFilterEndDate").value;

  return tasks.filter((task) => {
    if (sector && String(task.sector || "").toLowerCase() !== sector.toLowerCase()) return false;
    if (priority && String(task.priority || "").toLowerCase() !== priority.toLowerCase()) return false;
    if (responsible) {
      const names = (task.assignees || []).map((a) => String(a.username).toLowerCase());
      if (!names.includes(responsible.toLowerCase()) && String(task.assigned_name || "").toLowerCase() !== responsible.toLowerCase()) {
        return false;
      }
    }
    if (startDate && task.due_date && task.due_date < startDate) return false;
    if (endDate && task.due_date && task.due_date > endDate) return false;
    return true;
  });
}

function clearTaskFilters() {
  document.getElementById("taskFilterSector").value = "";
  document.getElementById("taskFilterResponsible").value = "";
  document.getElementById("taskFilterPriority").value = "";
  document.getElementById("taskFilterStartDate").value = "";
  document.getElementById("taskFilterEndDate").value = "";
  renderTasks();
  renderTaskBoard();
}

function populateTaskFilterOptions(tasks) {
  const sectorSelect = document.getElementById("taskFilterSector");
  const responsibleSelect = document.getElementById("taskFilterResponsible");
  if (!sectorSelect || !responsibleSelect) return;

  const sectors = [...new Set(tasks.map((task) => task.sector || ""))].filter(Boolean).sort();
  const users = [...new Set(tasks.flatMap((task) => (task.assignees || []).map((a) => a.username)))].sort();

  sectorSelect.innerHTML = '<option value="">Todos os setores</option>' + sectors.map((sector) => `<option value="${sector}">${sector}</option>`).join("");
  responsibleSelect.innerHTML = '<option value="">Todos os responsáveis</option>' + users.map((username) => `<option value="${username}">${username}</option>`).join("");
}

function renderTasks() {
  const tbody = document.getElementById("tasksTableBody");
  const detailTbody = document.getElementById("detailTasksTableBody");
  if (tbody) tbody.innerHTML = "";
  if (detailTbody) detailTbody.innerHTML = "";

  if (!allTasks || allTasks.length === 0) {
    const emptyRow = `<tr><td colspan="6" class="empty-row">Nenhuma tarefa cadastrada para este projeto.</td></tr>`;
    if (tbody) tbody.innerHTML = emptyRow;
    if (detailTbody) detailTbody.innerHTML = emptyRow;
    return;
  }

  const filteredTasks = getFilteredTasks(allTasks);
  const canEditTasks = currentUser.role === "owner" || currentUser.role === "admin" || currentProjectAccessLevel === "edit";
  filteredTasks.forEach((task) => {
    const tr = document.createElement("tr");
    const assignedNames = (task.assignees && task.assignees.length) ? task.assignees.map(a => a.username).join(', ') : (task.assigned_name || '-');
    const actionButtons = `<div class="action-buttons"><button class="btn-sm btn-primary" onclick="openTaskWorkspace(${task.id})">Workspace</button>${canEditTasks ? `<button class="btn-sm btn-edit" onclick="editTask(${task.id})">Editar</button><button class="btn-sm btn-delete" onclick="deleteTask(${task.id})">Del</button>` : ""}</div>`;
    tr.innerHTML = `
      <td>${task.name}</td>
      <td>${task.status}</td>
      <td>${task.priority}</td>
      <td>${assignedNames}</td>
      <td>${task.due_date || "-"}</td>
      <td>${actionButtons}</td>
    `;
    if (tbody) tbody.appendChild(tr);
    if (detailTbody) {
      const clone = tr.cloneNode(true);
      detailTbody.appendChild(clone);
    }
  });
}

async function openTaskModal(taskId = null) {
  if (!selectedProjectId) {
    showMessage("Selecione um projeto primeiro.", "error");
    return;
  }
  if (!(currentUser.role === "owner" || currentUser.role === "admin" || currentProjectAccessLevel === "edit")) {
    showMessage("Você não tem permissão para gerenciar tarefas deste projeto.", "error");
    return;
  }

  document.getElementById("taskForm").reset();
  document.getElementById("taskId").value = "";
  document.getElementById("taskProjectId").value = selectedProjectId;
  document.getElementById("taskAssignee").innerHTML = '<option value="">Sem responsável</option>';
  document.getElementById("taskSector").value = "";
  allTeamMembers.forEach((member) => {
    const opt = document.createElement("option");
    opt.value = member.id;
    opt.textContent = member.username;
    document.getElementById("taskAssignee").appendChild(opt);
  });

  if (taskId) {
    const task = allTasks.find((t) => t.id === taskId);
    if (task) {
      document.getElementById("taskModalTitle").textContent = "Editar Tarefa";
      document.getElementById("taskId").value = taskId;
      document.getElementById("taskName").value = task.name;
      document.getElementById("taskDescription").value = task.description || "";
      document.getElementById("taskStatus").value = task.status || "pendente";
      document.getElementById("taskPriority").value = task.priority || "média";
      document.getElementById("taskSector").value = task.sector || "";
      document.getElementById("taskDueDate").value = task.due_date || "";
      if (task.assignees && task.assignees.length) {
        const sel = document.getElementById("taskAssignee");
        Array.from(sel.options).forEach(opt => { opt.selected = task.assignees.some(a => String(a.id) === String(opt.value)); });
      } else if (task.assigned_to) {
        document.getElementById("taskAssignee").value = task.assigned_to;
      }
    }
  } else {
    document.getElementById("taskModalTitle").textContent = "Nova Tarefa";
  }

  document.getElementById("taskModal").classList.remove("hidden");
}

async function saveTask(e) {
  e.preventDefault();
  const taskId = document.getElementById("taskId").value;
  const projectId = document.getElementById("taskProjectId").value;
  const assignedTo = Array.from(document.getElementById("taskAssignee").selectedOptions)
    .map((opt) => parseInt(opt.value, 10))
    .filter((id) => !Number.isNaN(id));
  const data = {
    name: document.getElementById("taskName").value.trim(),
    description: document.getElementById("taskDescription").value.trim(),
    status: document.getElementById("taskStatus").value,
    priority: document.getElementById("taskPriority").value,
    sector: document.getElementById("taskSector").value.trim() || null,
    assigned_to: assignedTo.length ? assignedTo : null,
    due_date: document.getElementById("taskDueDate").value || null,
  };

  if (!data.name) {
    showMessage("Nome da tarefa é obrigatório.", "error");
    return;
  }

  try {
    const endpoint = taskId ? `/api/tasks/${taskId}` : `/api/projects/${projectId}/tasks`;
    const method = taskId ? "PUT" : "POST";
    const res = await fetch(endpoint, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }
    document.getElementById("taskModal").classList.add("hidden");
    await loadProjectTasks(projectId);
    showMessage(`Tarefa ${taskId ? "atualizada" : "criada"} com sucesso.`, "success");
  } catch (error) {
    showMessage("Erro ao salvar tarefa", "error");
  }
}

function editTask(taskId) {
  openTaskModal(taskId);
}

async function deleteTask(taskId) {
  if (!confirm("Deseja realmente excluir esta tarefa?")) return;
  try {
    await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
    await loadProjectTasks(selectedProjectId);
    showMessage("Tarefa removida.", "success");
  } catch (error) {
    showMessage("Erro ao deletar tarefa", "error");
  }
}

async function loadTeamMembers() {
  try {
    const res = await fetch("/api/users");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    allTeamMembers = await res.json();
    renderTeamMembers();
  } catch (err) {
    console.error("Error loading team members:", err);
    allTeamMembers = [];
  }
}

function renderTeamMembers() {
  const tbody = document.getElementById("teamTableBody");
  tbody.innerHTML = "";

  if (!allTeamMembers || allTeamMembers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">Nenhum membro encontrado.</td></tr>`;
    return;
  }

  allTeamMembers.forEach((member) => {
    const tr = document.createElement("tr");
    const canManage = currentUser.role === "owner" || currentUser.role === "admin";
    tr.innerHTML = `
      <td>${member.username}</td>
      <td>${member.email || "-"}</td>
      <td>${member.role}</td>
      <td>${member.status || "active"}</td>
      <td>${new Date(member.created_at).toLocaleDateString("pt-BR")}</td>
      <td>
        <div class="action-buttons">
          ${canManage ? `<button class="btn-sm btn-edit" onclick="openUserAccessModal(${member.id})">Acesso</button>` : ""}
          ${canManage ? `<button class="btn-sm btn-toggle" onclick="toggleUserStatus(${member.id}, '${member.status === "active" ? "inactive" : "active"}')">${member.status === "active" ? "Desabilitar" : "Habilitar"}</button>` : ""}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  const assigneeSelect = document.getElementById("taskAssignee");
  if (assigneeSelect) {
    assigneeSelect.innerHTML = '<option value="">Sem responsável</option>';
    allTeamMembers.forEach((member) => {
      const opt = document.createElement("option");
      opt.value = member.id;
      opt.textContent = member.username;
      assigneeSelect.appendChild(opt);
    });
  }
}

function applyUserPermissions() {
  const hasFullAccess = currentUser.role === "owner" || currentUser.role === "admin";
  const userPermissions = currentUser.permissions || [];

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    const perm = btn.dataset.permission;
    if (!perm) {
      btn.classList.remove("hidden");
      return;
    }

    if (perm === "items") {
      const inventoryPerms = ["items", "warehouse", "historico", "relatorios"];
      if (hasFullAccess || inventoryPerms.some((p) => userPermissions.includes(p))) {
        btn.classList.remove("hidden");
      } else {
        btn.classList.add("hidden");
      }
      return;
    }

    if (hasFullAccess || userPermissions.includes(perm)) {
      btn.classList.remove("hidden");
    } else {
      btn.classList.add("hidden");
    }
  });

  const inviteSection = document.getElementById("inviteMemberForm")?.closest(".config-section");
  if (inviteSection) {
    if (hasFullAccess) {
      inviteSection.classList.remove("hidden");
    } else {
      inviteSection.classList.add("hidden");
    }
  }
}

function initializeSidebar() {
  const toggleBtn = document.getElementById("sidebarToggleBtn");
  const openBtn = document.getElementById("sidebarOpenBtn");
  
  if (!toggleBtn || !openBtn) return;
  
  const collapsed = localStorage.getItem("sidebarCollapsed") === "true";
  setSidebarCollapsed(collapsed);
  
  toggleBtn.addEventListener("click", () => setSidebarCollapsed(true));
  openBtn.addEventListener("click", () => setSidebarCollapsed(false));
}

function setSidebarCollapsed(collapsed) {
  const sidebar = document.getElementById("sidebar");
  const openButton = document.getElementById("sidebarOpenBtn");
  
  if (!sidebar || !openButton) return;

  if (collapsed) {
    sidebar.classList.add("collapsed");
    openButton.classList.remove("hidden");
  } else {
    sidebar.classList.remove("collapsed");
    openButton.classList.add("hidden");
  }
  localStorage.setItem("sidebarCollapsed", collapsed ? "true" : "false");
}

function openUserAccessModal(userId) {
  const user = allTeamMembers.find((member) => member.id === userId);
  if (!user) {
    showMessage("Usuário não encontrado.", "error");
    return;
  }

  document.getElementById("accessUserId").value = user.id;
  document.getElementById("accessUserRole").value = user.role || "member";
  document.getElementById("accessUserStatus").value = user.status || "active";
  document.querySelectorAll(".access-permission").forEach((checkbox) => {
    checkbox.checked = (user.permissions || []).includes(checkbox.value);
  });
  document.getElementById("userPermissionsModal").classList.remove("hidden");
}

async function saveUserAccess(e) {
  e.preventDefault();
  const userId = document.getElementById("accessUserId").value;
  const role = document.getElementById("accessUserRole").value;
  const status = document.getElementById("accessUserStatus").value;
  const permissions = Array.from(document.querySelectorAll(".access-permission:checked")).map((checkbox) => checkbox.value);

  try {
    const res = await fetch(`/api/users/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, status, permissions }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao salvar acesso.", "error");
      return;
    }
    document.getElementById("userPermissionsModal").classList.add("hidden");
    await loadTeamMembers();
    showMessage("Acesso do usuário atualizado.", "success");
  } catch (error) {
    showMessage("Erro ao salvar acesso do usuário.", "error");
  }
}

async function toggleUserStatus(userId, status) {
  const user = allTeamMembers.find((member) => member.id === userId);
  if (!user) {
    showMessage("Usuário não encontrado.", "error");
    return;
  }

  try {
    const res = await fetch(`/api/users/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: user.role, status, permissions: user.permissions || [] }),
    });
    const result = await res.json();
    if (!res.ok) {
      showMessage(result.error || "Erro ao atualizar status.", "error");
      return;
    }
    await loadTeamMembers();
    showMessage(`Usuário ${status === "active" ? "ativado" : "desativado"} com sucesso.`, "success");
  } catch (error) {
    showMessage("Erro ao atualizar status do usuário.", "error");
  }
}

async function inviteTeamMember(e) {
  e.preventDefault();
  const username = document.getElementById("inviteUsername").value.trim();
  const email = document.getElementById("inviteEmail").value.trim();
  const password = document.getElementById("invitePassword").value;
  const role = document.getElementById("inviteRole").value;

  if (!username || !password) {
    showMessage("Usuário e senha são obrigatórios.", "error");
    return;
  }

  try {
    const res = await fetch("/api/team/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, role }),
    });
    const result = await res.json();
    if (result.error) {
      showMessage(result.error, "error");
      return;
    }

    document.getElementById("inviteMemberForm").reset();
    await loadTeamMembers();
    if (result.warning) {
      showMessage(result.warning, "warning");
      return;
    }
    showMessage("Membro convidado com sucesso.", "success");
  } catch (error) {
    showMessage("Erro ao convidar membro", "error");
  }
}

// ==================== MUDAR SENHA ====================
function openChangePasswordModal() {
  document.getElementById("changePasswordModal").classList.remove("hidden");
  document.getElementById("changePasswordForm").reset();
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
