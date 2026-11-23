import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Sparkles,
  Bot,
  User,
  RotateCcw,
  Calculator,
} from "lucide-react";
import "./AIQuestionsPage.css";

const API_URL = "http://127.0.0.1:8000";

const SUGGESTIONS = [
  "Give me a quick summary of this dataset",
  "Which columns have missing values?",
  "Which group brings in the most, and how much?",
  "How did the main number change over time, and why?",
  "Are there any duplicate rows?",
];

const formatCell = (value) => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  return String(value);
};

function MiniTable({ rows }) {
  if (!rows?.length) return null;
  const columns = Object.keys(rows[0]);

  return (
    <div className="aiq-table-wrap">
      <table className="aiq-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 10).map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{formatCell(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CalculationView({ calculation }) {
  const result = calculation.result || {};
  const spec = calculation.spec || {};

  if (result.error) {
    return <p className="aiq-calc-error">Could not calculate: {result.error}</p>;
  }

  if (calculation.tool === "explain_change") {
    return (
      <div className="aiq-calc-block">
        <p className="aiq-calc-line">
          <strong>{result.metric}</strong>: {result.previous_period} was{" "}
          {formatCell(result.previous_value)}, {result.current_period} is{" "}
          {formatCell(result.current_value)} ({formatCell(result.change_pct)}%).
        </p>
        {Object.entries(result.breakdown || {}).map(([dimension, rows]) => (
          <div key={dimension}>
            <span className="aiq-calc-label">By {dimension}</span>
            <MiniTable rows={rows} />
          </div>
        ))}
        {(result.notes || []).map((note, i) => (
          <p className="aiq-calc-note" key={i}>
            {note}
          </p>
        ))}
      </div>
    );
  }

  const filters = (spec.filters || [])
    .map((f) => `${f.column} ${f.op} ${f.value ?? ""}`.trim())
    .join(", ");

  return (
    <div className="aiq-calc-block">
      <p className="aiq-calc-line">
        {spec.agg || "count"} of <strong>{spec.metric || "rows"}</strong>
        {spec.group_by?.length
          ? ` by ${spec.group_by
              .map((g) => (typeof g === "string" ? g : `${g.column} (${g.grain || "value"})`))
              .join(", ")}`
          : ""}
        {filters ? ` where ${filters}` : ""}. Matched{" "}
        {formatCell(result.matched_rows)} of {formatCell(result.total_rows)} rows.
      </p>
      <MiniTable rows={result.rows} />
      {result.note && <p className="aiq-calc-note">{result.note}</p>}
    </div>
  );
}

function Calculations({ calculations }) {
  const [open, setOpen] = useState(false);

  if (!calculations?.length) return null;

  return (
    <div className="aiq-calcs">
      <button
        type="button"
        className="aiq-calcs-toggle"
        onClick={() => setOpen((value) => !value)}
      >
        <Calculator size={14} />
        {open ? "Hide calculation" : "Show how this was calculated"}
      </button>

      {open &&
        calculations.map((calculation, i) => (
          <CalculationView calculation={calculation} key={i} />
        ))}
    </div>
  );
}

function AIQuestionsPage({ dataset }) {
  const [question, setQuestion] = useState("");
  const [version, setVersion] = useState("cleaned");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [usedVersion, setUsedVersion] = useState(null);

  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleAsk = async (selectedQuestion = question) => {
    const trimmed = String(selectedQuestion).trim();
    if (!trimmed || loading) return;

    const previousMessages = messages;

    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/v1/datasets/${dataset.dataset_id}/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: trimmed,
            version,
            history: previousMessages.slice(-6).map((m) => ({
              role: m.role,
              content: m.content,
            })),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to get an answer.");
      }

      setUsedVersion(data.version);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
          version: data.version,
          calculations: data.calculations || [],
        },
      ]);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setError("");
    setQuestion("");
  };

  return (
    <div className="aiq-page">
      <span className="aiq-eyebrow">AI ANALYTICS</span>
      <h2>Ask questions about your data</h2>
      <p className="aiq-lead">
        Every number in an answer is calculated from your data, and you can open
        the calculation to check it.
      </p>

      <div className="aiq-container">
        <div className="aiq-header">
          <div className="aiq-title">
            <div className="aiq-avatar">
              <Sparkles size={20} />
            </div>
            <div>
              <h3>DataLens Assistant</h3>
              <span>Answers backed by calculations</span>
            </div>
          </div>

          <div className="aiq-controls">
            <select
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              disabled={loading}
              aria-label="Select dataset version"
            >
              <option value="cleaned">Cleaned data (if available)</option>
              <option value="original">Original data</option>
            </select>

            <button
              type="button"
              className="aiq-clear"
              onClick={handleClearChat}
              disabled={loading || messages.length === 0}
              title="Clear conversation"
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        <div className="aiq-messages">
          {messages.length === 0 ? (
            <div className="aiq-welcome">
              <div className="aiq-welcome-icon">
                <Sparkles size={28} />
              </div>

              <h3>Hi! I'm your DataLens Assistant.</h3>

              <p>
                Ask in English, Hindi or Hinglish. I can compare groups, find
                trends and explain what changed between two periods.
              </p>

              <div className="aiq-suggestions">
                <span>Try asking</span>
                {SUGGESTIONS.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => handleAsk(item)}
                    disabled={loading}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                className={`aiq-message ${
                  message.role === "user" ? "aiq-user" : "aiq-assistant"
                }`}
                key={index}
              >
                <div className="aiq-message-avatar">
                  {message.role === "user" ? <User size={17} /> : <Bot size={18} />}
                </div>

                <div className="aiq-message-content">
                  <div className="aiq-message-meta">
                    <strong>{message.role === "user" ? "You" : "DataLens AI"}</strong>
                    {message.version && (
                      <span>
                        {message.version === "cleaned" ? "Cleaned data" : "Original data"}
                      </span>
                    )}
                  </div>

                  <div className="aiq-message-text">
                    {message.role === "assistant" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </div>

                  {message.role === "assistant" && (
                    <Calculations calculations={message.calculations} />
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="aiq-message aiq-assistant">
              <div className="aiq-message-avatar">
                <Bot size={18} />
              </div>
              <div className="aiq-message-content">
                <div className="aiq-message-meta">
                  <strong>DataLens AI</strong>
                </div>
                <p className="aiq-typing">Calculating from your data...</p>
              </div>
            </div>
          )}

          {error && <div className="aiq-error">{error}</div>}

          <div ref={chatEndRef} />
        </div>

        <form
          className="aiq-input"
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
        >
          <input
            type="text"
            placeholder="Ask a question about your dataset..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={loading}
          />

          <button type="submit" disabled={loading || !question.trim()}>
            <Send size={18} />
            Send
          </button>
        </form>

        <p className="aiq-footer">
          Analyzing:{" "}
          {usedVersion
            ? usedVersion === "cleaned"
              ? "cleaned data"
              : "original data"
            : version === "cleaned"
            ? "cleaned data when available, otherwise original"
            : "original data"}
        </p>
      </div>
    </div>
  );
}

export default AIQuestionsPage;