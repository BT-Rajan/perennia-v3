import "./ChatMessage.css";

export default function ChatMessage({ from, text }) {
  return (
    <div className={`msg msg-${from}`}>
      <div className="msg-bubble">{text}</div>
    </div>
  );
}
