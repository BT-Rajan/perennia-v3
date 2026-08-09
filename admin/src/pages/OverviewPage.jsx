import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import PageHeader from "../components/PageHeader.jsx";
import StatCard from "../components/StatCard.jsx";
import "./OverviewPage.css";

export default function OverviewPage() {
  const { handleSessionExpired } = useAuth();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .statsOverview()
      .then(setStats)
      .catch((e) => (e.status === 401 ? handleSessionExpired() : setError(e.message)));
  }, [handleSessionExpired]);

  if (error) return <div className="page-error">{error}</div>;
  if (!stats) return <div className="page-loading">Loading…</div>;

  return (
    <div>
      <PageHeader title="Overview" subtitle="What's happening across bookings and leads." />

      <div className="stat-grid">
        <StatCard label="Leads" value={stats.leads_total} detail={`${stats.leads_by_status.new ?? 0} new`} />
        <StatCard label="Appointments" value={stats.appointments_total} detail={`${stats.appointments_upcoming} upcoming`} />
        <StatCard label="This week" value={stats.appointments_this_week} detail="confirmed appointments" />
      </div>

      <div className="overview-columns">
        <section className="card overview-panel">
          <div className="overview-panel-head">
            <h2>Upcoming appointments</h2>
            <Link to="/appointments">View all →</Link>
          </div>
          {stats.upcoming_appointments.length === 0 ? (
            <p className="overview-empty">Nothing booked yet.</p>
          ) : (
            <table>
              <tbody>
                {stats.upcoming_appointments.map((a) => (
                  <tr key={a.id}>
                    <td><span className="mono-chip">{a.id}</span></td>
                    <td>{a.name}</td>
                    <td>{a.date} · {a.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card overview-panel">
          <div className="overview-panel-head">
            <h2>Recent leads</h2>
            <Link to="/leads">View all →</Link>
          </div>
          {stats.recent_leads.length === 0 ? (
            <p className="overview-empty">No leads captured yet.</p>
          ) : (
            <table>
              <tbody>
                {stats.recent_leads.map((l) => (
                  <tr key={l.id}>
                    <td>{l.name || l.email}</td>
                    <td><span className={`status-pill ${l.status}`}>{l.status}</span></td>
                    <td>{l.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
