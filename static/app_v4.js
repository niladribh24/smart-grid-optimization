/**
 * PowerGrid — Revamped Interactive Frontend Application
 * ======================================================
 * Renders the grid as interactive SVG, handles live simulation,
 * clicks/double-clicks for routing and failures, console logs,
 * ML metrics, pathfinding comparisons, and guided tour onboarding.
 */

// ─── State Variables ───
let pipelineData = null;
let currentRoute = null;
let selectedSource = "G1";
let selectedTarget = "C6";
let clickMode = 'source';
let userMode = 'beginner'; // 'beginner' | 'expert'
let legendFilter = null;
let showNodeLabels = true;
let graphZoom = 1;
let graphPan = { x: 0, y: 0 };
let rerouteTotal = 0;
let timelineEvents = [];
let predictionHistory = [];

// Simulation State
let isSimulating = false;
let simInterval = null;
let simSpeed = 2500;
let currentScenario = 'normal';
let simulationTick = 0;
let logHistory = [];

// Onboarding Stepper
let currentTourStep = 1;
const totalTourSteps = 5;

// SVG Sizing
const SVG_PADDING = 32;
const SVG_WIDTH = 500;
const SVG_HEIGHT = 420;

// Node display — premium light theme palette
const NODE_STYLES = {
    generator: { fill: '#34d399', stroke: '#059669', shape: 'circle', size: 16 },
    substation: { fill: '#60a5fa', stroke: '#2563eb', shape: 'diamond', size: 13 },
    consumer: { fill: '#fb923c', stroke: '#ea580c', shape: 'circle', size: 12 },
};

const WEATHER_MAP = {
    normal: { icon: '☀️', name: 'Sunny — Normal Day' },
    peak: { icon: '🌆', name: 'Peak Evening Load' },
    heatwave: { icon: '🌡️', name: 'Heatwave — High AC Demand' },
    storm: { icon: '⛈️', name: 'Storm — Heavy Wind & Rain' },
    windy: { icon: '💨', name: 'Windy — High Renewable Output' },
    rain: { icon: '🌧️', name: 'Rain — Moderate Load' },
    live: { icon: '🌍', name: 'Live Weather API' },
};

// Map grid coordinates (0-10) to SVG view coordinates
function gridToSvg(x, y) {
    const svgX = SVG_PADDING + (x / 10) * (SVG_WIDTH - 2 * SVG_PADDING);
    const svgY = SVG_PADDING + ((10 - y) / 10) * (SVG_HEIGHT - 2 * SVG_PADDING);
    return { x: svgX, y: svgY };
}

// Congestion color scales
function getCongestionColor(score) {
    if (score >= 0.85) return '#ef4444';
    if (score >= 0.70) return '#f97316';
    if (score >= 0.50) return '#facc15';
    return '#4ade80';
}

function plainCongestion(score) {
    const pct = Math.round(score * 100);
    if (score >= 0.85) return `Heavy traffic on this line (${pct}%)`;
    if (score >= 0.70) return `Getting busy (${pct}% capacity used)`;
    if (score >= 0.50) return `Moderate load (${pct}%)`;
    return `Clear — running smoothly (${pct}%)`;
}

function plainStatus(score, failed) {
    if (failed) return '⚫ Failed — line offline';
    if (score >= 0.85) return '🔴 Congested — at risk';
    if (score >= 0.70) return '🟡 Warning — elevated load';
    return '🟢 Healthy';
}

function getCongestionLevel(score) {
    if (score >= 0.85) return 'critical';
    if (score >= 0.70) return 'high';
    if (score >= 0.50) return 'medium';
    return 'low';
}

// ─── Initialization ───
document.addEventListener('DOMContentLoaded', () => {
    initCanvasBackground();
    simulateLoading();
    fetchPipelineData();
    setupEventListeners();
    setupKeyboardShortcuts();
    setupGraphPanZoom();
    checkFirstTimeUser();
    setUserMode(localStorage.getItem('grid_user_mode') || 'beginner');
});

function setupEventListeners() {
    // Route selectors handled via updateRouteEndpoint() in HTML onchange
}

function checkFirstTimeUser() {
    if (!localStorage.getItem('powergrid_tour_seen')) {
        localStorage.setItem('powergrid_tour_seen', 'true');
        setTimeout(() => showToast('Need help? Open the guided tour from the top bar.', 'info'), 1200);
    }
}

// Fetch initial data on page load
async function fetchPipelineData() {
    try {
        const res = await fetch('/api/pipeline');
        pipelineData = await res.json();
        
        // Cache initial endpoint settings
        selectedSource = pipelineData.source || "G1";
        selectedTarget = pipelineData.target || "C6";
        currentRoute = pipelineData.ml_route;
        
        // Initialize HTML views
        populateSelectors();
        renderAll();
        hideLoading();
        addLogEntry('Control center online. Grid topology and AI model loaded.', 'success');
        addTimelineEvent('System initialized — grid online');
        showToast('Control center ready', 'success');
        updateRouteFlowDisplay();
    } catch (err) {
        console.error('Failed to load initial pipeline data:', err);
        document.querySelector('.loader-text').textContent = 'Initialization Failed';
        document.querySelector('.loader-subtext').textContent = `Check backend terminal. Error: ${err.message}`;
        addLogEntry(`Initial pipeline loading failed: ${err.message}`, 'error');
    }
}

function simulateLoading() {
    const steps = [
        { text: 'Initializing Grid...', pct: 25 },
        { text: 'Loading AI Model...', pct: 55 },
        { text: 'Training Predictions...', pct: 80 },
        { text: 'Control Center Ready', pct: 100 },
    ];
    let i = 0;
    const interval = setInterval(() => {
        if (i >= steps.length) { clearInterval(interval); return; }
        const el = document.getElementById('loader-step');
        const bar = document.getElementById('loader-bar-fill');
        if (el) el.textContent = steps[i].text;
        if (bar) bar.style.width = steps[i].pct + '%';
        i++;
    }, 600);
}

function hideLoading() {
    const loader = document.getElementById('loading-screen');
    const shell = document.getElementById('app-shell');
    if (loader) loader.classList.add('hidden');
    if (shell) shell.style.opacity = '1';
}

// Global render trigger
function renderAll() {
    renderGrid();
    renderPlainLanguageSummary();
    renderDashboardStats(pipelineData.dashboard);
    renderMLMetrics();
    renderFeatureImportance();
    renderRouteComparison();
    renderHealingSection();
    renderCongestionTable();
    updateRouteFlowDisplay();
    updateGauges();
    renderAnalytics();
    renderMinimap();
    updateWeatherDisplay();
}

function describeCongestion(score) {
    const pct = Math.round(score * 100);
    if (score >= 0.85) return `This line is overloaded (${pct}%)`;
    if (score >= 0.70) return `This line is getting risky (${pct}%)`;
    if (score >= 0.50) return `This line is moderately busy (${pct}%)`;
    return `This line is operating normally (${pct}%)`;
}

function describeStatus(score, failed) {
    if (failed) return 'Offline';
    if (score >= 0.85) return 'Critical';
    if (score >= 0.70) return 'Warning';
    return 'Healthy';
}

function renderPlainLanguageSummary() {
    const route = currentRoute || pipelineData?.ml_route;
    const edges = pipelineData?.grid?.edges || [];
    const busy = edges.filter(edge => !edge.is_failed && edge.congestion_score >= 0.70).length;
    const failed = edges.filter(edge => edge.is_failed).length;
    const topRisk = [...edges]
        .filter(edge => !edge.is_failed)
        .sort((a, b) => b.congestion_score - a.congestion_score)[0];

    const plainSummary = document.getElementById('plain-summary');
    const plainCardSummary = document.getElementById('plain-card-summary');
    const plainNextStep = document.getElementById('plain-next-step');
    const plainTopRisk = document.getElementById('plain-top-risk');
    const graphTitle = document.getElementById('graph-title');
    const graphSubtitle = document.getElementById('graph-subtitle');
    const graphSource = document.getElementById('graph-source');
    const graphTarget = document.getElementById('graph-target');
    const graphHealth = document.getElementById('graph-health');

    let headline = `Power is currently routed from ${selectedSource} to ${selectedTarget}.`;
    let detail = `There are ${busy} busy lines and ${failed} offline lines right now.`;
    let nextStep = 'No action needed. The current route is stable.';
    let health = failed > 0 ? 'Needs attention' : (busy > 0 ? 'Watch closely' : 'Stable');

    if (!route || !route.path || route.path.length === 0) {
        headline = `${selectedTarget} is currently isolated from ${selectedSource}.`;
        detail = 'The app could not find a safe path through the grid.';
        nextStep = 'Repair a line or pick a different destination.';
        health = 'Route unavailable';
    } else if (failed > 0) {
        nextStep = 'A line is offline. Check whether the rerouted path still looks acceptable.';
    } else if (busy > 0) {
        nextStep = 'Watch the busiest line or run one simulation step to see if the path changes.';
    }

    if (plainSummary) plainSummary.textContent = `${headline} ${detail}`;
    if (plainCardSummary) {
        plainCardSummary.textContent = route && route.path
            ? `Current path: ${route.path.join(' -> ')}`
            : 'No current path is available.';
    }
    if (plainNextStep) plainNextStep.textContent = nextStep;
    if (plainTopRisk) {
        plainTopRisk.textContent = topRisk
            ? `${topRisk.source} -> ${topRisk.target} at ${Math.round(topRisk.congestion_score * 100)}%`
            : 'No high-risk line detected';
    }
    if (graphTitle) {
        graphTitle.textContent = route && route.path
            ? `${selectedSource} -> ${selectedTarget} uses ${route.num_hops} steps`
            : `No safe route from ${selectedSource} to ${selectedTarget}`;
    }
    if (graphSubtitle) {
        graphSubtitle.textContent = topRisk
            ? `Highest pressure is on ${topRisk.source} -> ${topRisk.target}. Hover any line to see why it matters.`
            : 'Hover a line or node to see what it does in the grid.';
    }
    if (graphSource) graphSource.textContent = selectedSource;
    if (graphTarget) graphTarget.textContent = selectedTarget;
    if (graphHealth) graphHealth.textContent = health;
}

// ─── SVG Map Rendering ───
function renderGrid() {
    const edgesLayer = document.getElementById('edges-layer');
    const routeLayer = document.getElementById('route-layer');
    const nodesLayer = document.getElementById('nodes-layer');
    const labelsLayer = document.getElementById('labels-layer');

    // Clear previous drawing
    edgesLayer.innerHTML = '';
    routeLayer.innerHTML = '';
    nodesLayer.innerHTML = '';
    labelsLayer.innerHTML = '';

    const nodes = pipelineData.grid.nodes;
    const edges = pipelineData.grid.edges;

    // Node positioning lookup table
    const nodePosMap = {};
    nodes.forEach(n => {
        const pos = gridToSvg(n.x, n.y);
        nodePosMap[n.id] = { ...n, svgX: pos.x, svgY: pos.y };
    });

    // Draw grid transmission lines
    edges.forEach((edge) => {
        const src = nodePosMap[edge.source];
        const tgt = nodePosMap[edge.target];
        if (!src || !tgt) return;

        const isLineFailed = edge.is_failed;
        const color = isLineFailed ? '#0f172a' : getCongestionColor(edge.congestion_score);
        const width = isLineFailed ? 2.5 : 2.2 + edge.congestion_score * 2.2;

        const routePath = (currentRoute || pipelineData.ml_route)?.path || [];
        const onRoute = routePath.some((n, i) => i < routePath.length - 1 &&
            ((routePath[i] === edge.source && routePath[i+1] === edge.target) ||
             (routePath[i] === edge.target && routePath[i+1] === edge.source)));

        let edgeClass = isLineFailed ? 'grid-edge failed-edge' : 'grid-edge';
        if (legendFilter === 'failed' && !isLineFailed) edgeClass += ' dimmed';
        else if (legendFilter === 'congested' && edge.congestion_score < 0.7 && !isLineFailed) edgeClass += ' dimmed';
        else if (legendFilter === 'healthy' && (edge.congestion_score >= 0.5 || isLineFailed)) edgeClass += ' dimmed';
        else if (legendFilter === 'route' && !onRoute) edgeClass += ' dimmed';
        else if (legendFilter === 'congested' && edge.congestion_score >= 0.7) edgeClass += ' highlighted';
        else if (legendFilter === 'failed' && isLineFailed) edgeClass += ' highlighted';

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', src.svgX);
        line.setAttribute('y1', src.svgY);
        line.setAttribute('x2', tgt.svgX);
        line.setAttribute('y2', tgt.svgY);
        line.setAttribute('stroke', color);
        line.setAttribute('stroke-width', width);
        line.setAttribute('stroke-linecap', 'round');
        line.setAttribute('opacity', isLineFailed ? '0.55' : (onRoute ? '0.95' : '0.72'));
        line.setAttribute('stroke-dasharray', isLineFailed ? '8 6' : '0');
        line.setAttribute('class', edgeClass);
        line.dataset.source = edge.source;
        line.dataset.target = edge.target;
        if (isLineFailed) {
            line.setAttribute('filter', 'url(#glow-red)');
        } else if (onRoute) {
            line.setAttribute('filter', 'url(#glow-blue)');
        }

        line.addEventListener('mouseenter', (e) => showEdgeTooltip(e, edge));
        line.addEventListener('mouseleave', hideEdgeTooltip);
        line.addEventListener('dblclick', () => toggleEdgeFailure(edge.source, edge.target));
        edgesLayer.appendChild(line);

        if (isLineFailed) {
            const mx = (src.svgX + tgt.svgX) / 2;
            const my = (src.svgY + tgt.svgY) / 2;
            const cross = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            cross.setAttribute('x', mx);
            cross.setAttribute('y', my + 5);
            cross.setAttribute('text-anchor', 'middle');
            cross.setAttribute('fill', '#EF4444');
            cross.setAttribute('font-size', '14');
            cross.setAttribute('font-weight', 'bold');
            cross.textContent = '✕';
            edgesLayer.appendChild(cross);
        }
    });

    // Draw active computed energy route overlay (running particles animation)
    const activeRoute = currentRoute || pipelineData.ml_route;
    if (activeRoute && activeRoute.path && activeRoute.path.length > 1) {
        const path = activeRoute.path;
        for (let i = 0; i < path.length - 1; i++) {
            const src = nodePosMap[path[i]];
            const tgt = nodePosMap[path[i + 1]];
            if (!src || !tgt) continue;

            const routeLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            routeLine.setAttribute('x1', src.svgX);
            routeLine.setAttribute('y1', src.svgY);
            routeLine.setAttribute('x2', tgt.svgX);
            routeLine.setAttribute('y2', tgt.svgY);
            routeLine.setAttribute('stroke', '#38bdf8');
            routeLine.setAttribute('stroke-width', '7');
            routeLine.setAttribute('stroke-dasharray', '10 8');
            routeLine.setAttribute('stroke-linecap', 'round');
            routeLine.setAttribute('class', 'route-edge-anim');
            routeLine.setAttribute('filter', 'url(#glow-blue)');
            routeLayer.appendChild(routeLine);

            // Moving glowing energy packets along active route path
            const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            pulse.setAttribute('r', '4.5');
            pulse.setAttribute('fill', '#e0f2fe');
            pulse.setAttribute('filter', 'url(#glow-blue)');
            
            const anim = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion');
            anim.setAttribute('dur', '1.9s');
            anim.setAttribute('repeatCount', 'indefinite');
            anim.setAttribute('path', `M ${src.svgX} ${src.svgY} L ${tgt.svgX} ${tgt.svgY}`);
            pulse.appendChild(anim);
            routeLayer.appendChild(pulse);
        }
    }

    // Draw grid station nodes
    nodes.forEach(n => {
        const pos = nodePosMap[n.id];
        const style = NODE_STYLES[n.type] || NODE_STYLES.consumer;

        let nodeClass = 'grid-node';
        if (legendFilter === 'generator' && n.type !== 'generator') nodeClass += ' dimmed';
        else if (legendFilter === 'substation' && n.type !== 'substation') nodeClass += ' dimmed';
        else if (legendFilter === 'consumer' && n.type !== 'consumer') nodeClass += ' dimmed';
        else if (legendFilter && ['generator','substation','consumer'].includes(legendFilter)) nodeClass += ' highlighted';

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', nodeClass);
        g.setAttribute('data-id', n.id);

        let shape;
        if (style.shape === 'diamond') {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', pos.svgX - style.size);
            shape.setAttribute('y', pos.svgY - style.size);
            shape.setAttribute('width', style.size * 2);
            shape.setAttribute('height', style.size * 2);
            shape.setAttribute('rx', '2');
            shape.setAttribute('transform', `rotate(45 ${pos.svgX} ${pos.svgY})`);
        } else {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            shape.setAttribute('cx', pos.svgX);
            shape.setAttribute('cy', pos.svgY);
            shape.setAttribute('r', style.size);
        }

        const isSourceSelected = n.id === selectedSource;
        const isTargetSelected = n.id === selectedTarget;

        shape.setAttribute('fill', style.fill);
        if (isSourceSelected) {
            shape.setAttribute('stroke', '#ffffff');
            shape.setAttribute('stroke-width', '4');
            shape.setAttribute('filter', 'url(#glow-green)');
        } else if (isTargetSelected) {
            shape.setAttribute('stroke', '#f8fafc');
            shape.setAttribute('stroke-width', '4');
            shape.setAttribute('filter', 'url(#glow-blue)');
        } else {
            shape.setAttribute('stroke', style.stroke);
            shape.setAttribute('stroke-width', '2');
        }

        g.appendChild(shape);
        g.addEventListener('click', () => handleNodeClick(n.id));
        g.addEventListener('mouseenter', (e) => showNodeTooltip(e, n));
        g.addEventListener('mouseleave', hideNodeTooltip);
        nodesLayer.appendChild(g);

        if (showNodeLabels) {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', pos.svgX);
            text.setAttribute('y', pos.svgY + style.size + 14);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', isSourceSelected ? '#dcfce7' : (isTargetSelected ? '#dbeafe' : '#cbd5e1'));
            text.setAttribute('font-size', '10');
            text.setAttribute('font-weight', (isSourceSelected || isTargetSelected) ? '700' : '600');
            text.setAttribute('font-family', 'JetBrains Mono, monospace');
            text.textContent = n.id;
            labelsLayer.appendChild(text);
        }
    });

    applyGraphTransform();
}

// Edge properties overlay tooltip
function showEdgeTooltip(e, edge) {
    const tooltip = document.getElementById('edge-tooltip');
    const wrapper = document.querySelector('.graph-panel');
    if (!tooltip || !wrapper) return;
    const rect = wrapper.getBoundingClientRect();

    tooltip.classList.add('visible');
    document.getElementById('tt-label').textContent = `${edge.source} ↔ ${edge.target}`;
    document.getElementById('tt-cong').textContent = userMode === 'beginner'
        ? describeCongestion(edge.congestion_score)
        : edge.congestion_score.toFixed(4);
    document.getElementById('tt-res').textContent = edge.resistance.toFixed(4) + ' Ω';
    document.getElementById('tt-len').textContent = edge.length_km.toFixed(1) + ' km';
    document.getElementById('tt-age').textContent = edge.age.toFixed(0) + ' yrs';
    document.getElementById('tt-status').textContent = describeStatus(edge.congestion_score, edge.is_failed);

    tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
    tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
}

function showNodeTooltip(e, node) {
    const tooltip = document.getElementById('node-tooltip');
    const wrapper = document.querySelector('.graph-panel');
    if (!tooltip || !wrapper) return;
    const rect = wrapper.getBoundingClientRect();

    const typeLabels = { generator: '⚡ Power Plant', substation: '🔵 Substation', consumer: '🟠 Consumer' };
    tooltip.classList.add('visible');
    document.getElementById('nt-label').textContent = node.label || node.id;
    document.getElementById('nt-type').textContent = typeLabels[node.type] || node.type;
    document.getElementById('nt-voltage').textContent = '220 kV';
    document.getElementById('nt-status').textContent = node.id === selectedSource ? '🔵 Active Source' :
        node.id === selectedTarget ? '🔵 Active Destination' : '🟢 Healthy';

    tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
    tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
}

function hideNodeTooltip() {
    const t = document.getElementById('node-tooltip');
    if (t) t.classList.remove('visible');
}

function hideEdgeTooltip() {
    document.getElementById('edge-tooltip').classList.remove('visible');
}

// ─── Click Node Handlers ───
function handleNodeClick(nodeId) {
    if (clickMode === 'source') {
        selectedSource = nodeId;
        document.getElementById('source-select').value = nodeId;
        addLogEntry(`Clicked to set source terminal: ${nodeId}`, 'info');
        clickMode = 'target';
        renderGrid();
    } else {
        selectedTarget = nodeId;
        document.getElementById('target-select').value = nodeId;
        addLogEntry(`Clicked to set destination terminal: ${nodeId}`, 'info');
        clickMode = 'source';
        renderGrid();
        computeRoute(); // Instantly find path
    }
}

// ─── Selectors Setup ───
function populateSelectors() {
    const nodes = pipelineData.grid.nodes;
    const sourceSelect = document.getElementById('source-select');
    const targetSelect = document.getElementById('target-select');

    sourceSelect.innerHTML = '';
    targetSelect.innerHTML = '';

    nodes.forEach(n => {
        const typeLabel = n.type === 'generator' ? '⚡' : n.type === 'substation' ? '🔄' : '🏠';
        const opt1 = new Option(`${typeLabel} ${n.id} — ${n.label}`, n.id);
        const opt2 = new Option(`${typeLabel} ${n.id} — ${n.label}`, n.id);
        sourceSelect.add(opt1);
        targetSelect.add(opt2);
    });

    sourceSelect.value = selectedSource;
    targetSelect.value = selectedTarget;
}

function updateFailEdgeSelector(edges) {
    const failSelect = document.getElementById('fail-edge-select');
    const panelFailSelect = document.getElementById('fail-edge-select-panel');
    if (!failSelect && !panelFailSelect) return;
    if (failSelect) failSelect.innerHTML = '';
    if (panelFailSelect) panelFailSelect.innerHTML = '';
    
    edges.forEach(e => {
        const statusLabel = e.is_failed ? 'OFFLINE' : `cong: ${e.congestion_score.toFixed(2)}`;
        const label = `${e.source} ↔ ${e.target} (${statusLabel})`;
        const value = `${e.source}-${e.target}`;
        if (failSelect) failSelect.add(new Option(label, value));
        if (panelFailSelect) panelFailSelect.add(new Option(label, value));
    });
}

// ─── API Integrations ───

// Compute custom route endpoint
async function computeRoute() {
    const source = document.getElementById('source-select').value;
    const target = document.getElementById('target-select').value;
    const btn = document.getElementById('btn-reroute');

    btn.textContent = 'Routing...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/reroute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source, target })
        });
        const data = await res.json();

        // Update local route variables
        currentRoute = data.ml_route;
        pipelineData.ml_route = data.ml_route;
        pipelineData.naive_route = data.naive_route;

        renderGrid();
        renderDashboardStats(data.dashboard);
        renderRouteComparison();

        addLogEntry(`Custom routing complete from ${source} to ${target}. Hops: ${data.ml_route ? data.ml_route.num_hops : 0}`, 'success');
    } catch (err) {
        console.error('Route calculation error:', err);
        addLogEntry(`Routing failed: ${err.message}`, 'error');
    } finally {
        btn.textContent = 'Find Route';
        btn.disabled = false;
    }
}

// Toggle failure / repair
async function toggleEdgeFailure(u, v) {
    const edge = pipelineData.grid.edges.find(e => (e.source === u && e.target === v) || (e.source === v && e.target === u));
    if (!edge) return;

    const currentAction = edge.is_failed ? 'restore' : 'fail';
    const source = selectedSource;
    const target = selectedTarget;

    addLogEntry(`Processing line state update: ${u} ↔ ${v} → ${currentAction.toUpperCase()}`, 'system');

    try {
        const res = await fetch('/api/toggle_edge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edge_u: u, edge_v: v, action: currentAction, source, target })
        });
        const data = await res.json();

        // Cache response state
        pipelineData.grid.edges = data.grid.edges;
        pipelineData.edges_by_congestion = data.edges_by_congestion;
        currentRoute = data.route;

        renderAll();

        if (currentAction === 'fail') {
            addLogEntry(`🚨 Transmission fault simulated: ${u} ↔ ${v} isolated. Connected components: ${data.connectivity.num_components}`, 'warn');
            if (data.connectivity.isolated_consumers && data.connectivity.isolated_consumers.length > 0) {
                addLogEntry(`🔴 ALERT: Consumers isolated: ${data.connectivity.isolated_consumers.join(', ')}`, 'error');
            }
            if (data.route) {
                const msg = data.path_changed
                    ? `🛡️ Rerouted: ${data.route.path.join(' → ')}`
                    : `🛡️ Route updated (cost: ${data.route.total_cost.toFixed(3)})`;
                addLogEntry(msg, 'success');
                addTimelineEvent(`A* New route: ${data.route.path.join(' → ')}`);
                if (data.explanation) addLogEntry(data.explanation, 'info');
            } else {
                addLogEntry(`🚨 Emergency: Target node ${target} is isolated from generators!`, 'error');
            }
        } else {
            addLogEntry(`✅ Transmission line ${u} ↔ ${v} repaired and synchronized online.`, 'success');
            if (data.route) {
                addLogEntry(`🔄 Dynamic route updated: ${data.route.path.join(' → ')}`, 'info');
            }
        }
    } catch (err) {
        console.error('Toggle edge failure error:', err);
        addLogEntry(`Failed to update line state: ${err.message}`, 'error');
    }
}

// Trigger failure via dropdown
function simulateFailure() {
    const val = document.getElementById('fail-edge-select').value;
    if (!val) return;
    const [u, v] = val.split('-');
    toggleEdgeFailure(u, v);
}

// Restore selected failure line
async function restoreSelectedEdge() {
    const val = document.getElementById('fail-edge-select').value;
    if (!val) return;
    const [u, v] = val.split('-');
    
    const edge = pipelineData.grid.edges.find(e => (e.source === u && e.target === v) || (e.source === v && e.target === u));
    if (edge && !edge.is_failed) {
        addLogEntry(`Line ${u} ↔ ${v} is already healthy.`, 'warn');
        return;
    }
    
    toggleEdgeFailure(u, v);
}

// ─── Simulation Engine ───
function togglePlaySimulation() {
    const playBtn = document.getElementById('btn-play');
    if (isSimulating) {
        isSimulating = false;
        clearInterval(simInterval);
        playBtn.textContent = '▶ Start';
        playBtn.className = 'btn btn-primary';
        addLogEntry('Simulation paused.', 'system');
    } else {
        isSimulating = true;
        playBtn.textContent = '⏸ Pause';
        playBtn.className = 'btn btn-danger';
        addLogEntry(`Simulation started in ${currentScenario} mode. Tick frequency: ${simSpeed}ms`, 'success');
        
        // Execute tick immediately then loop
        runSimulationTick();
        simInterval = setInterval(runSimulationTick, simSpeed);
    }
}

async function runSimulationTick() {
    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: selectedSource,
                target: selectedTarget,
                scenario: currentScenario
            })
        });
        const data = await res.json();

        // Sync local grid state with simulated state
        pipelineData.grid.edges = data.grid.edges;
        pipelineData.edges_by_congestion = data.edges_by_congestion;
        currentRoute = data.route;
        simulationTick = data.tick;

        const hour = data.tick % 24;
        const timeStr = `${hour.toString().padStart(2, '0')}:00`;
        document.getElementById('sim-time-display').textContent = timeStr;

        renderAll();

        addLogEntry(`[Tick: ${data.tick} | Hour: ${timeStr}] Scenario: ${currentScenario.toUpperCase()}. Load randomized. Mean congestion: ${data.dashboard.average_congestion.toFixed(3)}`, 'info');

        // Log faults
        if (data.failed_this_tick && data.failed_this_tick.length > 0) {
            data.failed_this_tick.forEach(f => {
                addLogEntry(`🚨 Line tripped: ${f.source} ↔ ${f.target} (${(f.congestion_score * 100).toFixed(0)}%)`, 'error');
                addTimelineEvent(`Edge removed: ${f.source}↔${f.target}`);
            });
        }

        if (data.destination_isolated) {
            addLogEntry(`🔴 BLACKOUT: ${selectedTarget} is isolated!`, 'error');
            addTimelineEvent(`Consumer ${selectedTarget} isolated`);
            showToast('Emergency: destination isolated', 'error');
        } else if (data.failed_this_tick?.length > 0 && data.path_changed) {
            addLogEntry(`🛡️ Self-healing: ${data.route.path.join(' → ')}`, 'success');
            addTimelineEvent(`Power restored via ${data.route.path.join('→')}`);
            showToast('Route optimized around failure', 'success');
        } else if (data.failed_this_tick?.length > 0) {
            addLogEntry(`🛡️ Active path: ${data.route?.path?.join(' → ') || '—'}`, 'success');
        }
    } catch (err) {
        console.error('Simulation tick calculation error:', err);
        addLogEntry(`Simulation tick calculation error: ${err.message}`, 'error');
    }
}

function stepSimulation() {
    if (isSimulating) {
        togglePlaySimulation();
    }
    runSimulationTick();
}

function resetSimulation() {
    if (isSimulating) {
        togglePlaySimulation();
    }
    addLogEntry('Resetting grid system to baseline state...', 'system');
    fetchPipelineData();
}

function adjustSpeed(val) {
    simSpeed = parseInt(val);
    const mult = (5000 / simSpeed).toFixed(1);
    const speedDisplay = document.getElementById('speed-display');
    const speedDisplayPanel = document.getElementById('speed-display-panel');
    if (speedDisplay) speedDisplay.textContent = mult + 'x';
    if (speedDisplayPanel) speedDisplayPanel.textContent = mult + 'x';
    const topSpeed = document.getElementById('topbar-speed');
    const topSpeedMirror = document.getElementById('topbar-speed-mirror');
    if (topSpeed) topSpeed.textContent = mult + 'x';
    if (topSpeedMirror) topSpeedMirror.textContent = mult + 'x';

    if (isSimulating) {
        clearInterval(simInterval);
        simInterval = setInterval(runSimulationTick, simSpeed);
    }
}

function injectScenario(type) {
    currentScenario = type === 'peak' ? 'normal' : type;
    if (type === 'windy') currentScenario = 'storm';
    if (type === 'live') currentScenario = 'live';

    document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.scenario-btn[data-scenario="${type}"]`);
    if (btn) btn.classList.add('active');

    updateWeatherDisplay(type);
    addLogEntry(`Scenario: ${WEATHER_MAP[type]?.name || type}`, 'system');
    addTimelineEvent(`Scenario changed: ${WEATHER_MAP[type]?.name || type}`);
    showToast(`Scenario: ${WEATHER_MAP[type]?.name || type}`, 'info');

    if (!isSimulating) runSimulationTick();
}

// ─── Dashboard Stats & KPIs ───
function renderDashboardStats(dashboard) {
    if (!dashboard) return;

    animateCounter('val-cost', dashboard.total_route_cost, 3);
    animateCounter('val-failed-count', dashboard.failed_lines, 0);

    const edges = pipelineData?.grid?.edges || [];
    const congested = edges.filter(e => !e.is_failed && e.congestion_score >= 0.7).length;
    animateCounter('stat-congested', congested, 0);
    animateCounter('stat-reroutes', dashboard.reroutes || rerouteTotal, 0);

    const avgCong = dashboard.average_congestion || 0;
    const avgCongEl = document.getElementById('stat-avg-cong');
    if (avgCongEl) {
        avgCongEl.textContent = userMode === 'beginner'
            ? plainCongestion(avgCong)
            : (avgCong * 100).toFixed(1) + '%';
        flashStat(avgCongEl.closest('.live-stat'));
    }

    const avgLossEl = document.getElementById('stat-avg-loss');
    if (avgLossEl) avgLossEl.textContent = (avgCong * 3.2).toFixed(1) + '%';

    if (pipelineData.ml_route && pipelineData.naive_route && pipelineData.naive_route.avg_congestion > 0) {
        const improvement = ((pipelineData.naive_route.avg_congestion - pipelineData.ml_route.avg_congestion)
                            / pipelineData.naive_route.avg_congestion * 100);
        const impEl = document.getElementById('val-improvement');
        if (impEl) impEl.textContent = improvement.toFixed(1) + '%';
    }

    const route = currentRoute || pipelineData.ml_route;
    const hopsEl = document.getElementById('val-hops');
    if (hopsEl && route) hopsEl.textContent = route.num_hops;

    updateFailEdgeSelector(pipelineData.edges_by_congestion);
}

// ─── ML Model Analytics tab ───
function renderMLMetrics() {
    const m = pipelineData.ml_metrics;
    if (!m) return;

    document.getElementById('ml-r2').textContent = m.r2.toFixed(4);
    document.getElementById('ml-rmse').textContent = m.rmse.toFixed(4);
    document.getElementById('ml-mae').textContent = m.mae.toFixed(4);
    document.getElementById('ml-samples').textContent = m.train_samples.toLocaleString();

    const acc = (m.r2 * 100).toFixed(1) + '%';
    ['topbar-accuracy', 'card-accuracy'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = acc;
    });
    const updated = document.getElementById('card-updated');
    if (updated) updated.textContent = 'just now';
}

function renderFeatureImportance() {
    const fi = pipelineData.feature_importances;
    const container = document.getElementById('fi-bars');
    if (!container || !fi) return;

    container.innerHTML = '';
    const entries = Object.entries(fi);
    const maxVal = Math.max(...entries.map(([, value]) => value), 1e-6);

    entries.forEach(([name, value], i) => {
        const pct = (value / maxVal) * 100;
        const tierClass = i === 0 ? 'top' : (i < 3 ? 'mid' : 'low');

        const row = document.createElement('div');
        row.className = 'fi-bar-row';
        row.innerHTML = `
            <span class="fi-bar-label font-mono">${name}</span>
            <div class="fi-bar-track">
                <div class="fi-bar-fill ${tierClass}" style="width: 0%;">
                    <span class="fi-bar-value">${value.toFixed(3)}</span>
                </div>
            </div>
        `;
        container.appendChild(row);

        // Animate width expansion
        setTimeout(() => {
            const bar = row.querySelector('.fi-bar-fill');
            if (bar) bar.style.width = pct + '%';
        }, 150 + i * 50);
    });
}

// ─── Pathfinding Comparison tab ───
function renderRouteComparison() {
    const ml = currentRoute || pipelineData.ml_route;
    const naive = pipelineData.naive_route;

    updateRouteCard('astar', ml);
    updateRouteCard('dijkstra', naive);

    const impBanner = document.getElementById('cb-improvement');
    if (ml && naive && naive.avg_congestion > 0) {
        const imp = ((naive.avg_congestion - ml.avg_congestion) / naive.avg_congestion * 100);
        impBanner.textContent = imp.toFixed(1) + '%';
        document.getElementById('val-improvement').textContent = imp.toFixed(1) + '%';
    } else {
        impBanner.textContent = '0.0%';
    }
}

function updateRouteCard(type, route) {
    const pathEl = document.getElementById(`${type}-path`);
    const costEl = document.getElementById(`${type}-cost`);
    const congEl = document.getElementById(`${type}-cong`);
    const hopsEl = document.getElementById(`${type}-hops`);

    if (!pathEl) return;

    if (!route || !route.path || route.path.length === 0) {
        pathEl.innerHTML = '<span class="text-red font-mono">ISOLATED / NO PATH AVAILABLE</span>';
        costEl.textContent = '∞';
        congEl.textContent = '1.0000';
        hopsEl.textContent = '0';
        return;
    }

    pathEl.innerHTML = route.path.map((node, i) => {
        let html = `<span class="route-node">${node}</span>`;
        if (i < route.path.length - 1) html += `<span class="route-arrow">→</span>`;
        return html;
    }).join('');

    costEl.textContent = route.total_cost.toFixed(3);
    congEl.textContent = route.avg_congestion.toFixed(4);
    hopsEl.textContent = route.num_hops;
}

// ─── Self-Healing Cycle Demo ───
function renderHealingSection() {
    const h = pipelineData.healing;
    if (!h) return;

    document.getElementById('heal-step2-text').textContent =
        `Simulated fault on line ${h.failed_edge[0]} ↔ ${h.failed_edge[1]} (congestion: ${h.congestion_at_failure.toFixed(3)})`;
    document.getElementById('heal-step3-text').textContent =
        `DFS verified connectivity: components = ${h.num_components} (${h.is_connected ? 'Connected' : 'DISCONNECTED'})`;
    document.getElementById('heal-step4-text').textContent =
        h.reroute_success
            ? (h.path_changed
                ? `A* rerouted backup path: ${h.original_path.join(' → ')} → ${h.new_path.join(' → ')} (cost: ${h.new_cost.toFixed(3)})`
                : `Route recalculated: ${h.new_path.join(' → ')} (cost: ${h.new_cost.toFixed(3)})`)
            : 'No viable recovery path found — destination isolated!';

    // Default fields values
    document.getElementById('hr-edge').textContent = `${h.failed_edge[0]} ↔ ${h.failed_edge[1]}`;
    document.getElementById('hr-cong').textContent = h.congestion_at_failure.toFixed(3);
    if (h.explanation) {
        const detailEl = document.getElementById('hr-detail');
        if (detailEl) detailEl.textContent = h.explanation;
    }
}

let healingTimer = null;
function playHealingDemo() {
    resetHealingDemo();
    const steps = document.querySelectorAll('.healing-step');
    const h = pipelineData.healing;
    if (!h) return;

    let currentStep = 0;

    function nextStep() {
        if (currentStep > 0) {
            steps[currentStep - 1].classList.remove('active');
            steps[currentStep - 1].classList.add('completed');
        }

        if (currentStep >= steps.length) {
            // Final summary report
            const statusEl = document.getElementById('hr-status');
            if (h.reroute_success) {
                statusEl.textContent = 'HEALED & RESTORED';
                statusEl.className = 'hr-status success';
            } else {
                statusEl.textContent = 'UNRECOVERED BLACKOUT';
                statusEl.className = 'hr-status fail';
            }

            document.getElementById('hr-connected').textContent = h.is_connected ? 'Connected ✅' : 'Isolated ❌';
            document.getElementById('hr-newpath').textContent = h.new_path.join(' → ');
            document.getElementById('hr-newcost').textContent = h.new_cost.toFixed(3);

            // Re-render SVG to show mock route
            const routeLayer = document.getElementById('route-layer');
            routeLayer.innerHTML = '';
            
            // Re-render failed lines
            const nodes = pipelineData.grid.nodes;
            const nodePosMap = {};
            nodes.forEach(n => {
                const pos = gridToSvg(n.x, n.y);
                nodePosMap[n.id] = { svgX: pos.x, svgY: pos.y };
            });

            // Draw failure cross
            drawFailedLineMidpoint(h.failed_edge[0], h.failed_edge[1], routeLayer, nodePosMap);
            
            // Draw route
            if (h.new_path.length > 1) {
                for (let i = 0; i < h.new_path.length - 1; i++) {
                    const src = nodePosMap[h.new_path[i]];
                    const tgt = nodePosMap[h.new_path[i+1]];
                    const routeLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    routeLine.setAttribute('x1', src.svgX);
                    routeLine.setAttribute('y1', src.svgY);
                    routeLine.setAttribute('x2', tgt.svgX);
                    routeLine.setAttribute('y2', tgt.svgY);
                    routeLine.setAttribute('stroke', '#059669');
                    routeLine.setAttribute('stroke-width', '4.5');
                    routeLine.setAttribute('class', 'route-edge');
                    routeLine.setAttribute('filter', 'url(#glow-green)');
                    routeLayer.appendChild(routeLine);
                }
            }

            document.getElementById('hr-detail').textContent = h.explanation || (
                h.path_changed
                    ? 'Self-healing demo complete. Overloaded line isolated and power rerouted.'
                    : 'Self-healing demo complete. Grid verified connectivity after fault.'
            );
            addLogEntry(
                h.path_changed
                    ? `Healing demo: ${h.failed_edge[0]}↔${h.failed_edge[1]} failed → new route ${h.new_path.join(' → ')}`
                    : `Healing demo completed: isolated ${h.failed_edge[0]}↔${h.failed_edge[1]}.`,
                h.reroute_success ? 'success' : 'error'
            );
            return;
        }

        steps[currentStep].classList.add('active');

        // Update panel descriptions
        const statusEl = document.getElementById('hr-status');
        const detailEl = document.getElementById('hr-detail');
        
        switch (currentStep) {
            case 0:
                statusEl.textContent = 'SCANNING FOR FAULTS...';
                statusEl.className = 'hr-status';
                detailEl.textContent = 'Processing Random Forest predictions for transmission anomalies...';
                break;
            case 1:
                statusEl.textContent = 'LINE FAULT ISOLATION';
                statusEl.className = 'hr-status fail';
                detailEl.textContent = `Congestion limit hit! Tripping breakers on ${h.failed_edge[0]} ↔ ${h.failed_edge[1]}...`;
                break;
            case 2:
                statusEl.textContent = 'DFS PATH VERIFICATION';
                statusEl.className = 'hr-status';
                detailEl.textContent = 'Executing Depth First Search to map topological islands...';
                break;
            case 3:
                statusEl.textContent = 'CALCULATING BACKUP PATH';
                statusEl.className = 'hr-status success';
                detailEl.textContent = 'A* algorithm optimizing energy flows around isolated lines...';
                break;
        }

        currentStep++;
        healingTimer = setTimeout(nextStep, 1400);
    }

    nextStep();
}

function drawFailedLineMidpoint(u, v, layer, nodeMap) {
    const src = nodeMap[u];
    const tgt = nodeMap[v];
    if (!src || !tgt) return;
    
    const mx = (src.svgX + tgt.svgX) / 2;
    const my = (src.svgY + tgt.svgY) / 2;
    
    const cross = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    cross.setAttribute('x', mx);
    cross.setAttribute('y', my + 5);
    cross.setAttribute('text-anchor', 'middle');
    cross.setAttribute('fill', '#ff073a');
    cross.setAttribute('font-size', '20');
    cross.setAttribute('font-weight', 'bold');
    cross.textContent = '✕';
    layer.appendChild(cross);
}

function resetHealingDemo() {
    if (healingTimer) clearTimeout(healingTimer);
    const steps = document.querySelectorAll('.healing-step');
    steps.forEach(s => s.classList.remove('active', 'completed'));

    document.getElementById('hr-status').textContent = 'Awaiting Demo';
    document.getElementById('hr-status').className = 'hr-status';
    document.getElementById('hr-detail').textContent = 'Click "Play Demo Cycle" to execute testing routine.';
    document.getElementById('hr-connected').textContent = '—';
    document.getElementById('hr-newpath').textContent = '—';
    document.getElementById('hr-newcost').textContent = '—';

    renderGrid();
}

// ─── Congestion Heatmap Table ───
function renderCongestionTable() {
    const tbody = document.getElementById('congestion-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';

    pipelineData.edges_by_congestion.forEach((edge, i) => {
        const isFailed = edge.is_failed;
        const level = isFailed ? 'critical' : getCongestionLevel(edge.congestion_score);
        const color = isFailed ? '#ff073a' : getCongestionColor(edge.congestion_score);
        const ratioText = isFailed ? 'OFFLINE' : (userMode === 'beginner'
            ? plainCongestion(edge.congestion_score)
            : edge.congestion_score.toFixed(4));
        const pct = isFailed ? 100 : (edge.congestion_score * 100).toFixed(0);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color: var(--text-muted); font-family: var(--font-mono);">${i + 1}</td>
            <td>
                <span class="edge-link" onclick="scrollToMapAndSelect('${edge.source}', '${edge.target}')">
                    ${edge.source} ↔ ${edge.target}
                </span>
            </td>
            <td>
                <div class="cong-bar-cell">
                    <div class="cong-bar-mini">
                        <div class="cong-bar-mini-fill ${level}" style="width: ${pct}%;"></div>
                    </div>
                    <span class="font-mono" style="color: ${color}; font-weight: 700;">${ratioText}</span>
                </div>
            </td>
            <td>
                <span style="color: ${color}; text-transform: uppercase; font-size: 0.75rem; font-weight: 700;">
                    ${isFailed ? 'FAILED' : level}
                </span>
            </td>
            <td class="font-mono">${edge.resistance.toFixed(4)} Ω</td>
            <td class="font-mono">${edge.length_km.toFixed(1)} km</td>
            <td class="font-mono">${edge.age.toFixed(0)} yrs</td>
            <td>
                <button class="btn ${isFailed ? 'btn-outline-green' : 'btn-danger'} btn-sm" 
                    style="padding: 4px 8px; font-size: 0.65rem;"
                    onclick="toggleEdgeFailure('${edge.source}', '${edge.target}')">
                    ${isFailed ? 'Repair' : 'Fail'}
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function scrollToMapAndSelect(u, v) {
    switchView('dashboard');
    const sel = document.getElementById('fail-edge-select');
    if (sel) sel.value = `${u}-${v}`;
}

// ─── Terminal Logging Console ───
function addLogEntry(text, type = 'info') {
    const logBox = document.getElementById('console-logs-feed');
    if (!logBox) return;

    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="text-muted">[${timestamp}]</span> ${text}`;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;

    logHistory.push({ timestamp, type: type.toUpperCase(), message: text });
    if (logBox.children.length > 80) logBox.removeChild(logBox.firstChild);

    // Toasts for important events
    if (type === 'success' && text.includes('reroute')) showToast('Route optimized successfully', 'success');
    if (type === 'error' && text.includes('FAULT')) showToast('Transmission failure detected', 'error');
    if (type === 'warn' && text.includes('Congestion')) showToast('Congestion rising', 'warn');
}

function addTimelineEvent(message) {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    timelineEvents.unshift({ time, message });
    if (timelineEvents.length > 20) timelineEvents.pop();

    const markup = timelineEvents.map((ev, i) =>
        `<div class="timeline-event${i === 0 ? ' flash' : ''}">
            <span class="timeline-time">${ev.time}</span>
            <span class="timeline-msg">${ev.message}</span>
        </div>`
    ).join('');
    ['event-timeline', 'event-timeline-panel'].forEach(id => {
        const container = document.getElementById(id);
        if (container) container.innerHTML = markup;
    });
}

function exportLogsToCSV() {
    if (logHistory.length === 0) {
        alert('No logs recorded to export.');
        return;
    }

    let csv = 'Timestamp,Severity,Event Message\r\n';
    logHistory.forEach(row => {
        const cleanMsg = row.message.replace(/"/g, '""');
        csv += `"${row.timestamp}","${row.type}","${cleanMsg}"\r\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `powergrid_sim_logs_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    addLogEntry('Simulation activity logs successfully exported to CSV.', 'system');
}

// ─── Navigation ───
function switchView(viewId) {
    document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewId);
    });
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const view = document.getElementById(`view-${viewId}`);
    if (view) view.classList.add('active');

    if (viewId === 'ml') setTimeout(renderFeatureImportance, 100);
    if (viewId === 'analytics') renderAnalytics();
    addLogEntry(`View: ${viewId}`, 'info');
}

function switchTab(tabId) { switchView(tabId === 'routes' ? 'topology' : tabId === 'simulation' ? 'dashboard' : tabId); }

// ─── Interactive Tour Modal ───
function startOnboarding() {
    currentTourStep = 1;
    document.getElementById('onboarding-overlay').classList.remove('hidden');
    updateTourStepUI();
}

function closeOnboarding() {
    document.getElementById('onboarding-overlay').classList.add('hidden');
}

function nextTourStep() {
    if (currentTourStep < totalTourSteps) {
        currentTourStep++;
        updateTourStepUI();
    } else {
        closeOnboarding();
        addLogEntry('Operations tutorial complete. Welcome to PowerGrid Console!', 'success');
    }
}

function prevTourStep() {
    if (currentTourStep > 1) {
        currentTourStep--;
        updateTourStepUI();
    }
}

function updateTourStepUI() {
    document.querySelectorAll('.tour-step').forEach(step => {
        step.classList.remove('active');
    });

    const activeStep = document.querySelector(`.tour-step[data-step="${currentTourStep}"]`);
    if (activeStep) activeStep.classList.add('active');

    // Update dot indicator elements
    document.querySelectorAll('.progress-dot').forEach((dot, index) => {
        if (index + 1 === currentTourStep) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });

    // Handle back button disabled state
    document.getElementById('btn-tour-prev').disabled = currentTourStep === 1;
    
    // Next/Finish text change
    document.getElementById('btn-tour-next').textContent = currentTourStep === totalTourSteps ? 'Finish' : 'Next';
}

// ─── Animated Particle Canvas Background ───
function initCanvasBackground() {
    const canvas = document.getElementById('canvas-bg');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    
    window.addEventListener('resize', () => {
        width = (canvas.width = window.innerWidth);
        height = (canvas.height = window.innerHeight);
    });
    
    const particles = [];
    const maxParticles = 70;
    
    class Particle {
        constructor() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.vx = (Math.random() - 0.5) * 0.35;
            this.vy = (Math.random() - 0.5) * 0.35;
            this.radius = Math.random() * 1.5 + 0.5;
            this.color = Math.random() > 0.5 ? 'rgba(16, 185, 129, 0.35)' : 'rgba(52, 211, 153, 0.25)';
        }
        
        update() {
            this.x += this.vx;
            this.y += this.vy;
            
            if (this.x < 0 || this.x > width) this.vx *= -1;
            if (this.y < 0 || this.y > height) this.vy *= -1;
        }
        
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.fill();
        }
    }
    
    for (let i = 0; i < maxParticles; i++) {
        particles.push(new Particle());
    }
    
    function animate() {
        ctx.clearRect(0, 0, width, height);
        
        // Draw constellation lines
        for (let i = 0; i < particles.length; i++) {
            const p1 = particles[i];
            p1.update();
            p1.draw();
            
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist < 130) {
                    const alpha = (1 - dist / 130) * 0.08;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = `rgba(16, 185, 129, ${alpha * 0.6})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(animate);
    }
    
    animate();
}

// ─── UI Feature Modules ───

function setUserMode(mode) {
    userMode = mode;
    localStorage.setItem('grid_user_mode', mode);
    document.body.classList.toggle('expert-mode', mode === 'expert');
    document.getElementById('btn-beginner')?.classList.toggle('active', mode === 'beginner');
    document.getElementById('btn-expert')?.classList.toggle('active', mode === 'expert');
    const hint = document.getElementById('map-hint');
    if (hint) hint.textContent = mode === 'beginner'
        ? 'Click nodes to set route · Double-click lines to test failures · Try Beginner-friendly tooltips!'
        : 'Click nodes to route · Double-click lines to fail/repair · Expert metrics enabled';
    renderGrid();
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function setLegendFilter(filter) {
    legendFilter = legendFilter === filter ? null : filter;
    document.querySelectorAll('.legend-item').forEach(item => {
        item.classList.toggle('active', item.dataset.filter === legendFilter);
    });
    if (filter === null) document.querySelector('.legend-clear')?.classList.add('active');
    renderGrid();
}

function toggleSidebar() {
    document.getElementById('sidebar')?.classList.toggle('collapsed');
}

function toggleLabels() {
    showNodeLabels = !showNodeLabels;
    const btn = document.getElementById('btn-labels');
    if (btn) btn.style.opacity = showNodeLabels ? '1' : '0.4';
    renderGrid();
}

function zoomGraph(factor) {
    graphZoom = Math.max(0.5, Math.min(3, graphZoom * factor));
    applyGraphTransform();
}

function resetGraphView() {
    graphZoom = 1;
    graphPan = { x: 0, y: 0 };
    applyGraphTransform();
}

function centerGraph() { resetGraphView(); }

function applyGraphTransform() {
    const svg = document.getElementById('grid-svg');
    if (!svg) return;
    const layers = ['edges-layer', 'route-layer', 'nodes-layer', 'labels-layer'];
    layers.forEach(id => {
        const g = document.getElementById(id);
        if (g) g.setAttribute('transform', `translate(${graphPan.x},${graphPan.y}) scale(${graphZoom})`);
    });
}

function setupGraphPanZoom() {
    const viewport = document.getElementById('svg-viewport');
    if (!viewport) return;
    let dragging = false, last = { x: 0, y: 0 };
    viewport.addEventListener('mousedown', e => {
        if (e.target.closest('.grid-node') || e.target.closest('.grid-edge')) return;
        dragging = true; last = { x: e.clientX, y: e.clientY };
    });
    window.addEventListener('mousemove', e => {
        if (!dragging) return;
        graphPan.x += (e.clientX - last.x) / graphZoom;
        graphPan.y += (e.clientY - last.y) / graphZoom;
        last = { x: e.clientX, y: e.clientY };
        applyGraphTransform();
    });
    window.addEventListener('mouseup', () => dragging = false);
    viewport.addEventListener('wheel', e => {
        e.preventDefault();
        zoomGraph(e.deltaY < 0 ? 1.1 : 0.9);
    }, { passive: false });
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', e => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        if (e.code === 'Space') { e.preventDefault(); togglePlaySimulation(); }
        if (e.key === 'r' || e.key === 'R') resetSimulation();
        if (e.key === 'f' || e.key === 'F') simulateFailure();
        if (e.key === 'b' || e.key === 'B') setUserMode(userMode === 'beginner' ? 'expert' : 'beginner');
    });
}

function updateRouteEndpoint() {
    selectedSource = document.getElementById('source-select').value;
    selectedTarget = document.getElementById('target-select').value;
    updateRouteFlowDisplay();
    computeRoute();
}

function updateRouteFlowDisplay() {
    const srcLabel = document.getElementById('route-source-label');
    const tgtLabel = document.getElementById('route-target-label');
    const pathDisplay = document.getElementById('route-path-display');
    if (srcLabel) srcLabel.textContent = selectedSource;
    if (tgtLabel) tgtLabel.textContent = selectedTarget;

    const route = currentRoute || pipelineData?.ml_route;
    if (pathDisplay && route?.path) {
        pathDisplay.textContent = route.path.join(' → ');
    }

    const explain = document.getElementById('route-explain');
    const healing = pipelineData?.healing;
    if (explain && healing?.explanation && healing.path_changed) {
        explain.textContent = '💡 ' + healing.explanation;
        explain.classList.add('visible');
    } else if (explain) {
        explain.classList.remove('visible');
    }
}

function updateGauges() {
    const edges = pipelineData?.grid?.edges || [];
    const active = edges.filter(e => !e.is_failed);
    const avgCong = active.length ? active.reduce((s, e) => s + e.congestion_score, 0) / active.length : 0;
    const failed = edges.filter(e => e.is_failed).length;
    const r2 = pipelineData?.ml_metrics?.r2 || 0.9;

    setGauge('transmission', 1 - avgCong);
    setGauge('stability', 1 - failed / Math.max(edges.length, 1));
    setGauge('ai', r2);
    setGauge('efficiency', pipelineData?.ml_route && pipelineData?.naive_route
        ? Math.max(0, 1 - pipelineData.ml_route.avg_congestion) : 0.75, 'efficiency');
}

function setGauge(name, value, idOverride) {
    const id = idOverride || name;
    const circle = document.getElementById(`gauge-${id}`);
    const valEl = document.getElementById(`gauge-${id}-val`);
    if (!circle) return;
    const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
    const offset = 201 - (201 * value);
    circle.style.strokeDashoffset = offset;
    if (valEl) valEl.textContent = pct + '%';
}

function animateCounter(id, value, decimals) {
    const el = document.getElementById(id);
    if (!el) return;
    const target = typeof value === 'number' ? value : parseFloat(value) || 0;
    const start = parseFloat(el.textContent) || 0;
    const duration = 500;
    const startTime = performance.now();
    function step(now) {
        const t = Math.min(1, (now - startTime) / duration);
        const current = start + (target - start) * t;
        el.textContent = decimals > 0 ? current.toFixed(decimals) : Math.round(current);
        if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
    flashStat(el.closest('.live-stat'));
}

function flashStat(el) { if (el) { el.classList.add('updated'); setTimeout(() => el.classList.remove('updated'), 600); } }

async function updateWeatherDisplay(scenario) {
    const s = scenario || currentScenario;
    let w = WEATHER_MAP[s] || WEATHER_MAP.normal;
    
    if (s === 'live') {
        try {
            const res = await fetch('/api/weather');
            const data = await res.json();
            if (!data.error) {
                w = { icon: '🌍', name: `Live: ${data.city} (${data.temperature}°C, ${data.windspeed} km/h)` };
            }
        } catch(e) {}
    }
    
    const icon = document.getElementById('weather-icon');
    if (icon) icon.textContent = w.icon;
    ['weather-name', 'sim-weather-name'].forEach(id => {
        const name = document.getElementById(id);
        if (name) name.textContent = w.name;
    });
}

async function updateLiveCity(city) {
    if (!city) return;
    try {
        const res = await fetch('/api/weather', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city })
        });
        const data = await res.json();
        if (data.error) {
            addLogEntry(`Weather API Error: ${data.error}`, 'error');
            return;
        }
        addLogEntry(`Live weather set to ${data.city}: ${data.temperature}°C, Wind ${data.windspeed} km/h`, 'success');
        if (currentScenario === 'live') {
            updateWeatherDisplay('live');
        }
    } catch (err) {
        addLogEntry(`Failed to fetch weather: ${err.message}`, 'error');
    }
}

function renderMinimap() {
    const mini = document.getElementById('minimap-svg');
    if (!mini || !pipelineData?.grid) return;
    mini.innerHTML = '';
    const nodes = pipelineData.grid.nodes;
    const edges = pipelineData.grid.edges;

    edges.forEach(edge => {
        const s = nodes.find(n => n.id === edge.source);
        const t = nodes.find(n => n.id === edge.target);
        if (!s || !t) return;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        const sp = gridToSvg(s.x, s.y), tp = gridToSvg(t.x, t.y);
        line.setAttribute('x1', sp.x); line.setAttribute('y1', sp.y);
        line.setAttribute('x2', tp.x); line.setAttribute('y2', tp.y);
        line.setAttribute('stroke', edge.is_failed ? '#334155' : getCongestionColor(edge.congestion_score));
        line.setAttribute('stroke-width', '1');
        mini.appendChild(line);
    });
    nodes.forEach(n => {
        const p = gridToSvg(n.x, n.y);
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', '3');
        c.setAttribute('fill', NODE_STYLES[n.type]?.fill || '#fff');
        mini.appendChild(c);
    });
}

function renderAnalytics() {
    if (!pipelineData?.grid?.edges) return;
    const heatmap = document.getElementById('congestion-heatmap');
    if (heatmap) {
        heatmap.innerHTML = pipelineData.edges_by_congestion.slice(0, 24).map(e => {
            const color = getCongestionColor(e.congestion_score);
            return `<div class="heatmap-cell" style="background:${color}" title="${e.source}↔${e.target}: ${(e.congestion_score*100).toFixed(0)}%">${e.source}</div>`;
        }).join('');
    }

    const pie = document.getElementById('health-pie');
    if (pie) {
        const edges = pipelineData.grid.edges;
        const healthy = edges.filter(e => !e.is_failed && e.congestion_score < 0.5).length;
        const warn = edges.filter(e => !e.is_failed && e.congestion_score >= 0.5 && e.congestion_score < 0.85).length;
        const crit = edges.filter(e => !e.is_failed && e.congestion_score >= 0.85).length;
        const fail = edges.filter(e => e.is_failed).length;
        const total = edges.length || 1;
        let acc = 0;
        const segments = [
            { pct: healthy/total, color: '#22C55E', label: 'Healthy' },
            { pct: warn/total, color: '#FACC15', label: 'Warning' },
            { pct: crit/total, color: '#EF4444', label: 'Critical' },
            { pct: fail/total, color: '#334155', label: 'Failed' },
        ];
        const gradient = segments.map(s => { const start = acc * 360; acc += s.pct; return `${s.color} ${start}deg ${acc * 360}deg`; }).join(', ');
        pie.style.setProperty('--pie-gradient', `conic-gradient(${gradient})`);
        pie.style.background = '';
        pie.innerHTML = `<div class="pie-donut" aria-hidden="true"></div><div class="pie-legend">${segments.filter(s=>s.pct>0).map(s =>
            `<span class="pie-legend-item"><span class="pie-swatch" style="background:${s.color}"></span>${s.label} ${Math.round(s.pct*100)}%</span>`
        ).join('')}</div>`;
    }

    drawSparkline('load-trend-chart', generateTrendData(24, 300, 600));
    drawSparkline('hourly-cong-chart', generateTrendData(24, 0.3, 0.9));
    drawPredictionChart();
}

function generateTrendData(n, min, max) {
    const data = [];
    let v = (min + max) / 2;
    for (let i = 0; i < n; i++) {
        v += (Math.random() - 0.5) * (max - min) * 0.15;
        v = Math.max(min, Math.min(max, v));
        data.push(v);
    }
    return data;
}

function drawSparkline(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.offsetWidth || 300;
    const h = canvas.height = 120;
    ctx.clearRect(0, 0, w, h);
    const min = Math.min(...data), max = Math.max(...data);
    const range = max - min || 1;
    ctx.beginPath();
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2;
    data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 20) - 10;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = 'rgba(37, 99, 235, 0.10)';
    ctx.fill();
}

function drawPredictionChart() {
    const canvas = document.getElementById('prediction-chart');
    if (!canvas) return;
    const avg = pipelineData?.dashboard?.average_congestion || 0.5;
    predictionHistory.push(avg);
    if (predictionHistory.length > 20) predictionHistory.shift();
    drawSparkline('prediction-chart', predictionHistory.length > 1 ? predictionHistory : [avg, avg * 1.1, avg * 0.9, avg]);
}

// ─── AI Assistant (rule-based) ───
function toggleAssistant() {
    document.getElementById('ai-assistant-panel')?.classList.toggle('open');
}

function askAssistant(question) {
    const input = document.getElementById('assistant-input');
    const q = (question || input?.value || '').trim();
    if (!q) return;
    if (input) input.value = '';

    appendAssistantMsg(q, 'user');
    const answer = generateAssistantAnswer(q.toLowerCase());
    setTimeout(() => appendAssistantMsg(answer, 'bot'), 400);
}

function appendAssistantMsg(text, role) {
    const box = document.getElementById('assistant-messages');
    if (!box) return;
    const div = document.createElement('div');
    div.className = `assistant-msg ${role}`;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function generateAssistantAnswer(q) {
    const edges = pipelineData?.grid?.edges || [];
    const route = currentRoute || pipelineData?.ml_route;
    const topRisk = [...edges].filter(e => !e.is_failed).sort((a, b) => b.congestion_score - a.congestion_score)[0];
    const failed = edges.filter(e => e.is_failed);

    if (q.includes('reroute') || q.includes('route change')) {
        const h = pipelineData?.healing;
        return h?.explanation || 'Power reroutes when a transmission line becomes overloaded (above 85% capacity). The AI finds a safer alternate path using A* search, avoiding congested lines.';
    }
    if (q.includes('highest risk') || q.includes('overloaded')) {
        return topRisk
            ? `The highest-risk line is ${topRisk.source} ↔ ${topRisk.target} at ${(topRisk.congestion_score * 100).toFixed(0)}% capacity. ${plainCongestion(topRisk.congestion_score)}`
            : 'No at-risk lines detected right now. The grid is operating normally.';
    }
    if (q.includes('failure') || q.includes('failed')) {
        return failed.length
            ? `${failed.length} line(s) are currently offline: ${failed.map(e => `${e.source}↔${e.target}`).join(', ')}. Self-healing rerouted power around them.`
            : 'No transmission failures right now. All lines are operational.';
    }
    if (q.includes('safest path') || q.includes('safest')) {
        return route
            ? `The current optimal route is: ${route.path.join(' → ')} with average congestion of ${(route.avg_congestion * 100).toFixed(0)}%. This path avoids the most congested lines.`
            : 'No active route computed. Select a source and destination, then click Find Route.';
    }
    if (q.includes('overload') || q.includes('node')) {
        return `The grid has ${edges.filter(e => e.congestion_score >= 0.85).length} critically overloaded lines. Check the congestion heatmap in Analytics for details.`;
    }
    return `I can help explain the grid! Try asking: "Why did power reroute?", "Which line is at highest risk?", "How many failures occurred?", or "Show me the safest path."`;
}
