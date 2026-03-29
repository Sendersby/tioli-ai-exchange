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
    MCP:           '#E67E22',
    ROADMAP:       '#7BA7D9'
};

var NODE_SIZES = {
    PAGE:        { width: 120, height: 36 },
    SERVICE:     { width: 140, height: 40 },
    ENDPOINT:    { width: 100, height: 30 },
    FEATURE:     { width: 130, height: 38 },
    INTEGRATION: { width: 150, height: 42 }
};

var FORCE_PARAMS = {
    linkDistance:   100,
    linkStrength:   0.6,
    manyBody:     -350,
    collideRadius:  95
};

var CANVAS_BG       = '#0A1520';

// Zone colours — translucent, won't interfere with existing palette
var ZONE_COLOURS = {
    FRONTEND:  'rgba(119, 212, 229, 0.06)',  // very faint teal
    BACKEND:   'rgba(237, 192, 95, 0.06)',   // very faint gold
    ISOLATED:  'rgba(192, 57, 43, 0.08)',    // very faint red
};
var ZONE_BORDERS = {
    FRONTEND:  'rgba(119, 212, 229, 0.25)',
    BACKEND:   'rgba(237, 192, 95, 0.25)',
    ISOLATED:  'rgba(192, 57, 43, 0.3)',
};

// Frontend nodes: public pages, agent registration, MCP
var FRONTEND_PREFIXES = ['node_nav_', 'node_reg_', 'node_mcp_'];
// Backend nodes: owner dashboard, tools
var BACKEND_PREFIXES = ['node_owner_', 'node_dash_', 'node_tool_'];

function classifyNode(nodeId, edges) {
    // Direct classification by prefix
    var isFrontend = FRONTEND_PREFIXES.some(function(p) { return nodeId.indexOf(p) === 0; });
    var isBackend = BACKEND_PREFIXES.some(function(p) { return nodeId.indexOf(p) === 0; });
    if (isFrontend) return 'FRONTEND';
    if (isBackend) return 'BACKEND';

    // For services/payments/compliance/API/banking — check what they connect to
    var connectsToFrontend = false;
    var connectsToBackend = false;
    edges.forEach(function(e) {
        var src = e.source.id || e.source;
        var tgt = e.target.id || e.target;
        if (src === nodeId || tgt === nodeId) {
            var other = (src === nodeId) ? tgt : src;
            if (FRONTEND_PREFIXES.some(function(p) { return other.indexOf(p) === 0; })) connectsToFrontend = true;
            if (BACKEND_PREFIXES.some(function(p) { return other.indexOf(p) === 0; })) connectsToBackend = true;
        }
    });

    // Nodes connected to both zones appear in BOTH (genuine overlap)
    if (connectsToFrontend && connectsToBackend) return 'BOTH';
    if (connectsToFrontend) return 'FRONTEND';
    if (connectsToBackend) return 'BACKEND';

    // Check if truly isolated (no edges at all)
    var hasEdge = edges.some(function(e) {
        var src = e.source.id || e.source;
        var tgt = e.target.id || e.target;
        return src === nodeId || tgt === nodeId;
    });
    if (!hasEdge) return 'ISOLATED';

    return null;
}
var ZOOM_MIN        = 0.2;
var ZOOM_MAX        = 4.0;
var CLUSTER_STRENGTH = 0.08;
var SIM_TICKS       = 300;
var POLL_INTERVAL   = 60000;
var TOOLTIP_DELAY   = 400;

var ALL_CATEGORIES = ['REGISTRATION', 'PAYMENT', 'COMPLIANCE', 'AGENT_SERVICE', 'NAVIGATION', 'API', 'MCP', 'ROADMAP'];
var ALL_STATUSES   = ['ACTIVE', 'RESTRICTED', 'INACTIVE', 'PLANNED', 'DEPRECATED'];


// === SECTION 2: STATE MANAGEMENT ===

var state = {
    graphData:        null,
    selectedNodeId:   null,
    activeCategories: new Set(ALL_CATEGORIES),
    activeStatuses:   new Set(ALL_STATUSES),
    hiddenNodes:      new Set(),
    zonesVisible:     { FRONTEND: false, BACKEND: false, ISOLATED: false },
    enrichment:       null,
    showHeatmap:      false,
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
            fetchEnrichment();
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

function fetchEnrichment() {
    return fetch('/api/v1/owner/workflow-map/enrichment', { credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error('Enrichment fetch failed: ' + res.status);
            return res.json();
        })
        .then(function (data) {
            state.enrichment = data;
            applyEnrichment();
            console.log('[PWM] Enrichment loaded:', Object.keys(data.nodes || {}).length, 'nodes enriched');
        })
        .catch(function (err) {
            console.error('[PWM] fetchEnrichment error:', err);
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
        // Roadmap nodes use blue instead of status colour
        var sCol = d.category === 'ROADMAP' ? '#7BA7D9' : getStatusColour(d.status);
        var isDimmed = (d.status === 'INACTIVE' || (d.status === 'PLANNED' && d.category !== 'ROADMAP'));
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

        // Label — wrap into multiple lines
        var maxCharsPerLine = Math.floor((size.width - 20) / 6);
        var lines = wrapText(d.label, maxCharsPerLine);
        var textColour = '#ffffff';
        if (d.status === 'INACTIVE')   textColour = '#999999';
        if (d.status === 'PLANNED')    textColour = '#8fa88b';

        var lineHeight = 12;
        var totalHeight = lines.length * lineHeight;

        // Resize rect to fit wrapped text
        var newHeight = Math.max(size.height, totalHeight + 14);
        g.select('.pwm-node-rect')
            .attr('height', newHeight)
            .attr('y', -newHeight / 2);
        g.select('.pwm-node-dot')
            .attr('cy', 0);

        // Clear old tspans and rebuild
        var labelEl = g.select('.pwm-node-label');
        labelEl.selectAll('tspan').remove();
        labelEl.text(null)
            .attr('fill', textColour)
            .attr('text-decoration', isDeprecated ? 'line-through' : 'none');

        var startY = -(totalHeight / 2) + lineHeight / 2;
        lines.forEach(function (line, i) {
            labelEl.append('tspan')
                .attr('x', 0)
                .attr('dy', i === 0 ? startY : lineHeight)
                .text(line);
        });
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
        var notHidden = !state.hiddenNodes.has(n.id);
        if (catMatch && statusMatch && searchMatch && notHidden) {
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
        .force('x', d3.forceX(width / 2).strength(0.05))
        .force('y', d3.forceY(height / 2).strength(0.05))
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

    // Update zone hulls
    renderZones();
}

function renderZones() {
    if (!state.graphData || !graphGroup) return;

    var nodes = state.graphData.nodes;
    var edges = state.graphData.edges;

    // Classify nodes into zones
    var zones = { FRONTEND: [], BACKEND: [], ISOLATED: [] };
    nodes.forEach(function (n) {
        if (!n.x && n.x !== 0) return;
        var zone = classifyNode(n.id, edges);
        if (zone === 'BOTH') {
            zones.FRONTEND.push(n);
            zones.BACKEND.push(n);
        } else if (zone && zones[zone]) {
            zones[zone].push(n);
        }
    });

    // Also find truly isolated nodes (no edges at all)
    var connectedIds = new Set();
    edges.forEach(function (e) {
        connectedIds.add(e.source.id || e.source);
        connectedIds.add(e.target.id || e.target);
    });
    nodes.forEach(function (n) {
        if (!connectedIds.has(n.id) && n.x) {
            // Remove from other zones, add to isolated
            zones.FRONTEND = zones.FRONTEND.filter(function(fn) { return fn.id !== n.id; });
            zones.BACKEND = zones.BACKEND.filter(function(fn) { return fn.id !== n.id; });
            if (!zones.ISOLATED.some(function(fn) { return fn.id === n.id; })) {
                zones.ISOLATED.push(n);
            }
        }
    });

    // Remove old zones
    graphGroup.selectAll('.pwm-zone').remove();

    // Create zone group BEHIND everything else
    var zoneGroup = graphGroup.insert('g', ':first-child').attr('class', 'pwm-zones-container');

    ['FRONTEND', 'BACKEND', 'ISOLATED'].forEach(function (zoneKey) {
        if (!state.zonesVisible[zoneKey]) return;
        var zoneNodes = zones[zoneKey];
        if (zoneNodes.length < 1) return;

        if (zoneKey === 'ISOLATED') {
            // Individual highlight per isolated node
            zoneNodes.forEach(function (n) {
                var size = getNodeSize(n.node_type);
                var pad = 12;
                zoneGroup.append('rect')
                    .attr('class', 'pwm-zone')
                    .attr('x', n.x - size.width / 2 - pad)
                    .attr('y', n.y - size.height / 2 - pad)
                    .attr('width', size.width + pad * 2)
                    .attr('height', size.height + pad * 2)
                    .attr('rx', 8)
                    .attr('ry', 8)
                    .attr('fill', ZONE_COLOURS.ISOLATED)
                    .attr('stroke', ZONE_BORDERS.ISOLATED)
                    .attr('stroke-width', 1.5)
                    .attr('stroke-dasharray', '4,3')
                    .attr('pointer-events', 'none');
            });
        } else {
            // Convex hull wrapping tightly around zone nodes
            var pad = 35;
            // Generate points around each node's bounding box corners
            var hullPoints = [];
            zoneNodes.forEach(function (n) {
                var size = getNodeSize(n.node_type);
                var hw = size.width / 2 + pad;
                var hh = size.height / 2 + pad;
                // 8 points per node (corners + midpoints) for smoother hull
                hullPoints.push([n.x - hw, n.y - hh]);
                hullPoints.push([n.x + hw, n.y - hh]);
                hullPoints.push([n.x - hw, n.y + hh]);
                hullPoints.push([n.x + hw, n.y + hh]);
                hullPoints.push([n.x, n.y - hh]);
                hullPoints.push([n.x, n.y + hh]);
                hullPoints.push([n.x - hw, n.y]);
                hullPoints.push([n.x + hw, n.y]);
            });

            var hull = d3.polygonHull(hullPoints);
            if (hull && hull.length > 2) {
                // Smooth the hull into a curved path
                var hullPath = 'M' + hull.map(function(p) { return p[0] + ',' + p[1]; }).join(' L') + ' Z';

                zoneGroup.append('path')
                    .attr('class', 'pwm-zone')
                    .attr('d', hullPath)
                    .attr('fill', ZONE_COLOURS[zoneKey])
                    .attr('stroke', ZONE_BORDERS[zoneKey])
                    .attr('stroke-width', 1.5)
                    .attr('stroke-dasharray', '8,4')
                    .attr('stroke-linejoin', 'round')
                    .attr('pointer-events', 'none');

                // Label placement: Frontend bottom-right, Backend top-left
                var hMinX = Infinity, hMinY = Infinity, hMaxX = -Infinity, hMaxY = -Infinity;
                hull.forEach(function(p) {
                    if (p[0] < hMinX) hMinX = p[0];
                    if (p[1] < hMinY) hMinY = p[1];
                    if (p[0] > hMaxX) hMaxX = p[0];
                    if (p[1] > hMaxY) hMaxY = p[1];
                });
                var labels = { FRONTEND: 'FRONTEND', BACKEND: 'BACKEND (OWNER)' };
                var labelColours = { FRONTEND: 'rgba(119,212,229,0.6)', BACKEND: 'rgba(237,192,95,0.6)' };
                var lx = zoneKey === 'FRONTEND' ? hMaxX - 80 : hMinX + 10;
                var ly = zoneKey === 'FRONTEND' ? hMaxY - 8 : hMinY + 16;
                zoneGroup.append('text')
                    .attr('class', 'pwm-zone')
                    .attr('x', lx)
                    .attr('y', ly)
                    .attr('font-size', 11)
                    .attr('font-weight', 700)
                    .attr('letter-spacing', '2px')
                    .attr('fill', labelColours[zoneKey])
                    .attr('pointer-events', 'none')
                    .text(labels[zoneKey]);
            }
        }
    });
}

function applyEnrichment() {
    if (!state.enrichment || !state.enrichment.nodes || !graphGroup) return;
    var enr = state.enrichment.nodes;

    graphGroup.selectAll('.pwm-node').each(function (d) {
        var g = d3.select(this);
        var e = enr[d.id];
        if (!e) return;

        var size = getNodeSize(d.node_type);
        var rectH = parseFloat(g.select('.pwm-node-rect').attr('height')) || size.height;

        // Remove old enrichment elements
        g.selectAll('.pwm-enrich').remove();

        // 1. Health indicator — pulsing dot top-right
        if (e.health && e.health !== 'unknown') {
            var hCol = e.health === 'green' ? '#4ade80' : (e.health === 'amber' ? '#f59e0b' : '#ef4444');
            g.append('circle')
                .attr('class', 'pwm-enrich')
                .attr('cx', size.width / 2 - 6)
                .attr('cy', -rectH / 2 + 6)
                .attr('r', 4)
                .attr('fill', hCol)
                .attr('stroke', '#0A1520')
                .attr('stroke-width', 1);
        }

        // 2. Traffic heatmap — glow intensity on node rect
        if (state.showHeatmap && e.traffic_heat > 0) {
            var glow = Math.min(e.traffic_heat * 15, 12);
            g.select('.pwm-node-rect')
                .attr('filter', null)
                .style('box-shadow', null);
            // Use stroke glow effect
            g.insert('rect', '.pwm-node-rect')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2 - 3)
                .attr('y', -rectH / 2 - 3)
                .attr('width', size.width + 6)
                .attr('height', rectH + 6)
                .attr('rx', 8)
                .attr('fill', 'none')
                .attr('stroke', 'rgba(119,212,229,' + Math.min(e.traffic_heat + 0.2, 0.8) + ')')
                .attr('stroke-width', glow)
                .attr('pointer-events', 'none');
        }

        // 3. Revenue badge — bottom-left, gold
        if (e.revenue > 0) {
            var revText = e.revenue >= 1000 ? Math.round(e.revenue / 1000) + 'k' : Math.round(e.revenue);
            g.append('rect')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2)
                .attr('y', rectH / 2 - 2)
                .attr('width', 32)
                .attr('height', 14)
                .attr('rx', 3)
                .attr('fill', '#D4A94A')
                .attr('pointer-events', 'none');
            g.append('text')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2 + 16)
                .attr('y', rectH / 2 + 9)
                .attr('text-anchor', 'middle')
                .attr('font-size', 8)
                .attr('font-weight', 700)
                .attr('fill', '#0D1B2A')
                .attr('pointer-events', 'none')
                .text(revText + '₳');
        }

        // 4. Build phase badge — top-left
        if (e.build_phase) {
            g.append('rect')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2)
                .attr('y', -rectH / 2 - 14)
                .attr('width', 20)
                .attr('height', 13)
                .attr('rx', 3)
                .attr('fill', '#8fa88b')
                .attr('pointer-events', 'none');
            g.append('text')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2 + 10)
                .attr('y', -rectH / 2 - 4)
                .attr('text-anchor', 'middle')
                .attr('font-size', 8)
                .attr('font-weight', 700)
                .attr('fill', '#0D1B2A')
                .attr('pointer-events', 'none')
                .text('P' + e.build_phase);
        }

        // 5. Dependency warning — amber border flash
        if (e.has_dependency_warning) {
            g.append('rect')
                .attr('class', 'pwm-enrich')
                .attr('x', -size.width / 2 - 2)
                .attr('y', -rectH / 2 - 2)
                .attr('width', size.width + 4)
                .attr('height', rectH + 4)
                .attr('rx', 7)
                .attr('fill', 'none')
                .attr('stroke', '#f59e0b')
                .attr('stroke-width', 2)
                .attr('stroke-dasharray', '4,2')
                .attr('pointer-events', 'none')
                .attr('opacity', 0.7);
        }

        // 6. Last activity — shown in tooltip (handled by hover, stored in enrichment)

        // 7. Agent count badge — bottom-right, teal
        if (e.agent_count > 0) {
            var acText = e.agent_count >= 1000 ? Math.round(e.agent_count / 1000) + 'k' : e.agent_count;
            var acWidth = String(acText).length * 6 + 16;
            g.append('rect')
                .attr('class', 'pwm-enrich')
                .attr('x', size.width / 2 - acWidth)
                .attr('y', rectH / 2 - 2)
                .attr('width', acWidth)
                .attr('height', 14)
                .attr('rx', 3)
                .attr('fill', '#028090')
                .attr('pointer-events', 'none');
            g.append('text')
                .attr('class', 'pwm-enrich')
                .attr('x', size.width / 2 - acWidth / 2)
                .attr('y', rectH / 2 + 9)
                .attr('text-anchor', 'middle')
                .attr('font-size', 8)
                .attr('font-weight', 700)
                .attr('fill', '#fff')
                .attr('pointer-events', 'none')
                .text(acText + ' agents');
        }
    });
}

function toggleZone(zoneKey) {
    state.zonesVisible[zoneKey] = !state.zonesVisible[zoneKey];
    renderZones();
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

    // Enrichment extras for tooltip
    var extras = '';
    if (state.enrichment && state.enrichment.nodes && state.enrichment.nodes[d.id]) {
        var e = state.enrichment.nodes[d.id];
        if (e.health && e.health !== 'unknown') {
            var hc = e.health === 'green' ? '#4ade80' : '#ef4444';
            extras += '<br><span style="color:' + hc + '">&#9679;</span> Health: ' + e.health;
        }
        if (e.traffic_count > 0) extras += '<br>Traffic: ' + e.traffic_count + ' hits';
        if (e.agent_count > 0) extras += '<br>Agents: ' + e.agent_count;
        if (e.revenue > 0) extras += '<br>Revenue: ' + Math.round(e.revenue) + ' AGENTIS';
        if (e.build_phase) extras += '<br>Build Phase: P' + e.build_phase;
        if (e.last_activity) extras += '<br>Last activity: ' + e.last_activity.substring(0, 10);
        if (e.has_dependency_warning) extras += '<br><span style="color:#f59e0b">&#9888; Dependency blocked</span>';
    }

    tooltip.html(
        '<strong>' + d.label + '</strong><br>'
        + statusBadge + '<em>' + d.status + '</em> &middot; ' + d.category + '<br>'
        + '<span style="color:#aaa;">' + desc + '</span>'
        + extras
    )
    .style('left', (event.offsetX + 15) + 'px')
    .style('top', (event.offsetY - 10) + 'px')
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

    var node = nodeDetail.node || nodeDetail;
    var meta = node.metadata || {};

    // Position panel near the clicked node — inside the canvas wrap
    var wrap = document.getElementById('pwm-canvas-wrap');
    var wrapRect = wrap ? wrap.getBoundingClientRect() : { left: 0, top: 0, width: 1200, height: 800 };
    var transform = state.zoomTransform || d3.zoomIdentity;
    var nx = transform.applyX(node.x || 0);
    var ny = transform.applyY(node.y || 0);

    // Place right next to the node with small offset
    var panelW = 420;
    var minTop = 60;  // Below the stats bar pills
    var panelLeft = nx + 30;
    var panelTop = ny - 20;

    // Flip left if too close to right edge
    if (panelLeft + panelW > wrapRect.width - 10) panelLeft = nx - panelW - 30;
    // Keep within canvas bounds — always below stats bar
    if (panelTop < minTop) panelTop = minTop;
    if (panelTop + 380 > wrapRect.height) panelTop = wrapRect.height - 390;
    if (panelLeft < 5) panelLeft = 5;

    panel.style.left = panelLeft + 'px';
    panel.style.top = panelTop + 'px';
    panel.classList.add('open');

    // Status badge
    var badgeEl = document.getElementById('pwm-info-status');
    if (badgeEl) {
        badgeEl.textContent = node.status;
        badgeEl.className = 'pwm-status-badge pwm-status--' + node.status.toLowerCase();
        badgeEl.style.padding = '3px 10px';
        badgeEl.style.borderRadius = '12px';
        badgeEl.style.fontSize = '11px';
        badgeEl.style.fontWeight = '600';
    }

    // Label
    var labelEl = document.getElementById('pwm-info-label');
    if (labelEl) labelEl.textContent = node.label || '';

    // Description
    var descEl = document.getElementById('pwm-info-desc');
    if (descEl) descEl.textContent = node.description || 'No description available.';

    // Details grid
    var detailsEl = document.getElementById('pwm-info-details');
    if (detailsEl) {
        var rows = '';
        rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Category</span><span class="pwm-dv">' + (node.category || '-') + '</span></div>';
        rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Node Type</span><span class="pwm-dv">' + (node.node_type || '-') + '</span></div>';
        rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Feature Flag</span><span class="pwm-dv">' + (node.feature_flag || 'none') + '</span></div>';
        rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Build Phase</span><span class="pwm-dv">' + (meta.build_phase ? 'Phase ' + meta.build_phase : '-') + '</span></div>';
        rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Module</span><span class="pwm-dv">' + (meta.module || '-') + '</span></div>';
        if (node.url_path) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">URL</span><span class="pwm-dv" style="color:var(--pwm-teal)">' + node.url_path + '</span></div>';
        if (node.api_endpoint) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">API</span><span class="pwm-dv" style="font-family:monospace;font-size:10px">' + node.api_endpoint + '</span></div>';

        // Enrichment data
        var enr = state.enrichment && state.enrichment.nodes ? state.enrichment.nodes[node.id] : null;
        if (enr) {
            if (enr.health && enr.health !== 'unknown') {
                var hCol = enr.health === 'green' ? '#4ade80' : '#ef4444';
                rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Health</span><span class="pwm-dv" style="color:' + hCol + '">&#9679; ' + enr.health.toUpperCase() + '</span></div>';
            }
            if (enr.traffic_count > 0) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Traffic</span><span class="pwm-dv">' + enr.traffic_count + ' recent hits</span></div>';
            if (enr.agent_count > 0) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Agents Using</span><span class="pwm-dv" style="color:var(--pwm-teal)">' + enr.agent_count + '</span></div>';
            if (enr.revenue > 0) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Revenue</span><span class="pwm-dv" style="color:var(--pwm-gold)">' + Math.round(enr.revenue) + ' AGENTIS</span></div>';
            if (enr.last_activity) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Last Activity</span><span class="pwm-dv">' + enr.last_activity.substring(0, 16).replace('T', ' ') + '</span></div>';
            if (enr.has_dependency_warning) rows += '<div class="pwm-info-detail-row"><span class="pwm-dl">Warning</span><span class="pwm-dv" style="color:#f59e0b">&#9888; Dependency blocked</span></div>';
        }

        detailsEl.innerHTML = rows;
    }

    // Linked endpoints
    var endpointsEl = document.getElementById('pwm-info-endpoints');
    if (endpointsEl) {
        var endpoints = node.linked_endpoints || [];
        if (endpoints.length > 0) {
            endpointsEl.innerHTML = endpoints.map(function (ep) {
                return '<span class="pwm-endpoint-chip">' + ep + '</span>';
            }).join(' ');
        } else {
            endpointsEl.innerHTML = '<span style="color:var(--pwm-text-muted);font-size:11px">None</span>';
        }
    }

    // "Go There" button
    var goBtn = document.getElementById('pwm-info-go');
    if (goBtn) {
        if (node.url_path && (node.status === 'ACTIVE' || node.status === 'RESTRICTED')) {
            goBtn.style.display = 'inline-flex';
            goBtn.href = node.url_path;
        } else {
            goBtn.style.display = 'none';
        }
    }

    // Status history
    var historyEl = document.getElementById('pwm-info-history');
    if (historyEl && nodeDetail.status_history) {
        var history = nodeDetail.status_history.slice(0, 5);
        if (history.length > 0) {
            historyEl.innerHTML = history.map(function (h) {
                var sCol = getStatusColour(h.status);
                var ts = h.changed_at ? h.changed_at.substring(0, 16).replace('T', ' ') : '';
                return '<div style="display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid var(--pwm-border)">'
                    + '<span style="width:8px;height:8px;border-radius:50%;background:' + sCol + ';flex-shrink:0"></span>'
                    + '<span style="font-size:11px;color:var(--pwm-text-light)">' + h.status + '</span>'
                    + (h.previous_status ? '<span style="font-size:9px;color:var(--pwm-text-muted)">from ' + h.previous_status + '</span>' : '')
                    + '<span style="font-size:10px;color:var(--pwm-text-muted);margin-left:auto">' + ts + '</span>'
                    + '</div>';
            }).join('');
        } else {
            historyEl.innerHTML = '<span style="color:var(--pwm-text-muted);font-size:11px">No status changes recorded</span>';
        }
    }

    // Status select
    var statusSelect = document.getElementById('pwm-info-status-select');
    if (statusSelect) {
        statusSelect.value = node.status;
    }

    // Store selected node ID for status change
    state._infoPanelNodeId = node.id;
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

function toggleNode(el) {
    var nodeId = el.dataset.node;
    if (!nodeId) return;

    el.classList.toggle('active');

    if (el.classList.contains('active')) {
        state.hiddenNodes.delete(nodeId);
    } else {
        state.hiddenNodes.add(nodeId);
    }
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
        html += '<div class="pwm-toggle active" data-node="' + n.id + '" onclick="PWM.toggleNode(this)" style="width:28px;height:14px;flex-shrink:0"><div class="pwm-toggle-knob" style="width:10px;height:10px;top:2px;left:2px"></div></div>';
        html += '<span style="width:7px;height:7px;border-radius:50%;background:' + statusCol + ';flex-shrink:0"></span>';
        html += '<' + tag + link + ' style="' + linkStyle + 'flex:1;font-size:11px;line-height:1.3" title="' + n.label + ' — ' + n.status + '">' + n.label + '</' + tag + '>';
        html += '<span style="font-size:10px;color:' + statusCol + ';flex-shrink:0;font-weight:700;min-width:32px;text-align:right;padding-right:4px">' + n.status.substring(0, 3).toUpperCase() + '</span>';
        html += '</div>';
    });

    container.innerHTML = html;
}


// === SECTION 12: UTILITY ===

function wrapText(text, maxCharsPerLine) {
    if (!text) return [''];
    if (text.length <= maxCharsPerLine) return [text];

    var words = text.split(/\s+/);
    var lines = [];
    var current = '';

    words.forEach(function (word) {
        if (current.length === 0) {
            current = word;
        } else if ((current + ' ' + word).length <= maxCharsPerLine) {
            current += ' ' + word;
        } else {
            lines.push(current);
            current = word;
        }
    });
    if (current) lines.push(current);

    return lines.length > 0 ? lines : [text];
}

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
    fetchEnrichment();
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

PWM.toggleNode = function (el) {
    toggleNode(el);
};

PWM.closeInfoPanel = function () {
    closeInfoPanel();
};

PWM.changeStatus = function () {
    var nodeId = state._infoPanelNodeId;
    var select = document.getElementById('pwm-info-status-select');
    if (!nodeId || !select) return;
    var newStatus = select.value;
    var reason = prompt('Reason for status change (optional):') || '';
    // Note: this requires 3FA token in production. For now, attempt without.
    fetch('/api/v1/owner/workflow-map/node/' + encodeURIComponent(nodeId) + '/status', {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, reason: reason }),
    })
    .then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.detail || 'Failed'); });
        return r.json();
    })
    .then(function () {
        alert('Status updated to ' + newStatus);
        PWM.refresh();
    })
    .catch(function (err) {
        alert('Status change failed: ' + err.message);
    });
};

PWM.toggleHeatmap = function () {
    state.showHeatmap = !state.showHeatmap;
    applyEnrichment();
};

PWM.toggleZone = function (zoneKey) {
    toggleZone(zoneKey);
};

PWM.selectAllNodes = function () {
    state.hiddenNodes.clear();
    document.querySelectorAll('#pwm-services-list .pwm-toggle').forEach(function (t) {
        t.classList.add('active');
    });
    applyFilters();
};

PWM.deselectAllNodes = function () {
    if (!state.graphData) return;
    state.graphData.nodes.forEach(function (n) {
        state.hiddenNodes.add(n.id);
    });
    document.querySelectorAll('#pwm-services-list .pwm-toggle').forEach(function (t) {
        t.classList.remove('active');
    });
    applyFilters();
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
