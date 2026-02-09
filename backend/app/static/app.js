const apiBase = "/api";

const symbolEl = document.getElementById("symbol");
const instrumentTypeEl = document.getElementById("instrumentType");
const expiryEl = document.getElementById("expiry");
const useSampleEl = document.getElementById("useSample");
const refreshEl = document.getElementById("refresh");
const statusEl = document.getElementById("status");
const rowsEl = document.getElementById("rows");
const summaryEl = document.getElementById("summary");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#ff9b8a" : "var(--accent-2)";
}

function formatNumber(value) {
  if (value === null || value === undefined) return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("en-IN");
}

async function loadExpiries() {
  const params = new URLSearchParams({
    symbol: symbolEl.value.trim().toUpperCase(),
    instrument_type: instrumentTypeEl.value,
    use_sample: useSampleEl.checked ? "true" : "false",
  });

  setStatus("Loading expiries...");
  try {
    const res = await fetch(`${apiBase}/option-chain/expiries?${params.toString()}`);
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const data = await res.json();
    expiryEl.innerHTML = "";

    if (!data.expiries || data.expiries.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No expiries";
      expiryEl.appendChild(option);
      setStatus("No expiries found.", true);
      return;
    }

    data.expiries.forEach((exp) => {
      const option = document.createElement("option");
      option.value = exp;
      option.textContent = exp;
      expiryEl.appendChild(option);
    });
    setStatus(`Loaded ${data.expiries.length} expiries.`);
  } catch (err) {
    setStatus(`Failed to load expiries: ${err.message}`, true);
  }
}

async function loadSummary() {
  const params = new URLSearchParams({
    symbol: symbolEl.value.trim().toUpperCase(),
    instrument_type: instrumentTypeEl.value,
    expiry: expiryEl.value,
    use_sample: useSampleEl.checked ? "true" : "false",
  });

  setStatus("Fetching option chain...");
  summaryEl.textContent = "";
  rowsEl.innerHTML = "";

  try {
    const res = await fetch(`${apiBase}/option-chain/summary?${params.toString()}`);
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const data = await res.json();

    const meta = data.meta || {};
    summaryEl.textContent = `Symbol ${meta.symbol || "-"} | Expiry ${meta.expiry || "-"} | Spot ${
      meta.spot ?? "-"
    } | ${meta.timestamp || ""}`;

    (data.rows || []).forEach((row, idx) => {
      const tr = document.createElement("tr");
      tr.style.animation = `fadeIn 350ms ease-out ${idx * 12}ms both`;
      tr.innerHTML = `
        <td>${formatNumber(row.strike)}</td>
        <td>${formatNumber(row.CE_OI)}</td>
        <td>${formatNumber(row.CE_DeltaOI)}</td>
        <td>${formatNumber(row.CE_Volume)}</td>
        <td>${formatNumber(row.PE_OI)}</td>
        <td>${formatNumber(row.PE_DeltaOI)}</td>
        <td>${formatNumber(row.PE_Volume)}</td>
        <td>${row.signal || "-"}</td>
      `;
      rowsEl.appendChild(tr);
    });

    setStatus(`Loaded ${data.rows ? data.rows.length : 0} rows.`);
  } catch (err) {
    setStatus(`Failed to load summary: ${err.message}`, true);
  }
}

refreshEl.addEventListener("click", loadSummary);
symbolEl.addEventListener("change", loadExpiries);
instrumentTypeEl.addEventListener("change", loadExpiries);
useSampleEl.addEventListener("change", loadExpiries);

loadExpiries().then(loadSummary);
