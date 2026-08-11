import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client.js";
import "./CalendarSyncConnector.css";

// Google redirects back to this very Settings page (calendar_sync.
// google_redirect_uri should point here) with ?code=&state= — this
// component picks those up on mount and completes the exchange itself,
// rather than the browser landing on a raw JSON response. See
// PASS13_NOTES.md.
export default function CalendarSyncConnector() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [status, setStatus] = useState(null);
  const [pendingCredentialId, setPendingCredentialId] = useState(null);
  const [pendingCalendars, setPendingCalendars] = useState(null);
  const [selectedCalendarId, setSelectedCalendarId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function loadStatus() {
    adminApi.getCalendarSyncStatus().then(setStatus).catch((e) => setError(e.message));
  }

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    if (!code || !state) return;

    setBusy(true);
    adminApi
      .completeCalendarSyncCallback(code, state)
      .then((data) => {
        setPendingCredentialId(data.credential_id);
        setPendingCalendars(data.calendars);
        if (data.calendars.length > 0) setSelectedCalendarId(data.calendars[0].id);
      })
      .catch((e) => setError(e.message))
      .finally(() => {
        setBusy(false);
        // Strip ?code=&state= so a page refresh doesn't try to reuse
        // Google's single-use authorization code.
        navigate(location.pathname, { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSelectCalendar() {
    setBusy(true);
    setError("");
    try {
      await adminApi.selectCalendarSyncCalendar(pendingCredentialId, selectedCalendarId);
      setPendingCalendars(null);
      setPendingCredentialId(null);
      loadStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDisconnect() {
    if (!confirm("Disconnect Google Calendar? Booking slots will stop checking its busy time.")) return;
    setBusy(true);
    setError("");
    try {
      await adminApi.disconnectCalendarSync();
      loadStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="calendar-sync-connector">
      <label className="setting-label">Google Calendar connection</label>
      <p className="setting-help">
        Optional — connect a Google Calendar so its busy time blocks booking slots. Save the client
        ID, secret, and redirect URI above first (Google's consent screen needs them); then connect.
      </p>

      {error && <div className="calendar-sync-error">{error}</div>}

      {pendingCalendars ? (
        <div className="calendar-sync-picker">
          <p className="setting-help">Connected — choose which calendar to sync:</p>
          <select
            className="setting-input"
            value={selectedCalendarId}
            onChange={(e) => setSelectedCalendarId(e.target.value)}
          >
            {pendingCalendars.map((c) => (
              <option key={c.id} value={c.id}>{c.summary}{c.primary ? " (primary)" : ""}</option>
            ))}
          </select>
          <button type="button" className="btn-primary" onClick={handleSelectCalendar} disabled={busy}>
            Use this calendar
          </button>
        </div>
      ) : status?.connected ? (
        <div className="calendar-sync-status">
          <div className="calendar-sync-status-info">
            <span className="status-pill confirmed">Connected</span>
            <span className="calendar-sync-detail">{status.calendar_id}</span>
          </div>
          <button type="button" className="row-action danger" onClick={handleDisconnect} disabled={busy}>
            Disconnect
          </button>
        </div>
      ) : (
        <div className="calendar-sync-status">
          <span className="status-pill cancelled">Not connected</span>
          <a className="btn-primary calendar-sync-connect-btn" href="/admin/api/calendar-sync/connect">
            Connect Google Calendar
          </a>
        </div>
      )}
    </div>
  );
}
