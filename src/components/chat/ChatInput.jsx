import { useRef } from "react";
import IconButton from "../ui/IconButton.jsx";
import "./ChatInput.css";

export default function ChatInput({ value, onChange, onSend, placeholder, sendLabel = "Send", disabled }) {
  const areaRef = useRef(null);

  function handleInput(e) {
    onChange(e.target.value);
    const el = areaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) onSend();
    }
  }

  return (
    <div className="chat-input-area">
      <textarea
        ref={areaRef}
        className="chat-input"
        rows={1}
        value={value}
        placeholder={placeholder}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <IconButton title={sendLabel} disabled={!value.trim() || disabled} onClick={onSend} size="md">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </IconButton>
    </div>
  );
}
