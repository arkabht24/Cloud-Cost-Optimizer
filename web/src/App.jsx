import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const money = (value, currency = "USD") => (
  typeof value === "number"
    ? new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(value)
    : "N/A"
);

const compact = (value) => typeof value === "number"
  ? new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)
  : "N/A";

const signalLabel = (decision) => ({
  yes: "Opportunity identified",
  no: "No change advised",
  approved_with_conditions: "Action after validation",
  needs_review: "Review required",
  insufficient_evidence: "More evidence needed",
  analysis_unavailable: "Analysis unavailable",
  not_supported: "Outside scope",
}[decision] || "AI analysis");

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || payload.title || "Request failed");
  return payload;
}

function TrendChart({ points }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  if (!points?.length) return <div className="chart-empty">Cost trend is unavailable for this scope.</div>;
  const values = points.map((point) => point.cost);
  const max = Math.max(...values, 1);
  const width = 620;
  const height = 164;
  const step = width / Math.max(points.length - 1, 1);
  const path = values.map((value, index) => `${index ? "L" : "M"}${index * step},${height - (value / max) * (height - 18)}`).join(" ");
  const hovered = hoveredIndex === null ? null : points[hoveredIndex];
  const timestamp = hovered?.timestamp || hovered?.date;
  const dateLabel = timestamp ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(timestamp)) : "Time unavailable";
  const position = hoveredIndex === null ? 0 : (hoveredIndex / Math.max(points.length - 1, 1)) * 100;
  function updateHover(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
    setHoveredIndex(Math.round(ratio * (points.length - 1)));
  }
  return (
    <div className="trend-chart" aria-label="Daily cost trend" onMouseMove={updateHover} onMouseLeave={() => setHoveredIndex(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img">
        <path d={`M0,${height} ${path} L${width},${height} Z`} className="area" />
        <path d={path} className="line" />
        {hovered && <><line className="hover-line" x1={hoveredIndex * step} x2={hoveredIndex * step} y1="0" y2={height} /><circle className="hover-point" cx={hoveredIndex * step} cy={height - (hovered.cost / max) * (height - 18)} r="5" /></>}
      </svg>
      {hovered && <div className="chart-tooltip" style={{ left: `${position}%` }}><strong>{money(hovered.cost)}</strong><span>{dateLabel} UTC</span></div>}
      <div className="chart-axis"><span>{(points[0].timestamp || points[0].date).slice(0, 10)}</span><span>Today</span></div>
    </div>
  );
}

function CostBreakdown({ entries }) {
  const max = Math.max(...entries.map((entry) => entry.cost), 1);
  return (
    <div className="breakdown">
      {entries.slice(0, 5).map((entry) => (
        <div className="breakdown-row" key={entry.name}>
          <div className="breakdown-label"><span>{entry.name}</span><strong>{money(entry.cost)}</strong></div>
          <div className="bar-track"><span style={{ width: `${(entry.cost / max) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

function MetricCard({ label, value, detail, accent = false }) {
  return <article className={`metric-card ${accent ? "metric-card--accent" : ""}`}><p>{label}</p><strong>{value}</strong><small>{detail}</small></article>;
}

function OptimizationPanel({ item, result, loading, onClose }) {
  if (!item) return null;
  const analysis = result?.analysis;
  const decision = analysis?.decision;
  return (
    <aside className="optimization-panel" aria-live="polite">
      <button className="icon-button" onClick={onClose} aria-label="Close recommendation">×</button>
      <p className="eyebrow">RESOURCE TECHNIQUE</p>
      <h2>{item.name}</h2>
      <p className="panel-summary">Azure inventory, cost, and performance facts are shown below. Generate an on-demand RAG recommendation to assess this resource.</p>
      <div className="panel-facts">
        <span>Last 30-day cost</span><strong>{money(item.cost.last_30_days, item.cost.currency)}</strong>
        <span>Performance / consumption</span><strong>{Object.entries(item.performance.metrics).map(([label, value]) => `${label}: ${value}`).join(" · ") || "Not available"}</strong>
        <span>AI recommendation</span><strong>Generated on demand</strong>
      </div>
      {loading && <div className="loader">Building an evidence-grounded recommendation…</div>}
      {analysis?.answer && <div className="generated-advice">
        <p className="eyebrow">AI RESPONSE</p>
        <h3>{signalLabel(decision?.decision)}</h3>
        <p>{analysis.answer}</p>
      </div>}
      {!loading && !analysis?.answer && <p className="panel-note">The RAG recommendation has not been generated yet.</p>}
    </aside>
  );
}

function Assistant({ resourceGroup, subscription, contextResource }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);

  async function send(event) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setMessages((items) => [...items, { role: "user", text }]);
    setQuestion("");
    setBusy(true);
    try {
      const history = messages.slice(-8).map((message) => ({ role: message.role, text: message.text }));
      const result = await api("/v1/assistant", { method: "POST", body: JSON.stringify({ question: text, resource_group: resourceGroup, subscription, context_resource: contextResource?.name || null, history }) });
      setMessages((items) => [...items, { role: "assistant", text: result.answer }]);
    } catch (error) {
      setMessages((items) => [...items, { role: "assistant", text: `Unable to analyse this request: ${error.message}` }]);
    } finally { setBusy(false); }
  }

  return <section className={`assistant ${open ? "assistant--open" : ""}`}>
    {open && <div className="assistant-window">
      <div className="assistant-header"><div><span className="spark">✦</span><strong>Cost assistant</strong><small>{contextResource ? `Context: ${contextResource.name}` : "Cloud cost optimization only"}</small></div><button className="icon-button" onClick={() => setOpen(false)}>×</button></div>
      <div className="assistant-messages">
        {!messages.length && <p className="assistant-welcome">Ask about cost trends, utilization, rightsizing, reservations, lifecycle policy, or autoscaling.</p>}
        {messages.map((message, index) => <div className={`chat-bubble chat-bubble--${message.role}`} key={`${message.role}-${index}`}>{message.text}</div>)}
      </div>
      <form onSubmit={send} className="assistant-form"><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a cost question…" /><button disabled={busy}>{busy ? "…" : "→"}</button></form>
    </div>}
    <button className="assistant-toggle" onClick={() => setOpen((value) => !value)}>{open ? "Close" : "Ask cost assistant"}<span>↗</span></button>
  </section>;
}

export default function App() {
  const [resourceGroup, setResourceGroup] = useState("");
  const [subscription, setSubscription] = useState("");
  const [days, setDays] = useState(30);
  const [dashboard, setDashboard] = useState(null);
  const [scopeInfo, setScopeInfo] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [aiRecommendations, setAiRecommendations] = useState({});
  const [analysingResources, setAnalysingResources] = useState({});
  const [allOptimizationsLoading, setAllOptimizationsLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  async function loadDashboard() {
    if (!resourceGroup.trim()) {
      setDashboard(null);
      setError("Enter an Azure resource group to load its cost workspace.");
      return;
    }
    setLoading(true); setError("");
    try {
      const data = await api(`/v1/dashboard?resource_group=${encodeURIComponent(resourceGroup)}&subscription=${encodeURIComponent(subscription)}&days=${days}`);
      setDashboard(data); setAiRecommendations({}); setAnalysingResources({});
    } catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }

  useEffect(() => { api(`/v1/scopes${subscription ? `?subscription=${encodeURIComponent(subscription)}` : ""}`).then(setScopeInfo).catch(() => undefined); }, [subscription]);

  const resources = useMemo(() => (dashboard?.resources || []).filter((resource) => `${resource.name} ${resource.type_label} ${resource.region}`.toLowerCase().includes(search.toLowerCase())), [dashboard, search]);

  async function suggestTechnique(resource) {
    setSelected(resource); setOptimizationResult(null); setOptimizationLoading(true); setAnalysingResources((items) => ({ ...items, [resource.name]: true }));
    try {
      const result = await api(`/v1/resources/${encodeURIComponent(resource.name)}/optimization`, { method: "POST", body: JSON.stringify({ resource_group: resourceGroup, subscription: subscription || null, days }) });
      setOptimizationResult(result);
      setAiRecommendations((items) => ({ ...items, [resource.name]: result.analysis }));
    } catch (requestError) { setOptimizationResult({ analysis: { answer: requestError.message } }); } finally { setOptimizationLoading(false); setAnalysingResources((items) => ({ ...items, [resource.name]: false })); }
  }

  async function suggestAllTechniques() {
    if (!dashboard || allOptimizationsLoading) return;
    setAllOptimizationsLoading(true); setError("");
    try {
      const response = await fetch(`${API_BASE}/v1/dashboard/optimizations/stream`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resource_group: resourceGroup, subscription: subscription || null, days }) });
      if (!response.ok || !response.body) { const problem = await response.json(); throw new Error(problem.detail || problem.title || "Batch request failed"); }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffered = "";
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffered += decoder.decode(chunk.value, { stream: true });
        const events = buffered.split("\n\n");
        buffered = events.pop() || "";
        for (const event of events) {
          const dataLine = event.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;
          const eventData = JSON.parse(dataLine.slice(6));
          if (eventData.type === "started") setAnalysingResources(Object.fromEntries(eventData.resources.map((name) => [name, true])));
          if (eventData.type === "resource_started") setAnalysingResources((items) => ({ ...items, [eventData.resource]: true }));
          if (eventData.type === "resource_completed" || eventData.type === "resource_failed") {
            setAiRecommendations((items) => ({ ...items, [eventData.resource]: eventData.analysis }));
            setAnalysingResources((items) => ({ ...items, [eventData.resource]: false }));
          }
          if (eventData.type === "error") throw new Error(eventData.detail || "Batch request failed");
        }
      }
    } catch (requestError) { setError(`Unable to analyse all resources: ${requestError.message}`); setAnalysingResources({}); } finally { setAllOptimizationsLoading(false); }
  }

  async function downloadReport() {
    if (!dashboard || reportLoading) return;
    setReportLoading(true); setError("");
    try {
      const response = await fetch(`${API_BASE}/v1/reports/resource-group`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resource_group: resourceGroup, subscription: subscription || null, days, analyses: aiRecommendations }) });
      if (!response.ok) { const problem = await response.json(); throw new Error(problem.detail || problem.title || "Report request failed"); }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url; link.download = `cloud-cost-report-${resourceGroup}.html`; link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) { setError(`Unable to create report: ${requestError.message}`); } finally { setReportLoading(false); }
  }

  const summary = dashboard?.summary;
  return <main>
    <nav className="topbar"><div className="brand"><span className="brand-mark">C</span><span>CLOUD COST OPTIMISER</span></div><div className="topbar-status"><span className={`status-dot ${dashboard?.source === "demo" ? "status-dot--demo" : ""}`} />{dashboard ? (dashboard.source === "demo" ? "Demo workspace" : "Azure CLI connected") : "Select a resource group"}</div></nav>
    <section className="hero">
      <h1>Cloud Cost Optimiser</h1>
      <div className="scope-line"><input value={resourceGroup} onChange={(event) => setResourceGroup(event.target.value)} aria-label="Resource group" placeholder="Enter Azure resource group" /><span className="scope-chevron">⌄</span></div>
      <div className="scope-controls">
        <input className="subscription-input" value={subscription} onChange={(event) => setSubscription(event.target.value)} placeholder="Azure subscription ID" list="subscriptions" />
        <datalist id="subscriptions">{scopeInfo?.subscriptions?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</datalist>
        <button className="primary-button" onClick={loadDashboard} disabled={loading}>{loading ? "Loading…" : "Load resource group"}<span>→</span></button>
      </div>
      {scopeInfo?.mode === "demo_only" && <p className="connection-note">Azure CLI is not connected. You can explore the demo workspace or sign in with <code>az login</code>.</p>}
    </section>

    {error && <section className="error-banner"><strong>Dashboard unavailable.</strong> {error}</section>}
    {!dashboard && !loading && !error && <section className="empty-state"><p className="eyebrow">GET STARTED</p><h2>Select a subscription and enter a resource group.</h2><p>The dashboard will retrieve the inventory, available cost information, performance signals, and cost-optimization opportunities for that scope.</p></section>}
    {dashboard && <>
      <section className="summary-grid">
        <MetricCard label="30-day cloud cost" value={money(summary.total_cost, summary.currency)} detail={`${dashboard.source === "demo" ? "Demo estimate" : "Available Azure cost data"}`} accent />
        <MetricCard label="Resources in scope" value={compact(summary.resource_count)} detail="Inventory discovered" />
        <MetricCard label="AI recommendations" value={compact(Object.keys(aiRecommendations).length)} detail="Generated on demand" />
        <MetricCard label="Potential monthly impact" value="On request" detail="AI does not estimate savings without evidence" />
      </section>

      <section className="insight-grid">
        <article className="chart-card chart-card--wide"><div className="card-heading"><div><p className="eyebrow">SPEND VELOCITY</p><h2>Cost trend</h2></div><span>Last {days} days</span></div><TrendChart points={dashboard.cost_trend} /></article>
        <article className="chart-card"><div className="card-heading"><div><p className="eyebrow">COST MIX</p><h2>By resource type</h2></div></div><CostBreakdown entries={dashboard.cost_by_type} /></article>
      </section>

      <section className="resources-section">
        <div className="resources-heading"><div><p className="eyebrow">RESOURCE EXPLORER</p><h2>Your cost optimization backlog</h2><p>Review resource-level spend and performance, then generate an evidence-grounded technique.</p></div><div className="table-actions"><button className="report-button" onClick={downloadReport} disabled={reportLoading}>{reportLoading ? "Preparing report…" : "Download HTML report"}</button><button className="analyse-all-button" onClick={suggestAllTechniques} disabled={allOptimizationsLoading}>{allOptimizationsLoading ? "Analysing all resources…" : "Analyse all resources"}</button><div className="period-toggle">{[7, 30, 90].map((period) => <button key={period} className={days === period ? "active" : ""} onClick={() => { setDays(period); }}>{period}d</button>)}</div><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search resources" /></div></div>
        <div className="availability-strip"><span>Inventory: {dashboard.availability.inventory}</span><span>Cost: {dashboard.availability.cost}</span><span>Performance: {dashboard.availability.performance}</span>{dashboard.availability.message && <span>{dashboard.availability.message}</span>}</div>
        <div className="table-wrap"><table><thead><tr><th>Resource</th><th>30-day cost</th><th>Performance / consumption</th><th>Optimization signal</th><th aria-label="Actions" /></tr></thead><tbody>{resources.map((resource) => { const analysis = aiRecommendations[resource.name]; const verdict = analysis?.decision?.decision; const analysing = analysingResources[resource.name]; return <tr key={resource.id}><td><strong>{resource.name}</strong><span>{resource.type_label} · {resource.region}</span><em>{resource.sku || "SKU not reported"}</em></td><td><strong>{money(resource.cost.last_30_days, resource.cost.currency)}</strong><span className={resource.cost.trend_percent > 0 ? "trend trend--up" : "trend"}>{typeof resource.cost.trend_percent === "number" ? `${resource.cost.trend_percent > 0 ? "+" : ""}${resource.cost.trend_percent}%` : "No trend data"}</span></td><td className="metrics">{Object.entries(resource.performance.metrics).slice(0, 3).map(([label, value]) => <span key={label}><b>{label}</b>{value}</span>)}{!Object.keys(resource.performance.metrics).length && <span>Metrics unavailable</span>}</td><td>{analysing ? <span className="signal-loading"><i />AI analysis in progress</span> : <><strong>{verdict ? signalLabel(verdict) : "Not analysed"}</strong><span className={`confidence ${verdict ? "confidence--ai" : "confidence--low"}`}>{verdict ? "AI response ready" : "Generate on demand"}</span></>}</td><td><button className="technique-button" onClick={() => suggestTechnique(resource)} disabled={analysing}>Suggest technique <span>→</span></button></td></tr>; })}</tbody></table></div>
      </section>
    </>}
    <OptimizationPanel item={selected} result={optimizationResult} loading={optimizationLoading} onClose={() => { setSelected(null); setOptimizationResult(null); }} />
    {dashboard && <Assistant resourceGroup={resourceGroup} subscription={subscription || null} contextResource={selected} />}
  </main>;
}
