import { Fragment, useCallback, useEffect, useState } from "react";
import { adminApi } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import "./AppointmentsPage.css";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "confirmed", label: "Confirmed" },
  { value: "cancelled", label: "Cancelled" },
];

export default function AppointmentsPage() {
  const { handleSessionExpired } = useAuth();
  const [appointments, setAppointments] = useState(null);
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState("");
  const [cancellingId, setCancellingId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const load = useCallback(() => {
    adminApi
      .listAppointments({ status_filter: statusFilter, date_from: dateFrom, date_to: dateTo })
      .then(setAppointments)
      .catch((e) => (e.status === 401 ? handleSessionExpired() : setError(e.message)));
  }, [statusFilter, dateFrom, dateTo, handleSessionExpired]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCancel(id) {
    if (!confirm(`Cancel appointment ${id}? The visitor's cancellation email will still go out if notifications are enabled.`)) return;
    setCancellingId(id);
    try {
      await adminApi.cancelAppointment(id);
      load();
    } catch (e) {
      if (e.status === 401) handleSessionExpired();
      else alert(e.message);
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <div>
      <PageHeader title="Appointments" subtitle="Every booking made through the site." />

      <div className="filters-row">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} title="From date" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} title="To date" />
        {(dateFrom || dateTo) && (
          <button className="clear-filter" onClick={() => { setDateFrom(""); setDateTo(""); }}>Clear dates</button>
        )}
      </div>

      {error && <div className="page-error">{error}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Contact</th>
              <th>When</th>
              <th>Service</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {appointments === null && (
              <tr><td colSpan={7} className="table-empty">Loading…</td></tr>
            )}
            {appointments?.length === 0 && (
              <tr><td colSpan={7} className="table-empty">No appointments match these filters.</td></tr>
            )}
            {appointments?.map((a) => (
              <Fragment key={a.id}>
                <tr onClick={() => a.answers?.length > 0 && setExpandedId(expandedId === a.id ? null : a.id)}
                    style={{ cursor: a.answers?.length > 0 ? "pointer" : "default" }}>
                  <td><span className="mono-chip">{a.id}</span></td>
                  <td>{a.name}</td>
                  <td>
                    <div>{a.email}</div>
                    {a.phone && <div className="table-subtext">{a.phone}</div>}
                  </td>
                  <td>{a.date} · {a.time}</td>
                  <td>
                    {a.service_name || a.service || "—"}
                    {a.answers?.length > 0 && <span className="table-subtext"> · {a.answers.length} answer{a.answers.length > 1 ? "s" : ""}</span>}
                  </td>
                  <td><span className={`status-pill ${a.status}`}>{a.status}</span></td>
                  <td>
                    {a.status === "confirmed" && (
                      <button
                        className="row-action danger"
                        disabled={cancellingId === a.id}
                        onClick={(e) => { e.stopPropagation(); handleCancel(a.id); }}
                      >
                        {cancellingId === a.id ? "Cancelling…" : "Cancel"}
                      </button>
                    )}
                  </td>
                </tr>
                {expandedId === a.id && a.answers?.length > 0 && (
                  <tr key={`${a.id}-answers`} className="appt-answers-row">
                    <td colSpan={7}>
                      <div className="appt-answers">
                        {a.answers.map((ans) => (
                          <div key={ans.question_id ?? ans.label} className="appt-answer-item">
                            <span className="appt-answer-label">{ans.label}</span>
                            <span>{ans.answer}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
