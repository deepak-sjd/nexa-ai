"""
Run from the frontend/ folder:   python patch_app_auth.py

Patches src/App.jsx in place (backup: src/App.jsx.bak2):
  - every API call goes through authFetch (sends the login token)
  - avatar shows the user's initial, sidebar gets a "Log out" button
  - image generation UI is removed

Every edit must match exactly once or NOTHING is changed and the script
lists which edit missed. Safe to run twice.
"""
import pathlib
import re
import sys

APP = pathlib.Path("src/App.jsx")

EXAMPLE_PROMPTS_NEW = '''  {
    label: "Explain a topic simply",
    prompt:
      "Explain how vector databases work in simple terms.",
  },
  {
    label: "Draw a sequence diagram",
    prompt:
      "Show me a sequence diagram of how a chat message flows through this system.",
  },
'''

# (name, old, new, already_done(text) -> bool)
EDITS = [
    ("imports",
     '''import { API_BASE_URL } from "./services/api";
import { useImageGeneration } from "./hooks/useImageGeneration";
import { normalizeHistory, parseImageCommand } from "./utils/imageMessage";
import GeneratedImage from "./components/GeneratedImage";
import {
  ImageErrorCard,
  ImageGeneratingCard,
} from "./components/ImageStatusCards";
import { ImageIcon, AlertIcon, RefreshIcon } from "./components/ImageIcons";
''',
     '''import { API_BASE_URL } from "./services/api";
import { authFetch } from "./services/auth";
import { useAuth } from "./context/useAuth";
import { normalizeHistory } from "./utils/imageMessage";
import { ImageErrorCard } from "./components/ImageStatusCards";
import { AlertIcon, RefreshIcon } from "./components/ImageIcons";
''',
     lambda t: 'from "./context/useAuth"' in t),

    ("example prompts (no image ones)",
     '''  {
    label: "Create an image",
    prompt:
      "A serene mountain lake at sunrise, soft watercolor style",
    mode: "image",
  },
  {
    label: "Design a logo",
    prompt:
      "A minimal logo for a coffee shop called Ember, flat vector, warm colors",
    mode: "image",
  },
''',
     EXAMPLE_PROMPTS_NEW,
     lambda t: "Explain a topic simply" in t),

    ("empty-state subtitle",
     '''        Ask a question, upload a document, request a
        diagram, or create an image — NEXA AI grounds its
        answers in what it actually knows.
''',
     '''        Ask a question, upload a document, or request a
        diagram — NEXA AI grounds its answers in what it
        actually knows.
''',
     lambda t: "or request a\n        diagram" in t),

    ("function App: useAuth + initial",
     'function App() {\n',
     '''function App() {
  const { user, logout } = useAuth();

  const userInitial = (user?.name || user?.email || "U")
    .charAt(0)
    .toUpperCase();

''',
     lambda t: "const { user, logout } = useAuth();" in t),

    ("imageMode state",
     '''  // When on, the next message is sent to the image endpoint
  // instead of the chat endpoint. One-shot: it switches itself
  // off after sending so a stray Enter never costs an image.
  const [imageMode, setImageMode] = useState(false);

''',
     '',
     lambda t: "const [imageMode" not in t),

    ("image generation hook",
     '''  const {
    generate: generateImage,
    cancel: cancelImageGeneration,
    retry: retryImageGeneration,
  } = useImageGeneration({
    conversationId,
    setMessages,
    setLoading,
    onConversationUpdate: applyConversationTitleUpdate,
  });
''',
     '  // (Image generation was removed from this app.)\n',
     lambda t: "useImageGeneration({" not in t),

    ("example prompt click",
     '''  function handleExamplePromptClick(promptText, mode) {
    setImageMode(mode === "image");

    setInput(promptText);
''',
     '''  function handleExamplePromptClick(promptText) {
    setInput(promptText);
''',
     lambda t: "handleExamplePromptClick(promptText) {" in t),

    ("handleImageLoaded",
     '''  function handleImageLoaded() {
    messagesEndRef.current?.scrollIntoView({
      behavior: "auto",
      block: "end",
    });
  }
''',
     '',
     lambda t: "function handleImageLoaded" not in t),

    ("sendMessage image branch",
     '''    const imageCommand = parseImageCommand(text);

    if (imageMode || imageCommand) {
      const imagePrompt = imageCommand ? imageCommand.prompt : text;

      setInput("");

      resetTextarea();

      if (!imagePrompt) {
        // A bare "/image" just switches the composer to image mode.
        setImageMode(true);

        return;
      }

      stopSpeaking();

      setImageMode(false);

      // Image mode and a composer attachment don't really combine —
      // drop the (unrelated) chip so it doesn't linger stale.
      setAttachedFile(null);

      generateImage(imagePrompt);

      return;
    }

''',
     '',
     lambda t: "parseImageCommand(text)" not in t),

    ("sendMessage header comment",
     '    // IMAGE REQUEST ("image mode" toggle or /image command)\n',
     '    // STOP ANY SPEECH\n',
     lambda t: "// STOP ANY SPEECH" in t),

    ("isCreatingImage",
     '''  const isCreatingImage = messages.some(
    (message) => message.kind === "image-pending"
  );

''',
     '',
     lambda t: "const isCreatingImage" not in t),

    ("history: drop old image messages",
     '      setMessages(normalizeHistory(data));\n',
     '''      // Old generated-image messages are dropped (feature removed).
      setMessages(
        normalizeHistory(data).filter((message) => !message.image)
      );
''',
     lambda t: "filter((message) => !message.image)" in t),

    ("message render: image branches",
     '''                          ) : message.kind === "image-pending" ? (
                            <ImageGeneratingCard
                              startedAt={message.startedAt}
                              onCancel={cancelImageGeneration}
                            />
                          ) : message.kind === "image-error" ? (
                            <ImageErrorCard
                              message={message.error}
                              cancelled={message.cancelled}
                              retryDisabled={loading}
                              onRetry={() =>
                                retryImageGeneration(
                                  message.clientId,
                                  message.prompt
                                )
                              }
                            />
                          ) : message.image ? (
                            <GeneratedImage
                              src={message.image.src}
                              prompt={message.image.prompt}
                              caption={message.content}
                              onRegenerate={generateImage}
                              regenerateDisabled={loading}
                              // Only freshly generated images (which
                              // have a clientId) re-scroll on load;
                              // history images lazy-load as you
                              // scroll up and must not yank the view.
                              onLoad={
                                message.clientId
                                  ? handleImageLoaded
                                  : undefined
                              }
                            />
                          ) : message.content ? (
''',
     '''                          ) : message.content ? (
''',
     lambda t: "<GeneratedImage" not in t),

    ("composer menu: Create image item",
     '''
                  <button
                    type="button"
                    className="composer-menu-item"
                    onClick={() => {
                      setComposerMenuOpen(false);
                      setImageMode(true);
                      textareaRef.current?.focus();
                    }}
                  >
                    <span className="composer-menu-icon">
                      <ImageIcon size={16} />
                    </span>

                    Create image
                  </button>
''',
     '',
     lambda t: "Create image\n" not in t),

    ("textarea placeholder",
     '''                  : imageMode
                  ? "Describe the image you want to create..."
                  : conversationId
''',
     '''                  : conversationId
''',
     lambda t: "Describe the image you want" not in t),

    ("image toggle button",
     '''            <button
              type="button"
              className="image-toggle-button"
              onClick={() => setImageMode((current) => !current)}
              aria-pressed={imageMode}
              disabled={!conversationId || loading}
              aria-label={
                imageMode ? "Turn off image mode" : "Create an image"
              }
              title={
                imageMode
                  ? "Image mode on — click to turn off"
                  : "Create an image"
              }
            >
              <ImageIcon />
            </button>

''',
     '',
     lambda t: "image-toggle-button" not in t),

    ("send button label",
     '              aria-label={imageMode ? "Create image" : "Send message"}\n',
     '              aria-label="Send message"\n',
     lambda t: 'aria-label="Send message"' in t),

    ("input hint",
     '''            {isUploading ? (
              "Uploading document..."
            ) : loading ? (
              isCreatingImage ? (
                "Creating your image..."
              ) : (
                "NEXA AI is generating a response..."
              )
            ) : imageMode ? (
              <>
                <span className="input-hint-mode">Image mode</span>
                {" • Enter to create • Shift + Enter for a new line"}
              </>
            ) : (
              "Enter to send • Shift + Enter for a new line • /image to create an image"
            )}
''',
     '''            {isUploading ? (
              "Uploading document..."
            ) : loading ? (
              "NEXA AI is generating a response..."
            ) : (
              "Enter to send • Shift + Enter for a new line"
            )}
''',
     lambda t: "/image to create an image" not in t),

    ("user avatar initial",
     '''                      <div className="avatar user-avatar">
                        D
                      </div>
''',
     '''                      <div className="avatar user-avatar">
                        {userInitial}
                      </div>
''',
     lambda t: "{userInitial}" in t),

    ("sidebar log out button",
     '''          <span>
            NEXA AI is online
          </span>

        </div>
''',
     '''          <span>
            NEXA AI is online
          </span>

          <button
            type="button"
            className="sidebar-logout"
            onClick={logout}
            title={user?.email}
          >
            Log out
          </button>

        </div>
''',
     lambda t: 'className="sidebar-logout"' in t),

    ("stale comment mentioning the old image retry",
     "  // (mirrors retryImageGeneration: drop the failed pair, resend)\n",
     "  // (drops the failed pair, then resends)\n",
     lambda t: "(drops the failed pair, then resends)" in t),
]

# Names that must NOT remain once the image UI is gone.
LEFTOVERS = [
    r"\bimageMode\b", r"\bsetImageMode\b", r"\bgenerateImage\b",
    r"\bGeneratedImage\b", r"\bImageGeneratingCard\b", r"\bImageIcon\b",
    r"\bparseImageCommand\b", r"\buseImageGeneration\b",
    r"\bisCreatingImage\b", r"\bhandleImageLoaded\b",
    r"\bretryImageGeneration\b", r"\bcancelImageGeneration\b",
    r"\bimageCommand\b", r'"image-pending"', r'"image-error"',
]


def patch(text):
    failed = []

    for name, old, new, is_done in EDITS:
        count = text.count(old)

        if is_done(text):
            print(f"  already   {name}")
        elif count == 1:
            text = text.replace(old, new)
            print(f"  applied   {name}")
        else:
            failed.append(f"{name} (matched {count}x)")
            print(f"  MISSING   {name} (matched {count}x)")

    # fetch(...) -> authFetch(...)  (the \b keeps authFetch( untouched)
    text, replaced = re.subn(r"\bfetch\(", "authFetch(", text)

    if replaced:
        print(f"  applied   fetch -> authFetch ({replaced} calls)")
    elif "authFetch(" in text:
        print("  already   fetch -> authFetch")
    else:
        failed.append("fetch -> authFetch (no fetch( calls found)")

    left = [p for p in LEFTOVERS if re.search(p, text)]

    if left and not failed:
        failed.append(
            "leftover image code still referenced: "
            + ", ".join(p.replace("\\b", "") for p in left)
        )

    return text, failed


def main():
    if not APP.exists():
        sys.exit("Run this from the frontend/ folder (src/App.jsx not found).")

    raw = APP.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")

    print("App.jsx:")
    text, failed = patch(text)

    if failed:
        sys.exit(
            "\nNothing was changed. Problems:\n  - "
            + "\n  - ".join(failed)
            + "\nSend me this list and I'll adjust."
        )

    out = text.replace("\n", "\r\n") if crlf else text

    if out == raw:
        print("\nApp.jsx was already patched.")
        return

    pathlib.Path(str(APP) + ".bak2").write_bytes(raw.encode("utf-8"))
    APP.write_bytes(out.encode("utf-8"))

    print("\nSaved src/App.jsx (backup: src/App.jsx.bak2)")
    print("Now run: npm run lint && npm run build")


if __name__ == "__main__":
    main()