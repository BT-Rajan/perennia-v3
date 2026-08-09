import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import "./SlotPicker.css";

export default function SlotPicker({ date, value, onChange, emptyLabel }) {
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!date) {
      setSlots([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api.getSlots(date).then((s) => {
      if (!cancelled) {
        setSlots(s);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [date]);

  if (!date) return <div className="bk-slots-empty">{emptyLabel}</div>;
  if (loading) return <div className="bk-slots-empty">…</div>;
  if (slots.length === 0) return <div className="bk-slots-empty">No availability that day — try another date.</div>;

  return (
    <div className="bk-slots">
      {slots.map((s) => (
        <button
          key={s}
          type="button"
          className={`bk-slot${value === s ? " bk-slot-active" : ""}`}
          onClick={() => onChange(s)}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
