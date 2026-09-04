(function () {
  "use strict";

  function normalizeText(value) {
    return (value || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function parseNumber(value) {
    if (value == null) return null;
    const raw = String(value).trim();
    if (!raw) return null;

    const negative = /^\(.*\)$/.test(raw);
    const cleaned = raw
      .replace(/[,$%]/g, "")
      .replace(/[()]/g, "")
      .replace(/\s+/g, "");
    if (!cleaned) return null;

    const parsed = Number(cleaned);
    if (Number.isNaN(parsed)) return null;
    return negative ? -parsed : parsed;
  }

  function parseDate(value) {
    if (value == null) return null;
    const raw = String(value).trim();
    if (!raw) return null;
    const parsed = Date.parse(raw);
    if (Number.isNaN(parsed)) return null;
    return parsed;
  }

  function getCellSortValue(cell) {
    if (!cell) return "";
    if (cell.dataset && cell.dataset.sortValue) {
      return cell.dataset.sortValue;
    }

    const timestampEl = cell.querySelector("[data-timestamp]");
    if (timestampEl && timestampEl.dataset && timestampEl.dataset.timestamp) {
      return timestampEl.dataset.timestamp;
    }

    return normalizeText(cell.textContent || "");
  }

  function detectColumnType(rows, colIndex, explicitType) {
    if (explicitType) return explicitType;

    const sample = rows.slice(0, 25).map(function (row) {
      const cell = row.cells[colIndex];
      return getCellSortValue(cell);
    }).filter(Boolean);

    if (!sample.length) return "text";

    const numberMatches = sample.filter(function (v) {
      return parseNumber(v) !== null;
    }).length;
    if (numberMatches === sample.length) return "number";

    const dateMatches = sample.filter(function (v) {
      return parseDate(v) !== null;
    }).length;
    if (dateMatches === sample.length) return "date";

    return "text";
  }

  function compareValues(a, b, type) {
    if (type === "number") {
      const av = parseNumber(a);
      const bv = parseNumber(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return av - bv;
    }

    if (type === "date") {
      const av = parseDate(a);
      const bv = parseDate(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return av - bv;
    }

    return String(a).localeCompare(String(b), undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }

  function applyHeaderState(headers, activeIndex, direction) {
    headers.forEach(function (header, idx) {
      const indicator = header.querySelector(".sort-indicator");
      if (!indicator) return;
      if (idx !== activeIndex) {
        indicator.textContent = "↕";
        return;
      }
      indicator.textContent = direction === "asc" ? "↑" : "↓";
    });
  }

  function makeTableSortable(table) {
    const thead = table.tHead;
    const tbody = table.tBodies && table.tBodies[0];
    if (!thead || !tbody) return;

    const headerRow = thead.rows[0];
    if (!headerRow) return;

    const headers = Array.from(headerRow.cells);
    if (!headers.length) return;

    headers.forEach(function (header, colIndex) {
      if (header.dataset && header.dataset.sort === "none") {
        return;
      }

      const label = normalizeText(header.textContent || "");
      if (!label) return;

      header.style.cursor = "pointer";
      header.title = "Click to sort";
      header.tabIndex = 0;
      header.setAttribute("aria-label", "Sort by " + label);
      header.setAttribute("aria-sort", "none");

      if (!header.querySelector(".sort-indicator")) {
        const indicator = document.createElement("span");
        indicator.className = "sort-indicator ms-1 text-muted";
        indicator.textContent = "↕";
        header.appendChild(indicator);
      }

      header.addEventListener("click", function () {
        const currentCol = Number(table.dataset.sortCol || "-1");
        const currentDir = table.dataset.sortDir || "asc";
        const nextDir = (currentCol === colIndex && currentDir === "asc") ? "desc" : "asc";

        const rows = Array.from(tbody.rows).map(function (row, idx) {
          const cell = row.cells[colIndex];
          return {
            row: row,
            originalIndex: idx,
            value: getCellSortValue(cell),
          };
        });

        const explicitType = header.dataset ? header.dataset.sortType : "";
        const colType = detectColumnType(rows.map(function (r) { return r.row; }), colIndex, explicitType);

        rows.sort(function (a, b) {
          const cmp = compareValues(a.value, b.value, colType);
          if (cmp === 0) return a.originalIndex - b.originalIndex;
          return nextDir === "asc" ? cmp : -cmp;
        });

        const frag = document.createDocumentFragment();
        rows.forEach(function (item) {
          frag.appendChild(item.row);
        });
        tbody.appendChild(frag);

        table.dataset.sortCol = String(colIndex);
        table.dataset.sortDir = nextDir;
        applyHeaderState(headers, colIndex, nextDir);
        headers.forEach(function (candidate, idx) {
          candidate.setAttribute("aria-sort", idx === colIndex ? nextDir : "none");
        });
      });

      header.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        header.click();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table.js-sortable").forEach(makeTableSortable);
  });
})();
