import { useState } from "react";
import Field from "./Field.jsx";
import SlotPicker from "./SlotPicker.jsx";
import Button from "../ui/Button.jsx";
import { useLang } from "../../context/LangContext.jsx";
import { api } from "../../api/client.js";

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function NewAppointmentForm({ onCancel, onBooked }) {
  const { copy } = useLang();
  const t = copy.booking;
  const [form, setForm] = useState({ date: "", slot: "", name: "", email: "", phone: "", service: "", notes: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function set(key, val) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  async function handleSubmit() {
    if (!form.date || !form.slot) return setError("Please pick a date and time.");
    if (!form.name.trim()) return setError("Please enter your name.");
    if (!/^\S+@\S+\.\S+$/.test(form.email)) return setError("Please enter a valid email.");

    setError("");
    setSubmitting(true);
    const result = await api.createAppointment(form);
    setSubmitting(false);
    if (result.ok) {
      onBooked({ ...form, id: result.id });
    } else {
      setError(result.error || "Something went wrong — please try again.");
    }
  }

  return (
    <div>
      <Field label={t.date}>
        <input type="date" min={todayISO()} value={form.date} onChange={(e) => set("date", e.target.value)} />
      </Field>
      <Field label={t.slot}>
        <SlotPicker date={form.date} value={form.slot} onChange={(s) => set("slot", s)} emptyLabel={t.slotEmpty} />
      </Field>
      <Field label={t.name}>
        <input type="text" maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} />
      </Field>
      <Field label={t.email}>
        <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
      </Field>
      <Field label={t.phone}>
        <input type="tel" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
      </Field>
      <Field label={t.service}>
        <input type="text" maxLength={200} value={form.service} onChange={(e) => set("service", e.target.value)} />
      </Field>
      <Field label={t.notes}>
        <textarea rows={2} maxLength={1000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </Field>

      {error && <div className="bk-err">{error}</div>}

      <div className="booking-foot">
        <Button variant="ghost" onClick={onCancel}>{t.cancel}</Button>
        <Button variant="primary" fullWidth onClick={handleSubmit} disabled={submitting}>
          {t.confirm}
        </Button>
      </div>
    </div>
  );
}
