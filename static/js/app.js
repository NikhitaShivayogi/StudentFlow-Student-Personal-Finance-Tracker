/* StudentFlow – app.js */
document.addEventListener('DOMContentLoaded', function () {

  // ── Category lists ────────────────────────────────────────────────────────
  var INCOME_CATS = [
    'Parents Allowance', 'Scholarship', 'Part-time Job',
    'Freelance Work', 'Stipend', 'Prize / Award',
    'Loan (Education)', 'Gift / Festival Money', 'Other Income'
  ];
  var EXPENSE_CATS = [
    'Food & Canteen', 'College Fees / Tuition', 'Books & Stationery',
    'Transport / Commute', 'Rent / Hostel', 'Electricity & Internet',
    'Clothing & Shopping', 'Entertainment & OTT', 'Medical / Health',
    'Mobile Recharge', 'Gym / Sports', 'Subscriptions',
    'Exam Fees', 'Project / Lab Costs', 'Other Expense'
  ];

  var CHART_COLORS = [
    '#06b6d4','#22d3ee','#34d399','#f59e0b','#a78bfa',
    '#f472b6','#60a5fa','#fb923c','#4ade80','#e879f9',
    '#38bdf8','#fbbf24'
  ];
  var INCOME_COLOR  = '#34d399';
  var EXPENSE_COLOR = '#f87171';

  // ── State ─────────────────────────────────────────────────────────────────
  var currentType    = 'income';
  var currentFilter  = 'all';
  var currentCatType = 'expense';
  var currentDays    = 30;
  var allTransactions = [];
  var pieChart = null;
  var timeChart = null;

  // ── DOM refs ─────────────────────────────────────────────────────────────
  var txList        = document.getElementById('txList');
  var addForm       = document.getElementById('addForm');
  var dateInput     = document.getElementById('dateInput');
  var txTypeInput   = document.getElementById('txTypeInput');
  var categorySelect= document.getElementById('categorySelect');
  var addBtn        = document.getElementById('addBtn');
  var addBtnLabel   = document.getElementById('addBtnLabel');
  var toast         = document.getElementById('toast');
  var floatingRoot  = document.getElementById('floating-root');
  var balancePill   = document.getElementById('balancePill');
  var budgetModal   = document.getElementById('budgetModal');
  var budgetInput   = document.getElementById('budgetInput');
  var monthSelector = document.getElementById('monthSelector');
  // budget goal fields (used in loadSummary too)
  var goalTypeInput   = document.getElementById('goalTypeInput');
  var goalFromDate    = document.getElementById('goalFromDate');
  var goalToDate      = document.getElementById('goalToDate');
  var goalCustomDates = document.getElementById('goalCustomDates');
  var goalMonthlyHint = document.getElementById('goalMonthlyHint');

  // init date
  if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);

  // init month selector
  if (monthSelector) {
    var now = new Date();
    monthSelector.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  }

  // ── Toast ─────────────────────────────────────────────────────────────────
  function notify(msg, isError) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    toast.classList.toggle('error', !!isError);
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      toast.classList.remove('show', 'error');
    }, 2500);
  }

  // ── Fetch helper ──────────────────────────────────────────────────────────
  async function api(url, opts) {
    var res = await fetch(url, opts);
    var data = await res.json();
    if (res.status === 401) { window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  // ── "Other" specify field ─────────────────────────────────────────────────
  var otherCatWrap  = document.getElementById('otherCatWrap');
  var otherCatInput = document.getElementById('otherCatInput');

  function isOtherCat(val) {
    return val === 'Other Expense' || val === 'Other Income';
  }

  function toggleOtherField(val) {
    if (!otherCatWrap) return;
    var show = isOtherCat(val);
    otherCatWrap.style.display = show ? '' : 'none';
    if (otherCatInput) {
      otherCatInput.required = show;
      if (!show) otherCatInput.value = '';
    }
  }

  // ── Category dropdown ─────────────────────────────────────────────────────
  function updateCategories(type) {
    var cats = type === 'income' ? INCOME_CATS : EXPENSE_CATS;
    categorySelect.innerHTML = '<option value="" disabled selected>Select category</option>';
    cats.forEach(function (c) {
      var o = document.createElement('option');
      o.value = c; o.textContent = c;
      categorySelect.appendChild(o);
    });
    toggleOtherField(''); // hide on type switch
  }
  updateCategories('income');

  categorySelect.addEventListener('change', function () {
    toggleOtherField(categorySelect.value);
  });

  // ── Type toggle ───────────────────────────────────────────────────────────
  document.querySelectorAll('.type-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      currentType = btn.dataset.type;
      document.querySelectorAll('.type-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      txTypeInput.value = currentType;
      updateCategories(currentType);
      if (currentType === 'income') {
        addBtn.className = 'btn-add-income';
        addBtnLabel.textContent = 'Add Income';
      } else {
        addBtn.className = 'btn-add-expense';
        addBtnLabel.textContent = 'Add Expense';
      }
    });
  });

  // ── Filter tabs ───────────────────────────────────────────────────────────
  document.querySelectorAll('.filter-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      currentFilter = tab.dataset.filter;
      document.querySelectorAll('.filter-tab').forEach(function (t) { t.classList.remove('active'); });
      tab.classList.add('active');
      renderTxList(allTransactions);
    });
  });

  // ── Category chart type ───────────────────────────────────────────────────
  document.querySelectorAll('[data-ctype]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      currentCatType = chip.dataset.ctype;
      document.querySelectorAll('[data-ctype]').forEach(function (c) { c.classList.remove('active'); });
      chip.classList.add('active');
      loadPieChart();
    });
  });

  // ── Range chips ───────────────────────────────────────────────────────────
  document.querySelectorAll('.range-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      currentDays = parseInt(chip.dataset.days);
      document.querySelectorAll('.range-chip').forEach(function (c) { c.classList.remove('active'); });
      chip.classList.add('active');
      loadTimeChart();
    });
  });

  // ── Render transaction row ────────────────────────────────────────────────
  var CAT_ICONS = {
    'Parents Allowance':'fas fa-home','Scholarship':'fas fa-award',
    'Part-time Job':'fas fa-briefcase','Freelance Work':'fas fa-laptop',
    'Stipend':'fas fa-university','Prize / Award':'fas fa-trophy',
    'Loan (Education)':'fas fa-hand-holding-usd','Gift / Festival Money':'fas fa-gift',
    'Food & Canteen':'fas fa-utensils','College Fees / Tuition':'fas fa-graduation-cap',
    'Books & Stationery':'fas fa-book','Transport / Commute':'fas fa-bus',
    'Rent / Hostel':'fas fa-bed','Electricity & Internet':'fas fa-bolt',
    'Clothing & Shopping':'fas fa-shopping-bag','Entertainment & OTT':'fas fa-film',
    'Medical / Health':'fas fa-heartbeat','Mobile Recharge':'fas fa-mobile-alt',
    'Gym / Sports':'fas fa-dumbbell','Subscriptions':'fas fa-credit-card',
    'Exam Fees':'fas fa-file-alt','Project / Lab Costs':'fas fa-flask'
  };

  function txIcon(cat) {
    return CAT_ICONS[cat] || 'fas fa-tag';
  }

  function createTxRow(tx) {
    var isIncome = tx.type === 'income';
    var div = document.createElement('div');
    div.className = 'tx-row';
    div.dataset.id = tx.id;
    div.dataset.type = tx.type;
    var sign = isIncome ? '+' : '-';
    div.innerHTML =
      '<div class="d-flex align-items-center" style="gap:.75rem;min-width:0;flex:1">' +
        '<div class="tx-cat-badge ' + (isIncome ? 'income-badge' : 'expense-badge') + '" style="flex-shrink:0">' +
          '<i class="' + txIcon(tx.category) + '"></i>' +
        '</div>' +
        '<div style="min-width:0">' +
          '<div class="tx-cat" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(tx.category) + '</div>' +
          '<div class="tx-meta">' + esc(tx.date) + (tx.description ? ' · ' + esc(tx.description) : '') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="tx-actions">' +
        '<div class="tx-amount ' + (isIncome ? 'income-amt' : 'expense-amt') + '">' + sign + ' Rs ' + Number(tx.amount).toFixed(2) + '</div>' +
        '<button class="tx-edit" data-id="' + tx.id + '" title="Edit"><i class="fas fa-pen"></i></button>' +
        '<button class="tx-del"  data-id="' + tx.id + '" title="Delete"><i class="fas fa-trash"></i></button>' +
      '</div>';
    div.querySelector('.tx-del').addEventListener('click', function (e) {
      e.stopPropagation();
      deleteTransaction(tx.id);
    });
    div.querySelector('.tx-edit').addEventListener('click', function (e) {
      e.stopPropagation();
      openEditModal(tx);
    });
    return div;
  }

  function esc(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function renderTxList(list) {
    txList.innerHTML = '';
    var filtered = list.filter(function (tx) {
      if (currentFilter === 'all') return true;
      return tx.type === currentFilter;
    });
    if (filtered.length === 0) {
      txList.innerHTML = '<div class="tx-empty"><i class="fas fa-inbox" style="font-size:2rem;opacity:.3;display:block;margin-bottom:.5rem"></i>No transactions found</div>';
      return;
    }
    filtered.slice(0, 80).forEach(function (tx, i) {
      var el = createTxRow(tx);
      el.style.animationDelay = (i * 0.04) + 's';
      txList.appendChild(el);
    });
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  async function deleteTransaction(id) {
    if (!confirm('Delete this transaction?')) return;
    try {
      await api('/api/transactions/' + encodeURIComponent(id), { method: 'DELETE' });
      notify('Transaction deleted');
      await refresh();
    } catch (err) {
      notify(err.message || 'Delete failed', true);
    }
  }

  // ── Load summary ──────────────────────────────────────────────────────────
  async function loadSummary() {
    var data = await api('/api/summary');
    if (!data) return;
    setText('sumIncome', 'Rs ' + data.all_time.income.toFixed(2));
    setText('sumExpense', 'Rs ' + data.all_time.expense.toFixed(2));
    var bal = data.all_time.balance;
    var balEl = document.getElementById('sumBalance');
    if (balEl) {
      balEl.textContent = 'Rs ' + Math.abs(bal).toFixed(2);
      balEl.style.color = bal >= 0 ? '#34d399' : '#f87171';
    }
    setText('sumIncomeMonth', 'This month: Rs ' + data.this_month.income.toFixed(2));
    setText('sumExpenseMonth', 'This month: Rs ' + data.this_month.expense.toFixed(2));
    var bm = data.this_month.balance;
    setText('sumBalanceMonth', 'This month: Rs ' + Math.abs(bm).toFixed(2) + (bm < 0 ? ' (deficit)' : ''));
    if (balancePill) balancePill.innerHTML = '<i class="fas fa-wallet" style="margin-right:.35rem"></i>Rs ' + Math.abs(bal).toFixed(2);
    // budget
    var pct = Math.min(data.budget_used_pct, 100);
    var fill = document.getElementById('budgetFill');
    if (fill) {
      fill.style.width = pct + '%';
      fill.className = 'budget-fill' + (pct >= 100 ? ' danger' : pct >= 80 ? ' warning' : '');
    }
    setText('budgetSpent', 'Spent: Rs ' + data.budget_spent.toFixed(2));
    if (data.budget_limit > 0) {
      setText('budgetLimit', 'Limit: Rs ' + data.budget_limit.toFixed(2));
      var pctLabel = pct.toFixed(1) + '% of budget used';
      if (data.goal_type === 'custom' && data.goal_from && data.goal_to) {
        pctLabel = pct.toFixed(1) + '% used · ' + fmtDateShort(data.goal_from) + ' → ' + fmtDateShort(data.goal_to);
        // Restore goal type in modal
        if (goalTypeInput) goalTypeInput.value = 'custom';
        document.querySelectorAll('[data-gtype]').forEach(function(b){
          b.classList.toggle('active', b.dataset.gtype === 'custom');
        });
        if (goalCustomDates) goalCustomDates.style.display = '';
        if (goalMonthlyHint) goalMonthlyHint.style.display = 'none';
        if (goalFromDate) goalFromDate.value = data.goal_from;
        if (goalToDate)   goalToDate.value   = data.goal_to;
      }
      setText('budgetSubtitle', pctLabel);
      if (budgetInput) budgetInput.value = data.budget_limit;
    } else {
      setText('budgetLimit', 'Limit: not set');
      setText('budgetSubtitle', 'Set a spending goal');
    }
  }

  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  // ── Load transactions ─────────────────────────────────────────────────────
  async function loadTransactions() {
    var data = await api('/api/transactions');
    if (!data) return;
    allTransactions = data;
    renderTxList(allTransactions);
  }

  // ── Pie chart ─────────────────────────────────────────────────────────────
  async function loadPieChart() {
    var data = await api('/api/stats?type=' + currentCatType);
    if (!data) return;
    var ctx = document.getElementById('pieChart');
    if (!ctx) return;
    if (pieChart) pieChart.destroy();
    pieChart = new Chart(ctx.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: data.labels,
        datasets: [{ data: data.values, backgroundColor: CHART_COLORS, borderWidth: 0 }]
      },
      options: {
        cutout: '65%',
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 11 }, padding: 14 } }
        }
      }
    });
    var tbody = document.getElementById('catTableBody');
    if (tbody) {
      tbody.innerHTML = '';
      data.summary.forEach(function (row) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td>' + esc(row.category) + '</td><td class="text-end">Rs ' + row.total.toFixed(2) + '</td>';
        tbody.appendChild(tr);
      });
      if (data.summary.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:var(--text-light);padding:.75rem">No data</td></tr>';
      }
    }
  }

  // ── Time chart ────────────────────────────────────────────────────────────
  async function loadTimeChart() {
    var data = await api('/api/timeseries?days=' + currentDays);
    if (!data) return;
    var ctx = document.getElementById('timeChart');
    if (!ctx) return;
    if (timeChart) timeChart.destroy();
    timeChart = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'Income',
            data: data.income,
            fill: true,
            backgroundColor: 'rgba(52,211,153,.15)',
            borderColor: INCOME_COLOR,
            tension: 0.4, pointRadius: 2, borderWidth: 2
          },
          {
            label: 'Expense',
            data: data.expense,
            fill: true,
            backgroundColor: 'rgba(248,113,113,.15)',
            borderColor: EXPENSE_COLOR,
            tension: 0.4, pointRadius: 2, borderWidth: 2
          }
        ]
      },
      options: {
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,.05)' }, ticks: { color: '#94a3b8' } },
          x: { grid: { display: false }, ticks: { color: '#94a3b8', maxTicksLimit: 10 } }
        },
        plugins: { legend: { labels: { color: '#94a3b8' } } }
      }
    });
  }

  // ── Monthly table ─────────────────────────────────────────────────────────
  async function loadMonthlyTable() {
    var data = await api('/api/monthly');
    if (!data) return;
    var tbody = document.getElementById('monthTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    data.summary.forEach(function (row) {
      var tr = document.createElement('tr');
      var savedColor = row.balance >= 0 ? '#34d399' : '#f87171';
      tr.innerHTML =
        '<td>' + esc(row.month) + '</td>' +
        '<td class="text-end" style="color:#34d399">Rs ' + row.income.toFixed(2) + '</td>' +
        '<td class="text-end" style="color:#f87171">Rs ' + row.expense.toFixed(2) + '</td>' +
        '<td class="text-end" style="color:' + savedColor + ';font-weight:600">Rs ' + Math.abs(row.balance).toFixed(2) + '</td>';
      tbody.appendChild(tr);
    });
    if (data.summary.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-light);padding:.75rem">No data yet</td></tr>';
    }
  }

  // ── Add transaction ───────────────────────────────────────────────────────
  if (addForm) {
    addForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var fd = new FormData(addForm);
      var selectedCat = fd.get('category') || '';
      var finalCat = isOtherCat(selectedCat)
        ? (otherCatInput && otherCatInput.value.trim()) || selectedCat
        : selectedCat;
      var payload = {
        type: fd.get('type') || currentType,
        date: fd.get('date'),
        category: finalCat,
        amount: fd.get('amount'),
        description: fd.get('description')
      };
      if (addBtn) { addBtn.disabled = true; }
      try {
        var newTx = await api('/api/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!newTx) return;
        // floating pop
        if (floatingRoot) {
          var floatEl = document.createElement('div');
          floatEl.className = 'floating-amount';
          floatEl.style.background = newTx.type === 'income'
            ? 'linear-gradient(135deg,#059669,#34d399)'
            : 'linear-gradient(135deg,#dc2626,#f87171)';
          floatEl.textContent = (newTx.type === 'income' ? '+' : '-') + ' Rs ' + Number(newTx.amount).toFixed(2);
          floatingRoot.appendChild(floatEl);
          setTimeout(function () { floatEl.remove(); }, 1400);
        }
        addForm.reset();
        if (dateInput) dateInput.value = new Date().toISOString().slice(0, 10);
        txTypeInput.value = currentType;
        updateCategories(currentType);
        if (otherCatInput) otherCatInput.value = '';
        if (otherCatWrap)  otherCatWrap.style.display = 'none';
        notify(newTx.type === 'income' ? '💰 Income added!' : '📝 Expense recorded!');
        await refresh();
      } catch (err) {
        notify(err.message || 'Failed to add', true);
      } finally {
        if (addBtn) addBtn.disabled = false;
      }
    });
  }

  // ── Edit modal ────────────────────────────────────────────────────────────
  var editModal       = document.getElementById('editModal');
  var editForm        = document.getElementById('editForm');
  var editTxId        = document.getElementById('editTxId');
  var editDate        = document.getElementById('editDate');
  var editAmount      = document.getElementById('editAmount');
  var editCategory    = document.getElementById('editCategory');
  var editTypeInput   = document.getElementById('editTypeInput');
  var editOtherWrap   = document.getElementById('editOtherWrap');
  var editOtherInput  = document.getElementById('editOtherInput');
  var editDescription = document.getElementById('editDescription');

  function fillEditCategories(type, selected) {
    var cats = type === 'income' ? INCOME_CATS : EXPENSE_CATS;
    editCategory.innerHTML = '<option value="" disabled>Select category</option>';
    // Always add currently selected value even if not in list (custom "other")
    var inList = cats.indexOf(selected) >= 0;
    cats.forEach(function (c) {
      var o = document.createElement('option');
      o.value = c; o.textContent = c;
      if (c === selected) o.selected = true;
      editCategory.appendChild(o);
    });
    // If it's a custom value not in list, show it in the "other" field
    if (!inList && selected) {
      // Select "Other" option and fill the text box
      var otherVal = type === 'income' ? 'Other Income' : 'Other Expense';
      editCategory.value = otherVal;
      if (editOtherInput) editOtherInput.value = selected;
      if (editOtherWrap)  editOtherWrap.style.display = '';
    } else {
      if (editOtherWrap)  editOtherWrap.style.display = 'none';
      if (editOtherInput) editOtherInput.value = '';
    }
  }

  // Edit type toggle
  document.querySelectorAll('[data-etype]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var etype = btn.dataset.etype;
      editTypeInput.value = etype;
      document.querySelectorAll('[data-etype]').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      fillEditCategories(etype, editCategory.value || '');
    });
  });

  // Edit category "other" toggle
  if (editCategory) {
    editCategory.addEventListener('change', function () {
      var show = isOtherCat(editCategory.value);
      if (editOtherWrap) { editOtherWrap.style.display = show ? '' : 'none'; }
      if (editOtherInput) { editOtherInput.required = show; if (!show) editOtherInput.value = ''; }
    });
  }

  function openEditModal(tx) {
    if (!editModal) return;
    editTxId.value        = tx.id;
    editDate.value        = tx.date;
    editAmount.value      = tx.amount;
    editDescription.value = tx.description || '';
    editTypeInput.value   = tx.type;

    // Set type tabs
    document.querySelectorAll('[data-etype]').forEach(function (b) {
      b.classList.toggle('active', b.dataset.etype === tx.type);
    });

    fillEditCategories(tx.type, tx.category);
    editModal.classList.add('open');
    editAmount.focus();
  }

  var editCancelBtn = document.getElementById('editCancelBtn');
  if (editCancelBtn) {
    editCancelBtn.addEventListener('click', function () { editModal.classList.remove('open'); });
  }
  if (editModal) {
    editModal.addEventListener('click', function (e) {
      if (e.target === editModal) editModal.classList.remove('open');
    });
  }

  if (editForm) {
    editForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var id       = parseInt(editTxId.value);
      var selCat   = editCategory.value || '';
      var finalCat = isOtherCat(selCat)
        ? (editOtherInput && editOtherInput.value.trim()) || selCat
        : selCat;
      var payload = {
        type:        editTypeInput.value,
        date:        editDate.value,
        amount:      editAmount.value,
        category:    finalCat,
        description: editDescription.value,
      };
      try {
        await api('/api/transactions/' + id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        editModal.classList.remove('open');
        notify('✏️ Transaction updated!');
        await refresh();
        // Also refresh range report if it was loaded
        if (lastRangeData) {
          loadRangeReport(lastRangeData.from_date, lastRangeData.to_date);
        }
      } catch (err) {
        notify(err.message || 'Update failed', true);
      }
    });
  }

  // ── Budget modal (upgraded) ───────────────────────────────────────────────
  var budgetEditBtn  = document.getElementById('budgetEditBtn');
  var budgetCancelBtn= document.getElementById('budgetCancelBtn');
  var budgetSaveBtn  = document.getElementById('budgetSaveBtn');

  // Goal type tabs
  document.querySelectorAll('[data-gtype]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var gtype = btn.dataset.gtype;
      goalTypeInput.value = gtype;
      document.querySelectorAll('[data-gtype]').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var isCustom = gtype === 'custom';
      if (goalCustomDates) goalCustomDates.style.display = isCustom ? '' : 'none';
      if (goalMonthlyHint) goalMonthlyHint.style.display = isCustom ? 'none' : '';
    });
  });

  if (budgetEditBtn) {
    budgetEditBtn.addEventListener('click', function () {
      if (budgetModal) budgetModal.classList.add('open');
    });
  }
  if (budgetCancelBtn) {
    budgetCancelBtn.addEventListener('click', function () {
      if (budgetModal) budgetModal.classList.remove('open');
    });
  }
  if (budgetModal) {
    budgetModal.addEventListener('click', function (e) {
      if (e.target === budgetModal) budgetModal.classList.remove('open');
    });
  }
  if (budgetSaveBtn) {
    budgetSaveBtn.addEventListener('click', async function () {
      var limit  = parseFloat(budgetInput ? budgetInput.value : 0) || 0;
      var gtype  = goalTypeInput ? goalTypeInput.value : 'monthly';
      var payload = { monthly_limit: limit, goal_type: gtype };
      if (gtype === 'custom') {
        var from = goalFromDate ? goalFromDate.value : '';
        var to   = goalToDate   ? goalToDate.value   : '';
        if (!from || !to) { notify('Please select both dates for custom goal', true); return; }
        if (from > to)    { notify('Start date must be before end date', true); return; }
        payload.from_date = from;
        payload.to_date   = to;
      }
      try {
        await api('/api/budget', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (budgetModal) budgetModal.classList.remove('open');
        notify('🎯 Budget goal saved!');
        await loadSummary();
      } catch (err) {
        notify(err.message || 'Failed to save budget', true);
      }
    });
  }

  // ── CSV downloads ─────────────────────────────────────────────────────────

  // Dropdown open/close
  var csvDropdownBtn  = document.getElementById('csvDropdownBtn');
  var csvDropdown     = document.getElementById('csvDropdown');
  if (csvDropdownBtn && csvDropdown) {
    csvDropdownBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      csvDropdown.style.display = csvDropdown.style.display === 'none' ? '' : 'none';
    });
    document.addEventListener('click', function () {
      if (csvDropdown) csvDropdown.style.display = 'none';
    });
    csvDropdown.addEventListener('click', function (e) { e.stopPropagation(); });
  }

  // Custom range row toggle
  var csvCustomToggleBtn  = document.getElementById('csvCustomToggleBtn');
  var csvCustomRangeRow   = document.getElementById('csvCustomRangeRow');
  var csvCustomCloseBtn   = document.getElementById('csvCustomCloseBtn');
  var csvRangeFrom        = document.getElementById('csvRangeFrom');
  var csvRangeTo          = document.getElementById('csvRangeTo');

  if (csvCustomToggleBtn) {
    csvCustomToggleBtn.addEventListener('click', function () {
      if (csvDropdown) csvDropdown.style.display = 'none';
      if (csvCustomRangeRow) {
        csvCustomRangeRow.style.display = '';
        // Pre-fill sensible defaults if empty
        if (csvRangeFrom && !csvRangeFrom.value) {
          var d = new Date();
          csvRangeFrom.value = new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
        }
        if (csvRangeTo && !csvRangeTo.value) {
          csvRangeTo.value = new Date().toISOString().slice(0, 10);
        }
        csvRangeFrom && csvRangeFrom.focus();
      }
    });
  }
  if (csvCustomCloseBtn) {
    csvCustomCloseBtn.addEventListener('click', function () {
      if (csvCustomRangeRow) csvCustomRangeRow.style.display = 'none';
    });
  }

  // 1. Selected Month — Excel download
  var downloadMonthCsv = document.getElementById('downloadMonthCsv');
  if (downloadMonthCsv) {
    downloadMonthCsv.addEventListener('click', function () {
      if (csvDropdown) csvDropdown.style.display = 'none';
      var sel = monthSelector ? monthSelector.value : '';
      if (!sel) { notify('Select a month first', true); return; }
      // month = YYYY-MM  →  from = YYYY-MM-01, to = last day of that month
      var parts = sel.split('-');
      var y = parseInt(parts[0]), m = parseInt(parts[1]);
      var from = sel + '-01';
      var lastDay = new Date(y, m, 0).getDate();
      var to = sel + '-' + String(lastDay).padStart(2, '0');
      window.location.href = '/api/report/excel?from_date=' + from + '&to_date=' + to;
      notify('📊 Preparing Excel report…');
    });
  }

  // 2. All Months — Excel download (full history)
  var downloadAllMonthsCsv = document.getElementById('downloadAllMonthsCsv');
  if (downloadAllMonthsCsv) {
    downloadAllMonthsCsv.addEventListener('click', function () {
      if (csvDropdown) csvDropdown.style.display = 'none';
      // from very beginning to today
      var today = new Date().toISOString().slice(0, 10);
      window.location.href = '/api/report/excel?from_date=2000-01-01&to_date=' + today;
      notify('📊 Preparing full Excel report…');
    });
  }

  // 3. Custom Date Range — Excel download
  var downloadCustomRangeCsv = document.getElementById('downloadCustomRangeCsv');
  if (downloadCustomRangeCsv) {
    downloadCustomRangeCsv.addEventListener('click', function () {
      var from = csvRangeFrom ? csvRangeFrom.value : '';
      var to   = csvRangeTo   ? csvRangeTo.value   : '';
      if (!from || !to) { notify('Select both dates', true); return; }
      if (from > to)    { notify('Start date must be before end date', true); return; }
      // Trigger Excel download via direct browser navigation
      window.location.href = '/api/report/excel?from_date=' + from + '&to_date=' + to;
      notify('📊 Preparing Excel report…');
    });
  }

  // Shared CSV builder
  function buildAndDownloadCsv(txList, filename, periodLabel, summary) {
    var csv = 'StudentFlow – Transaction Report\n';
    csv += 'Period,' + periodLabel + '\n';
    csv += 'Generated,' + new Date().toLocaleDateString('en-IN') + '\n\n';
    csv += 'Date,Type,Category,Amount (Rs),Description\n';
    txList.forEach(function (t) {
      csv += [
        t.date,
        t.type,
        (t.category || '').replace(/,/g, ' '),
        Number(t.amount).toFixed(2),
        (t.description || '').replace(/,/g, ' ')
      ].join(',') + '\n';
    });

    // Totals
    var totIncome  = txList.filter(function(t){return t.type==='income' }).reduce(function(s,t){return s+Number(t.amount)},0);
    var totExpense = txList.filter(function(t){return t.type==='expense'}).reduce(function(s,t){return s+Number(t.amount)},0);
    var totSaved   = totIncome - totExpense;
    csv += '\nSummary\n';
    csv += 'Total Income,,' + totIncome.toFixed(2) + ',,\n';
    csv += 'Total Expense,,' + totExpense.toFixed(2) + ',,\n';
    csv += 'Net Savings,,' + totSaved.toFixed(2) + ',,\n';

    // Optional pre-built summary (from /api/range)
    if (summary && summary.tx_count !== undefined) {
      csv += 'Transactions,' + summary.tx_count + ',,,\n';
    }

    downloadFile(csv, filename);
  }

  function downloadFile(content, filename) {
    var blob = new Blob([content], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  }

  // Category chart CSV (unchanged)
  var downloadCsv = document.getElementById('downloadCsv');
  if (downloadCsv) {
    downloadCsv.addEventListener('click', async function () {
      var data = await api('/api/stats?type=' + currentCatType);
      if (!data) return;
      var csv = 'Category,Total\n';
      data.summary.forEach(function (r) { csv += r.category + ',' + r.total.toFixed(2) + '\n'; });
      downloadFile(csv, 'category-' + currentCatType + '.csv');
    });
  }

  // ── Date Range Report ─────────────────────────────────────────────────────
  var rangeFrom       = document.getElementById('rangeFrom');
  var rangeTo         = document.getElementById('rangeTo');
  var customRangeInputs = document.getElementById('customRangeInputs');
  var rangeApplyBtn   = document.getElementById('rangeApplyBtn');
  var rangeDateLabel  = document.getElementById('rangeDateLabel');
  var rangeDownloadCsv= document.getElementById('rangeDownloadCsv');
  var lastRangeData   = null; // store last result for CSV

  // Preset logic
  function getPresetDates(preset) {
    var today = new Date();
    var y = today.getFullYear(), m = today.getMonth(), d = today.getDate();
    var fmt = function(dt) { return dt.toISOString().slice(0, 10); };
    switch (preset) {
      case 'this_week': {
        var day = today.getDay(); // 0=Sun
        var mon = new Date(y, m, d - (day === 0 ? 6 : day - 1));
        return { from: fmt(mon), to: fmt(today) };
      }
      case 'this_month':
        return { from: fmt(new Date(y, m, 1)), to: fmt(today) };
      case 'last_month': {
        var lm = new Date(y, m - 1, 1);
        var lmEnd = new Date(y, m, 0);
        return { from: fmt(lm), to: fmt(lmEnd) };
      }
      case 'last_3months':
        return { from: fmt(new Date(y, m - 2, 1)), to: fmt(today) };
      case 'this_year':
        return { from: fmt(new Date(y, 0, 1)), to: fmt(today) };
      default:
        return null;
    }
  }

  function fmtDate(iso) {
    var d = new Date(iso + 'T00:00:00');
    return d.getDate() + ' ' + ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()] + ' ' + d.getFullYear();
  }

  function fmtDateShort(iso) {
    var d = new Date(iso + 'T00:00:00');
    return d.getDate() + ' ' + ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
  }

  async function loadRangeReport(fromDate, toDate) {
    if (!fromDate || !toDate) return;
    try {
      var data = await api('/api/range?from_date=' + fromDate + '&to_date=' + toDate);
      if (!data) return;
      lastRangeData = data;

      // Label
      if (rangeDateLabel) {
        rangeDateLabel.innerHTML =
          '<i class="fas fa-calendar-range me-1" style="color:var(--accent)"></i>' +
          '<strong style="color:var(--text)">' + fmtDate(fromDate) + '</strong>' +
          '<span style="margin:0 .4rem;color:var(--text-light)">→</span>' +
          '<strong style="color:var(--text)">' + fmtDate(toDate) + '</strong>' +
          '<span style="margin-left:.75rem;color:var(--text-light)">(' + data.summary.tx_count + ' transaction' + (data.summary.tx_count !== 1 ? 's' : '') + ')</span>';
      }

      // Summary cards
      setText('rangeIncome',  'Rs ' + data.summary.income.toFixed(2));
      setText('rangeExpense', 'Rs ' + data.summary.expense.toFixed(2));
      var bal = data.summary.balance;
      var balEl = document.getElementById('rangeBalance');
      if (balEl) {
        balEl.textContent = (bal < 0 ? '-' : '') + 'Rs ' + Math.abs(bal).toFixed(2);
        balEl.style.color = bal >= 0 ? 'var(--accent)' : '#f87171';
        balEl.closest('div').style.borderColor = bal >= 0 ? 'rgba(6,182,212,.25)' : 'rgba(239,68,68,.25)';
      }
      setText('rangeTxCount', '(' + data.summary.tx_count + ')');

      // Category breakdown (expense)
      var catBody = document.getElementById('rangeCatBody');
      if (catBody) {
        catBody.innerHTML = '';
        var cats = data.expense_categories;
        if (cats.length === 0) {
          catBody.innerHTML = '<tr><td colspan="2" style="text-align:center;color:var(--text-light);padding:.75rem">No expenses</td></tr>';
        } else {
          cats.forEach(function (r) {
            var tr = document.createElement('tr');
            tr.innerHTML = '<td>' + esc(r.category) + '</td><td class="text-end" style="color:#f87171">Rs ' + r.total.toFixed(2) + '</td>';
            catBody.appendChild(tr);
          });
        }
      }

      // Transactions list
      var rtxList = document.getElementById('rangeTxList');
      if (rtxList) {
        rtxList.innerHTML = '';
        if (data.transactions.length === 0) {
          rtxList.innerHTML = '<div class="tx-empty"><i class="fas fa-inbox" style="font-size:2rem;opacity:.3;display:block;margin-bottom:.5rem"></i>No transactions in this range</div>';
        } else {
          data.transactions.forEach(function (tx, i) {
            var el = createTxRow(tx);
            el.style.animationDelay = (i * 0.03) + 's';
            // Range list: delete should refresh range too
            el.querySelector('.tx-del').addEventListener('click', function (e) {
              e.stopPropagation();
              deleteTransactionAndRefreshRange(tx.id, fromDate, toDate);
            });
            rtxList.appendChild(el);
          });
        }
      }

    } catch (err) {
      notify(err.message || 'Failed to load range report', true);
    }
  }

  async function deleteTransactionAndRefreshRange(id, fromDate, toDate) {
    if (!confirm('Delete this transaction?')) return;
    try {
      await api('/api/transactions/' + encodeURIComponent(id), { method: 'DELETE' });
      notify('Transaction deleted');
      await refresh();
      await loadRangeReport(fromDate, toDate);
    } catch (err) {
      notify(err.message || 'Delete failed', true);
    }
  }

  // Preset buttons
  var activePreset = 'this_month';
  document.querySelectorAll('.range-preset-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.range-preset-btn').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      activePreset = btn.dataset.preset;

      if (activePreset === 'custom') {
        if (customRangeInputs) customRangeInputs.style.display = '';
        // pre-fill with today if empty
        if (rangeFrom && !rangeFrom.value) rangeFrom.value = new Date().toISOString().slice(0, 10);
        if (rangeTo   && !rangeTo.value)   rangeTo.value   = new Date().toISOString().slice(0, 10);
      } else {
        if (customRangeInputs) customRangeInputs.style.display = 'none';
        var dates = getPresetDates(activePreset);
        if (dates) loadRangeReport(dates.from, dates.to);
      }
    });
  });

  // Apply custom range
  if (rangeApplyBtn) {
    rangeApplyBtn.addEventListener('click', function () {
      var from = rangeFrom ? rangeFrom.value : '';
      var to   = rangeTo   ? rangeTo.value   : '';
      if (!from || !to) { notify('Please select both dates', true); return; }
      if (from > to)    { notify('Start date must be before end date', true); return; }
      loadRangeReport(from, to);
    });
  }

  // CSV for range report section (also now Excel)
  if (rangeDownloadCsv) {
    rangeDownloadCsv.addEventListener('click', function () {
      if (!lastRangeData) { notify('Run a report first', true); return; }
      window.location.href = '/api/report/excel?from_date=' + lastRangeData.from_date + '&to_date=' + lastRangeData.to_date;
      notify('📊 Preparing Excel report…');
    });
  }

  // Auto-load "This Month" on page ready
  var initDates = getPresetDates('this_month');
  if (initDates) loadRangeReport(initDates.from, initDates.to);

  // ── Refresh all ───────────────────────────────────────────────────────────
  async function refresh() {
    await Promise.all([
      loadSummary(),
      loadTransactions(),
      loadPieChart(),
      loadTimeChart(),
      loadMonthlyTable()
    ]);
  }

  // ── Initial load ──────────────────────────────────────────────────────────
  refresh().catch(function () { notify('Failed to load dashboard', true); });
});
