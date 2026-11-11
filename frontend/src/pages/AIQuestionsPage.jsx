
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Sparkles,
  Bot,
  User,
  RotateCcw,
} from "lucide-react";

function AIQuestionsPage({ dataset }) {
  const [question, setQuestion] = useState("");
  const [version, setVersion] = useState("original");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chatEndRef = useRef(null);

  const suggestions = [
    "How many missing values are there?",
    "Which columns contain missing values?",
    "What is the average value of numerical columns?",
    "Are there any duplicate rows?",
    "Give me some insights about this dataset.",
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleAsk = async (selectedQuestion = question) => {
    const trimmedQuestion = selectedQuestion.trim();

    if (!trimmedQuestion || loading) return;

    const previousMessages = messages;

    const userMessage = {
      role: "user",
      content: trimmedQuestion,
      version,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/datasets/${dataset.dataset_id}/ask`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: trimmedQuestion,
            version,
            history: previousMessages.slice(-8).map((message) => ({
              role: message.role,
              content: message.content,
            })),
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to get an answer.");
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
          version,
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
    <div className="workspace-page">
      <span className="eyebrow">AI ANALYTICS</span>
      <h2>Ask questions about your data</h2>
      <p>
        Explore your dataset through a natural conversation
        with DataLens AI.
      </p>

      <div className="ai-chat-container">
        <div className="ai-chat-header">
          <div className="ai-chat-title">
            <div className="ai-avatar">
              <Sparkles size={20} />
            </div>
            <div>
              <h3>DataLens Assistant</h3>
              <span>AI-powered data analysis</span>
            </div>
          </div>

          <div className="ai-chat-controls">
            <select
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              disabled={loading}
              aria-label="Select dataset version"
            >
              <option value="original">Original Dataset</option>
              <option value="cleaned">Cleaned Dataset</option>
            </select>

            <button
              type="button"
              className="clear-chat-button"
              onClick={handleClearChat}
              disabled={loading || messages.length === 0}
              title="Clear conversation"
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        <div className="ai-chat-messages">
          {messages.length === 0 ? (
            <div className="ai-welcome">
              <div className="ai-welcome-icon">
                <Sparkles size={28} />
              </div>

              <h3>Hi! I'm your DataLens Assistant.</h3>

              <p>
                Ask me anything about your uploaded dataset.
                I can help you understand missing values,
                statistics, patterns and more.
              </p>

              <div className="ai-suggestions">
                <span>Try asking</span>

                {suggestions.map((item) => (
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
                className={`ai-message ${
                  message.role === "user"
                    ? "user-message"
                    : "assistant-message"
                }`}
                key={index}
              >
                <div className="message-avatar">
                  {message.role === "user" ? (
                    <User size={17} />
                  ) : (
                    <Bot size={18} />
                  )}
                </div>

                <div className="message-content">
                  <div className="message-meta">
                    <strong>
                      {message.role === "user"
                        ? "You"
                        : "DataLens AI"}
                    </strong>
                    <span>
                      {message.version === "cleaned"
                        ? "Cleaned dataset"
                        : "Original dataset"}
                    </span>
                  </div>

                  <div className="message-text">
                    {message.role === "assistant" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="ai-message assistant-message">
              <div className="message-avatar">
                <Bot size={18} />
              </div>

              <div className="message-content">
                <div className="message-meta">
                  <strong>DataLens AI</strong>
                </div>
                <p className="typing-indicator">
                  Analyzing your dataset...
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="ai-chat-error">
              {error}
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <form
          className="ai-chat-input"
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

          <button
            type="submit"
            disabled={loading || !question.trim()}
          >
            <Send size={18} />
            Send
          </button>
        </form>

        <p className="ai-chat-footer">
          Currently analyzing:{" "}
          {version === "original" ? "Original" : "Cleaned"} dataset
        </p>
      </div>
    </div>
  );
}

export default AIQuestionsPage;
