// ──────────────────────────────────────────────────────────
// Every call here uses a *relative* path ("api/…"), never a
// hardcoded host:port. That's what lets the exact same build
// work unmodified whether Apache/XAMPP is serving it on 80,
// 8080, or whatever free port it found — see xampp-backend/
// and vite.config.js for the matching dev-time proxy.
//
// If the PHP backend isn't reachable (e.g. running `npm run dev`
// without XAMPP), every call transparently falls back to an
// in-memory mock so the UI is still fully explorable.
// ──────────────────────────────────────────────────────────

const API_BASE = "api";

export async function tryFetch(path, options) {
  try {
    const res = await fetch(`${API_BASE}/${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return null; // signal caller to use the mock
  }
}

// ---- Mock data used only when no backend is present ----
const mockAppointments = new Map();
let mockCounter = 1000;

function genId() {
  mockCounter += 1;
  return `PRN-${mockCounter.toString(36).toUpperCase().padStart(8, "0")}`;
}

function mockSlotsFor(dateStr) {
  const base = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:30", "16:30"];
  const date = new Date(dateStr);
  const isWeekend = date.getDay() === 5 || date.getDay() === 6; // Fri/Sat off, matching Gulf work week
  if (isWeekend) return [];
  return base.filter((_, i) => (date.getDate() + i) % 4 !== 0);
}

export const api = {
  async chat(message, lang, history) {
    const data = await tryFetch("chat.php", {
      method: "POST",
      body: JSON.stringify({ message, lang, history }),
    });
    if (data) return data.reply;
    // mock fallback: simple canned response
    return lang === "ar"
      ? "شكرًا لك! سيقوم أحد أعضاء فريقنا بمتابعة رسالتك قريبًا. هل ترغب في حجز موعد؟"
      : "Thanks for sharing that! Someone from our team will follow up shortly. Would you like to book a time to talk?";
  },

  async getFaq(lang) {
    const data = await tryFetch(`faq.php?lang=${lang}`);
    return data?.items ?? null; // null → caller uses local content.js data
  },

  async getSlots(date) {
    const data = await tryFetch(`appointments.php?action=slots&date=${date}`);
    if (data) return data.slots;
    return mockSlotsFor(date);
  },

  async createAppointment(payload) {
    const data = await tryFetch("appointments.php?action=create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (data) return data;
    const id = genId();
    mockAppointments.set(id, { ...payload, id, status: "confirmed" });
    return { ok: true, id };
  },

  async lookupAppointment(id, email) {
    const data = await tryFetch(`appointments.php?action=lookup&id=${id}&email=${encodeURIComponent(email)}`);
    if (data) return data;
    const appt = mockAppointments.get(id);
    if (appt && appt.email?.toLowerCase() === email.toLowerCase()) {
      return { ok: true, appointment: appt };
    }
    return { ok: false, error: "not_found" };
  },

  async cancelAppointment(id, email) {
    const data = await tryFetch("appointments.php?action=cancel", {
      method: "POST",
      body: JSON.stringify({ id, email }),
    });
    if (data) return data;
    const appt = mockAppointments.get(id);
    if (appt) appt.status = "cancelled";
    return { ok: true };
  },

  async rescheduleAppointment(id, email, date, time) {
    const data = await tryFetch("appointments.php?action=reschedule", {
      method: "POST",
      body: JSON.stringify({ id, email, date, time }),
    });
    if (data) return data;
    const appt = mockAppointments.get(id);
    if (appt) Object.assign(appt, { date, time });
    return { ok: true };
  },
};
