import { useEffect, useRef, useState } from "react";

import { useAuth } from "../context/useAuth";
import "./UserMenu.css";

const AVATAR_SIZE = 256;

// Crops the picture to a centered square and shrinks it, so the saved
// photo is only a few KB (it is stored in the database, not on disk).
function resizeToDataUrl(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) {
      reject(new Error("Please choose an image file."));
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      reject(new Error("That image is too large (max 10 MB)."));
      return;
    }

    const url = URL.createObjectURL(file);
    const image = new Image();

    image.onload = () => {
      URL.revokeObjectURL(url);

      const side = Math.min(image.width, image.height);
      const canvas = document.createElement("canvas");

      canvas.width = AVATAR_SIZE;
      canvas.height = AVATAR_SIZE;

      canvas
        .getContext("2d")
        .drawImage(
          image,
          (image.width - side) / 2,
          (image.height - side) / 2,
          side,
          side,
          0,
          0,
          AVATAR_SIZE,
          AVATAR_SIZE
        );

      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };

    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not read that image."));
    };

    image.src = url;
  });
}

function displayName(user) {
  return user?.name || user?.email?.split("@")[0] || "You";
}

function UserAvatar({ user, large = false }) {
  return (
    <span className={`user-menu-avatar ${large ? "large" : ""}`}>
      {user?.avatar_url ? (
        <img src={user.avatar_url} alt="" />
      ) : (
        displayName(user).charAt(0).toUpperCase()
      )}
    </span>
  );
}

export default function UserMenu() {
  const { user, updateProfile, logout } = useAuth();

  const [open, setOpen] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const wrapperRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (!wrapperRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function toggle() {
    if (!open) {
      setNameDraft(user?.name || "");
      setError("");
    }

    setOpen((current) => !current);
  }

  async function save(payload) {
    setBusy(true);
    setError("");

    try {
      await updateProfile(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePhotoChosen(event) {
    const file = event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    try {
      await save({ avatar: await resizeToDataUrl(file) });
    } catch (err) {
      setError(err.message);
    }
  }

  const nameChanged = nameDraft.trim() !== (user?.name || "");

  return (
    <div className="user-menu" ref={wrapperRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={toggle}
        aria-haspopup="menu"
        aria-expanded={open}
        title={user?.email}
      >
        <UserAvatar user={user} />

        <span className="user-menu-name">{displayName(user)}</span>

        <svg
          className="user-menu-chevron"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="user-menu-panel" role="menu">
          <div className="user-menu-profile">
            <UserAvatar user={user} large />

            <div className="user-menu-profile-text">
              <strong>{displayName(user)}</strong>
              <span>{user?.email}</span>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handlePhotoChosen}
            style={{ display: "none" }}
          />

          <div className="user-menu-row">
            <button
              type="button"
              className="user-menu-action"
              onClick={() => fileInputRef.current?.click()}
              disabled={busy}
            >
              {user?.avatar_url ? "Change photo" : "Upload photo"}
            </button>

            {user?.avatar_url && (
              <button
                type="button"
                className="user-menu-action subtle"
                onClick={() => save({ avatar: "" })}
                disabled={busy}
              >
                Remove
              </button>
            )}
          </div>

          <label className="user-menu-field">
            <span>Display name</span>

            <div className="user-menu-name-edit">
              <input
                type="text"
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
                maxLength={100}
                placeholder="Your name"
              />

              <button
                type="button"
                className="user-menu-save"
                onClick={() => save({ name: nameDraft })}
                disabled={busy || !nameChanged}
              >
                Save
              </button>
            </div>
          </label>

          {error && <div className="user-menu-error">{error}</div>}

          <div className="user-menu-divider" />

          <button
            type="button"
            className="user-menu-action danger"
            onClick={logout}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
