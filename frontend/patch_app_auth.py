"""
Run from the frontend/ folder:   python patch_app_profile.py

Adds the user menu (photo + name) to the header of src/App.jsx and shows
the user's photo on their chat messages. Backup: src/App.jsx.bak3.
Every edit must match exactly once or NOTHING is changed. Safe to run twice.
"""
import pathlib
import sys

APP = pathlib.Path("src/App.jsx")

EDITS = [
    ("import UserMenu",
     'import { useAuth } from "./context/useAuth";\n',
     'import { useAuth } from "./context/useAuth";\nimport UserMenu from "./components/UserMenu";\n',
     lambda t: 'from "./components/UserMenu"' in t),

    ("UserMenu in header",
     '''            <div className="status">

              <span className="status-dot" />

              <span>
                Online
              </span>

            </div>
''',
     '''            <div className="status">

              <span className="status-dot" />

              <span>
                Online
              </span>

            </div>

            <UserMenu />
''',
     lambda t: "<UserMenu />" in t),

    ("photo on user messages",
     '                        {userInitial}\n',
     '''                        {user?.avatar_url ? (
                          <img src={user.avatar_url} alt="" />
                        ) : (
                          userInitial
                        )}
''',
     lambda t: "user?.avatar_url" in t),
]


def main():
    if not APP.exists():
        sys.exit("Run this from the frontend/ folder (src/App.jsx not found).")

    raw = APP.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
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

    if failed:
        sys.exit(
            "\nNothing was changed. Problems:\n  - " + "\n  - ".join(failed)
            + "\nSend me this list and I'll adjust."
        )

    out = text.replace("\n", "\r\n") if crlf else text

    if out == raw:
        print("\nApp.jsx was already patched.")
        return

    pathlib.Path(str(APP) + ".bak3").write_bytes(raw.encode("utf-8"))
    APP.write_bytes(out.encode("utf-8"))

    print("\nSaved src/App.jsx (backup: src/App.jsx.bak3)")
    print("Now run: npm run lint && npm run build")


if __name__ == "__main__":
    main()