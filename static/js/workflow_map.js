/**
 * Platform Workflow Map (PWM) — D3.js v7 Engine
 * TiOLi AI Exchange
 *
 * Global namespace: PWM
 * 12 sections, force-directed graph with category clustering,
 * minimap, info panel, search, filters, position persistence.
 */

// === SECTION 1: CONSTANTS & DESIGN SYSTEM ===

var STATUS_COLOURS = {
    ACTIVE:      '#028090',
    RESTRICTED:  '#D4A94A',
    INACTIVE:    '#6C757D',
    PLANNED:     '#8fa88b',
    DEPRECATED:  '#C0392B'
};

var CATEGORY_COLOURS = {
    REGISTRATION:  '#028090',
    PAYMENT:       '#D4A94A',
    COMPLIANCE:    '#8fa88b',
    AGENT_SERVICE: '#4A90D9',
    NAVIGATION:    '#AAAAAA',
    API:           '#9B59B6',
    MCP:           '#E67E22'
};

var NODE_SIZES = {
    PAGE:        { width: 120, height: 36 },
    SERVICE:     { width: 140, height: 40 },
    ENDPOINT:    { width: 100, height: 30 },
    FEATURE:     { width: 130, height: 38 },
    INTEGRATION: { width: 150, height: 42 }
};

var FORCE_PARAMS = {
    linkDistance:   80,
    linkStrength:   0.7,
    manyBody:     -150,
    collideRadius:  50
};

var CANVAS_BG       = '#0A1520';
var ZOOM_MIN        = 0.2;
var ZOOM_MAX        = 4.0;
var CLUSTER_STRENGTH = 0.08;
var SIM_TICKS       = 300;
var POLL_INTERVAL   = 60000;
var TOOLTIP_DELAY   = 400;

var ALL_CATEGORIES = ['REGISTRATION', 'PAYMENT', 'COMPLIANCE', 'AGENT_SERVICE', 'NAVIGATION', 'API', 'MCP'];
var ALL_STATUSES   = ['ACTIVE', 'RESTRICTED', 'INACTIVE', 'PLANNED', 'DEPRECATED'];


// === SECTION 2: STATE MANAGEMENT ===

var state = {
    graphData:        null,
    selectedNodeId:   null,
    activeCategories: new Set(ALL_CATEGORIES),
    activeStatuses:   new Set(ALL_STATUSES),
    searchQuery:      '',
    criticalPathsOnly: false,
    zoomTransform:    null,
    simulation:       null,
    tooltipTimer:     null,
    pollHandle:       null,
    svgWidth:         0,
    svgHeight:        0
};


// === SECTION 3: DATA FETCHING ===

function fetchGraph() {
    return fetch('/api/v1/owner/workflow-map/graph', { credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error('Graph fetch failed: ' + res.status);
            return res.json();
        })
        .then(function (data) {
            state.graphData = data;
            renderGraph(data);
            updateStats();
            renderServicesList(data);
            console.log('[PWM] Graph loaded:', data.meta.total_nodes, 'nodes,', data.meta.total_edges, 'edges');
        })
        .catch(function (err) {
            console.error('[PWM] fetchGraph error:', err);
            // Show error visually on canvas
            var wrap = document.getElementById('pwm-canvas-wrap');
            if (wrap) {
                var msg = document.createElement('div');
                msg.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;color:#C0392B;font-size:14px;z-index:5';
                msg.innerHTML = '<div style="font-size:48px;margin-bottom:12px">&#9888;</div><div style="font-weight:600;margin-bottom:8px">Failed to load graph</div><div style="color:#888;font-size:12px">' + err.message + '</div><div style="color:#888;font-size:11px;margin-top:8px">Check browser console (F12) for details</div>';
                wrap.appendChild(msg);
            }
        });
}

function fetchNodeDetail(nodeId) {
    return fetch('/api/v1/owner/workflow-map/node/' + encodeURIComponent(nodeId), { credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error('Node detail fetch failed: ' + res.status);
            return res.json();
        });
}

function fetchStatusSummary() {
    return fetch('/api/v1/owner/workflow-map/status-summary', { credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error('Status summary fetch failed: ' + res.status);
            return res.json();
        })
        .then(function (summary) {
            updateStatsBar(summary);
        })
        .catch(function (err) {
            console.error('[PWM] fetchStatusSummary error:', err);
        });
}

function startPolling() {
    if (state.pollHandle) clearInterval(state.pollHandle);
    state.pollHandle = setInterval(fetchStatusSummary, POLL_INTERVAL);
}

function updateStats() {
    if (!state.graphData) return;
    var counts = {};
    ALL_STATUSES.forEach(function (s) { counts[s] = 0; });
    state.graphData.nodes.forEach(function (n) {
        if (counts[n.status] !== undefined) counts[n.status]++;
    });
    ALL_STATUSES.forEach(function (s) {
        var el = document.getElementById('pwm-count-' + s.toLowerCase());
        if (el) el.textContent = counts[s];
    });
}

function updateStatsBar(summary) {
    if (!summary || !summary.by_status) return;
    Object.keys(summary.by_status).forEach(function (s) {
        var el = document.getElementById('pwm-count-' + s.toLowerCase());
        if (el) el.textContent = summary.by_status[s];
    });
    var lastEl = document.getElementById('pwm-last-change');
    if (lastEl && summary.last_status_change) {
        lastEl.textContent = summary.last_status_change;
    }
}


// === SECTION 4: D3 SETUP ===

var svg, graphGroup, zoomBehaviour, minimapSvg, minimapGroup, minimapViewport;

function init() {
    var container = document.getElementById('pwm-svg');
    if (!container) {
        console.error('[PWM] #pwm-svg element not found');
        return;
    }

    var rect = container.getBoundingClientRect();
    // If SVG has no dimensions yet (flex layout not computed), use parent or fallback
    state.svgWidth  = rect.width  || (container.parentElement ? container.parentElement.clientWidth : 0) || 1200;
    state.svgHeight = rect.height || (container.parentElement ? container.parentElement.clientHeight : 0) || 800;
    if (state.svgWidth < 100) state.svgWidth = 1200;
    if (state.svgHeight < 100) state.svgHeight = 800;

    svg = d3.select('#pwm-svg')
        .attr('width', state.svgWidth)
        .attr('height', state.svgHeight)
        .style('background', CANVAS_BG);

    // Defs: arrow markers per category colour
    var defs = svg.append('defs');
    Object.keys(CATEGORY_COLOURS).forEach(function (cat) {
        var colour = CATEGORY_COLOURS[cat];
        defs.append('marker')
            .attr('id', 'arrow-' + cat)
            .attr('viewBox', '0 0 10 6')
            .attr('refX', 10)
            .attr('refY', 3)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,0 L10,3 L0,6 Z')
            .attr('fill', colour);
    });

    // Main graph group (zoom container)
    graphGroup = svg.append('g').attr('class', 'pwm-graph');

    // Zoom behaviour
    zoomBehaviour = d3.zoom()
        .scaleExtent([ZOOM_MIN, ZOOM_MAX])
        .on('zoom', function (event) {
            state.zoomTransform = event.transform;
            graphGroup.attr('transform', event.transform);
            updateMinimapViewport();
        });
    svg.call(zoomBehaviour);

    // Canvas click (deselect)
    svg.on('click', onCanvasClick);

    // Search input
    var searchInput = document.getElementById('pwm-search');
    if (searchInput) {
        searchInput.addEventListener('input', onSearch);
    }

    // Escape key closes info panel
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeInfoPanel();
    });

    // Minimap setup
    initMinimap();

    // Fetch initial data
    fetchGraph();
    fetchStatusSummary();
}


// === SECTION 5: RENDER PIPELINE ===

function renderGraph(data) {
    if (!data || !data.nodes || !data.edges) return;

    var nodes = data.nodes;
    var edges = data.edges;

    // Apply stored positions
    var stored = loadPositions();
    applyStoredPositions(nodes, stored);

    // --- Edges ---
    var edgeSelection = graphGroup.selectAll('.pwm-edge')
        .data(edges, function (d) { return d.id; });

    edgeSelection.exit().remove();

    var edgeEnter = edgeSelection.enter()
        .append('path')
        .attr('class', 'pwm-edge')
        .attr('fill', 'none');

    var edgeMerge = edgeEnter.merge(edgeSelection);

    edgeMerge.each(function (d) {
        var el = d3.select(this);
        var colour = getCategoryColourForEdge(d);
        var width  = d.is_critical_path ? 3 : 1.5;
        var dash   = '';
        if (d.flow_type === 'COMPLIANCE') dash = '6,3';
        else if (d.flow_type === 'NAVIGATION') dash = '2,4';

        el.attr('stroke', colour)
          .attr('stroke-width', width)
          .attr('stroke-dasharray', dash)
          .attr('opacity', 0.7);

        // Arrow for directed edges
        if (d.direction === 'DIRECTED' || d.direction === 'forward' || d.direction === 'directed') {
            var cat = getCategoryForEdge(d);
            el.attr('marker-end', 'url(#arrow-' + cat + ')');
        } else {
            el.attr('marker-end', null);
        }
    });

    // --- Nodes ---
    var nodeSelection = graphGroup.selectAll('.pwm-node')
        .data(nodes, function (d) { return d.id; });

    nodeSelection.exit().remove();

    var nodeEnter = nodeSelection.enter()
        .append('g')
        .attr('class', 'pwm-node')
        .style('cursor', 'pointer')
        .on('click', onNodeClick)
        .on('mouseenter', onNodeHover)
        .on('mouseleave', onNodeHoverOut)
        .call(d3.drag()
            .on('start', onDragStart)
            .on('drag', onDragDrag)
            .on('end', onDragEnd)
        );

    // Background rect
    nodeEnter.append('rect')
        .attr('class', 'pwm-node-rect')
        .attr('rx', 6)
        .attr('ry', 6);

    // Status dot
    nodeEnter.append('circle')
        .attr('class', 'pwm-node-dot')
        .attr('r', 3);

    // Label text
    nodeEnter.append('text')
        .attr('class', 'pwm-node-label')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('font-size', 11)
        .attr('font-family', 'Inter, sans-serif')
        .attr('pointer-events', 'none');

    var nodeMerge = nodeEnter.merge(nodeSelection);

    // Update all node visuals
    nodeMerge.each(function (d) {
        var g    = d3.select(this);
        var size = getNodeSize(d.node_type);
        var sCol = getStatusColour(d.status);
        var isDimmed = (d.status === 'INACTIVE' || d.status === 'PLANNED');
        var isDeprecated = (d.status === 'DEPRECATED');

        // Rect
        g.select('.pwm-node-rect')
            .attr('width', size.width)
            .attr('height', size.height)
            .attr('x', -size.width / 2)
            .attr('y', -size.height / 2)
            .attr('fill', sCol)
            .attr('fill-opacity', isDimmed ? 0.35 : 0.85)
            .attr('stroke', sCol)
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', isDimmed ? '4,2' : 'none');

        // Status dot (left edge)
        g.select('.pwm-node-dot')
            .attr('cx', -size.width / 2 + 8)
            .attr('cy', 0)
            .attr('fill', sCol)
            .attr('stroke', '#fff')
            .attr('stroke-width', 0.5);

        // Label
        var maxChars = Math.floor(size.width / 7);
        var labelText = truncateLabel(d.label, maxChars);
        var textColour = '#ffffff';
        if (d.status === 'INACTIVE')   textColour = '#999999';
        if (d.status === 'PLANNED')    textColour = '#8fa88b';

        g.select('.pwm-node-label')
            .text(labelText)
            .attr('fill', textColour)
            .attr('text-decoration', isDeprecated ? 'line-through' : 'none');
    });

    // Store references for simulation
    state._nodeMerge = nodeMerge;
    state._edgeMerge = edgeMerge;
    state._nodes     = nodes;
    state._edges     = edges;

    // Start simulation
    setupSimulation(nodes, edges);
    renderMinimap();
}

function applyFilters() {
    if (!state.graphData) return;

    var nodes = state.graphData.nodes;
    var edges = state.graphData.edges;
    var query = state.searchQuery.toLowerCase();

    // Determine visible node IDs
    var visibleNodeIds = new Set();
    nodes.forEach(function (n) {
        var catMatch    = state.activeCategories.has(n.category);
        var statusMatch = state.activeStatuses.has(n.status);
        var searchMatch = !query || n.label.toLowerCase().indexOf(query) !== -1
                          || (n.description && n.description.toLowerCase().indexOf(query) !== -1);
        if (catMatch && statusMatch && searchMatch) {
            visibleNodeIds.add(n.id);
        }
    });

    // Critical paths filter
    if (state.criticalPathsOnly) {
        var cpNodeIds = new Set();
        edges.forEach(function (e) {
            if (e.is_critical_path) {
                cpNodeIds.add(e.source.id || e.source);
                cpNodeIds.add(e.target.id || e.target);
            }
        });
        // Intersect
        var filtered = new Set();
        visibleNodeIds.forEach(function (id) {
            if (cpNodeIds.has(id)) filtered.add(id);
        });
        visibleNodeIds = filtered;
    }

    // Apply opacity to nodes — interrupt any existing transition first
    graphGroup.selectAll('.pwm-node')
        .interrupt()
        .transition().duration(300)
        .attr('opacity', function (d) {
            return visibleNodeIds.has(d.id) ? 1.0 : 0.15;
        })
        .each(function (d) {
            // Search highlight: gold border
            var g = d3.select(this);
            if (query && d.label.toLowerCase().indexOf(query) !== -1) {
                g.select('.pwm-node-rect')
                    .transition().duration(300)
                    .attr('stroke', '#D4A94A')
                    .attr('stroke-width', 2.5);
            } else {
                g.select('.pwm-node-rect')
                    .transition().duration(300)
                    .attr('stroke', getStatusColour(d.status))
                    .attr('stroke-width', 1.5);
            }
        });

    // Apply opacity to edges — also check flow_type against active categories
    graphGroup.selectAll('.pwm-edge')
        .interrupt()
        .transition().duration(300)
        .attr('opacity', function (d) {
            var srcId = d.source.id || d.source;
            var tgtId = d.target.id || d.target;
            var catVisible = state.activeCategories.has(d.flow_type);
            return (catVisible && visibleNodeIds.has(srcId) && visibleNodeIds.has(tgtId)) ? 0.7 : 0.05;
        });
}

function getCategoryForEdge(d) {
    // Derive category from source node
    if (d.source && d.source.category) return d.source.category;
    if (state.graphData) {
        var srcId = d.source.id || d.source;
        var found = state.graphData.nodes.find(function (n) { return n.id === srcId; });
        if (found) return found.category;
    }
    return 'NAVIGATION';
}

function getCategoryColourForEdge(d) {
    return CATEGORY_COLOURS[getCategoryForEdge(d)] || '#AAAAAA';
}


// === SECTION 6: FORCE SIMULATION ===

function setupSimulation(nodes, edges) {
    if (state.simulation) state.simulation.stop();

    var width  = state.svgWidth;
    var height = state.svgHeight;

    state.simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges)
            .id(function (d) { return d.id; })
            .distance(FORCE_PARAMS.linkDistance)
            .strength(FORCE_PARAMS.linkStrength)
        )
        .force('charge', d3.forceManyBody()
            .strength(FORCE_PARAMS.manyBody)
        )
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide(FORCE_PARAMS.collideRadius))
        .force('cluster', clusterForce(nodes))
        .alphaTarget(0)
        .alphaDecay(0.02)
        .on('tick', onSimulationTick);

    // Run initial ticks
    for (var i = 0; i < SIM_TICKS; i++) {
        state.simulation.tick();
    }
    state.simulation.stop();
    onSimulationTick();
}

function clusterForce(nodes) {
    // Custom force: nudge nodes toward their category centroid
    return function (alpha) {
        // Compute centroids per category
        var centroids = {};
        var counts    = {};
        nodes.forEach(function (n) {
            if (!centroids[n.category]) {
                centroids[n.category] = { x: 0, y: 0 };
                counts[n.category] = 0;
            }
            centroids[n.category].x += n.x || 0;
            centroids[n.category].y += n.y || 0;
            counts[n.category]++;
        });
        Object.keys(centroids).forEach(function (cat) {
            if (counts[cat] > 0) {
                centroids[cat].x /= counts[cat];
                centroids[cat].y /= counts[cat];
            }
        });

        // Nudge each node toward its category centroid
        var strength = CLUSTER_STRENGTH * alpha;
        nodes.forEach(function (n) {
            var c = centroids[n.category];
            if (c) {
                n.vx += (c.x - n.x) * strength;
                n.vy += (c.y - n.y) * strength;
            }
        });
    };
}

function onSimulationTick() {
    if (!state._nodeMerge || !state._edgeMerge) return;

    // Update node positions
    state._nodeMerge.attr('transform', function (d) {
        return 'translate(' + d.x + ',' + d.y + ')';
    });

    // Update edge paths (cubic bezier)
    state._edgeMerge.attr('d', function (d) {
        var sx = d.source.x || 0;
        var sy = d.source.y || 0;
        var tx = d.target.x || 0;
        var ty = d.target.y || 0;
        var mx = (sx + tx) / 2;
        return 'M' + sx + ',' + sy
             + ' C' + mx + ',' + sy
             + ' ' + mx + ',' + ty
             + ' ' + tx + ',' + ty;
    });

    // Update minimap
    renderMinimapNodes();
}


// === SECTION 7: INTERACTION HANDLERS ===

function onNodeClick(event, d) {
    event.stopPropagation();

    state.selectedNodeId = d.id;

    // Build set of connected node IDs
    var connectedIds = new Set();
    connectedIds.add(d.id);
    if (state.graphData) {
        state.graphData.edges.forEach(function (e) {
            var srcId = e.source.id || e.source;
            var tgtId = e.target.id || e.target;
            if (srcId === d.id) connectedIds.add(tgtId);
            if (tgtId === d.id) connectedIds.add(srcId);
        });
    }

    // Highlight selected node
    graphGroup.selectAll('.pwm-node')
        .transition().duration(200)
        .attr('opacity', function (n) {
            return connectedIds.has(n.id) ? 1.0 : 0.2;
        })
        .each(function (n) {
            d3.select(this).select('.pwm-node-rect')
                .transition().duration(200)
                .attr('stroke', n.id === d.id ? '#ffffff' : getStatusColour(n.status))
                .attr('stroke-width', n.id === d.id ? 3 : 1.5);
        });

    // Highlight connected edges
    graphGroup.selectAll('.pwm-edge')
        .transition().duration(200)
        .attr('opacity', function (e) {
            var srcId = e.source.id || e.source;
            var tgtId = e.target.id || e.target;
            return (srcId === d.id || tgtId === d.id) ? 1.0 : 0.1;
        })
        .attr('stroke-width', function (e) {
            var srcId = e.source.id || e.source;
            var tgtId = e.target.id || e.target;
            return (srcId === d.id || tgtId === d.id) ? 2 : (e.is_critical_path ? 3 : 1.5);
        });

    // Fetch detail and open panel
    fetchNodeDetail(d.id).then(function (detail) {
        openInfoPanel(detail);
    }).catch(function (err) {
        console.error('[PWM] Node detail error:', err);
    });
}

function onNodeHover(event, d) {
    var el = d3.select(this);
    el.transition().duration(150)
      .attr('transform', 'translate(' + d.x + ',' + d.y + ') scale(1.1)');

    // Tooltip with delay
    clearTimeout(state.tooltipTimer);
    state.tooltipTimer = setTimeout(function () {
        showTooltip(event, d);
    }, TOOLTIP_DELAY);
}

function onNodeHoverOut(event, d) {
    var el = d3.select(this);
    el.transition().duration(150)
      .attr('transform', 'translate(' + d.x + ',' + d.y + ') scale(1)');

    clearTimeout(state.tooltipTimer);
    hideTooltip();
}

function showTooltip(event, d) {
    var tooltip = d3.select('#pwm-tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div')
            .attr('id', 'pwm-tooltip')
            .style('position', 'absolute')
            .style('background', '#1a2a3a')
            .style('border', '1px solid #2a3a4a')
            .style('border-radius', '6px')
            .style('padding', '8px 12px')
            .style('font-size', '12px')
            .style('color', '#ffffff')
            .style('pointer-events', 'none')
            .style('z-index', '10000')
            .style('max-width', '250px');
    }

    var statusBadge = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'
        + getStatusColour(d.status) + ';margin-right:4px;"></span>';
    var desc = d.description ? d.description.split('.')[0] + '.' : '';

    tooltip.html(
        '<strong>' + d.label + '</strong><br>'
        + statusBadge + '<em>' + d.status + '</em> &middot; ' + d.category + '<br>'
        + '<span style="color:#aaa;">' + desc + '</span>'
    )
    .style('left', (event.pageX + 12) + 'px')
    .style('top', (event.pageY - 10) + 'px')
    .style('display', 'block')
    .style('opacity', 1);
}

function hideTooltip() {
    var tooltip = d3.select('#pwm-tooltip');
    if (!tooltip.empty()) {
        tooltip.style('display', 'none').style('opacity', 0);
    }
}

function onDragStart(event, d) {
    if (!event.active && state.simulation) state.simulation.alphaTarget(0.1).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function onDragDrag(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function onDragEnd(event, d) {
    if (!event.active && state.simulation) state.simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
    savePositions();
}

function onCanvasClick(event) {
    // Only act if click is directly on the SVG background
    if (event.target.tagName === 'svg' || event.target === svg.node()) {
        state.selectedNodeId = null;
        resetOpacities();
        closeInfoPanel();
    }
}

function onSearch(event) {
    state.searchQuery = event.target.value || '';
    applyFilters();
}

function resetOpacities() {
    graphGroup.selectAll('.pwm-node')
        .transition().duration(200)
        .attr('opacity', 1.0)
        .each(function (d) {
            d3.select(this).select('.pwm-node-rect')
                .transition().duration(200)
                .attr('stroke', getStatusColour(d.status))
                .attr('stroke-width', 1.5);
        });

    graphGroup.selectAll('.pwm-edge')
        .transition().duration(200)
        .attr('opacity', 0.7)
        .attr('stroke-width', function (e) {
            return e.is_critical_path ? 3 : 1.5;
        });
}


// === SECTION 8: INFO PANEL ===

function openInfoPanel(nodeDetail) {
    var panel = document.getElementById('pwm-info-panel');
    if (!panel || !nodeDetail) return;

    panel.classList.add('open');

    var node = nodeDetail.node || nodeDetail;

    // Status badge
    var badgeEl = panel.querySelector('.pwm-panel-status');
    if (badgeEl) {
        badgeEl.textContent = node.status;
        badgeEl.style.background = getStatusColour(node.status);
        badgeEl.style.color = '#ffffff';
        badgeEl.style.padding = '2px 10px';
        badgeEl.style.borderRadius = '12px';
        badgeEl.style.fontSize = '11px';
    }

    // Label
    var labelEl = panel.querySelector('.pwm-panel-label');
    if (labelEl) labelEl.textContent = node.label || '';

    // Description
    var descEl = panel.querySelector('.pwm-panel-description');
    if (descEl) descEl.textContent = node.description || '';

    // Details grid
    var detailsEl = panel.querySelector('.pwm-panel-details');
    if (detailsEl) {
        var meta = node.metadata || {};
        detailsEl.innerHTML =
            '<div class="pwm-detail-row"><span>Category</span><span>' + (node.category || '-') + '</span></div>' +
            '<div class="pwm-detail-row"><span>Node Type</span><span>' + (node.node_type || '-') + '</span></div>' +
            '<div class="pwm-detail-row"><span>Feature Flag</span><span>' + (node.feature_flag || '-') + '</span></div>' +
            '<div class="pwm-detail-row"><span>Build Phase</span><span>' + (meta.build_phase || '-') + '</span></div>' +
            '<div class="pwm-detail-row"><span>Module</span><span>' + (meta.module || '-') + '</span></div>';
    }

    // Linked endpoints as chips
    var endpointsEl = panel.querySelector('.pwm-panel-endpoints');
    if (endpointsEl) {
        var endpoints = node.linked_endpoints || [];
        if (endpoints.length > 0) {
            endpointsEl.innerHTML = endpoints.map(function (ep) {
                return '<span class="pwm-chip">' + ep + '</span>';
            }).join(' ');
        } else {
            endpointsEl.innerHTML = '<span style="color:#666;">None</span>';
        }
    }

    // "Go There" button
    var goBtn = panel.querySelector('.pwm-panel-go');
    if (goBtn) {
        if (node.url_path && node.status === 'ACTIVE') {
            goBtn.style.display = 'inline-block';
            goBtn.href = node.url_path;
        } else {
            goBtn.style.display = 'none';
        }
    }

    // Status history (last 3)
    var historyEl = panel.querySelector('.pwm-panel-history');
    if (historyEl && nodeDetail.status_history) {
        var history = nodeDetail.status_history.slice(0, 3);
        if (history.length > 0) {
            historyEl.innerHTML = history.map(function (h) {
                return '<div class="pwm-history-entry">'
                    + '<span class="pwm-history-dot" style="background:' + getStatusColour(h.status) + ';"></span>'
                    + '<span>' + h.status + '</span>'
                    + '<span style="color:#666;margin-left:8px;">' + (h.changed_at || h.timestamp || '') + '</span>'
                    + '</div>';
            }).join('');
        } else {
            historyEl.innerHTML = '<span style="color:#666;">No history</span>';
        }
    }

    // Status select
    var statusSelect = panel.querySelector('.pwm-panel-status-select');
    if (statusSelect) {
        statusSelect.value = node.status;
    }
}

function closeInfoPanel() {
    var panel = document.getElementById('pwm-info-panel');
    if (panel) panel.classList.remove('open');
    state.selectedNodeId = null;
    resetOpacities();
}


// === SECTION 9: MINIMAP ===

function initMinimap() {
    var container = document.getElementById('pwm-minimap-svg');
    if (!container) return;

    minimapSvg = d3.select('#pwm-minimap-svg')
        .style('background', '#0d1b2a');

    minimapGroup = minimapSvg.append('g').attr('class', 'pwm-minimap-graph');

    // Viewport rectangle
    minimapViewport = minimapSvg.append('rect')
        .attr('class', 'pwm-minimap-viewport')
        .attr('fill', 'rgba(255,255,255,0.08)')
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 1)
        .attr('rx', 2);

    // Click on minimap to pan
    minimapSvg.on('click', onMinimapClick);

    // Drag viewport
    minimapViewport.call(
        d3.drag()
            .on('drag', onMinimapDrag)
    );
}

function renderMinimap() {
    if (!minimapGroup || !state.graphData) return;

    var mmWidth  = 200;
    var mmHeight = 140;
    var nodes = state.graphData.nodes;
    var edges = state.graphData.edges;

    // Compute bounds
    var bounds = computeNodeBounds(nodes);
    if (!bounds) return;

    var scaleX = mmWidth / (bounds.maxX - bounds.minX + 100);
    var scaleY = mmHeight / (bounds.maxY - bounds.minY + 100);
    var scale  = Math.min(scaleX, scaleY, 1);

    var offsetX = (mmWidth - (bounds.maxX - bounds.minX) * scale) / 2 - bounds.minX * scale;
    var offsetY = (mmHeight - (bounds.maxY - bounds.minY) * scale) / 2 - bounds.minY * scale;

    minimapGroup.attr('transform', 'translate(' + offsetX + ',' + offsetY + ') scale(' + scale + ')');

    // Edges
    var edgeSel = minimapGroup.selectAll('.pwm-mm-edge')
        .data(edges, function (d) { return d.id; });
    edgeSel.exit().remove();
    edgeSel.enter()
        .append('line')
        .attr('class', 'pwm-mm-edge')
        .merge(edgeSel)
        .attr('stroke-width', 0.5 / scale)
        .each(function (d) {
            var cat = getCategoryForEdge(d);
            d3.select(this).attr('stroke', CATEGORY_COLOURS[cat] || '#AAAAAA');
        });

    // Nodes
    var nodeSel = minimapGroup.selectAll('.pwm-mm-node')
        .data(nodes, function (d) { return d.id; });
    nodeSel.exit().remove();
    nodeSel.enter()
        .append('circle')
        .attr('class', 'pwm-mm-node')
        .attr('r', 3 / scale)
        .merge(nodeSel)
        .each(function (d) {
            d3.select(this).attr('fill', getStatusColour(d.status));
        });

    renderMinimapNodes();
    updateMinimapViewport();

    // Store minimap scale info for viewport calculations
    state._mmScale  = scale;
    state._mmOffX   = offsetX;
    state._mmOffY   = offsetY;
}

function renderMinimapNodes() {
    if (!minimapGroup) return;

    minimapGroup.selectAll('.pwm-mm-node')
        .attr('cx', function (d) { return d.x || 0; })
        .attr('cy', function (d) { return d.y || 0; });

    minimapGroup.selectAll('.pwm-mm-edge')
        .attr('x1', function (d) { return (d.source.x || 0); })
        .attr('y1', function (d) { return (d.source.y || 0); })
        .attr('x2', function (d) { return (d.target.x || 0); })
        .attr('y2', function (d) { return (d.target.y || 0); });
}

function updateMinimapViewport() {
    if (!minimapViewport || !state._mmScale) return;

    var t = state.zoomTransform || d3.zoomIdentity;
    var scale  = state._mmScale;
    var offX   = state._mmOffX;
    var offY   = state._mmOffY;

    // Inverse transform: visible area in graph coords
    var vx = -t.x / t.k;
    var vy = -t.y / t.k;
    var vw = state.svgWidth / t.k;
    var vh = state.svgHeight / t.k;

    minimapViewport
        .attr('x', vx * scale + offX)
        .attr('y', vy * scale + offY)
        .attr('width', vw * scale)
        .attr('height', vh * scale);
}

function onMinimapClick(event) {
    if (!svg || !state._mmScale) return;
    var coords = d3.pointer(event, minimapSvg.node());
    var scale  = state._mmScale;
    var offX   = state._mmOffX;
    var offY   = state._mmOffY;

    // Convert minimap coords to graph coords
    var gx = (coords[0] - offX) / scale;
    var gy = (coords[1] - offY) / scale;

    // Center main canvas on this point
    var t = state.zoomTransform || d3.zoomIdentity;
    var newX = state.svgWidth / 2 - gx * t.k;
    var newY = state.svgHeight / 2 - gy * t.k;

    svg.transition().duration(400)
       .call(zoomBehaviour.transform, d3.zoomIdentity.translate(newX, newY).scale(t.k));
}

function onMinimapDrag(event) {
    if (!svg || !state._mmScale) return;
    var scale = state._mmScale;
    var t = state.zoomTransform || d3.zoomIdentity;

    var dx = event.dx / scale;
    var dy = event.dy / scale;

    var newX = (t.x || 0) - dx * t.k;
    var newY = (t.y || 0) - dy * t.k;

    svg.call(zoomBehaviour.transform, d3.zoomIdentity.translate(newX, newY).scale(t.k));
}


// === SECTION 10: CONTROL PANEL ===

function toggleCategory(el) {
    var cat = el.dataset.category;
    if (!cat) return;

    el.classList.toggle('active');

    if (state.activeCategories.has(cat)) {
        state.activeCategories.delete(cat);
    } else {
        state.activeCategories.add(cat);
    }
    applyFilters();
}

function filterStatus() {
    state.activeStatuses.clear();
    var checkboxes = document.querySelectorAll('#pwm-status-filters input[type=checkbox]');
    checkboxes.forEach(function (cb) {
        if (cb.checked && cb.dataset.status) {
            state.activeStatuses.add(cb.dataset.status);
        }
    });
    applyFilters();
}

function toggleCriticalPaths(el) {
    el.classList.toggle('active');
    state.criticalPathsOnly = el.classList.contains('active');
    applyFilters();
}

function resetView() {
    if (!svg || !zoomBehaviour) return;
    svg.transition().duration(500)
       .call(zoomBehaviour.transform, d3.zoomIdentity);
}

function fitAll() {
    if (!svg || !zoomBehaviour || !state.graphData) return;

    var nodes = state.graphData.nodes;
    var bounds = computeNodeBounds(nodes);
    if (!bounds) return;

    var padding = 60;
    var bw = bounds.maxX - bounds.minX + padding * 2;
    var bh = bounds.maxY - bounds.minY + padding * 2;
    var scale = Math.min(state.svgWidth / bw, state.svgHeight / bh, ZOOM_MAX);
    scale = Math.max(scale, ZOOM_MIN);

    var cx = (bounds.minX + bounds.maxX) / 2;
    var cy = (bounds.minY + bounds.maxY) / 2;
    var tx = state.svgWidth / 2 - cx * scale;
    var ty = state.svgHeight / 2 - cy * scale;

    svg.transition().duration(600)
       .call(zoomBehaviour.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

function exportPNG() {
    if (!svg) return;

    var svgNode = svg.node();
    var serializer = new XMLSerializer();
    var svgString  = serializer.serializeToString(svgNode);

    // Ensure xmlns
    if (!svgString.match(/xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
        svgString = svgString.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    }

    var canvas  = document.createElement('canvas');
    var w = state.svgWidth  * 2;  // 2x for retina
    var h = state.svgHeight * 2;
    canvas.width  = w;
    canvas.height = h;

    var ctx = canvas.getContext('2d');
    ctx.fillStyle = CANVAS_BG;
    ctx.fillRect(0, 0, w, h);

    var img  = new Image();
    var blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    var url  = URL.createObjectURL(blob);

    img.onload = function () {
        ctx.drawImage(img, 0, 0, w, h);
        URL.revokeObjectURL(url);

        var dataUrl = canvas.toDataURL('image/png');
        var link    = document.createElement('a');
        link.download = 'tioli-workflow-map.png';
        link.href     = dataUrl;
        link.click();
    };
    img.src = url;
}

function computeNodeBounds(nodes) {
    if (!nodes || nodes.length === 0) return null;
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodes.forEach(function (n) {
        var x = n.x || 0;
        var y = n.y || 0;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
    });
    return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
}


// === SECTION 11: POSITION PERSISTENCE ===

var STORAGE_KEY = 'pwm_node_positions_v1';

function savePositions() {
    if (!state.graphData || !state.graphData.nodes) return;
    var positions = {};
    state.graphData.nodes.forEach(function (n) {
        positions[n.id] = { x: n.x, y: n.y };
    });
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
    } catch (e) {
        console.warn('[PWM] Could not save positions:', e);
    }
}

function loadPositions() {
    try {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (raw) return JSON.parse(raw);
    } catch (e) {
        console.warn('[PWM] Could not load positions:', e);
    }
    return null;
}

function applyStoredPositions(nodes, stored) {
    if (!stored || !nodes) return;
    nodes.forEach(function (n) {
        if (stored[n.id]) {
            n.x = stored[n.id].x;
            n.y = stored[n.id].y;
        }
    });
}


// === SECTION 12A: SERVICES LIST ===

function renderServicesList(data) {
    var container = document.getElementById('pwm-services-list');
    if (!container || !data || !data.nodes) return;

    // Sort by category then label
    var sorted = data.nodes.slice().sort(function (a, b) {
        if (a.category !== b.category) return a.category.localeCompare(b.category);
        return a.label.localeCompare(b.label);
    });

    var currentCat = '';
    var html = '';

    sorted.forEach(function (n) {
        // Category header
        if (n.category !== currentCat) {
            currentCat = n.category;
            var catColour = CATEGORY_COLOURS[currentCat] || '#888';
            html += '<div style="margin-top:12px;margin-bottom:4px;font-size:10px;font-weight:700;color:' + catColour + ';text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:3px">' + currentCat.replace('_', ' ') + '</div>';
        }

        var statusCol = STATUS_COLOURS[n.status] || '#6C757D';
        var link = n.url_path ? ' href="' + n.url_path + '" target="_blank"' : '';
        var linkStyle = n.url_path ? 'color:' + statusCol + ';text-decoration:none;' : 'color:' + statusCol + ';cursor:default;';
        var tag = n.url_path ? 'a' : 'span';

        html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.04)">';
        html += '<span style="width:7px;height:7px;border-radius:50%;background:' + statusCol + ';flex-shrink:0"></span>';
        html += '<' + tag + link + ' style="' + linkStyle + 'flex:1;font-size:11px;line-height:1.3" title="' + n.label + ' — ' + n.status + '">' + n.label + '</' + tag + '>';
        html += '<span style="font-size:10px;color:' + statusCol + ';flex-shrink:0;font-weight:700;min-width:32px;text-align:right;padding-right:4px">' + n.status.substring(0, 3).toUpperCase() + '</span>';
        html += '</div>';
    });

    container.innerHTML = html;
}


// === SECTION 12: UTILITY ===

function getStatusColour(status) {
    return STATUS_COLOURS[status] || STATUS_COLOURS.INACTIVE;
}

function getCategoryColour(category) {
    return CATEGORY_COLOURS[category] || CATEGORY_COLOURS.NAVIGATION;
}

function getNodeSize(nodeType) {
    return NODE_SIZES[nodeType] || NODE_SIZES.PAGE;
}

function truncateLabel(text, maxLen) {
    if (!text) return '';
    maxLen = maxLen || 16;
    if (text.length <= maxLen) return text;
    return text.substring(0, maxLen - 1) + '\u2026';
}


// === INIT & PUBLIC API ===

var PWM = {};

PWM.refresh = function () {
    fetchGraph();
    fetchStatusSummary();
};

PWM.toggleCategory = function (el) {
    toggleCategory(el);
};

PWM.filterStatus = function () {
    filterStatus();
};

PWM.toggleCriticalPaths = function (el) {
    toggleCriticalPaths(el);
};

PWM.resetView = function () {
    resetView();
};

PWM.fitAll = function () {
    fitAll();
};

PWM.exportPNG = function () {
    exportPNG();
};

PWM.closePanel = function () {
    closeInfoPanel();
};

PWM.getState = function () {
    return state;
};

// Expose globally
window.PWM = PWM;

document.addEventListener('DOMContentLoaded', function () {
    init();
    startPolling();
});
