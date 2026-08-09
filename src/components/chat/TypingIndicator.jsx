import "./TypingIndicator.css";

export default function TypingIndicator() {
  return (
    <div className="msg msg-ai">
      <div className="msg-bubble typing-bubble" aria-label="Assistant is typing">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  );
}
