import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const USER_ID = 1;

const WELCOME_MESSAGE = {
  role: "assistant",
  content: "Hello! I'm NEXA AI. How can I help you today?",
};

function App() {
  // ============================================================
  // STATE
  // ============================================================

  const [conversationId, setConversationId] = useState(null);

  const [conversations, setConversations] = useState([]);

  const [messages, setMessages] = useState([
    {
      id: "welcome",
      ...WELCOME_MESSAGE,
    },
  ]);

  const [input, setInput] = useState("");

  const [loading, setLoading] = useState(false);

  const [copiedMessageId, setCopiedMessageId] = useState(null);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [editingConversationId, setEditingConversationId] =
    useState(null);

  const [editingTitle, setEditingTitle] = useState("");

  // ============================================================
  // REFS
  // ============================================================

  const messagesEndRef = useRef(null);

  const textareaRef = useRef(null);

  const conversationCreatedRef = useRef(false);

  // ============================================================
  // AUTO SCROLL
  // ============================================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: loading ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, loading]);

  // ============================================================
  // INITIALIZE APPLICATION
  // ============================================================

  useEffect(() => {
    if (conversationCreatedRef.current) {
      return;
    }

    conversationCreatedRef.current = true;

    initializeChat();
  }, []);

  // ============================================================
  // LOAD ALL CONVERSATIONS
  // ============================================================

  async function loadConversations() {
    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/user/${USER_ID}`,
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText || "Could not load conversation history"
        );
      }

      const data = await response.json();

      if (!Array.isArray(data)) {
        console.warn(
          "Unexpected conversations response:",
          data
        );

        return [];
      }

      /*
       * Keep backend order.
       *
       * If your backend returns updated_at, this additionally
       * puts recently updated conversations first.
       */
      const sortedConversations = [...data].sort(
        (a, b) => {
          if (!a.updated_at || !b.updated_at) {
            return 0;
          }

          return (
            new Date(b.updated_at) -
            new Date(a.updated_at)
          );
        }
      );

      setConversations(sortedConversations);

      console.log(
        "Conversation history refreshed:",
        sortedConversations
      );

      return sortedConversations;
    } catch (error) {
      console.error(
        "Conversation history error:",
        error
      );

      return [];
    }
  }

  // ============================================================
  // INITIALIZE CHAT
  // ============================================================

  async function initializeChat() {
    try {
      const data = await loadConversations();

      // --------------------------------------------------------
      // Existing conversations
      // --------------------------------------------------------

      if (data.length > 0) {
        const firstConversationId = data[0].id;

        setConversationId(firstConversationId);

        console.log(
          "Loaded existing conversation:",
          firstConversationId
        );

        await loadConversationMessages(
          firstConversationId
        );

        return;
      }

      // --------------------------------------------------------
      // No conversations
      // --------------------------------------------------------

      console.log(
        "No conversations found. Creating first conversation."
      );

      await createConversation();
    } catch (error) {
      console.error(
        "Chat initialization error:",
        error
      );
    }
  }

  // ============================================================
  // CREATE CONVERSATION
  // ============================================================

  async function createConversation(
    customTitle = "New Conversation"
  ) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            user_id: USER_ID,
            title: customTitle,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText ||
            "Could not create conversation"
        );
      }

      const conversation =
        await response.json();

      console.log(
        "NEXA AI conversation created:",
        conversation
      );

      // Add new conversation to top
      setConversations((previous) => [
        conversation,
        ...previous.filter(
          (item) =>
            item.id !== conversation.id
        ),
      ]);

      setConversationId(
        conversation.id
      );

      setMessages([
        {
          id: `welcome-${conversation.id}`,
          ...WELCOME_MESSAGE,
        },
      ]);

      setInput("");

      resetTextarea();

      return conversation;
    } catch (error) {
      console.error(
        "Conversation creation error:",
        error
      );

      return null;
    }
  }

  // ============================================================
  // LOAD CONVERSATION MESSAGES
  // ============================================================

  async function loadConversationMessages(
    conversationIdToLoad
  ) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/${conversationIdToLoad}/messages`,
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText ||
            "Could not load conversation messages"
        );
      }

      const data = await response.json();

      console.log(
        "Loaded conversation messages:",
        conversationIdToLoad,
        data
      );

      // --------------------------------------------------------
      // Invalid response
      // --------------------------------------------------------

      if (!Array.isArray(data)) {
        console.warn(
          "Unexpected message history response:",
          data
        );

        setMessages([
          {
            id: `welcome-${conversationIdToLoad}`,
            ...WELCOME_MESSAGE,
          },
        ]);

        return;
      }

      // --------------------------------------------------------
      // Empty conversation
      // --------------------------------------------------------

      if (data.length === 0) {
        setMessages([
          {
            id: `welcome-${conversationIdToLoad}`,
            ...WELCOME_MESSAGE,
          },
        ]);

        return;
      }

      // --------------------------------------------------------
      // Convert backend messages to frontend format
      // --------------------------------------------------------

      const historyMessages = data.map(
        (message) => ({
          id: message.id,
          role: message.role,
          content: message.content || "",
        })
      );

      setMessages(historyMessages);
    } catch (error) {
      console.error(
        "Conversation history loading error:",
        error
      );

      setMessages([
        {
          id: `welcome-${conversationIdToLoad}`,
          ...WELCOME_MESSAGE,
        },
      ]);
    }
  }

  // ============================================================
  // CREATE TITLE FROM FIRST MESSAGE
  // ============================================================

  function generateConversationTitle(text) {
    let title = text.trim();

    /*
     * Remove excessive whitespace.
     */
    title = title.replace(/\s+/g, " ");

    /*
     * Keep sidebar titles short.
     */
    const maxLength = 45;

    if (title.length > maxLength) {
      title =
        title.substring(0, maxLength).trim() +
        "...";
    }

    return title || "New Conversation";
  }

  // ============================================================
  // UPDATE CONVERSATION TITLE
  // ============================================================

  async function updateConversationTitle(
    conversationIdToUpdate,
    firstMessage
  ) {
    const conversation =
      conversations.find(
        (item) =>
          item.id ===
          conversationIdToUpdate
      );

    /*
     * Only automatically rename chats that still have
     * the default title.
     *
     * This means manually renamed conversations are safe.
     */
    if (
      conversation &&
      conversation.title &&
      conversation.title !==
        "New Conversation"
    ) {
      return;
    }

    const title =
      generateConversationTitle(
        firstMessage
      );

    if (
      !title ||
      title === "New Conversation"
    ) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/${conversationIdToUpdate}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
            Accept:
              "application/json",
          },
          body: JSON.stringify({
            title,
          }),
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            "Could not update conversation title"
        );
      }

      const updated =
        await response.json();

      console.log(
        "Conversation title updated:",
        updated
      );

      setConversations(
        (previous) =>
          previous.map(
            (conversationItem) =>
              conversationItem.id ===
              conversationIdToUpdate
                ? updated
                : conversationItem
          )
      );
    } catch (error) {
      console.error(
        "Conversation title update error:",
        error
      );
    }
  }

  // ============================================================
  // NEW CHAT
  // ============================================================

  async function handleNewChat() {
    if (loading) {
      return;
    }

    const conversation =
      await createConversation(
        "New Conversation"
      );

    if (conversation) {
      setSidebarOpen(false);
    }
  }

  // ============================================================
  // SELECT CONVERSATION
  // ============================================================

  async function selectConversation(id) {
    if (loading) {
      return;
    }

    setConversationId(id);

    setInput("");

    resetTextarea();

    setSidebarOpen(false);

    /*
     * Clear current messages while loading
     * selected conversation history.
     */
    setMessages([]);

    console.log(
      "Selected conversation:",
      id
    );

    await loadConversationMessages(id);
  }

  // ============================================================
  // RENAME CONVERSATION
  // ============================================================

  function startRename(conversation) {
    setEditingConversationId(
      conversation.id
    );

    setEditingTitle(
      conversation.title || ""
    );
  }

  async function saveRename(
    conversationIdToRename
  ) {
    const title =
      editingTitle.trim();

    if (!title) {
      setEditingConversationId(null);
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/${conversationIdToRename}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type":
              "application/json",
            Accept:
              "application/json",
          },
          body: JSON.stringify({
            title,
          }),
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            "Could not rename conversation"
        );
      }

      const updated =
        await response.json();

      setConversations(
        (previous) =>
          previous.map(
            (conversation) =>
              conversation.id ===
              conversationIdToRename
                ? updated
                : conversation
          )
      );

      setEditingConversationId(null);

      setEditingTitle("");
    } catch (error) {
      console.error(
        "Rename conversation error:",
        error
      );
    }
  }

  // ============================================================
  // DELETE CONVERSATION
  // ============================================================

  async function deleteConversation(
    conversationIdToDelete
  ) {
    if (loading) {
      return;
    }

    const confirmed =
      window.confirm(
        "Delete this conversation?"
      );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/conversations/${conversationIdToDelete}`,
        {
          method: "DELETE",
          headers: {
            Accept: "application/json",
          },
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            "Could not delete conversation"
        );
      }

      const remaining =
        conversations.filter(
          (conversation) =>
            conversation.id !==
            conversationIdToDelete
        );

      setConversations(
        remaining
      );

      // --------------------------------------------------------
      // Deleted current conversation
      // --------------------------------------------------------

      if (
        conversationId ===
        conversationIdToDelete
      ) {
        if (remaining.length > 0) {
          const nextConversation =
            remaining[0];

          setConversationId(
            nextConversation.id
          );

          await loadConversationMessages(
            nextConversation.id
          );
        } else {
          await createConversation();
        }
      }
    } catch (error) {
      console.error(
        "Delete conversation error:",
        error
      );
    }
  }

  // ============================================================
  // AUTO RESIZE TEXTAREA
  // ============================================================

  function resizeTextarea() {
    const textarea =
      textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";

    const maxHeight = 180;

    textarea.style.height =
      `${Math.min(
        textarea.scrollHeight,
        maxHeight
      )}px`;
  }

  // ============================================================
  // INPUT CHANGE
  // ============================================================

  function handleInputChange(event) {
    setInput(event.target.value);

    requestAnimationFrame(() => {
      resizeTextarea();
    });
  }

  // ============================================================
  // RESET INPUT HEIGHT
  // ============================================================

  function resetTextarea() {
    const textarea =
      textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";
  }

  // ============================================================
  // COPY AI RESPONSE
  // ============================================================

  async function copyMessage(
    messageId,
    content
  ) {
    try {
      await navigator.clipboard.writeText(
        content
      );

      setCopiedMessageId(
        messageId
      );

      setTimeout(() => {
        setCopiedMessageId(null);
      }, 1800);
    } catch (error) {
      console.error(
        "Could not copy message:",
        error
      );
    }
  }

  // ============================================================
  // SEND MESSAGE
  // ============================================================

  async function sendMessage() {
    const text = input.trim();

    if (!text) {
      return;
    }

    if (loading) {
      return;
    }

    if (!conversationId) {
      console.warn(
        "Conversation is not ready yet."
      );

      return;
    }

    // ========================================================
    // SAVE CURRENT CONVERSATION ID
    // ========================================================

    const activeConversationId =
      conversationId;

    // ========================================================
    // CHECK WHETHER THIS IS FIRST USER MESSAGE
    // ========================================================

    const hasPreviousUserMessage =
      messages.some(
        (message) =>
          message.role === "user"
      );

    // ========================================================
    // USER MESSAGE
    // ========================================================

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };

    setMessages(
      (previous) => [
        ...previous,
        userMessage,
      ]
    );

    setInput("");

    resetTextarea();

    setLoading(true);

    // ========================================================
    // EMPTY ASSISTANT MESSAGE
    // ========================================================

    const assistantId =
      `assistant-${Date.now()}`;

    setMessages(
      (previous) => [
        ...previous,
        {
          id: assistantId,
          role: "assistant",
          content: "",
        },
      ]
    );

    try {
      // ======================================================
      // STREAMING API REQUEST
      // ======================================================

      const response = await fetch(
        `${API_BASE_URL}/conversations/${activeConversationId}/messages/stream`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",

            Accept:
              "text/event-stream",
          },

          body: JSON.stringify({
            content: text,
          }),
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            `Request failed with status ${response.status}`
        );
      }

      if (!response.body) {
        throw new Error(
          "Streaming is not supported by this browser."
        );
      }

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder("utf-8");

      let buffer = "";

      // ======================================================
      // PROCESS STREAM
      // ======================================================

      while (true) {
        const {
          value,
          done,
        } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(
          value,
          {
            stream: true,
          }
        );

        const events =
          buffer.split(
            /\r?\n\r?\n/
          );

        buffer =
          events.pop() || "";

        // ====================================================
        // PROCESS EVENTS
        // ====================================================

        for (const event of events) {
          const lines =
            event.split(/\r?\n/);

          for (const line of lines) {
            if (
              !line.startsWith(
                "data:"
              )
            ) {
              continue;
            }

            const jsonText =
              line
                .slice(5)
                .trim();

            if (!jsonText) {
              continue;
            }

            let data;

            try {
              data =
                JSON.parse(
                  jsonText
                );
            } catch (error) {
              console.warn(
                "Invalid streaming event:",
                jsonText
              );

              continue;
            }

            // ==============================================
            // TEXT CHUNK
            // ==============================================

            if (
              data.type ===
              "chunk"
            ) {
              const chunk =
                data.content ||
                "";

              if (!chunk) {
                continue;
              }

              setMessages(
                (previous) =>
                  previous.map(
                    (message) =>
                      message.id ===
                      assistantId
                        ? {
                            ...message,
                            content:
                              message.content +
                              chunk,
                          }
                        : message
                  )
              );
            }

            // ==============================================
            // STREAM COMPLETE
            // ==============================================

            else if (
              data.type ===
              "done"
            ) {
              if (
                data.message
              ) {
                setMessages(
                  (previous) =>
                    previous.map(
                      (message) =>
                        message.id ===
                        assistantId
                          ? {
                              ...message,

                              id:
                                data.message
                                  .id ||
                                assistantId,

                              content:
                                data.message
                                  .content ||
                                message.content,
                            }
                          : message
                    )
                );
              }

              console.log(
                "NEXA AI response completed."
              );
            }

            // ==============================================
            // BACKEND ERROR
            // ==============================================

            else if (
              data.type ===
              "error"
            ) {
              throw new Error(
                data.message ||
                  "AI service temporarily unavailable."
              );
            }
          }
        }
      }

      // ======================================================
      // FINAL BUFFER
      // ======================================================

      if (buffer.trim()) {
        const lines =
          buffer.split(/\r?\n/);

        for (const line of lines) {
          if (
            !line.startsWith(
              "data:"
            )
          ) {
            continue;
          }

          const jsonText =
            line
              .slice(5)
              .trim();

          if (!jsonText) {
            continue;
          }

          try {
            const data =
              JSON.parse(
                jsonText
              );

            if (
              data.type ===
                "chunk" &&
              data.content
            ) {
              setMessages(
                (previous) =>
                  previous.map(
                    (message) =>
                      message.id ===
                      assistantId
                        ? {
                            ...message,
                            content:
                              message.content +
                              data.content,
                          }
                        : message
                  )
              );
            }

            if (
              data.type ===
                "done" &&
              data.message
            ) {
              setMessages(
                (previous) =>
                  previous.map(
                    (message) =>
                      message.id ===
                      assistantId
                        ? {
                            ...message,

                            id:
                              data.message
                                .id ||
                              assistantId,

                            content:
                              data.message
                                .content ||
                              message.content,
                          }
                        : message
                  )
              );
            }
          } catch (error) {
            console.warn(
              "Could not parse final event:",
              jsonText
            );
          }
        }
      }

      // ======================================================
      // AUTOMATICALLY NAME NEW CONVERSATION
      // ======================================================

      if (!hasPreviousUserMessage) {
        await updateConversationTitle(
          activeConversationId,
          text
        );
      }

      // ======================================================
      // REFRESH CONVERSATION HISTORY
      // ======================================================

      await loadConversations();

      console.log(
        "Conversation history refreshed after message."
      );
    } catch (error) {
      console.error(
        "NEXA AI streaming error:",
        error
      );

      setMessages(
        (previous) =>
          previous.map(
            (message) =>
              message.id ===
              assistantId
                ? {
                    ...message,
                    content:
                      "Sorry, I couldn't process your request. Please try again.",
                  }
                : message
          )
      );
    } finally {
      setLoading(false);
    }
  }

  // ============================================================
  // KEYBOARD HANDLING
  // ============================================================

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      sendMessage();
    }
  }

  // ============================================================
  // CURRENT CONVERSATION
  // ============================================================

  const currentConversation =
    conversations.find(
      (conversation) =>
        conversation.id ===
        conversationId
    );

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="app">

      {/* ======================================================
          MOBILE OVERLAY
      ====================================================== */}

      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={() =>
            setSidebarOpen(false)
          }
        />
      )}

      {/* ======================================================
          SIDEBAR
      ====================================================== */}

      <aside
        className={`sidebar ${
          sidebarOpen
            ? "sidebar-open"
            : ""
        }`}
      >

        {/* SIDEBAR HEADER */}

        <div className="sidebar-header">

          <div className="sidebar-brand">

            <div className="sidebar-logo">
              N
            </div>

            <div>
              <h2>NEXA AI</h2>

              <span>
                Intelligent AI Assistant
              </span>
            </div>

          </div>

          <button
            className="sidebar-close"
            onClick={() =>
              setSidebarOpen(false)
            }
            type="button"
            aria-label="Close sidebar"
          >
            ×
          </button>

        </div>

        {/* NEW CHAT */}

        <button
          className="new-chat-button"
          onClick={handleNewChat}
          disabled={loading}
          type="button"
        >
          <span className="new-chat-icon">
            +
          </span>

          <span>
            New Chat
          </span>
        </button>

        {/* CONVERSATION TITLE */}

        <div className="conversation-heading">

          <span>
            Conversations
          </span>

          <span className="conversation-count">
            {conversations.length}
          </span>

        </div>

        {/* CONVERSATIONS */}

        <div className="conversation-list">

          {conversations.length === 0 ? (
            <div className="empty-conversations">
              No conversations yet
            </div>
          ) : (
            conversations.map(
              (conversation) => (
                <div
                  key={conversation.id}
                  className={`conversation-item ${
                    conversation.id ===
                    conversationId
                      ? "active"
                      : ""
                  }`}
                >

                  {editingConversationId ===
                  conversation.id ? (
                    <input
                      className="conversation-edit-input"
                      value={
                        editingTitle
                      }
                      onChange={(
                        event
                      ) =>
                        setEditingTitle(
                          event.target
                            .value
                        )
                      }
                      onKeyDown={(
                        event
                      ) => {
                        if (
                          event.key ===
                          "Enter"
                        ) {
                          saveRename(
                            conversation.id
                          );
                        }

                        if (
                          event.key ===
                          "Escape"
                        ) {
                          setEditingConversationId(
                            null
                          );

                          setEditingTitle(
                            ""
                          );
                        }
                      }}
                      onBlur={() =>
                        saveRename(
                          conversation.id
                        )
                      }
                      autoFocus
                    />
                  ) : (
                    <>
                      <button
                        className="conversation-main"
                        onClick={() =>
                          selectConversation(
                            conversation.id
                          )
                        }
                        type="button"
                      >

                        <span className="conversation-icon">
                          ◇
                        </span>

                        <span className="conversation-title">
                          {
                            conversation.title ||
                            "New Conversation"
                          }
                        </span>

                      </button>

                      <div className="conversation-actions">

                        <button
                          type="button"
                          className="conversation-action"
                          onClick={() =>
                            startRename(
                              conversation
                            )
                          }
                          title="Rename"
                          aria-label="Rename conversation"
                        >
                          ✎
                        </button>

                        <button
                          type="button"
                          className="conversation-action delete"
                          onClick={() =>
                            deleteConversation(
                              conversation.id
                            )
                          }
                          title="Delete"
                          aria-label="Delete conversation"
                        >
                          ×
                        </button>

                      </div>
                    </>
                  )}

                </div>
              )
            )
          )}

        </div>

        {/* SIDEBAR FOOTER */}

        <div className="sidebar-footer">

          <div className="sidebar-status-dot" />

          <span>
            NEXA AI is online
          </span>

        </div>

      </aside>

      {/* ======================================================
          MAIN AREA
      ====================================================== */}

      <div className="main-area">

        {/* ====================================================
            HEADER
        ==================================================== */}

        <header className="header">

          <div className="header-left">

            <button
              className="menu-button"
              onClick={() =>
                setSidebarOpen(true)
              }
              type="button"
              aria-label="Open conversations"
            >
              ☰
            </button>

            <div className="brand">

              <div className="brand-logo">
                N
              </div>

              <div className="brand-text">

                <h1>
                  {currentConversation?.title ||
                    "NEXA AI"}
                </h1>

                <p>
                  Intelligent AI Assistant
                </p>

              </div>

            </div>

          </div>

          <div className="status">

            <span className="status-dot" />

            <span>
              Online
            </span>

          </div>

        </header>

        {/* ====================================================
            CHAT
        ==================================================== */}

        <main className="chat-container">

          <div className="chat-content">

            {messages.map(
              (message) => {

                const isUser =
                  message.role ===
                  "user";

                const isAssistant =
                  message.role ===
                  "assistant";

                const isStreaming =
                  loading &&
                  isAssistant &&
                  message.id ===
                    messages[
                      messages.length -
                        1
                    ]?.id;

                return (
                  <div
                    key={message.id}
                    className={`message-row ${
                      isUser
                        ? "user-row"
                        : "assistant-row"
                    }`}
                  >

                    {/* ASSISTANT AVATAR */}

                    {isAssistant && (
                      <div className="avatar assistant-avatar">
                        N
                      </div>
                    )}

                    {/* MESSAGE */}

                    <div className="message-wrapper">

                      <div className="message-header">

                        <span className="message-name">
                          {isUser
                            ? "You"
                            : "NEXA AI"}
                        </span>

                      </div>

                      <div
                        className={`message-bubble ${
                          isUser
                            ? "user-message"
                            : "assistant-message"
                        }`}
                      >

                        {isAssistant ? (
                          message.content ? (
                            <div className="markdown-content">

                              <ReactMarkdown
                                remarkPlugins={[
                                  remarkGfm,
                                ]}
                                components={{
                                  a: ({
                                    node,
                                    ...props
                                  }) => (
                                    <a
                                      {...props}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                    />
                                  ),

                                  code: ({
                                    inline,
                                    children,
                                    ...props
                                  }) =>
                                    inline ? (
                                      <code
                                        className="inline-code"
                                        {...props}
                                      >
                                        {children}
                                      </code>
                                    ) : (
                                      <pre className="code-block">
                                        <code
                                          {...props}
                                        >
                                          {children}
                                        </code>
                                      </pre>
                                    ),
                                }}
                              >
                                {
                                  message.content
                                }
                              </ReactMarkdown>

                            </div>
                          ) : (
                            <div className="thinking-state">

                              <span />
                              <span />
                              <span />

                            </div>
                          )
                        ) : (
                          <div className="user-text">
                            {
                              message.content
                            }
                          </div>
                        )}

                        {isStreaming &&
                          message.content && (
                            <span className="streaming-cursor">
                              ▌
                            </span>
                          )}

                      </div>

                      {/* COPY */}

                      {isAssistant &&
                        message.content &&
                        !isStreaming && (
                          <button
                            className="copy-button"
                            onClick={() =>
                              copyMessage(
                                message.id,
                                message.content
                              )
                            }
                            type="button"
                          >
                            {
                              copiedMessageId ===
                              message.id
                                ? "Copied"
                                : "Copy"
                            }
                          </button>
                        )}

                    </div>

                    {/* USER AVATAR */}

                    {isUser && (
                      <div className="avatar user-avatar">
                        D
                      </div>
                    )}

                  </div>
                );
              }
            )}

            <div
              ref={messagesEndRef}
            />

          </div>

        </main>

        {/* ====================================================
            INPUT
        ==================================================== */}

        <footer className="input-section">

          <div className="input-container">

            <textarea
              ref={textareaRef}
              value={input}
              onChange={
                handleInputChange
              }
              onKeyDown={
                handleKeyDown
              }
              placeholder={
                conversationId
                  ? "Ask NEXA AI anything..."
                  : "Connecting to NEXA AI..."
              }
              rows="1"
              disabled={!conversationId}
            />

            <button
              className="send-button"
              onClick={sendMessage}
              disabled={
                loading ||
                !input.trim() ||
                !conversationId
              }
              aria-label="Send message"
            >
              ➤
            </button>

          </div>

          <p className="input-hint">

            {loading
              ? "NEXA AI is generating a response..."
              : "Enter to send • Shift + Enter for a new line"}

          </p>

        </footer>

      </div>

    </div>
  );
}

export default App;