/**
 * Tri au clic sur l'en-tête + redimensionnement des colonnes par glisser, pour toute
 * <table data-table-enhance>. Un <th> devient triable via data-sort="text|number" ;
 * ajouter data-value="..." sur la <td> correspondante quand le contenu affiché
 * (input, badges…) ne reflète pas la valeur réelle à trier. data-no-resize sur un
 * <th> désactive son redimensionnement (utile pour la dernière colonne d'actions).
 *
 * Le tableau reste en layout naturel (auto) tant qu'aucune colonne n'a été
 * redimensionnée — pas de largeurs figées prématurément, donc pas de chevauchement.
 * Au premier glisser, on fige les largeurs courantes (déjà correctement calculées
 * par le navigateur) dans un <colgroup>, puis on bascule en table-layout: fixed.
 */
(function () {
  function isEmptyStateRow(row) {
    var firstCell = row.cells[0];
    return firstCell && firstCell.hasAttribute('colspan');
  }

  function cellValue(cell, type) {
    var raw = cell.dataset.value !== undefined ? cell.dataset.value : cell.textContent.trim();
    if (type === 'number') {
      var n = parseFloat(String(raw).replace(/\s/g, '').replace(',', '.'));
      return isNaN(n) ? 0 : n;
    }
    return raw.toLowerCase();
  }

  function sortRows(table, colIndex, type, dir) {
    var tbody = table.tBodies[0];
    var rows = Array.prototype.slice.call(tbody.rows);
    var dataRows = rows.filter(function (r) { return !isEmptyStateRow(r); });
    var otherRows = rows.filter(isEmptyStateRow);

    dataRows.sort(function (a, b) {
      var va = cellValue(a.cells[colIndex], type);
      var vb = cellValue(b.cells[colIndex], type);
      if (va < vb) return dir === 'asc' ? -1 : 1;
      if (va > vb) return dir === 'asc' ? 1 : -1;
      return 0;
    });

    dataRows.forEach(function (r) { tbody.appendChild(r); });
    otherRows.forEach(function (r) { tbody.appendChild(r); });
  }

  function initSortable(table) {
    var headerRow = table.tHead && table.tHead.rows[0];
    if (!headerRow) return;
    var ths = Array.prototype.slice.call(headerRow.cells);

    ths.forEach(function (th, idx) {
      var type = th.dataset.sort;
      if (!type) return;

      th.classList.add('cursor-pointer', 'select-none');
      var indicator = document.createElement('span');
      indicator.className = 'ml-1 text-ardoise-300 inline-block';
      indicator.textContent = '⇅';
      indicator.setAttribute('data-sort-indicator', '');
      th.appendChild(indicator);

      th.addEventListener('click', function (e) {
        if (e.target.closest('.col-resizer')) return;
        var dir = th.dataset.sortDir === 'asc' ? 'desc' : 'asc';

        ths.forEach(function (t) {
          delete t.dataset.sortDir;
          var ind = t.querySelector('[data-sort-indicator]');
          if (ind) ind.textContent = '⇅';
        });

        th.dataset.sortDir = dir;
        indicator.textContent = dir === 'asc' ? '↑' : '↓';
        sortRows(table, idx, type, dir);
      });
    });
  }

  function ensureColgroup(table, colCount) {
    var existing = table.querySelector(':scope > colgroup[data-enhance-colgroup]');
    if (existing) return existing;
    var colgroup = document.createElement('colgroup');
    colgroup.setAttribute('data-enhance-colgroup', '');
    for (var i = 0; i < colCount; i++) {
      colgroup.appendChild(document.createElement('col'));
    }
    table.insertBefore(colgroup, table.firstChild);
    return colgroup;
  }

  // Fige les largeurs actuelles (correctement calculées en layout auto) puis
  // bascule en table-layout: fixed — appelé uniquement au premier redimensionnement.
  function freezeColumnWidths(table) {
    if (table.dataset.widthsFrozen) return;
    var headerRow = table.tHead.rows[0];
    var ths = Array.prototype.slice.call(headerRow.cells);
    var colgroup = ensureColgroup(table, ths.length);
    var cols = colgroup.children;

    ths.forEach(function (th, idx) {
      cols[idx].style.width = th.offsetWidth + 'px';
    });

    // Empêche tout débordement visuel d'une colonne sur sa voisine une fois figée.
    table.querySelectorAll('th, td').forEach(function (cell) {
      cell.style.overflow = 'hidden';
    });

    table.style.tableLayout = 'fixed';
    table.dataset.widthsFrozen = '1';
  }

  function initResizable(table) {
    var headerRow = table.tHead && table.tHead.rows[0];
    if (!headerRow) return;

    Array.prototype.slice.call(headerRow.cells).forEach(function (th, idx) {
      if ('noResize' in th.dataset) return;

      th.style.position = 'relative';
      var handle = document.createElement('span');
      handle.className = 'col-resizer';
      handle.style.cssText =
        'position:absolute;right:-3px;top:0;bottom:0;width:6px;cursor:col-resize;z-index:1;';
      th.appendChild(handle);

      handle.addEventListener('mousedown', function (e) {
        e.preventDefault();
        e.stopPropagation();

        freezeColumnWidths(table);
        var colgroup = table.querySelector(':scope > colgroup[data-enhance-colgroup]');
        var col = colgroup.children[idx];
        var startX = e.pageX;
        var startWidth = col.offsetWidth;

        function onMouseMove(e2) {
          col.style.width = Math.max(40, startWidth + (e2.pageX - startX)) + 'px';
        }
        function onMouseUp() {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        }
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    });
  }

  function initAll() {
    document.querySelectorAll('table[data-table-enhance]').forEach(function (table) {
      if (table.dataset.tableEnhanced) return;
      table.dataset.tableEnhanced = '1';
      initSortable(table);
      initResizable(table);
    });
  }

  document.addEventListener('DOMContentLoaded', initAll);
  document.addEventListener('htmx:afterSwap', initAll);
})();
