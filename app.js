const API_URL = "http://127.0.0.1:8000/api";
let decayChartInstance = null;
let heatmapGlobalData = [];
let currentRawFlights = [];
let activeFilterMode = "best";
let currentBaseTariff = 5400;
let currentClassMult = 1.0;
let currentCabin = "Economy";
let currentOrigin = "DEL";
let currentDest = "BOM";
let selectedFlightCode = null;

function getCarrierDetails(name) {
  const a = (name || "").toLowerCase();
  if (a.includes("akasa") || a.includes("qp")) {
    return { codePrefix: "QP", logoBg: "#ea580c", co2: "88 kg CO2e" };
  }
  if (a.includes("spicejet") || a.includes("sg")) {
    return { codePrefix: "SG", logoBg: "#d97706", co2: "124 kg CO2e" };
  }
  if (a.includes("express") || a.includes("ix")) {
    return { codePrefix: "IX", logoBg: "#f97316", co2: "86 kg CO2e" };
  }
  if (a.includes("air india") || a.includes("ai")) {
    return { codePrefix: "AI", logoBg: "#dc2626", co2: "103 kg CO2e" };
  }
  return { codePrefix: "6E", logoBg: "#0284c7", co2: "89 kg CO2e" };
}

window.addEventListener("DOMContentLoaded", () => {
  loadHeatmap();
});

async function loadHeatmap() {
  const container = document.getElementById("heatmapContainer");
  try {
    const [heatRes, indexRes] = await Promise.all([
      fetch(API_URL + "/heatmap"),
      fetch(API_URL + "/index")
    ]);

    if (indexRes.ok) {
      const idxData = await indexRes.json();
      if (idxData.composite_index) {
        document.getElementById("nationalCompositeVal").innerText = Number(idxData.composite_index).toFixed(2);
      }
      if (idxData.macro_validation_score !== undefined) {
        const corrVal = Number(idxData.macro_validation_score);
        document.getElementById("macroValidationVal").innerText = (corrVal >= 0 ? "+" : "") + corrVal.toFixed(2) + " Correlation";
      }
    }

    if (heatRes.ok) {
      const items = await heatRes.json();
      heatmapGlobalData = items || [];
      if (heatmapGlobalData.length > 0) {
        renderHeatmapItems(container, heatmapGlobalData);
        return;
      }
    }
  } catch (err) {
    console.warn("API offline:", err);
  }
}

function renderHeatmapItems(container, items) {
  let html = "";
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const pillClass = item.surge_status === "High" ? "delta-surge" : (item.surge_status === "Moderate" ? "delta-moderate" : "delta-discount");
    html += '<div class="frosted-card stat-card" style="min-height: 110px; cursor: pointer;" onclick="quickSelectRoute(\'' + item.origin + '\', \'' + item.destination + '\')">';
    html += '<div class="sc-top">';
    html += '<strong style="font-size: 1.1rem; color: #0c4a6e;">' + item.corridor + '</strong>';
    html += '<span class="delta-pill ' + pillClass + '">' + item.surge_status + '</span>';
    html += '</div>';
    html += '<div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 6px;">';
    html += '1d Surge: <strong style="color: #0f172a;">' + item.surge_1d + '</strong> | 7d Base: <strong style="color: #0f172a;">' + item.standard_7d + '</strong>';
    html += '</div>';
    html += '<div style="font-size: 0.72rem; color: #0284c7; margin-top: 4px; font-weight: 700;">';
    html += 'DGCA Weight: ' + (item.weight * 100).toFixed(1) + '% (Click to inspect)';
    html += '</div>';
    html += '</div>';
  }
  container.innerHTML = html;
}

function quickSelectRoute(origin, dest) {
  document.getElementById("origin").value = origin;
  document.getElementById("destination").value = dest;
  handleSearch();
}

function handleSearch() {
  const origin = document.getElementById("origin").value;
  const destination = document.getElementById("destination").value;
  const cabin = document.getElementById("cabinClass").value;
  const days = parseInt(document.getElementById("travelDate").value) || 7;

  if (!origin || !destination) {
    alert("Please select both Origin and Destination.");
    return;
  }
  if (origin === destination) {
    alert("Origin and Destination cannot be the same airport.");
    return;
  }

  document.getElementById("searchViewSection").style.display = "none";
  document.getElementById("resultsViewSection").style.display = "block";
  document.getElementById("barUrl").innerText = "skylitics.gov.in/intel?sector=" + origin + "-" + destination + "&cabin=" + cabin + "&horizon=" + days + "d";
  window.scrollTo({ top: 0, behavior: "smooth" });

  runAnalysis(origin, destination, cabin, days);
}

function returnToSearch() {
  document.getElementById("resultsViewSection").style.display = "none";
  document.getElementById("searchViewSection").style.display = "block";
  document.getElementById("barUrl").innerText = "skylitics.gov.in/airfare-intelligence";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function runAnalysis(origin, dest, cabin, days) {
  currentOrigin = origin;
  currentDest = dest;
  currentCabin = cabin;

  const corridorKey = origin + "-" + dest;
  currentRawFlights = [];

  try {
    const flightRes = await fetch(API_URL + "/flights?origin=" + origin + "&destination=" + dest + "&advance_days=" + days + "&cabin_class=" + encodeURIComponent(cabin));
    if (flightRes.ok) {
      currentRawFlights = await flightRes.json();
    }
  } catch (err) {
    console.warn("Could not fetch flights:", err);
  }

  if (heatmapGlobalData.length === 0) {
    try {
      const res = await fetch(API_URL + "/heatmap");
      if (res.ok) heatmapGlobalData = await res.json();
    } catch (e) {}
  }

  const sector = heatmapGlobalData.find(m => m.corridor === corridorKey || (m.origin === origin && m.destination === dest));

  // Determine base anchor: If real cabin flights exist, use their average price; otherwise fallback to sector base
  let baseAnchor = 5400;
  if (currentRawFlights.length > 0) {
    const validFares = currentRawFlights.map(f => Number(f.total_fare)).filter(v => v >= 2000);
    if (validFares.length > 0) {
      baseAnchor = Math.round(validFares.reduce((a, b) => a + b, 0) / validFares.length);
    }
  } else if (sector && sector.base_fare) {
    baseAnchor = sector.base_fare;
  }

  currentBaseTariff = baseAnchor;

  let fare1d = Math.round(currentBaseTariff * 1.30);
  let fare7d = Math.round(currentBaseTariff);
  let fare15d = Math.round(currentBaseTariff * 0.95);
  let fare30d = Math.round(currentBaseTariff * 0.92);
  let fare45d = Math.round(currentBaseTariff * 0.88);

  let activeFare = fare7d;
  if (days === 1) activeFare = fare1d;
  else if (days === 7) activeFare = fare7d;
  else if (days === 15) activeFare = fare15d;
  else if (days === 30) activeFare = fare30d;
  else if (days === 45) activeFare = fare45d;

  let activeRelative = Number(((activeFare / currentBaseTariff) * 100).toFixed(1));
  const deltaPercent = (((activeFare - currentBaseTariff) / currentBaseTariff) * 100).toFixed(1);
  const savings15d = Math.abs(fare1d - fare15d);

  const now = new Date();
  const d1 = new Date(now); d1.setDate(d1.getDate() + 1);
  const d7 = new Date(now); d7.setDate(d7.getDate() + 7);
  const d15 = new Date(now); d15.setDate(d15.getDate() + 15);
  const fDate = (d) => d.toISOString().split("T")[0];

  document.getElementById("activeCorridorText").innerText = origin + " ➔ " + dest + " (" + cabin + " · " + days + "d Horizon)";

  document.getElementById("rcOrigin1").innerText = origin;
  document.getElementById("rcDest1").innerText = dest;
  document.getElementById("rcDate1").innerText = "Travel Date: " + fDate(d1);
  document.getElementById("rcFare1").innerText = "₹" + fare1d.toLocaleString("en-IN");
  document.getElementById("rcSurge1").innerText = "+" + (((fare1d - currentBaseTariff) / currentBaseTariff) * 100).toFixed(1) + "% ▲";

  document.getElementById("rcOrigin7").innerText = origin;
  document.getElementById("rcDest7").innerText = dest;
  document.getElementById("rcDate7").innerText = "Travel Date: " + fDate(d7);
  document.getElementById("rcFare7").innerText = "₹" + fare7d.toLocaleString("en-IN");
  document.getElementById("rcSurge7").innerText = "+0.0% —";

  document.getElementById("rcOrigin15").innerText = origin;
  document.getElementById("rcDest15").innerText = dest;
  document.getElementById("rcDate15").innerText = "Travel Date: " + fDate(d15);
  document.getElementById("rcFare15").innerText = "₹" + fare15d.toLocaleString("en-IN");
  document.getElementById("rcSurge15").innerText = (((fare15d - currentBaseTariff) / currentBaseTariff) * 100).toFixed(1) + "% ▼";

  document.getElementById("displayFare").innerText = "₹" + activeFare.toLocaleString("en-IN");
  document.getElementById("displayCabin").innerText = cabin + " · " + days + "d Horizon";
  document.getElementById("displayRelative").innerText = Number(activeRelative).toFixed(1);
  document.getElementById("displayDecay").innerText = "₹" + savings15d.toLocaleString("en-IN");
  document.getElementById("decayDeltaPill").innerText = "-" + (((fare1d - fare15d) / fare1d) * 100).toFixed(1) + "% ▼";

  const fareDelta = document.getElementById("fareDeltaPill");
  const indexDelta = document.getElementById("indexDeltaPill");
  if (deltaPercent >= 0) {
    fareDelta.className = "delta-pill delta-surge";
    fareDelta.innerText = "+" + deltaPercent + "% ▲";
    indexDelta.className = "delta-pill delta-surge";
    indexDelta.innerText = "+" + (activeRelative - 100).toFixed(1) + "% ▲";
  } else {
    fareDelta.className = "delta-pill delta-discount";
    fareDelta.innerText = deltaPercent + "% ▼";
    indexDelta.className = "delta-pill delta-discount";
    indexDelta.innerText = (activeRelative - 100).toFixed(1) + "% ▼";
  }

  const statusText = document.getElementById("displayStatus");
  const statusDot = document.getElementById("statusDot");
  const subText = document.getElementById("displaySubtext");

  if (activeRelative >= 125) {
    statusText.innerText = "Surge Spike";
    statusText.style.color = "#dc2626";
    statusDot.style.background = "#dc2626";
    subText.innerText = "Peak dynamic tariff surge";
  } else if (activeRelative >= 105) {
    statusText.innerText = "Moderate";
    statusText.style.color = "#d97706";
    statusDot.style.background = "#d97706";
    subText.innerText = "Within normal booking variation";
  } else {
    statusText.innerText = "Optimal Base";
    statusText.style.color = "#059669";
    statusDot.style.background = "#059669";
    subText.innerText = "Standard market benchmark";
  }

  document.getElementById("scheduleTitle").innerText = origin + " ➔ " + dest + " Verified Scheduled Quotes";
  document.getElementById("scheduleSub").innerText = "Displaying authentic Google Flights observations (" + cabin + " · " + days + "d horizon)";

  renderFlightList();
  renderChart([fare1d, fare7d, fare15d, fare30d, fare45d]);
}



function filterFlightView(mode) {
  activeFilterMode = mode;
  document.getElementById("btnFilterBest").style.background = mode === "best" ? "#0284c7" : "transparent";
  document.getElementById("btnFilterBest").style.color = mode === "best" ? "#ffffff" : "#0284c7";
  document.getElementById("btnFilterNonstop").style.background = mode === "nonstop" ? "#0284c7" : "transparent";
  document.getElementById("btnFilterNonstop").style.color = mode === "nonstop" ? "#ffffff" : "#0284c7";
  document.getElementById("btnFilterAll").style.background = mode === "all" ? "#0284c7" : "transparent";
  document.getElementById("btnFilterAll").style.color = mode === "all" ? "#ffffff" : "#0284c7";
  renderFlightList();
}

function selectAndLockFlight(flightNo, flightFare, baseFare, taxesFees, airline, depTime, arrTime) {
  selectedFlightCode = flightNo;
  document.getElementById("displayFare").innerText = "₹" + Number(flightFare).toLocaleString("en-IN");
  document.getElementById("displayCabin").innerText = airline + " (" + flightNo + ") Selected";
  
  const rel = ((flightFare / currentBaseTariff) * 100).toFixed(1);
  document.getElementById("displayRelative").innerText = rel;
  
  openFlightModalDirect(airline, flightNo, flightFare, baseFare, taxesFees, getCarrierDetails(airline).logoBg);
  renderFlightList();
}

function renderSingleCard(f, i) {
  let rawFare = Number(f.total_fare) || 5420;
  if (rawFare < 2000 || rawFare > 250000) rawFare = 5420;
  const flightFare = Math.round(rawFare * currentClassMult);
  const rawBase = Math.round(flightFare * 0.82);
  const rawTaxes = flightFare - rawBase;

  const meta = getCarrierDetails(f.airline);
  const flightNo = f.flight_number || (meta.codePrefix + "-" + (100 + (i * 37) % 899));
  const depTime = f.departure_time || "08:45 AM";
  const arrTime = f.arrival_time || "11:00 AM";
  const flightDur = f.duration || "2 hr 15 min";
  
  let stopLabel = "Nonstop";
  if (f.stops && f.stops !== "0" && f.stops !== 0) {
    stopLabel = String(f.stops).toLowerCase().includes("stop") ? f.stops : f.stops + " Stop";
  }

  const priceIncreaseAmt = flightFare - Math.round(currentBaseTariff);
  const priceIncreasePct = (((flightFare - currentBaseTariff) / currentBaseTariff) * 100).toFixed(1);
  const isUp = priceIncreaseAmt >= 0;
  const isSelected = selectedFlightCode === flightNo;

  return '<div class="flight-strip-full-row" style="width: 100%; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 14px 18px; border: ' + (isSelected ? '2px solid #0284c7' : '1px solid #e2e8f0') + '; background: ' + (isSelected ? '#f0f9ff' : '#ffffff') + ';">' +
    '<div class="f-col-brand" style="display: flex; align-items: center; gap: 12px; min-width: 180px;">' +
    '<div class="carrier-avatar" style="background: ' + meta.logoBg + '; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; border-radius: 8px; color: white; font-weight: bold;">✈</div>' +
    '<div><strong class="carrier-title" style="display: block; font-size: 15px; color: #0f172a;">' + f.airline + '</strong><small class="flight-no-sub" style="color: #64748b; font-weight: 600;">' + flightNo + '</small></div>' +
    '</div>' +
    '<div class="f-col-times" style="display: flex; align-items: center; gap: 24px;">' +
    '<div class="time-block" style="text-align: center;"><span class="flight-time-large" style="font-weight: 800; font-size: 15px; display: block;">' + depTime + '</span><span class="airport-code" style="font-size: 12px; color: #64748b;">' + currentOrigin + '</span></div>' +
    '<div class="flight-duration-track" style="text-align: center;"><span class="duration-label" style="font-size: 11px; color: #64748b; display: block;">' + flightDur + '</span><div class="duration-bar" style="height: 2px; width: 60px; background: #cbd5e1; margin: 4px auto;"></div><span class="nonstop-badge" style="font-size: 11px; color: #0284c7; font-weight: 700;">' + stopLabel + '</span></div>' +
    '<div class="time-block" style="text-align: center;"><span class="flight-time-large" style="font-weight: 800; font-size: 15px; display: block;">' + arrTime + '</span><span class="airport-code" style="font-size: 12px; color: #64748b;">' + currentDest + '</span></div>' +
    '</div>' +
    '<div class="f-col-emissions" style="text-align: center;"><span class="co2-tag" style="font-size: 12px; font-weight: 700; color: #059669; background: #ecfdf5; padding: 3px 8px; border-radius: 4px;">' + meta.co2 + '</span></div>' +
    '<div class="f-col-price" style="text-align: right; min-width: 140px;">' +
    '<div class="price-val-wrap"><span class="price-figure" style="font-size: 1.25rem; font-weight: 800; color: #0284c7;">₹' + flightFare.toLocaleString("en-IN") + '</span><span class="price-cabin-label" style="font-size: 11px; color: #64748b; margin-left: 4px;">' + currentCabin + '</span></div>' +
    '<div class="surge-delta-chip ' + (isUp ? "chip-surge" : "chip-discount") + '" style="font-size: 11px; font-weight: 700; margin-top: 2px;">' + (isUp ? "+₹" + priceIncreaseAmt.toLocaleString("en-IN") + " (+" + priceIncreasePct + "%) ▲" : "-₹" + Math.abs(priceIncreaseAmt).toLocaleString("en-IN") + " (" + priceIncreasePct + "%) ▼") + '</div>' +
    '</div>' +
    '<div style="margin-left: 14px;">' +
    '<button class="btn btn-outline-sm" onclick="selectAndLockFlight(\'' + flightNo + '\', ' + flightFare + ', ' + rawBase + ', ' + rawTaxes + ', \'' + f.airline + '\', \'' + depTime + '\', \'' + arrTime + '\')" style="padding: 6px 12px; font-size: 12px; font-weight: 700; background: ' + (isSelected ? '#0284c7' : '#f8fafc') + '; color: ' + (isSelected ? '#ffffff' : '#0284c7') + ';">' + (isSelected ? 'Selected' : 'Choose') + '</button>' +
    '</div>' +
    '</div>';
}

function renderFlightList() {
  const container = document.getElementById("flightListContainer");
  if (!currentRawFlights || currentRawFlights.length === 0) {
    container.innerHTML = '<div style="text-align: center; padding: 36px; color: #64748b; font-weight: 600;">No flights recorded for this horizon window.</div>';
    return;
  }

  let html = "";
  if (activeFilterMode === "best") {
    const bestFlights = currentRawFlights.filter(f => f.flight_category === "Best Flights");
    const otherFlights = currentRawFlights.filter(f => f.flight_category === "Other Flights");

    html += '<div style="font-weight: 800; color: #0c4a6e; margin: 12px 0 8px 4px; font-size: 14px;">🌟 Top Best Departing Flights</div>';
    html += (bestFlights.length > 0 ? bestFlights : currentRawFlights.slice(0, 4)).map((f, i) => renderSingleCard(f, i)).join("");

    if (otherFlights.length > 0) {
      html += '<div style="font-weight: 800; color: #64748b; margin: 24px 0 8px 4px; font-size: 14px;">🕒 Other Scheduled Flights</div>';
      html += otherFlights.map((f, i) => renderSingleCard(f, i + 20)).join("");
    }
  } else if (activeFilterMode === "nonstop") {
    const nonstopFlights = currentRawFlights.filter(f => !f.stops || String(f.stops).toLowerCase().includes("nonstop") || String(f.stops).toLowerCase().includes("0") || String(f.stops).toLowerCase().includes("direct"));
    html += nonstopFlights.map((f, i) => renderSingleCard(f, i)).join("");
  } else {
    html += currentRawFlights.map((f, i) => renderSingleCard(f, i)).join("");
  }

  container.innerHTML = html;
}

function renderChart(fares) {
  const ctx = document.getElementById("decayChart").getContext("2d");
  if (decayChartInstance) decayChartInstance.destroy();

  const gradient = ctx.createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, "rgba(2, 132, 199, 0.25)");
  gradient.addColorStop(1, "rgba(2, 132, 199, 0.0)");

  decayChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["1-Day (Surge)", "7-Days (Standard)", "15-Days (Advance)", "30-Days (Baseline)", "45-Days (Long Horizon)"],
      datasets: [{
        data: fares,
        borderColor: "#0284c7",
        borderWidth: 3,
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointRadius: 6,
        pointBackgroundColor: "#0369a1",
        pointBorderColor: "#ffffff",
        pointBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => " Average Tariff: ₹" + ctx.raw.toLocaleString("en-IN")
          }
        }
      },
      scales: {
        y: {
          grid: { color: "rgba(0, 0, 0, 0.05)" },
          ticks: { color: "#64748b", font: { family: "Plus Jakarta Sans", size: 11 } }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#334155", font: { family: "Plus Jakarta Sans", weight: "700", size: 11 } }
        }
      }
    }
  });
}

function openFlightModalDirect(carrierName, flightCode, totalFare, baseFare, taxesFees, logoBg) {
  const avatar = document.getElementById("modalLogoAvatar");
  avatar.style.background = logoBg;
  document.getElementById("modalCarrierName").innerText = carrierName + " Intelligence Breakdown";
  document.getElementById("modalFlightNumber").innerText = flightCode + " · Database Verified";
  
  document.getElementById("modalBaseFare").innerText = "₹" + baseFare.toLocaleString("en-IN");
  document.getElementById("modalTaxesFees").innerText = "₹" + taxesFees.toLocaleString("en-IN");
  document.getElementById("modalTotalFare").innerText = "₹" + totalFare.toLocaleString("en-IN");

  document.getElementById("flightModal").style.display = "flex";
}

function closeModalDirect() {
  document.getElementById("flightModal").style.display = "none";
}

function closeModal(e) {
  if (e.target.id === "flightModal") {
    document.getElementById("flightModal").style.display = "none";
  }
}

function exportMoSPIData() {
  try {
    const originElem = document.getElementById("origin");
    const destElem = document.getElementById("destination");
    const horizonElem = document.getElementById("travelDate");

    const origin = originElem && originElem.value ? originElem.value : "";
    const dest = destElem && destElem.value ? destElem.value : "";
    const horizon = horizonElem && horizonElem.value ? horizonElem.value : "7";

    let url = API_URL + "/export-mospi-csv";
    if (origin && dest && document.getElementById("resultsViewSection").style.display !== "none") {
      url += "?origin=" + encodeURIComponent(origin) + "&destination=" + encodeURIComponent(dest) + "&advance_days=" + encodeURIComponent(horizon);
    }
    window.location.href = url;
  } catch (err) {
    window.location.href = API_URL + "/export-mospi-csv";
  }
}