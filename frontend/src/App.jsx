import { useState } from "react";
import "./App.css";

function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm NEXA AI. How can I help you today?",
    },
  ]);

  const [input, setInput] = useState("");

  const sendMessage = () => {
    if (!input.trim()) return;

    const userMessage = {
      role: "user",
      content: input,
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
      {
        role: "assistant",
        content:
          "I'm connected to the frontend. Backend API integration is coming next.",
      },
    ]);

    setInput("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app">

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">N</div>

          <div>
            <h1>NEXA AI</h1>
            <span>AI Assistant</span>
          </div>
        </div>

        <button className="new-chat-button">
          <span>＋</span>
          New Conversation
        </button>

        <div className="conversation-section">
          <p className="section-title">CONVERSATIONS</p>

          <div className="conversation-item active">
            <span className="conversation-icon">💬</span>

            <div className="conversation-info">
              <span>New Conversation</span>
              <small>Just now</small>
            </div>
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="status-dot"></div>
          <span>AI System Online</span>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-area">

        {/* Header */}
        <header className="chat-header">
          <div>
            <h2>AI Assistant</h2>
            <p>
              Ask questions and get intelligent responses
            </p>
          </div>

          <div className="online-status">
            <span></span>
            Online
          </div>
        </header>

        {/* Messages */}
        <section className="messages-container">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`message-row ${message.role}`}
            >
              <div className="avatar">
                {message.role === "user" ? "D" : "N"}
              </div>

              <div className="message-content">
                <div className="message-name">
                  {message.role === "user"
                    ? "You"
                    : "NEXA AI"}
                </div>

                <div className="message-bubble">
                  {message.content}
                </div>
              </div>
            </div>
          ))}
        </section>

        {/* Input */}
        <div className="input-area">
          <div className="input-wrapper">

            <textarea
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask NEXA AI anything..."
              rows="1"
            />

            <button
              className="send-button"
              onClick={sendMessage}
              disabled={!input.trim()}
            >
              ➤
            </button>

          </div>

          <p className="input-hint">
            Press Enter to send • Shift + Enter for a new line
          </p>
        </div>

      </main>
    </div>
  );
}

export default App;