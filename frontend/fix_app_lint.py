"""
Run from the frontend/ folder:   python fix_app_lint.py                 (patches App.jsx too)
       python fix_app_lint.py --config-only   (leaves App.jsx untouched)

Patches src/App.jsx in place (backup: src/App.jsx.bak). Every edit must match
exactly once or the script changes NOTHING and tells you which one missed.
Safe to run twice. Also rewrites eslint.config.js and hides the sidebar drag
handle on phones (src/Mobile.css).
"""
import pathlib
import re
import sys

APP = pathlib.Path("src/App.jsx")
MOBILE = pathlib.Path("src/Mobile.css")
ESLINT = pathlib.Path("eslint.config.js")

HELPER = '''let clientIdSequence = 0;

function newClientId(prefix) {
  clientIdSequence += 1;
  return `${prefix}-${Date.now()}-${clientIdSequence}`;
}

'''

INIT_EFFECT = '''  function openDocumentsModal() {
    setDocumentsModalOpen(true);
    setUploadError("");
    setDocumentsLoading(true);

    loadDocuments();
  }

  // ============================================================
  // INITIALIZE APPLICATION
  // (placed after initializeChat / loadDocuments are declared)
  // ============================================================

  useEffect(() => {
    if (conversationCreatedRef.current) {
      return;
    }

    conversationCreatedRef.current = true;

    initializeChat();
    loadDocuments();
    // Runs once on mount (the ref guards StrictMode's double-invoke).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
'''

# (name, old, new, done_marker)  -- done_marker: text proving it's already applied
EDITS = [
    ("CSS order: Mobile.css last",
     'import "./Mobile.css";\nimport "./Sidebar.css";\n',
     'import "./Sidebar.css";\nimport "./Mobile.css";\n',
     None),

    ("mermaid id (no render-time reassignment)",
     '''let mermaidDiagramCounter = 0;

function MermaidDiagram({ code }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(null);

  const idRef = useRef(null);

  if (idRef.current === null) {
    mermaidDiagramCounter += 1;
    idRef.current = `nexa-mermaid-${mermaidDiagramCounter}`;
  }
''',
     '''function MermaidDiagram({ code }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(null);

  // useId is pure and stable per instance; mermaid needs a CSS-safe id.
  const reactId = useId();
  const diagramId = `nexa-mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`;
''',
     None),

    ("mermaid.render uses diagramId",
     '''        const { svg: renderedSvg } = await mermaid.render(
          idRef.current,
          code
        );
''',
     '''        const { svg: renderedSvg } = await mermaid.render(diagramId, code);
''',
     None),

    ("mermaid effect deps",
     '  }, [code]);\n',
     '  }, [code, diagramId]);\n',
     None),

    ("speechSupported as lazy state",
     '  const [speechSupported, setSpeechSupported] = useState(true);\n',
     '''  const [speechSupported] = useState(() => {
    const SpeechRecognitionApi =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    return (
      Boolean(SpeechRecognitionApi) &&
      typeof window.speechSynthesis !== "undefined"
    );
  });
''',
     None),

    ("voice effect: cleanup only",
     '''  useEffect(() => {
    const SpeechRecognitionApi =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    const hasSpeechSynthesis =
      typeof window.speechSynthesis !== "undefined";

    setSpeechSupported(
      Boolean(SpeechRecognitionApi) && hasSpeechSynthesis
    );

    // Stop any speaking/listening if the component unmounts
''',
     '''  useEffect(() => {
    // Stop any speaking/listening if the component unmounts
''',
     None),

    ("remove early init effect",
     '''  useEffect(() => {
    if (conversationCreatedRef.current) {
      return;
    }

    conversationCreatedRef.current = true;

    initializeChat();
    loadDocuments();
  }, []);

''',
     '  // (the init effect lives further down, after the functions it calls)\n\n',
     "(the init effect lives further down"),

    ("documentsLoading starts true",
     '  const [documentsLoading, setDocumentsLoading] =\n    useState(false);\n',
     '  const [documentsLoading, setDocumentsLoading] =\n    useState(true);\n',
     None),

    ("loadDocuments: no sync setState",
     '  async function loadDocuments() {\n    setDocumentsLoading(true);\n\n    try {\n',
     '  async function loadDocuments() {\n    try {\n',
     None),

    ("init effect after declarations",
     '''  function openDocumentsModal() {
    setDocumentsModalOpen(true);
    setUploadError("");

    loadDocuments();
  }
''',
     INIT_EFFECT,
     "// Runs once on mount (the ref guards StrictMode's double-invoke)."),

    ("client id helper",
     'function App() {\n',
     HELPER + 'function App() {\n',
     "function newClientId(prefix)"),

    ("user client id",
     '    const userClientId = `user-${Date.now()}`;\n',
     '    const userClientId = newClientId("user");\n',
     None),

    ("assistant client id",
     '    const assistantId =\n      `assistant-${Date.now()}`;\n',
     '    const assistantId = newClientId("assistant");\n',
     None),

    ("unused catch var (stream)",
     '''            } catch (error) {
              console.warn(
                "Invalid streaming event:",''',
     '''            } catch {
              console.warn(
                "Invalid streaming event:",''',
     None),

    ("unused catch var (final buffer)",
     '''          } catch (error) {
            console.warn(
              "Could not parse final event:",''',
     '''          } catch {
            console.warn(
              "Could not parse final event:",''',
     None),
]

ESLINT_CONFIG = """import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // `({ node, ...props })` is the standard react-markdown pattern
      'no-unused-vars': ['error', { ignoreRestSiblings: true }],
    },
  },
])
"""

MOBILE_RULE = """
/* Resizable sidebar: no drag handle in the mobile drawer layout */
@media (max-width: 900px) {
  .app .sidebar-resizer {
    display: none;
  }
}
"""


REACT_IMPORT = 'import { useEffect, useId, useRef, useState } from "react";\n'
REACT_IMPORT_RE = re.compile(r'^import \{[^}\n]*\} from "react";\n', re.M)


def fix_react_import(text):
    """Leave exactly one react import line, with useId included."""
    matches = list(REACT_IMPORT_RE.finditer(text))
    if not matches:
        return text, False
    if len(matches) == 1 and matches[0].group(0) == REACT_IMPORT:
        print("  already   react import")
        return text, True
    first = matches[0].start()
    text = REACT_IMPORT_RE.sub("", text)
    text = text[:first] + REACT_IMPORT + text[first:]
    print("  applied   react import (single line, with useId)")
    return text, True


def patch(text):
    """Returns (new_text, failed_names)."""
    failed = []
    text, ok = fix_react_import(text)
    if not ok:
        failed.append("react import (no import from \"react\" found)")
    for name, old, new, done in EDITS:
        count = text.count(old)
        if done and done in text:
            print(f"  already   {name}")
        elif count == 1:
            text = text.replace(old, new)
            print(f"  applied   {name}")
        elif count == 0 and new in text:
            print(f"  already   {name}")
        else:
            failed.append(name)
            print(f"  MISSING   {name} (matched {count}x)")
    return text, failed


def patch_app():

    raw = APP.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")

    print("App.jsx:")
    text, failed = patch(text)

    if failed:
        sys.exit(
            "\nNothing was changed. These edits didn't match your file:\n  - "
            + "\n  - ".join(failed)
            + "\nSend me those names and I'll adjust."
        )

    out = text.replace("\n", "\r\n") if crlf else text

    if out != raw:
        pathlib.Path(str(APP) + ".bak").write_bytes(raw.encode("utf-8"))
        APP.write_bytes(out.encode("utf-8"))
        print("\nSaved src/App.jsx (backup: src/App.jsx.bak)")
    else:
        print("\nApp.jsx was already fixed.")

def main():
    if not ESLINT.parent.joinpath("package.json").exists():
        sys.exit("Run this from the frontend/ folder (package.json not found).")

    if "--config-only" in sys.argv:
        print("Skipping App.jsx (--config-only)")
    elif not APP.exists():
        sys.exit("src/App.jsx not found.")
    else:
        patch_app()

    ESLINT.write_bytes(ESLINT_CONFIG.encode("utf-8"))
    print("Wrote eslint.config.js")

    if MOBILE.exists():
        css = MOBILE.read_text(encoding="utf-8")
        if "sidebar-resizer" not in css:
            MOBILE.write_text(css.rstrip() + "\n" + MOBILE_RULE, encoding="utf-8")
            print("Added .sidebar-resizer rule to src/Mobile.css")

    print("\nNow run: npm run lint && npm run build")


if __name__ == "__main__":
    main()