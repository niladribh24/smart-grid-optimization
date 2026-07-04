/**
 * PowerGrid — Interactive Frontend Application
 * ==============================================
 * Renders the grid as SVG, handles route computation,
 * self-healing demos, and all interactive features.
 */

// ─── State ───
let pipelineData = null;
let currentRoute = null;
let selectedSource = null;
let selectedTarget = null;

// ─── SVG Constants ───
const SVG_PADDING = 30;
const SVG_WIDTH = 500;
const SVG_HEIGHT = 420;
const NODE_RADIUS = 16;

// Map grid coords (0-10 x, 0-10 y) to SVG coords
function gridToSvg(x, y) {
    // y is inverted (grid y increases upward, SVG y increases downward)
    const svgX = SVG_PADDING + (x / 10) * (SVG_WIDTH - 2 * SVG_PADDING);
    const svgY = SVG_PADDING + ((10 - y) / 10) * (SVG_HEIGHT - 2 * SVG_PADDING);
    return { x: svgX, y: svgY };
}

// Congestion color
function getCongestionColor(score) {
    if (score >= 0.85) return '#ff0044';
    if (score >= 0.70) return '#ff8800';
    if (score >= 0.50) return '#ffdd00';
    return '#00ff88';
}

function getCongestionLevel(score) {
    if (score >= 0.85) return 'critical';
    if (score >= 0.70) return 'high';
    if (score >= 0.50) return 'medium';
    return 'low';
}

// Node styling
const NODE_STYLES = {
    generator: { fill: '#ff4444', stroke: '#ff6666', shape: 'rect', size: 14 },
    substation: { fill: '#ffd700', stroke: '#ffe44d', shape: 'diamond', size: 12 },
    consumer: { fill: '#4488ff', stroke: '#66aaff', shape: 'circle', size: 12 },
};

// ─── Initialization ───
document.addEventListener('DOMContentLoaded', () => {
    fetchPipelineData();
});

async function fetchPipelineData() {
    try {
        const res = await fetch('/api/pipeline');
        pipelineData = await res.json();
        renderAll();
        hideLoading();
    } catch (err) {
        console.error('Failed to load pipeline data:', err);
        document.querySelector('.loader-text').textContent = 'Error loading data';
        document.querySelector('.loader-subtext').textContent = err.message;
    }
}

function hideLoading() {
    setTimeout(() => {
        document.getElementById('loading-screen').classList.add('hidden');
    }, 600);
}

function renderAll() {
    renderHeroStats();
    renderGrid();
    renderMLMetrics();
    renderFeatureImportance();
    renderRouteComparison();
    renderHealingSection();
    renderCongestionTable();
    populateSelectors();
}

// ─── Hero Stats ───
function renderHeroStats() {
    const d = pipelineData;
    animateCounter('stat-r2', d.ml_metrics.r2, 4, '', true);
    document.getElementById('stat-nodes').textContent = d.grid.nodes.length;
    document.getElementById('stat-edges').textContent = d.grid.edges.length;

    const improvement = ((d.naive_route.avg_congestion - d.ml_route.avg_congestion)
                         / d.naive_route.avg_congestion * 100);
    animateCounter('stat-improvement', improvement, 1, '%');
}

function animateCounter(id, target, decimals, suffix = '', isFloat = false) {
    const el = document.getElementById(id);
    const duration = 1500;
    const start = performance.now();

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = target * eased;
        el.textContent = current.toFixed(decimals) + suffix;
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ─── SVG Grid Rendering ───
function renderGrid() {
    const svg = document.getElementById('grid-svg');
    const edgesLayer = document.getElementById('edges-layer');
    const routeLayer = document.getElementById('route-layer');
    const nodesLayer = document.getElementById('nodes-layer');
    const labelsLayer = document.getElementById('labels-layer');

    // Clear
    edgesLayer.innerHTML = '';
    routeLayer.innerHTML = '';
    nodesLayer.innerHTML = '';
    labelsLayer.innerHTML = '';

    const nodes = pipelineData.grid.nodes;
    const edges = pipelineData.grid.edges;

    // Build node position map
    const nodeMap = {};
    nodes.forEach(n => {
        const pos = gridToSvg(n.x, n.y);
        nodeMap[n.id] = { ...n, svgX: pos.x, svgY: pos.y };
    });

    // Draw edges
    edges.forEach((edge, i) => {
        const src = nodeMap[edge.source];
        const tgt = nodeMap[edge.target];
        if (!src || !tgt) return;

        const color = getCongestionColor(edge.congestion_score);
        const width = 1.5 + edge.congestion_score * 3;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', src.svgX);
        line.setAttribute('y1', src.svgY);
        line.setAttribute('x2', tgt.svgX);
        line.setAttribute('y2', tgt.svgY);
        line.setAttribute('stroke', color);
        line.setAttribute('stroke-width', width);
        line.setAttribute('opacity', '0.7');
        line.setAttribute('class', 'grid-edge');
        line.setAttribute('data-source', edge.source);
        line.setAttribute('data-target', edge.target);
        line.setAttribute('data-index', i);

        // Hover tooltip
        line.addEventListener('mouseenter', (e) => showEdgeTooltip(e, edge));
        line.addEventListener('mouseleave', hideEdgeTooltip);
        line.addEventListener('click', () => {
            document.getElementById('fail-edge-select').value = `${edge.source}-${edge.target}`;
        });

        edgesLayer.appendChild(line);
    });

    // Draw route (A* path)
    if (pipelineData.ml_route && pipelineData.ml_route.path.length > 1) {
        drawRoute(pipelineData.ml_route.path, '#00ff88', routeLayer, nodeMap);
    }

    // Draw nodes
    nodes.forEach(n => {
        const pos = nodeMap[n.id];
        const style = NODE_STYLES[n.type] || NODE_STYLES.consumer;
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'grid-node');
        g.setAttribute('data-id', n.id);

        let shape;
        if (style.shape === 'rect') {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', pos.svgX - style.size);
            shape.setAttribute('y', pos.svgY - style.size);
            shape.setAttribute('width', style.size * 2);
            shape.setAttribute('height', style.size * 2);
            shape.setAttribute('rx', '3');
        } else if (style.shape === 'diamond') {
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

        shape.setAttribute('fill', style.fill);
        shape.setAttribute('stroke', '#fff');
        shape.setAttribute('stroke-width', '2');
        g.appendChild(shape);

        // Click to select as source/target
        g.addEventListener('click', () => handleNodeClick(n.id));

        nodesLayer.appendChild(g);

        // Label
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', pos.svgX);
        text.setAttribute('y', pos.svgY + style.size + 14);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', '#ccc');
        text.setAttribute('font-size', '10');
        text.setAttribute('font-weight', '600');
        text.setAttribute('font-family', 'Inter, sans-serif');
        text.textContent = n.id;
        labelsLayer.appendChild(text);
    });
}

function drawRoute(path, color, layer, nodeMap) {
    for (let i = 0; i < path.length - 1; i++) {
        const src = nodeMap[path[i]];
        const tgt = nodeMap[path[i + 1]];
        if (!src || !tgt) continue;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', src.svgX);
        line.setAttribute('y1', src.svgY);
        line.setAttribute('x2', tgt.svgX);
        line.setAttribute('y2', tgt.svgY);
        line.setAttribute('stroke', color);
        line.setAttribute('stroke-width', '5');
        line.setAttribute('class', 'route-edge');
        line.setAttribute('filter', 'url(#glow-green)');
        layer.appendChild(line);
    }
}

function drawFailedEdge(u, v, layer, nodeMap) {
    const src = nodeMap[u];
    const tgt = nodeMap[v];
    if (!src || !tgt) return;

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', src.svgX);
    line.setAttribute('y1', src.svgY);
    line.setAttribute('x2', tgt.svgX);
    line.setAttribute('y2', tgt.svgY);
    line.setAttribute('stroke', '#ff0055');
    line.setAttribute('stroke-width', '5');
    line.setAttribute('class', 'failed-edge');
    line.setAttribute('filter', 'url(#glow-red)');
    layer.appendChild(line);

    // X mark at midpoint
    const mx = (src.svgX + tgt.svgX) / 2;
    const my = (src.svgY + tgt.svgY) / 2;
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', mx);
    text.setAttribute('y', my + 5);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('fill', '#ff0055');
    text.setAttribute('font-size', '18');
    text.setAttribute('font-weight', 'bold');
    text.textContent = '✕';
    layer.appendChild(text);
}

// ─── Edge Tooltip ───
function showEdgeTooltip(e, edge) {
    const tooltip = document.getElementById('edge-tooltip');
    const wrapper = document.querySelector('.grid-svg-wrapper');
    const rect = wrapper.getBoundingClientRect();

    tooltip.classList.add('visible');
    document.getElementById('tt-label').textContent = `${edge.source} ↔ ${edge.target}`;
    document.getElementById('tt-cong').textContent = edge.congestion_score.toFixed(4);
    document.getElementById('tt-res').textContent = edge.resistance.toFixed(4);
    document.getElementById('tt-len').textContent = edge.length_km.toFixed(1) + ' km';
    document.getElementById('tt-age').textContent = edge.age.toFixed(0) + ' yrs';

    const x = e.clientX - rect.left + 15;
    const y = e.clientY - rect.top - 10;
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
}

function hideEdgeTooltip() {
    document.getElementById('edge-tooltip').classList.remove('visible');
}

// ─── Node Click ───
let clickMode = 'source'; // alternates between source and target
function handleNodeClick(nodeId) {
    if (clickMode === 'source') {
        document.getElementById('source-select').value = nodeId;
        clickMode = 'target';
    } else {
        document.getElementById('target-select').value = nodeId;
        clickMode = 'source';
    }
}

// ─── Selectors ───
function populateSelectors() {
    const nodes = pipelineData.grid.nodes;
    const sourceSelect = document.getElementById('source-select');
    const targetSelect = document.getElementById('target-select');
    const failSelect = document.getElementById('fail-edge-select');

    nodes.forEach(n => {
        const typeLabel = n.type === 'generator' ? '⚡' : n.type === 'substation' ? '🔄' : '🏠';
        const opt1 = new Option(`${typeLabel} ${n.id} — ${n.label}`, n.id);
        const opt2 = new Option(`${typeLabel} ${n.id} — ${n.label}`, n.id);
        sourceSelect.add(opt1);
        targetSelect.add(opt2);
    });

    sourceSelect.value = pipelineData.source;
    targetSelect.value = pipelineData.target;

    // Populate edge selector
    pipelineData.edges_by_congestion.forEach(e => {
        const level = getCongestionLevel(e.congestion_score);
        const opt = new Option(
            `${e.source} ↔ ${e.target} (${e.congestion_score.toFixed(3)})`,
            `${e.source}-${e.target}`
        );
        failSelect.add(opt);
    });
}

// ─── Route Computation ───
async function computeRoute() {
    const source = document.getElementById('source-select').value;
    const target = document.getElementById('target-select').value;
    const btn = document.getElementById('btn-reroute');

    btn.textContent = 'Computing...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/reroute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source, target }),
        });
        const data = await res.json();

        // Update route on grid
        const routeLayer = document.getElementById('route-layer');
        routeLayer.innerHTML = '';

        const nodeMap = {};
        pipelineData.grid.nodes.forEach(n => {
            const pos = gridToSvg(n.x, n.y);
            nodeMap[n.id] = { svgX: pos.x, svgY: pos.y };
        });

        if (data.ml_route && data.ml_route.path.length > 1) {
            drawRoute(data.ml_route.path, '#00ff88', routeLayer, nodeMap);
        }

        // Update route comparison cards
        if (data.ml_route) {
            updateRouteCard('astar', data.ml_route);
        }
        if (data.naive_route) {
            updateRouteCard('dijkstra', data.naive_route);
        }

        // Update comparison banner
        if (data.ml_route && data.naive_route) {
            const imp = ((data.naive_route.avg_congestion - data.ml_route.avg_congestion)
                         / data.naive_route.avg_congestion * 100);
            document.getElementById('cb-improvement').textContent = imp.toFixed(1) + '%';
        }
    } catch (err) {
        console.error('Reroute error:', err);
    } finally {
        btn.textContent = 'Find Route';
        btn.disabled = false;
    }
}

function updateRouteCard(type, route) {
    const pathEl = document.getElementById(`${type === 'astar' ? 'astar' : 'dijkstra'}-path`);
    pathEl.innerHTML = route.path.map((node, i) => {
        let html = `<span class="route-node">${node}</span>`;
        if (i < route.path.length - 1) html += `<span class="route-arrow">→</span>`;
        return html;
    }).join('');

    document.getElementById(`${type === 'astar' ? 'astar' : 'dijkstra'}-cost`).textContent =
        route.total_cost.toFixed(4);
    document.getElementById(`${type === 'astar' ? 'astar' : 'dijkstra'}-cong`).textContent =
        route.avg_congestion.toFixed(4);
    document.getElementById(`${type === 'astar' ? 'astar' : 'dijkstra'}-hops`).textContent =
        route.num_hops;
}

// ─── Failure Simulation ───
async function simulateFailure() {
    const select = document.getElementById('fail-edge-select');
    const [u, v] = select.value.split('-');
    const source = document.getElementById('source-select').value;
    const target = document.getElementById('target-select').value;

    try {
        const res = await fetch('/api/heal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edge_u: u, edge_v: v, source, target }),
        });
        const data = await res.json();

        // Update grid visualization
        const routeLayer = document.getElementById('route-layer');
        routeLayer.innerHTML = '';

        const nodeMap = {};
        pipelineData.grid.nodes.forEach(n => {
            const pos = gridToSvg(n.x, n.y);
            nodeMap[n.id] = { svgX: pos.x, svgY: pos.y };
        });

        // Draw failed edge
        drawFailedEdge(u, v, routeLayer, nodeMap);

        // Draw new route
        if (data.new_path && data.new_path.length > 1) {
            drawRoute(data.new_path, '#00ff88', routeLayer, nodeMap);
        }

        // Update healing report
        document.getElementById('hr-edge').textContent = `${u} ↔ ${v}`;
        document.getElementById('hr-cong').textContent = data.congestion_at_failure.toFixed(4);
        document.getElementById('hr-connected').textContent = data.is_connected ? 'Yes ✅' : 'No ❌';
        document.getElementById('hr-newpath').textContent = data.new_path.join(' → ');
        document.getElementById('hr-newcost').textContent = data.new_cost.toFixed(4);

        const statusEl = document.getElementById('hr-status');
        if (data.reroute_success) {
            statusEl.textContent = '✅ HEALED';
            statusEl.className = 'hr-status success';
        } else {
            statusEl.textContent = '❌ FAILED';
            statusEl.className = 'hr-status fail';
        }
    } catch (err) {
        console.error('Healing error:', err);
    }
}

// ─── ML Metrics ───
function renderMLMetrics() {
    const m = pipelineData.ml_metrics;
    animateCounter('ml-r2', m.r2, 4);
    animateCounter('ml-rmse', m.rmse, 4);
    animateCounter('ml-mae', m.mae, 4);
    document.getElementById('ml-samples').textContent = m.train_samples.toLocaleString();
}

// ─── Feature Importance ───
function renderFeatureImportance() {
    const fi = pipelineData.feature_importances;
    const container = document.getElementById('fi-bars');
    container.innerHTML = '';

    const entries = Object.entries(fi);
    const maxVal = entries[0][1];

    entries.forEach(([name, value], i) => {
        const pct = (value / maxVal) * 100;
        const tierClass = i === 0 ? 'top' : (i < 3 ? 'mid' : 'low');

        const row = document.createElement('div');
        row.className = 'fi-bar-row';
        row.innerHTML = `
            <span class="fi-bar-label">${name}</span>
            <div class="fi-bar-track">
                <div class="fi-bar-fill ${tierClass}" style="width: 0%;">
                    <span class="fi-bar-value">${value.toFixed(3)}</span>
                </div>
            </div>
        `;
        container.appendChild(row);

        // Animate width after a small delay
        setTimeout(() => {
            row.querySelector('.fi-bar-fill').style.width = pct + '%';
        }, 200 + i * 80);
    });
}

// ─── Route Comparison ───
function renderRouteComparison() {
    const ml = pipelineData.ml_route;
    const nv = pipelineData.naive_route;

    updateRouteCard('astar', ml);
    updateRouteCard('dijkstra', nv);

    // Improvement banner
    if (ml && nv && nv.avg_congestion > 0) {
        const imp = ((nv.avg_congestion - ml.avg_congestion) / nv.avg_congestion * 100);
        animateCounter('cb-improvement', imp, 1, '%');
    }
}

// ─── Self-Healing Section ───
function renderHealingSection() {
    const h = pipelineData.healing;
    if (!h) return;

    document.getElementById('heal-step2-text').textContent =
        `Edge ${h.failed_edge[0]} ↔ ${h.failed_edge[1]} removed (congestion: ${h.congestion_at_failure.toFixed(3)})`;
    document.getElementById('heal-step3-text').textContent =
        `Network ${h.is_connected ? 'remains connected' : 'DISCONNECTED'} — ${h.num_components} component(s)`;
    document.getElementById('heal-step4-text').textContent =
        h.reroute_success
            ? `New path: ${h.new_path.join(' → ')} (cost: ${h.new_cost.toFixed(4)})`
            : 'No alternate route found!';

    // Pre-fill report
    document.getElementById('hr-edge').textContent = `${h.failed_edge[0]} ↔ ${h.failed_edge[1]}`;
    document.getElementById('hr-cong').textContent = h.congestion_at_failure.toFixed(4);
}

let healingTimer = null;
function playHealingDemo() {
    resetHealingDemo();
    const steps = document.querySelectorAll('.healing-step');
    const h = pipelineData.healing;

    let currentStep = 0;

    function nextStep() {
        if (currentStep > 0) {
            steps[currentStep - 1].classList.remove('active');
            steps[currentStep - 1].classList.add('completed');
        }

        if (currentStep >= steps.length) {
            // Final state
            const statusEl = document.getElementById('hr-status');
            if (h.reroute_success) {
                statusEl.textContent = '✅ HEALED — Grid Restored';
                statusEl.className = 'hr-status success';
            } else {
                statusEl.textContent = '❌ FAILED';
                statusEl.className = 'hr-status fail';
            }

            document.getElementById('hr-connected').textContent = h.is_connected ? 'Yes ✅' : 'No ❌';
            document.getElementById('hr-newpath').textContent = h.new_path.join(' → ');
            document.getElementById('hr-newcost').textContent = h.new_cost.toFixed(4);

            // Draw on grid
            const routeLayer = document.getElementById('route-layer');
            routeLayer.innerHTML = '';
            const nodeMap = {};
            pipelineData.grid.nodes.forEach(n => {
                const pos = gridToSvg(n.x, n.y);
                nodeMap[n.id] = { svgX: pos.x, svgY: pos.y };
            });

            drawFailedEdge(h.failed_edge[0], h.failed_edge[1], routeLayer, nodeMap);
            if (h.new_path.length > 1) {
                drawRoute(h.new_path, '#00ff88', routeLayer, nodeMap);
            }

            document.getElementById('hr-detail').textContent =
                'Self-healing cycle complete. The system detected the failure, verified connectivity, and rerouted power.';
            return;
        }

        steps[currentStep].classList.add('active');

        // Update status based on step
        const statusEl = document.getElementById('hr-status');
        const detailEl = document.getElementById('hr-detail');
        switch (currentStep) {
            case 0:
                statusEl.textContent = '🔍 Scanning...';
                statusEl.className = 'hr-status';
                statusEl.style.color = 'var(--accent-cyan)';
                detailEl.textContent = 'Analyzing edge congestion scores to identify at-risk lines...';
                break;
            case 1:
                statusEl.textContent = '⚡ Failure Detected';
                statusEl.className = 'hr-status';
                statusEl.style.color = 'var(--accent-red)';
                detailEl.textContent = `Line ${h.failed_edge[0]} ↔ ${h.failed_edge[1]} has failed! Initiating recovery...`;
                break;
            case 2:
                statusEl.textContent = '🔗 Checking Connectivity';
                statusEl.className = 'hr-status';
                statusEl.style.color = 'var(--accent-yellow)';
                detailEl.textContent = 'Running DFS to verify network connectivity after failure...';
                break;
            case 3:
                statusEl.textContent = '🔄 Rerouting...';
                statusEl.className = 'hr-status';
                statusEl.style.color = 'var(--accent-green)';
                detailEl.textContent = 'A* algorithm computing alternate optimal path...';
                break;
        }

        currentStep++;
        healingTimer = setTimeout(nextStep, 1500);
    }

    nextStep();
}

function resetHealingDemo() {
    if (healingTimer) clearTimeout(healingTimer);
    const steps = document.querySelectorAll('.healing-step');
    steps.forEach(s => {
        s.classList.remove('active', 'completed');
    });

    document.getElementById('hr-status').textContent = 'Awaiting Demo';
    document.getElementById('hr-status').className = 'hr-status';
    document.getElementById('hr-status').style.color = '';
    document.getElementById('hr-detail').textContent = 'Click "Play Demo" to watch the self-healing cycle.';
    document.getElementById('hr-connected').textContent = '—';
    document.getElementById('hr-newpath').textContent = '—';
    document.getElementById('hr-newcost').textContent = '—';

    // Restore route on grid
    const routeLayer = document.getElementById('route-layer');
    routeLayer.innerHTML = '';
    const nodeMap = {};
    pipelineData.grid.nodes.forEach(n => {
        const pos = gridToSvg(n.x, n.y);
        nodeMap[n.id] = { svgX: pos.x, svgY: pos.y };
    });
    if (pipelineData.ml_route && pipelineData.ml_route.path.length > 1) {
        drawRoute(pipelineData.ml_route.path, '#00ff88', routeLayer, nodeMap);
    }
}

// ─── Congestion Table ───
function renderCongestionTable() {
    const tbody = document.getElementById('congestion-tbody');
    tbody.innerHTML = '';

    pipelineData.edges_by_congestion.forEach((edge, i) => {
        const level = getCongestionLevel(edge.congestion_score);
        const color = getCongestionColor(edge.congestion_score);
        const pct = (edge.congestion_score * 100).toFixed(0);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color: var(--text-muted);">${i + 1}</td>
            <td>
                <span class="edge-link" onclick="document.getElementById('fail-edge-select').value='${edge.source}-${edge.target}'; document.getElementById('healing-section').scrollIntoView({behavior:'smooth'})">
                    ${edge.source} ↔ ${edge.target}
                </span>
            </td>
            <td>
                <div class="cong-bar-cell">
                    <div class="cong-bar-mini">
                        <div class="cong-bar-mini-fill ${level}" style="width: ${pct}%;"></div>
                    </div>
                    <span style="color: ${color};">${edge.congestion_score.toFixed(4)}</span>
                </div>
            </td>
            <td><span style="color: ${color}; text-transform: uppercase; font-size: 0.75rem; font-weight: 600;">${level}</span></td>
            <td>${edge.resistance.toFixed(4)}</td>
            <td>${edge.length_km.toFixed(1)}</td>
            <td>${edge.age.toFixed(0)}</td>
            <td>
                <button class="btn btn-danger btn-sm" style="padding: 4px 10px; font-size: 0.7rem;"
                    onclick="document.getElementById('fail-edge-select').value='${edge.source}-${edge.target}'; simulateFailure();">
                    Fail
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}
