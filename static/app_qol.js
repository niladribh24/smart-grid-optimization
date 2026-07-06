(function () {
    let hasAppliedDefaultFocus = false;

    function setText(selector, text) {
        const el = document.querySelector(selector);
        if (el) el.textContent = text;
    }

    function setHtml(selector, html) {
        const el = document.querySelector(selector);
        if (el) el.innerHTML = html;
    }

    function ensureNote(selector, className, text) {
        const host = document.querySelector(selector);
        if (!host) return;
        const selectorClass = "." + className.trim().split(/\s+/).join(".");
        let note = host.querySelector(selectorClass);
        if (!note) {
            note = document.createElement("p");
            note.className = className;
            host.insertBefore(note, host.firstChild ? host.firstChild.nextSibling : null);
        }
        note.textContent = text;
    }

    function friendlyCongestion(score) {
        const pct = Math.round((score || 0) * 100);
        if (score >= 0.85) return `Overloaded (${pct}%)`;
        if (score >= 0.70) return `Risky (${pct}%)`;
        if (score >= 0.50) return `Moderate (${pct}%)`;
        return `Normal (${pct}%)`;
    }

    function routeText(route) {
        return route?.path?.length ? route.path.join(" -> ") : "No route available";
    }

    function applyDefaultGraphFocus() {
        if (hasAppliedDefaultFocus || typeof applyGraphTransform !== "function") return;
        graphZoom = 1.16;
        graphPan = { x: 8, y: 4 };
        applyGraphTransform();
        hasAppliedDefaultFocus = true;
    }

    function humanizeTimelineMessage(message) {
        if (!message) return "";

        return message
            .replace("System initialized Ã¢â‚¬â€ grid online", "The dashboard loaded the grid.")
            .replace("System initialized â€” grid online", "The dashboard loaded the grid.")
            .replace("Edge removed:", "A line was shut off:")
            .replace("Scenario changed:", "Scenario changed to:")
            .replace("A* New route:", "The route changed to:")
            .replace("Power restored via", "Backup route:")
            .replace("Consumer", "Destination")
            .replace("isolated", "cut off");
    }

    function getCurrentRoute() {
        return currentRoute || pipelineData?.ml_route || null;
    }

    function applyPlainLanguageUI() {
        const route = getCurrentRoute();
        const edges = pipelineData?.grid?.edges || [];
        const busy = edges.filter((edge) => !edge.is_failed && edge.congestion_score >= 0.70).length;
        const failed = edges.filter((edge) => edge.is_failed).length;
        const topRisk = [...edges]
            .filter((edge) => !edge.is_failed)
            .sort((a, b) => b.congestion_score - a.congestion_score)[0];

        const summaryEl = document.getElementById("plain-summary");
        const cardSummaryEl = document.getElementById("plain-card-summary");
        const nextStepEl = document.getElementById("plain-next-step");
        const topRiskEl = document.getElementById("plain-top-risk");
        const graphTitleEl = document.getElementById("graph-title");
        const graphSubtitleEl = document.getElementById("graph-subtitle");
        const graphSourceEl = document.getElementById("graph-source");
        const graphTargetEl = document.getElementById("graph-target");
        const graphHealthEl = document.getElementById("graph-health");
        const mapHintEl = document.getElementById("map-hint");
        const routeExplainEl = document.getElementById("route-explain");
        const predictionEl = document.getElementById("prediction-explainer");

        let summary = `Power is moving from ${selectedSource} to ${selectedTarget} through ${route?.num_hops || 0} grid steps.`;
        let detail = `Right now there are ${busy} busy lines and ${failed} offline lines.`;
        let nextStep = "Nothing urgent to do. The current route looks stable.";
        let graphHealth = failed > 0 ? "Needs attention" : busy > 0 ? "Watch closely" : "Stable";
        let predictionExplainer = "The forecast model checks which lines may become crowded soon. The route then avoids those lines when it can.";

        if (!route?.path?.length) {
            summary = `${selectedTarget} is currently cut off from ${selectedSource}.`;
            detail = "The app could not find a safe route through the grid.";
            nextStep = "Repair a line or choose a different destination.";
            graphHealth = "Route unavailable";
            predictionExplainer = "The forecast is not the issue here. The grid is physically blocked, so no safe route is available.";
        } else if (failed > 0) {
            nextStep = "A line is offline. Check the replacement route and confirm it still looks reasonable.";
        } else if (busy > 0) {
            nextStep = "Watch the busiest line. The route may move if that line gets any worse.";
        }

        if (topRisk) {
            predictionExplainer = topRisk.congestion_score >= 0.85
                ? `Forecast warning: ${topRisk.source} -> ${topRisk.target} is close to overload, so the router is treating it as risky.`
                : `Forecast check: ${topRisk.source} -> ${topRisk.target} is currently the busiest line, so it matters most when the route is chosen.`;
        }

        if (summaryEl) summaryEl.textContent = `${summary} ${detail}`;

        if (cardSummaryEl) {
            cardSummaryEl.textContent = route?.path?.length
                ? `Power currently travels through: ${routeText(route)}`
                : "No usable route is available between the selected source and destination.";
        }

        if (nextStepEl) nextStepEl.textContent = nextStep;

        if (topRiskEl) {
            topRiskEl.textContent = topRisk
                ? `${topRisk.source} -> ${topRisk.target} ${friendlyCongestion(topRisk.congestion_score)}`
                : "No high-risk line detected";
        }

        if (graphTitleEl) {
            graphTitleEl.textContent = route?.path?.length
                ? `Current route: ${selectedSource} -> ${selectedTarget}`
                : `No safe route from ${selectedSource} to ${selectedTarget}`;
        }

        if (graphSubtitleEl) {
            graphSubtitleEl.textContent = topRisk
                ? `This route uses ${route?.num_hops || 0} steps. The most stressed line is ${topRisk.source} -> ${topRisk.target}.`
                : "Hover a line or node to see what it represents in the grid.";
        }

        if (graphSourceEl) graphSourceEl.textContent = selectedSource;
        if (graphTargetEl) graphTargetEl.textContent = selectedTarget;
        if (graphHealthEl) graphHealthEl.textContent = graphHealth;

        if (mapHintEl) {
            mapHintEl.textContent = "Click one node to choose the source, then a second node for the destination. Double-click a line only if you want to test a failure.";
        }

        if (routeExplainEl) {
            if (route?.path?.length) {
                routeExplainEl.textContent = `Why this route: it balances congestion risk, transmission loss, and line resistance across ${route.num_hops} steps.`;
                routeExplainEl.classList.add("visible");
            } else {
                routeExplainEl.textContent = "";
                routeExplainEl.classList.remove("visible");
            }
        }

        if (predictionEl) predictionEl.textContent = predictionExplainer;

        ensureNote(".graph-column", "section-note graph-note", "This map shows where power starts, which substations it passes through, and where it ends. The bright blue route is the path currently carrying power.");
        ensureNote(".timeline-section", "section-note timeline-note", "Recent changes is a short history of route updates, line failures, and scenario changes.");
        ensureNote(".controls-section", "section-note controls-note", "Use the controls only when you want to test what happens under different weather or load conditions.");
        ensureNote(".log-section", "section-note log-note", "Detailed notes is the raw activity feed. You can mostly ignore it unless you are debugging.");

        const assistantGreeting = document.querySelector(".assistant-msg.bot");
        if (assistantGreeting) {
            assistantGreeting.textContent = "Ask what changed, which line is risky, or why the route moved. I will answer in plain language.";
        }

        const healStep2 = document.getElementById("heal-step2-text");
        const healStep3 = document.getElementById("heal-step3-text");
        const healStep4 = document.getElementById("heal-step4-text");
        const healing = pipelineData?.healing;

        if (healing?.failed_edge?.length) {
            if (healStep2) {
                healStep2.textContent = `The demo trips line ${healing.failed_edge[0]} -> ${healing.failed_edge[1]} because it becomes too congested.`;
            }
            if (healStep3) {
                healStep3.textContent = healing.is_connected
                    ? "The grid stays connected, so the app can look for a backup route."
                    : "The grid splits apart here, so the destination may lose power.";
            }
            if (healStep4) {
                healStep4.textContent = healing.reroute_success
                    ? `The backup path becomes ${healing.new_path.join(" -> ")}.`
                    : "No backup route is available after the failure.";
            }
        }
    }

    function simplifyStaticCopy() {
        setHtml(".topbar-title", "Smart Grid <span class=\"accent\">Overview</span>");
        setText('.nav-item[data-view="dashboard"] .nav-label', "Overview");
        setText('.nav-item[data-view="simulation"] .nav-label', "Test scenarios");
        setText('.nav-item[data-view="ml"] .nav-label', "Why routes change");
        setText('.nav-item[data-view="analytics"] .nav-label', "Charts");
        setText('.nav-item[data-view="topology"] .nav-label', "Route details");

        setText(".timeline-section .dock-title", "Recent changes");
        setText(".controls-section .dock-title", "Try different conditions");
        setText(".log-section .dock-title", "Detailed notes");

        setText("#btn-assistant", "?");
        const assistantButton = document.getElementById("btn-assistant");
        if (assistantButton) assistantButton.title = "Ask a plain-language question";

        setText("#view-ml .section-badge", "ROUTE DECISION GUIDE");
        setText("#view-analytics .section-badge", "GRID CHARTS");
        setText("#tab-content-routes .section-badge", "ROUTE COMPARISON");
        setText("#view-ml .card-heading.text-cyan", "What the forecast model does");
        setText("#view-topology .card-heading", "Route recovery demo");

        const mlPlain = document.querySelector("#view-ml .explainer-section p");
        if (mlPlain) {
            mlPlain.textContent = "This forecast model estimates which lines may get too busy soon. The app then avoids those lines when it chooses a route.";
        }

        const mlTechHeading = document.querySelector("#view-ml .explainer-section.expert-only h4");
        if (mlTechHeading) mlTechHeading.textContent = "Advanced details";

        const mlInsight = document.querySelector("#view-ml .fi-insight");
        if (mlInsight) {
            mlInsight.innerHTML = "<strong>Automatic protection:</strong> if a line becomes too congested, the app takes it offline and looks for a backup route.";
        }

        const weatherCardTitle = document.querySelector(".weather-card h3");
        if (weatherCardTitle) weatherCardTitle.textContent = "Weather impact";

        const statusLabels = document.querySelectorAll(".status-card .plain-point-label");
        if (statusLabels[0]) statusLabels[0].textContent = "Best next step";
        if (statusLabels[1]) statusLabels[1].textContent = "Line to watch";

        const topbarStats = document.querySelectorAll(".stat-label");
        if (topbarStats[0]) topbarStats[0].textContent = "Model fit";
        if (topbarStats[1]) topbarStats[1].textContent = "Playback speed";

        const firstDockNote = document.querySelector(".timeline-section");
        if (firstDockNote) firstDockNote.classList.add("qol-dock");
    }

    const originalRenderAll = typeof renderAll === "function" ? renderAll : null;
    if (originalRenderAll) {
        renderAll = function () {
            originalRenderAll();
            applyPlainLanguageUI();
            applyDefaultGraphFocus();
        };
    }

    const originalRenderDashboardStats = typeof renderDashboardStats === "function" ? renderDashboardStats : null;
    if (originalRenderDashboardStats) {
        renderDashboardStats = function (dashboard) {
            originalRenderDashboardStats(dashboard);
            const avgCong = dashboard?.average_congestion || 0;
            const trafficEl = document.getElementById("stat-avg-cong");
            const lossEl = document.getElementById("stat-avg-loss");
            if (trafficEl) trafficEl.textContent = friendlyCongestion(avgCong);
            if (lossEl) lossEl.textContent = `${Math.round(avgCong * 32)} / 100`;
        };
    }

    const originalShowEdgeTooltip = typeof showEdgeTooltip === "function" ? showEdgeTooltip : null;
    if (originalShowEdgeTooltip) {
        showEdgeTooltip = function (event, edge) {
            originalShowEdgeTooltip(event, edge);
            const congEl = document.getElementById("tt-cong");
            const statusEl = document.getElementById("tt-status");
            const labelEl = document.getElementById("tt-cong-label");
            if (labelEl) labelEl.textContent = "How busy";
            if (congEl && userMode === "beginner") congEl.textContent = friendlyCongestion(edge.congestion_score);
            if (statusEl) statusEl.textContent = edge.is_failed ? "Offline" : friendlyCongestion(edge.congestion_score);
        };
    }

    const originalShowNodeTooltip = typeof showNodeTooltip === "function" ? showNodeTooltip : null;
    if (originalShowNodeTooltip) {
        showNodeTooltip = function (event, node) {
            originalShowNodeTooltip(event, node);
            const typeEl = document.getElementById("nt-type");
            const statusEl = document.getElementById("nt-status");
            const typeLabels = {
                generator: "Power plant",
                substation: "Substation",
                consumer: "Consumer"
            };

            if (typeEl) typeEl.textContent = typeLabels[node.type] || node.type;
            if (statusEl) {
                statusEl.textContent = node.id === selectedSource
                    ? "Current source"
                    : node.id === selectedTarget
                        ? "Current destination"
                        : "Available";
            }
        };
    }

    const originalAddTimelineEvent = typeof addTimelineEvent === "function" ? addTimelineEvent : null;
    if (originalAddTimelineEvent) {
        addTimelineEvent = function (message) {
            originalAddTimelineEvent(humanizeTimelineMessage(message));
        };
    }

    window.focusActiveRoute = function () {
        resetGraphView();
        graphZoom = 1.18;
        graphPan = { x: 8, y: 4 };
        if (typeof applyGraphTransform === "function") applyGraphTransform();
        if (typeof showToast === "function") showToast("Centered on the active route.", "info");
    };

    window.addEventListener("DOMContentLoaded", () => {
        simplifyStaticCopy();
        setTimeout(applyDefaultGraphFocus, 300);
    });
})();
