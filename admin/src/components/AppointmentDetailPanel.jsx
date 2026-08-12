import { useState } from "react";
import { adminApi } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import "./AppointmentDetailPanel.css";

export default function AppointmentDetailPanel({ appointment, onClose, onUpdated }) {
  const { handleSessionExpired } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function handleApiError(e) {
    if (e.status === 401) handleSessionExpired();
    else setError(e.message);
  }

  async function handleCancel() {
    if (!confirm(`Cancel appointment ${appointment.id}? The visitor's cancellation email will still go out if notifications are enabled.`)) return;
    setBusy(true);
    setError("");
    try {
      const updated = await adminApi.cancelAppointment(appointment.id);
      onUpdated(updated);
    } catch (e) {
      handleApiError(e);
    } finally {
      setBusy(false);
    }
  }

  async function handleAccept() {
    setBusy(true);
    setError("");
    try {
      const updated = await adminApi.acceptAppointment(appointment.id);
      onUpdated(updated);
    } catch (e) {
      handleApiError(e);
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    const reason = prompt("Reason for declining (optional, shown to the visitor):", "");
    if (reason === null) return;
    setBusy(true);
    setError("");
    try {
      const updated = await adminApi.rejectAppointment(appointment.id, reason);
      onUpdated(updated);
    } catch (e) {
      handleApiError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="card appt-panel">
      <div className="appt-panel-head">
        <div>
          <div className="appt-panel-name">{appointment.name}</div>
          <div className="appt-panel-code">{appointment.id}</div>
        </div>
        <button className="appt-panel-close" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="appt-panel-row"><span>Status</span><span className={`status-pill ${appointment.status}`}>{appointment.status}</span></div>
      <div className="appt-panel-row"><span>Email</span>{appointment.email}</div>
      {appointment.phone && <div className="appt-panel-row"><span>Phone</span>{appointment.phone}</div>}
      <div className="appt-panel-row"><span>When</span>{appointment.date} · {appointment.time}</div>
      <div className="appt-panel-row"><span>Service</span>{appointment.service_name || appointment.service || "—"}</div>

      {appointment.answers?.length > 0 && (
        <>
          <label className="appt-panel-label">Intake answers</label>
          <div className="appt-answers-list">
            {appointment.answers.map((ans) => (
              <div key={ans.question_id ?? ans.label} className="appt-answer-item">
                <span className="appt-answer-label">{ans.label}</span>
                <span>{ans.answer}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {error && <div className="appt-panel-error">{error}</div>}

      <div className="appt-panel-actions">
        {appointment.status === "confirmed" && (
          <button className="row-action danger" disabled={busy} onClick={handleCancel}>
            {busy ? "Cancelling…" : "Cancel appointment"}
          </button>
        )}
        {appointment.status === "pending" && (
          <>
            <button className="row-action primary" disabled={busy} onClick={handleAccept}>
              {busy ? "Working…" : "Accept"}
            </button>
            <button className="row-action danger" disabled={busy} onClick={handleReject}>
              {busy ? "Working…" : "Decline"}
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
