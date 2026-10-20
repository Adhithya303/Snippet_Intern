import React, { useEffect, useState, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

type Product = {
  id: string;
  name: string;
  category: 'laptop' | 'headphones';
  price_paise: number;
  currency: string;
  specifications: Record<string, string | number | boolean | null>;
  intended_uses: string[];
  features: string[];
};

type Page = {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

type Message = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
};

type HardConstraints = {
  max_price_paise: number | null;
  min_ram_gb: number | null;
  max_weight_kg: number | null;
  required_features: string[];
  noise_cancellation?: boolean | null;
  connection?: string | null;
  microphone?: boolean | null;
  min_battery_hours?: number | null;
};

type Preferences = {
  lightweight: boolean | null;
  brand: string | null;
  noise_cancellation?: boolean | null;
};

type Requirements = {
  category: 'laptop' | 'headphones' | null;
  intended_uses: string[];
  hard_constraints: HardConstraints;
  preferences: Preferences;
  answered_no_preference: string[];
  unresolved_questions: string[];
};

type RecommendationItem = {
  product: Product;
  reasons: string[];
  trade_offs: string[];
  unknowns: string[];
};

type AgentResponse =
  | { type: 'clarification'; question: string; requirements: Requirements }
  | { type: 'recommendations'; products: RecommendationItem[]; requirements: Requirements }
  | { type: 'no_match'; explanation: string; proposed_adjustment_question: string; requirements: Requirements };

type Conversation = {
  id: string;
  status: string;
  requirements: Requirements;
  messages: Message[];
  created_at: string;
  updated_at: string;
};

type Health = {
  status: string;
  database_engine: string;
  agent: string;
  build_stage: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + path, init);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error?.message || 'The service is unavailable. Check the backend and database.');
  }
  return data;
}

const money = (paise: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(paise / 100);

const label = (value: string) => value.replaceAll('_', ' ');

function ProductIcon({ category }: { category: string }) {
  return category === 'laptop' ? (
    <svg viewBox="0 0 180 100" aria-hidden="true">
      <rect x="35" y="12" width="110" height="67" rx="5" />
      <path d="M43 20h94v50H43z" className="screen" />
      <path d="M23 82h134l-10 9H33z" />
      <path d="m65 52 17-18 13 11 22-17" className="line" />
    </svg>
  ) : (
    <svg viewBox="0 0 180 100" aria-hidden="true">
      <path d="M54 60V47a36 36 0 0 1 72 0v13" className="headband" />
      <rect x="46" y="48" width="22" height="40" rx="9" />
      <rect x="112" y="48" width="22" height="40" rx="9" />
      <path d="M62 61v14M118 61v14" className="line" />
    </svg>
  );
}

function ProductCard({ product: p }: { product: Product }) {
  const s = p.specifications;
  const facts =
    p.category === 'laptop'
      ? [`${s.ram_gb} GB RAM`, `${s.storage_gb} GB SSD`, s.weight_kg === null ? 'Weight not specified' : `${s.weight_kg} kg`]
      : [
          String(s.connection),
          s.noise_cancellation === null ? 'ANC not specified' : s.noise_cancellation ? 'Active noise cancellation' : 'No active noise cancellation',
          s.battery_applicability === 'not_applicable' ? 'Battery not applicable' : s.battery_hours === null ? 'Battery not specified' : `${s.battery_hours}h sample battery`,
        ];
  return (
    <article className="product-card">
      <div className={'product-art ' + p.category}>
        <span className="product-id">{p.id}</span>
        <ProductIcon category={p.category} />
        <span className="sample-label">SYNTHETIC PRODUCT</span>
      </div>
      <div className="product-content">
        <span className="eyebrow">{p.category === 'laptop' ? 'LAPTOP' : 'HEADPHONES'}</span>
        <h3>{p.name}</h3>
        <p className="price">{money(p.price_paise)}</p>
        <ul className="facts">
          {facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
        <details>
          <summary>
            View stored specifications <span>↗</span>
          </summary>
          <dl>
            {Object.entries(s).map(([key, value]) => (
              <React.Fragment key={key}>
                <dt>{label(key)}</dt>
                <dd>{value === null ? 'Not specified' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</dd>
              </React.Fragment>
            ))}
          </dl>
          <p className="small">
            Intended uses: {p.intended_uses.map(label).join(', ')}. Synthetic use tags are not performance benchmarks.
          </p>
        </details>
      </div>
    </article>
  );
}

function GroundedRecommendationCard({ rec }: { rec: RecommendationItem }) {
  const p = rec.product;
  return (
    <div className="recommendation-card">
      <div className="rec-header">
        <div className="rec-badge-synthetic">SYNTHETIC CATALOGUE RECORD</div>
        <span className="rec-id">{p.id}</span>
      </div>
      <div className="rec-title-row">
        <h4>{p.name}</h4>
        <span className="rec-price">{money(p.price_paise)}</span>
      </div>
      <div className="rec-specs">
        {p.category === 'laptop' ? (
          <span>
            {p.specifications.cpu} · {p.specifications.ram_gb}GB RAM · {p.specifications.storage_gb}GB SSD
            {p.specifications.weight_kg ? ` · ${p.specifications.weight_kg}kg` : ''}
          </span>
        ) : (
          <span>
            {p.specifications.connection}
            {p.specifications.noise_cancellation ? ' · ANC' : ''}
            {p.specifications.battery_hours ? ` · ${p.specifications.battery_hours}h battery` : ''}
          </span>
        )}
      </div>

      <div className="rec-section">
        <strong className="rec-section-title">Why it fits your requirements:</strong>
        <ul className="rec-reasons">
          {rec.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </div>

      {rec.trade_offs && rec.trade_offs.length > 0 && (
        <div className="rec-section trade-offs">
          <strong className="rec-section-title">Trade-offs to consider:</strong>
          <ul className="rec-tradeoffs">
            {rec.trade_offs.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {rec.unknowns && rec.unknowns.length > 0 && (
        <div className="rec-unknowns">
          <small>Note: {rec.unknowns.join(' ')}</small>
        </div>
      )}
    </div>
  );
}

function RequirementsSummary({ reqs }: { reqs: Requirements }) {
  const hard = reqs.hard_constraints;
  const pref = reqs.preferences;

  return (
    <div className="requirements-summary" aria-label="Current extracted requirements">
      <div className="req-summary-header">
        <span className="tiny-label">LIVE CONVERSATION MEMORY</span>
        <span className="req-indicator">Updated</span>
      </div>
      <div className="req-chips">
        <span className={`chip ${reqs.category ? 'active' : ''}`}>
          <strong>Category:</strong> {reqs.category ? label(reqs.category) : 'Not specified'}
        </span>
        <span className={`chip ${hard.max_price_paise !== null ? 'active' : ''}`}>
          <strong>Budget:</strong>{' '}
          {hard.max_price_paise !== null
            ? `Max ${money(hard.max_price_paise)}`
            : reqs.answered_no_preference.includes('budget')
            ? 'No budget limit'
            : 'Any budget'}
        </span>
        {reqs.intended_uses.length > 0 && (
          <span className="chip active">
            <strong>Uses:</strong> {reqs.intended_uses.map(label).join(', ')}
          </span>
        )}
        {hard.min_ram_gb !== null && (
          <span className="chip active">
            <strong>Min RAM:</strong> {hard.min_ram_gb} GB
          </span>
        )}
        {hard.max_weight_kg !== null && (
          <span className="chip active">
            <strong>Max Weight:</strong> {hard.max_weight_kg} kg
          </span>
        )}
        {pref.lightweight && (
          <span className="chip active">
            <strong>Portability:</strong> Lightweight preferred
          </span>
        )}
        {pref.brand && (
          <span className="chip active">
            <strong>Brand:</strong> {pref.brand}
          </span>
        )}
        {reqs.answered_no_preference.length > 0 && (
          <span className="chip neutral">
            <strong>Explicit no-pref:</strong> {reqs.answered_no_preference.join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}

function App() {
  const [category, setCategory] = useState('');
  const [budgetDraft, setBudgetDraft] = useState('');
  const [budget, setBudget] = useState<number | undefined>();
  const [budgetError, setBudgetError] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<Health | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [conversationError, setConversationError] = useState('');
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);

  // Chat state
  const [inputMessage, setInputMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState('');
  const [lastFailedMessage, setLastFailedMessage] = useState('');
  const [latestRecommendations, setLatestRecommendations] = useState<RecommendationItem[]>([]);
  const [latestClarification, setLatestClarification] = useState<string | null>(null);
  const [latestNoMatch, setLatestNoMatch] = useState<{ explanation: string; adjustment: string } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages, sending, latestRecommendations, latestClarification, latestNoMatch]);

  useEffect(() => {
    const controller = new AbortController();
    request<Health>('/api/v1/health', { signal: controller.signal })
      .then(setHealth)
      .catch(() => setHealth(null));

    const id = localStorage.getItem('electronics-conversation-id');
    if (id) {
      request<Conversation>('/api/v1/conversations/' + encodeURIComponent(id), { signal: controller.signal })
        .then(setConversation)
        .catch((e) => {
          if (e.name !== 'AbortError') {
            setConversationError('Saved conversation could not be loaded. Start a new one.');
          }
        });
    }
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ page: String(page), page_size: '6' });
    if (category) params.set('category', category);
    if (budget !== undefined) params.set('max_price_paise', String(budget));
    setLoading(true);
    setError('');
    request<Page>('/api/v1/products?' + params, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [category, budget, page, refresh]);

  function applyBudget(event: React.FormEvent) {
    event.preventDefault();
    const input = budgetDraft.trim();
    if (input === '') {
      setBudget(undefined);
      setBudgetError('');
      setPage(1);
      return;
    }
    if (!/^\d+(\.\d{1,2})?$/.test(input)) {
      setBudgetError('Enter a positive rupee amount, with up to two decimal places.');
      return;
    }
    const [whole, fraction = ''] = input.split('.');
    const paise = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    if (!Number.isSafeInteger(paise) || paise > 2_000_000_000) {
      setBudgetError('Maximum supported budget is ₹2,00,00,000.');
      return;
    }
    setBudget(paise);
    setBudgetError('');
    setPage(1);
  }

  async function startConversation() {
    setCreating(true);
    setConversationError('');
    setChatError('');
    setLatestRecommendations([]);
    setLatestClarification(null);
    setLatestNoMatch(null);
    try {
      const c = await request<Conversation>('/api/v1/conversations', { method: 'POST' });
      setConversation(c);
      localStorage.setItem('electronics-conversation-id', c.id);
    } catch (e) {
      setConversationError(e instanceof Error ? e.message : 'Could not create conversation.');
    } finally {
      setCreating(false);
    }
  }

  async function sendMessage(textToSend?: string) {
    const content = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!content || sending) return;

    setSending(true);
    setChatError('');
    setLatestRecommendations([]);
    setLatestClarification(null);
    setLatestNoMatch(null);

    let activeConv = conversation;
    try {
      // Create conversation if not yet initialized
      if (!activeConv) {
        activeConv = await request<Conversation>('/api/v1/conversations', { method: 'POST' });
        setConversation(activeConv);
        localStorage.setItem('electronics-conversation-id', activeConv.id);
      }

      const res = await request<AgentResponse>(`/api/v1/conversations/${activeConv.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });

      // Clear draft message upon success
      setInputMessage('');
      setLastFailedMessage('');

      // Reload fresh conversation state from database
      const updatedConv = await request<Conversation>(`/api/v1/conversations/${activeConv.id}`);
      setConversation(updatedConv);

      if (res.type === 'recommendations') {
        setLatestRecommendations(res.products);
      } else if (res.type === 'clarification') {
        setLatestClarification(res.question);
      } else if (res.type === 'no_match') {
        setLatestNoMatch({ explanation: res.explanation, adjustment: res.proposed_adjustment_question });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to send message. Please retry.';
      setChatError(errorMsg);
      setLastFailedMessage(content);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#main">
          <span className="brand-mark">
            e<span>↗</span>
          </span>
          <span>
            electronics
            <br />
            <strong>assistant</strong>
          </span>
        </a>
        <div className="side-label">BUILD WORKSPACE</div>
        <a className="nav-item active" href="#main">
          <span>▦</span> Product catalogue
        </a>
        <a className="nav-item" href="#conversation">
          <span>◌</span> Sales Assistant
        </a>
        <a className="nav-item" href={API + '/docs'} target="_blank" rel="noreferrer">
          <span>↗</span> API documentation
        </a>
        <div className="build-card">
          <span className="eyebrow">CURRENT MILESTONE</span>
          <h3>Day 2 Assistant</h3>
          <p>Structured memory, clarification &amp; grounded recommendations.</p>
          <div className="progress">
            <i style={{ width: '66%' }} />
          </div>
          <p className="small">Active provider: Google Gemini Developer API (Free Tier).</p>
        </div>
        <div className="sidebar-foot">
          <span className={'status-dot ' + (health ? 'online' : 'offline')} />
          {health ? 'Database connected' : 'Backend unavailable'}
          <small>
            {health?.database_engine === 'sqlite'
              ? 'SQLite preview mode'
              : health
              ? 'PostgreSQL active'
              : 'Start the backend to connect'}
          </small>
        </div>
      </aside>

      <main id="main">
        <header className="topbar">
          <span>AI ENGINEER ASSESSMENT</span>
          <span className="badge">
            DAY 02 <span>/ 03</span>
          </span>
        </header>

        <div className="page-heading">
          <div>
            <p className="eyebrow">GROUNDED AI SALES ASSISTANT</p>
            <h1>
              AI Assistant with
              <br />
              Structured Memory.
            </h1>
            <p>Chat with the sales assistant to explore requirements, clarify gaps, and get verified recommendations.</p>
          </div>
          <div className="catalogue-note">
            <span>36</span>
            <p>
              synthetic records
              <br />
              across 2 categories
            </p>
          </div>
        </div>

        <div className="notice">
          <span className="notice-icon">✓</span>
          <p>
            <strong>Day 2 AI Assistant Active.</strong> Natural language requirements are extracted into structured memory via
            Google Gemini Developer API. Recommendations are strictly filtered and grounded against database records.
          </p>
        </div>

        <div className="content-layout">
          <section className="catalogue" aria-label="Product catalogue">
            <div className="section-title">
              <h2>Product catalogue</h2>
              <span aria-live="polite">
                {loading ? 'Loading…' : error ? 'Unavailable' : `${data?.total ?? 0} matching records`}
              </span>
            </div>
            <form className="filters" onSubmit={applyBudget}>
              <div>
                <label htmlFor="category">Category</label>
                <select
                  id="category"
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">All categories</option>
                  <option value="laptop">Laptops</option>
                  <option value="headphones">Headphones</option>
                </select>
              </div>
              <div className="budget-input">
                <label htmlFor="budget">Maximum budget (INR)</label>
                <input
                  id="budget"
                  inputMode="decimal"
                  placeholder="e.g. 70000"
                  value={budgetDraft}
                  onChange={(e) => setBudgetDraft(e.target.value)}
                />
              </div>
              <button type="submit" className="button primary">
                Apply budget
              </button>
            </form>
            {budgetError && (
              <p className="error" role="alert">
                {budgetError}
              </p>
            )}
            <p className="filter-note">
              {budget !== undefined ? `Budget applied: ${money(budget)}. ` : ''}
              Sorted by price, then product ID.
            </p>
            {error ? (
              <div className="empty" role="alert">
                <h3>Unable to load the catalogue</h3>
                <p>{error}</p>
                <button className="button" onClick={() => setRefresh((r) => r + 1)}>
                  Retry connection
                </button>
              </div>
            ) : loading ? (
              <div className="loading" role="status">
                Loading catalogue records…
              </div>
            ) : data?.items.length ? (
              <>
                <div className="product-grid">
                  {data.items.map((p) => (
                    <ProductCard key={p.id} product={p} />
                  ))}
                </div>
                <div className="pagination">
                  <button className="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    ← Previous
                  </button>
                  <span>
                    Page {page} of {data.total_pages}
                  </span>
                  <button className="button" disabled={page >= data.total_pages} onClick={() => setPage((p) => p + 1)}>
                    Next →
                  </button>
                </div>
              </>
            ) : (
              <div className="empty">
                <h3>No catalogue records match</h3>
                <p>Try a different category or increase the catalogue budget filter.</p>
                <button
                  className="button"
                  onClick={() => {
                    setBudget(undefined);
                    setBudgetDraft('');
                    setCategory('');
                    setPage(1);
                  }}
                >
                  Clear filters
                </button>
              </div>
            )}
          </section>

          <aside id="conversation" className="conversation-panel">
            <div className="panel-header-row">
              <div className="panel-icon">◌</div>
              <div>
                <p className="eyebrow">AI SALES ASSISTANT</p>
                <h2>Chat &amp; Advice</h2>
              </div>
            </div>

            <div className="conv-controls">
              {conversation ? (
                <div className="conv-id-badge">
                  <span className="tiny-label">CONVERSATION</span>
                  <code>{conversation.id.slice(0, 8)}…</code>
                  <button className="button-xs" onClick={startConversation} disabled={creating || sending}>
                    New Chat
                  </button>
                </div>
              ) : (
                <button className="button primary full" onClick={startConversation} disabled={creating}>
                  {creating ? 'Creating…' : 'Start conversation'} <span>↗</span>
                </button>
              )}
            </div>

            {conversationError && (
              <p className="error" role="alert">
                {conversationError}
              </p>
            )}

            {conversation && <RequirementsSummary reqs={conversation.requirements} />}

            <div className="chat-container">
              <div className="chat-thread" role="log" aria-live="polite">
                {!conversation || conversation.messages.length === 0 ? (
                  <div className="chat-welcome">
                    <p>
                      Hello! What are you shopping for today? Tell me your preferred category (laptop or headphones),
                      intended uses, budget, or specifications.
                    </p>
                    <div className="prompt-suggestions">
                      <button
                        className="suggestion-btn"
                        onClick={() => sendMessage('I need a programming laptop under 75,000 rupees, any brand is fine')}
                      >
                        "Programming laptop under ₹75,000"
                      </button>
                      <button
                        className="suggestion-btn"
                        onClick={() => sendMessage('Looking for wireless headphones with active noise cancellation under 10000')}
                      >
                        "Wireless headphones with ANC under ₹10,000"
                      </button>
                      <button
                        className="suggestion-btn"
                        onClick={() => sendMessage('I need a laptop for college')}
                      >
                        "I need a laptop for college"
                      </button>
                    </div>
                  </div>
                ) : (
                  conversation.messages.map((m) => (
                    <div key={m.id} className={`chat-message ${m.role}`}>
                      <div className="chat-meta">
                        <span className="chat-sender">{m.role === 'user' ? 'You' : 'Assistant'}</span>
                      </div>
                      <div className="chat-text">{m.content}</div>
                    </div>
                  ))
                )}

                {latestClarification && (
                  <div className="clarification-banner">
                    <span className="banner-icon">?</span>
                    <div>
                      <strong>Clarification needed:</strong>
                      <p>{latestClarification}</p>
                    </div>
                  </div>
                )}

                {latestNoMatch && (
                  <div className="no-match-banner">
                    <span className="banner-icon">!</span>
                    <div>
                      <strong>No matching products found:</strong>
                      <p>{latestNoMatch.explanation}</p>
                      <p className="suggestion-text">{latestNoMatch.adjustment}</p>
                    </div>
                  </div>
                )}

                {latestRecommendations.length > 0 && (
                  <div className="recommendations-container">
                    <div className="rec-container-header">
                      <span>GROUNDED RECOMMENDATIONS ({latestRecommendations.length})</span>
                    </div>
                    {latestRecommendations.map((rec) => (
                      <GroundedRecommendationCard key={rec.product.id} rec={rec} />
                    ))}
                  </div>
                )}

                {sending && (
                  <div className="chat-message assistant sending">
                    <div className="typing-indicator">
                      <span />
                      <span />
                      <span />
                    </div>
                    <small>Assistant is analyzing requirements…</small>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {chatError && (
                <div className="chat-error-banner" role="alert">
                  <p>{chatError}</p>
                  {lastFailedMessage && (
                    <button className="button-xs retry-btn" onClick={() => sendMessage(lastFailedMessage)}>
                      Retry
                    </button>
                  )}
                </div>
              )}

              <form
                className="chat-composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendMessage();
                }}
              >
                <input
                  type="text"
                  placeholder="Describe what you need or revise requirements…"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled={sending}
                  aria-label="Message for AI assistant"
                />
                <button type="submit" className="button primary" disabled={sending || !inputMessage.trim()}>
                  {sending ? 'Sending…' : 'Send'}
                </button>
              </form>
            </div>
          </aside>
        </div>

        <footer>
          <span>Built with FastAPI · React · PostgreSQL</span>
          <span>Synthetic data · Grounded Gemini Developer API · Free Tier</span>
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
