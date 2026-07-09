// StandardScaler Coefficients from scaler.pkl
const SCALER_MEAN = [0.932, 1.40275, 1.932, 4.87504926, 0.1575, 0.39775, 0.7735, 9.12007018, 8.26529895];
const SCALER_SCALE = [0.79270171, 1.28590141, 0.79270171, 0.51456457, 0.36427153, 0.48943328, 0.4185663, 2.79550328, 3.11820516];

// Features Names mapping
const FEATURE_NAMES = [
    "Num Joins",
    "Num Filters",
    "Num Tables",
    "Log Query Length",
    "Has GroupBy",
    "Has OrderBy",
    "Uses Index",
    "Log Est Rows",
    "Log Est Filt Rows"
];

// Quick Samples Mappings
const SAMPLES = {
    sample1: "SELECT C.first_name, C.last_name, C.email \nFROM Customers C \nWHERE C.country = 'Germany' AND C.gender = 'Female' \nORDER BY C.last_name DESC;",
    sample2: "SELECT * FROM Customers \nWHERE id = 1045;",
    sample3: "SELECT O.order_date, C.first_name, C.last_name \nFROM Orders O \nJOIN Customers C ON O.customer_id = C.id \nWHERE C.country = 'USA' AND O.status = 'Shipped';",
    sample4: "SELECT O.id, C.first_name, P.product_name, O.total_amount \nFROM Orders O \nJOIN Customers C ON O.customer_id = C.id \nJOIN Products P ON O.product_id = P.id \nWHERE O.status = 'Completed' AND P.price > 120.00 \nORDER BY O.total_amount DESC \nLIMIT 50;"
};

// State Variables
let currentMode = 'simulator'; // 'simulator' or 'live'
let dbConnectionTesting = false;

// DOM Elements
const queryInput = document.getElementById('query-input');
const sampleSelect = document.getElementById('sample-select');
const modeSimulator = document.getElementById('mode-simulator');
const modeLive = document.getElementById('mode-live');
const dbSettingsCard = document.getElementById('db-settings-card');
const simulatorSettingsCard = document.getElementById('simulator-settings-card');
const testConnectionBtn = document.getElementById('test-connection-btn');
const dbStatusBadge = document.getElementById('db-status-badge');

const sliderRows = document.getElementById('sim-rows');
const valRows = document.getElementById('val-sim-rows');
const checkboxIndex = document.getElementById('sim-index');
const sliderFiltered = document.getElementById('sim-filtered');
const valFiltered = document.getElementById('val-sim-filtered');

const predictedRuntimeEl = document.getElementById('predicted-runtime');
const gaugeFill = document.getElementById('gauge-fill');
const recsContainer = document.getElementById('recommendations-container');
const featuresBreakdown = document.getElementById('features-breakdown');

// Metrics details
const metricRows = document.getElementById('metric-rows');
const metricIndex = document.getElementById('metric-index');
const metricTables = document.getElementById('metric-tables');

// Load DB Connection from Local Storage
function loadStoredCredentials() {
    const saved = localStorage.getItem('sql_ml_db_credentials');
    if (saved) {
        try {
            const creds = JSON.parse(saved);
            document.getElementById('db-host').value = creds.host || '127.0.0.1';
            document.getElementById('db-port').value = creds.port || '3306';
            document.getElementById('db-user').value = creds.user || 'root';
            document.getElementById('db-password').value = creds.password || '';
            document.getElementById('db-name').value = creds.database || 'sql_ml_db';
            document.getElementById('save-credentials').checked = true;
        } catch (e) {
            console.error('Failed to parse saved credentials', e);
        }
    }
}

function saveCredentials() {
    const shouldSave = document.getElementById('save-credentials').checked;
    if (shouldSave) {
        const creds = {
            host: document.getElementById('db-host').value,
            port: document.getElementById('db-port').value,
            user: document.getElementById('db-user').value,
            password: document.getElementById('db-password').value,
            database: document.getElementById('db-name').value
        };
        localStorage.setItem('sql_ml_db_credentials', JSON.stringify(creds));
    } else {
        localStorage.removeItem('sql_ml_db_credentials');
    }
}

// SQL Query Parsing Functions
function parseNumFilters(query) {
    const q = query.toUpperCase();
    if (!q.includes(" WHERE ")) return 0;
    
    const parts = q.split(" WHERE ");
    if (parts.length < 2) return 0;
    
    let wherePart = parts[1];
    // Strip trailing clauses
    for (const keyword of [" GROUP BY ", " ORDER BY ", " LIMIT "]) {
        if (wherePart.includes(keyword)) {
            wherePart = wherePart.split(keyword)[0];
        }
    }
    const andCount = (wherePart.match(/\sAND\s/g) || []).length;
    const orCount = (wherePart.match(/\sOR\s/g) || []).length;
    return andCount + orCount + 1;
}

// Helper: Format large numbers
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
}

// Prediction and Processing logic
async function runPrediction() {
    const query = queryInput.value || '';
    
    // Parse query features
    const numJoins = (query.toUpperCase().match(/\sJOIN\s/g) || []).length;
    const numFilters = parseNumFilters(query);
    const queryLength = query.length;
    const hasGroupby = query.toUpperCase().includes(" GROUP BY ") ? 1 : 0;
    const hasOrderby = query.toUpperCase().includes(" ORDER BY ") ? 1 : 0;
    
    let numTables = numJoins + 1;
    let usesIndex = 0;
    let estimatedRows = 1;
    let estimatedFilteredRows = 1;
    let explainFailed = false;
    let explainError = "";

    if (currentMode === 'live' && query.trim()) {
        dbStatusBadge.textContent = "Analyzing...";
        dbStatusBadge.className = "badge badge-info";
        
        const dbConfig = {
            host: document.getElementById('db-host').value,
            port: document.getElementById('db-port').value,
            user: document.getElementById('db-user').value,
            password: document.getElementById('db-password').value,
            database: document.getElementById('db-name').value
        };
        
        try {
            const response = await fetch('/api/explain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, db_config: dbConfig })
            });
            const result = await response.json();
            
            if (result.success) {
                numTables = result.num_tables;
                usesIndex = result.uses_index ? 1 : 0;
                estimatedRows = result.estimated_rows;
                estimatedFilteredRows = result.estimated_filtered_rows;
                
                dbStatusBadge.textContent = "Connected";
                dbStatusBadge.className = "badge badge-success";
            } else {
                explainFailed = true;
                explainError = result.error;
                dbStatusBadge.textContent = "EXPLAIN Error";
                dbStatusBadge.className = "badge badge-warning";
            }
        } catch (err) {
            explainFailed = true;
            explainError = "Failed to communicate with local API. Make sure Vercel server is running.";
            dbStatusBadge.textContent = "API Offline";
            dbStatusBadge.className = "badge badge-error";
        }
    }

    // If simulator or live explain fails, fall back to slider / parsed defaults
    if (currentMode === 'simulator' || explainFailed) {
        estimatedRows = parseFloat(sliderRows.value);
        usesIndex = checkboxIndex.checked ? 1 : 0;
        const filterEffectiveness = parseFloat(sliderFiltered.value) / 100;
        estimatedFilteredRows = estimatedRows * filterEffectiveness;
        
        // Show status badge as Disconnected in simulator mode
        if (currentMode === 'simulator') {
            dbStatusBadge.textContent = "Sandbox Mode";
            dbStatusBadge.className = "badge badge-info";
        }
    }

    // Populate Metrics UI
    metricRows.textContent = formatNumber(Math.round(estimatedRows));
    metricIndex.textContent = usesIndex ? 'Yes' : 'No';
    metricTables.textContent = numTables.toString();

    // Prepare features input
    const logQueryLength = Math.log1p(queryLength);
    const logEstimatedRows = Math.log1p(estimatedRows);
    const logEstimatedFilteredRows = Math.log1p(estimatedFilteredRows);

    const rawFeatures = [
        numJoins,
        numFilters,
        numTables,
        logQueryLength,
        hasGroupby,
        hasOrderby,
        usesIndex,
        logEstimatedRows,
        logEstimatedFilteredRows
    ];

    // Standard Scale Features
    const scaledFeatures = rawFeatures.map((x, i) => (x - SCALER_MEAN[i]) / SCALER_SCALE[i]);

    // Run prediction using the compiled XGBoost score function
    let runtimeMs = 0;
    try {
        const scoreLog = score(scaledFeatures);
        runtimeMs = Math.max(0.01, Math.expm1(scoreLog));
    } catch (e) {
        console.error("XGBoost prediction failed:", e);
    }

    // Display prediction result
    predictedRuntimeEl.textContent = runtimeMs.toFixed(2);
    
    // Animate Gauge path
    // stroke-dasharray is 251.2. Map 0-100ms to 251.2-0 dashoffset.
    const maxGaugeRuntime = 100; 
    const dashoffset = Math.max(0, 251.2 - (Math.min(runtimeMs, maxGaugeRuntime) / maxGaugeRuntime) * 251.2);
    gaugeFill.style.strokeDashoffset = dashoffset;
    
    // Gauge colors based on runtime
    if (runtimeMs < 10) {
        gaugeFill.style.stroke = "var(--emerald-glow)";
        gaugeFill.style.filter = "drop-shadow(0 0 8px var(--emerald-glow))";
    } else if (runtimeMs < 50) {
        gaugeFill.style.stroke = "var(--amber-glow)";
        gaugeFill.style.filter = "drop-shadow(0 0 8px var(--amber-glow))";
    } else {
        gaugeFill.style.stroke = "var(--rose-glow)";
        gaugeFill.style.filter = "drop-shadow(0 0 8px var(--rose-glow))";
    }

    // Model Feature Breakdown rendering
    featuresBreakdown.innerHTML = '';
    rawFeatures.forEach((val, idx) => {
        let displayVal = val;
        // Format log features for user readability
        if ([3, 7, 8].includes(idx)) {
            displayVal = Math.expm1(val);
            if (idx === 3) displayVal = Math.round(displayVal) + " ch";
            else displayVal = formatNumber(Math.round(displayVal));
        } else if ([4, 5, 6].includes(idx)) {
            displayVal = val ? "True" : "False";
        }
        
        const card = document.createElement('div');
        card.className = 'feat-card';
        card.innerHTML = `
            <div class="feat-name" title="${FEATURE_NAMES[idx]}">${FEATURE_NAMES[idx]}</div>
            <div class="feat-val">${displayVal}</div>
        `;
        featuresBreakdown.appendChild(card);
    });

    // Generate Optimizer Recommendations
    const recommendations = [];
    const isSlow = runtimeMs > 15.0 || estimatedRows > 10000;

    if (explainError) {
        recommendations.push({
            type: 'warning',
            icon: '⚠️',
            text: `<strong>Database EXPLAIN Error:</strong> ${explainError}. Using simulated values for prediction.`
        });
    }

    if (isSlow) {
        if (numFilters > 0 && usesIndex === 0) {
            recommendations.push({
                type: 'warning',
                icon: '💡',
                text: '<strong>Add an index:</strong> The query filters data but does not use any index. Adding an index on filter columns would avoid slow full-table scans.'
            });
        }
        if (numJoins > 1) {
            recommendations.push({
                type: 'warning',
                icon: '💡',
                text: '<strong>Reduce JOINs:</strong> Multiple tables are joined, increasing overhead. Ensure all JOINs are necessary, or consider denormalization.'
            });
        }
        if (numFilters === 0 && numJoins > 0) {
            recommendations.push({
                type: 'warning',
                icon: '💡',
                text: '<strong>Filter earlier:</strong> Tables are joined without filters. Restrict row counts early with a WHERE clause.'
            });
        }
        if (hasOrderby && usesIndex === 0) {
            recommendations.push({
                type: 'warning',
                icon: '💡',
                text: '<strong>Optimize sorting:</strong> Sorting columns are not indexed, causing filesorts. Try indexing the ORDER BY column.'
            });
        }
        if (!query.toUpperCase().includes(" LIMIT ") && estimatedRows > 1000) {
            recommendations.push({
                type: 'warning',
                icon: '💡',
                text: '<strong>Add a LIMIT clause:</strong> The query scans/returns many rows. If you only need a preview, add a LIMIT to stop scans early.'
            });
        }
    }
    
    if (recommendations.length === 0) {
        recommendations.push({
            type: 'success',
            icon: '✅',
            text: '<strong>No optimization needed:</strong> This query is predicted to execute very quickly and utilizes index scans efficiently.'
        });
    }

    recsContainer.innerHTML = '';
    recommendations.forEach(rec => {
        const div = document.createElement('div');
        div.className = `rec-item ${rec.type}`;
        div.innerHTML = `
            <div class="rec-icon">${rec.icon}</div>
            <div class="rec-text">${rec.text}</div>
        `;
        recsContainer.appendChild(div);
    });

    // Update Comparison SVG Bar Chart
    drawComparisonChart(runtimeMs);
}

// Draw custom interactive SVG chart
function drawComparisonChart(queryTime) {
    const svg = document.getElementById('bar-chart-svg');
    svg.innerHTML = ''; // Clear SVG
    
    // Data labels & values
    const data = [
        { label: 'Current Query', val: queryTime, color: queryTime < 15 ? 'var(--emerald-glow)' : (queryTime < 50 ? 'var(--amber-glow)' : 'var(--rose-glow)') },
        { label: 'Avg 0-JOIN', val: 12.47, color: 'var(--text-muted)' },
        { label: 'Avg 1-JOIN', val: 44.35, color: 'var(--text-muted)' },
        { label: 'Avg 2-JOINs', val: 56.95, color: 'var(--text-muted)' }
    ];
    
    const margin = { top: 20, right: 20, bottom: 40, left: 55 };
    const width = 500;
    const height = 240;
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;
    
    // Find Max Value for Scaling
    const maxVal = Math.max(...data.map(d => d.val), 80);
    
    // Create Gridlines & Y-Axis labels
    const ticks = 4;
    for (let i = 0; i <= ticks; i++) {
        const yVal = (maxVal / ticks) * i;
        const yPos = chartHeight + margin.top - (yVal / maxVal) * chartHeight;
        
        // Gridline
        const grid = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        grid.setAttribute('x1', margin.left);
        grid.setAttribute('y1', yPos);
        grid.setAttribute('x2', width - margin.right);
        grid.setAttribute('y2', yPos);
        grid.setAttribute('stroke', 'rgba(255,255,255,0.05)');
        grid.setAttribute('stroke-dasharray', '3,3');
        svg.appendChild(grid);
        
        // Y label
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', margin.left - 10);
        text.setAttribute('y', yPos + 4);
        text.setAttribute('text-anchor', 'end');
        text.setAttribute('fill', 'var(--text-muted)');
        text.setAttribute('font-size', '10px');
        text.textContent = yVal.toFixed(0) + ' ms';
        svg.appendChild(text);
    }
    
    // Draw Bars
    const barWidth = 45;
    const barSpacing = chartWidth / data.length;
    
    data.forEach((d, index) => {
        const barHeight = (d.val / maxVal) * chartHeight;
        const xPos = margin.left + (index * barSpacing) + (barSpacing - barWidth) / 2;
        const yPos = chartHeight + margin.top - barHeight;
        
        // Create Bar Rectangle
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', xPos);
        rect.setAttribute('y', yPos);
        rect.setAttribute('width', barWidth);
        rect.setAttribute('height', Math.max(2, barHeight));
        rect.setAttribute('fill', d.color);
        rect.setAttribute('rx', '4');
        rect.style.transition = 'all 0.5s ease-out';
        svg.appendChild(rect);
        
        // Value Text on top of Bar
        const valText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        valText.setAttribute('x', xPos + barWidth / 2);
        valText.setAttribute('y', yPos - 6);
        valText.setAttribute('text-anchor', 'middle');
        valText.setAttribute('fill', 'var(--text-primary)');
        valText.setAttribute('font-size', '11px');
        valText.setAttribute('font-weight', 'bold');
        valText.textContent = d.val.toFixed(1) + ' ms';
        svg.appendChild(valText);
        
        // X-Axis Label
        const lblText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        lblText.setAttribute('x', xPos + barWidth / 2);
        lblText.setAttribute('y', chartHeight + margin.top + 20);
        lblText.setAttribute('text-anchor', 'middle');
        lblText.setAttribute('fill', 'var(--text-secondary)');
        lblText.setAttribute('font-size', '10px');
        lblText.textContent = d.label;
        svg.appendChild(lblText);
    });
    
    // X-Axis baseline
    const baseline = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    baseline.setAttribute('x1', margin.left);
    baseline.setAttribute('y1', chartHeight + margin.top);
    baseline.setAttribute('x2', width - margin.right);
    baseline.setAttribute('y2', chartHeight + margin.top);
    baseline.setAttribute('stroke', 'rgba(255,255,255,0.15)');
    svg.appendChild(baseline);
}

// Event Listeners Setup
function setupListeners() {
    // Mode selection
    modeSimulator.addEventListener('click', () => {
        currentMode = 'simulator';
        modeSimulator.classList.add('active');
        modeLive.classList.remove('active');
        dbSettingsCard.classList.add('disabled');
        simulatorSettingsCard.classList.remove('disabled');
        runPrediction();
    });
    
    modeLive.addEventListener('click', () => {
        currentMode = 'live';
        modeLive.classList.add('active');
        modeSimulator.classList.remove('active');
        dbSettingsCard.classList.remove('disabled');
        simulatorSettingsCard.classList.add('disabled');
        runPrediction();
    });
    
    // Live DB settings input changes
    const dbInputs = ['db-host', 'db-port', 'db-user', 'db-password', 'db-name', 'save-credentials'];
    dbInputs.forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            saveCredentials();
            if (currentMode === 'live') {
                runPrediction();
            }
        });
    });
    
    // Textarea changes
    let debounceTimer;
    queryInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(runPrediction, 300); // Debounce prediction for typing smooth performance
    });
    
    // Sample select change
    sampleSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val !== 'custom' && SAMPLES[val]) {
            queryInput.value = SAMPLES[val];
            runPrediction();
        }
    });

    // Slider inputs
    sliderRows.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        valRows.textContent = val.toLocaleString();
        runPrediction();
    });
    
    checkboxIndex.addEventListener('change', () => {
        runPrediction();
    });
    
    sliderFiltered.addEventListener('input', (e) => {
        const val = e.target.value;
        valFiltered.textContent = val + '%';
        runPrediction();
    });
    
    // Test connection button
    testConnectionBtn.addEventListener('click', async () => {
        if (dbConnectionTesting) return;
        
        dbConnectionTesting = true;
        testConnectionBtn.textContent = "Connecting...";
        dbStatusBadge.textContent = "Testing...";
        dbStatusBadge.className = "badge badge-info";
        
        const dbConfig = {
            host: document.getElementById('db-host').value,
            port: document.getElementById('db-port').value,
            user: document.getElementById('db-user').value,
            password: document.getElementById('db-password').value,
            database: document.getElementById('db-name').value
        };
        
        try {
            // Test connection using a simple mock query or standard call
            const response = await fetch('/api/explain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: 'SELECT 1;', db_config: dbConfig })
            });
            const result = await response.json();
            
            if (result.success) {
                alert("Database connection successful!");
                dbStatusBadge.textContent = "Connected";
                dbStatusBadge.className = "badge badge-success";
            } else {
                alert("Database connection failed:\n" + result.error);
                dbStatusBadge.textContent = "Error";
                dbStatusBadge.className = "badge badge-error";
            }
        } catch (err) {
            alert("Database connection failed. Make sure your local Vercel server is running.");
            dbStatusBadge.textContent = "Error";
            dbStatusBadge.className = "badge badge-error";
        } finally {
            dbConnectionTesting = false;
            testConnectionBtn.textContent = "Test Connection";
        }
    });
}

// Initializer
window.addEventListener('DOMContentLoaded', () => {
    loadStoredCredentials();
    setupListeners();
    // Default select first sample
    queryInput.value = SAMPLES.sample1;
    sampleSelect.value = "sample1";
    runPrediction();
});
