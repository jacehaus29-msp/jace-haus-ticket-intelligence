import { useEffect, useState, useRef } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const renderSlaBadge = (slaStatusOrTicket) => {
  let status = "on_track";
  if (typeof slaStatusOrTicket === "string") {
    status = slaStatusOrTicket;
  } else if (slaStatusOrTicket && typeof slaStatusOrTicket === "object") {
    status = slaStatusOrTicket.sla_status || slaStatusOrTicket.sla?.overall_status || "on_track";
  }
  status = (status || "on_track").toLowerCase();
  if (status === "breached") {
    return <span className="sla-badge sla-breached">🚨 Breached</span>;
  }
  if (status === "at_risk") {
    return <span className="sla-badge sla-at-risk">⚠️ At Risk</span>;
  }
  if (status === "met") {
    return <span className="sla-badge sla-met">✓ Met</span>;
  }
  return <span className="sla-badge sla-on-track">⏱ On Track</span>;
};

const getRouteFromPath = (pathname) => {
  const clean = (pathname || (typeof window !== "undefined" ? window.location.pathname : "") || "")
    .replace(/^\/+|\/+$/g, "")
    .toLowerCase();
  if (clean === "portal" || clean === "portal/dashboard") return "portal-dashboard";
  if (clean === "portal/tickets") return "portal-tickets";
  if (clean === "portal/new-ticket" || clean === "portal/new") return "portal-new";
  if (clean === "portal/notifications") return "portal-notifications";
  if (clean === "portal/profile") return "portal-profile";
  if (clean === "portal/reports") return "portal-reports";
  if (clean === "portal/kb" || clean === "portal/knowledge-base") return "portal-kb";
  if (clean.startsWith("portal")) return "portal-dashboard";
  if (clean === "workbench") return "workbench";
  if (clean === "tickets") return "tickets";
  if (clean === "rules" || clean === "routing-rules") return "rules";
  if (clean === "teams" || clean === "team-management") return "teams";
  if (clean === "knowledge-base" || clean === "kb") return "knowledge-base";
  if (clean === "analytics") return "analytics";
  if (clean === "reports") return "reports";
  if (clean === "users" || clean === "user-management") return "users";
  return "dashboard";
};

function App() {
  // Authentication State
  const [auth, setAuth] = useState(() => {
    try {
      const saved = localStorage.getItem("jace_auth");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.token && parsed.user) {
          return parsed;
        }
      }
    } catch (e) {
      console.error("Failed to parse saved auth", e);
    }
    return { token: null, user: null, isAuthenticated: false };
  });

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // Admin User Management State
  const [usersList, setUsersList] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [newUserForm, setNewUserForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "technician",
    technician_id: "",
    customer_id: ""
  });
  const [creatingUser, setCreatingUser] = useState(false);
  const [resetPasswordModalUser, setResetPasswordModalUser] = useState(null);
  const [newResetPassword, setNewResetPassword] = useState("");
  const [savingResetPassword, setSavingResetPassword] = useState(false);

  // Executive & Client SLA Reporting State (Phase 6)
  const [reportsSummary, setReportsSummary] = useState(null);
  const [reportsSla, setReportsSla] = useState(null);
  const [reportsTickets, setReportsTickets] = useState([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportFilters, setReportFilters] = useState({
    startDate: "",
    endDate: "",
    customerId: "",
    team: "",
    technicianId: "",
    priority: "",
    category: "",
    status: "",
    quickRange: "all"
  });

  const [portalReportsSummary, setPortalReportsSummary] = useState(null);
  const [portalReportsLoading, setPortalReportsLoading] = useState(false);
  const [portalReportFilters, setPortalReportFilters] = useState({
    startDate: "",
    endDate: "",
    status: "",
    quickRange: "all"
  });

  // Customer CSAT & Resolution Rating State (Phase 8)
  const [portalTicketCsat, setPortalTicketCsat] = useState(null);
  const [portalCsatLoading, setPortalCsatLoading] = useState(false);
  const [portalCsatRating, setPortalCsatRating] = useState(5);
  const [portalCsatHover, setPortalCsatHover] = useState(0);
  const [portalCsatFeedback, setPortalCsatFeedback] = useState("");
  const [portalCsatSubmitting, setPortalCsatSubmitting] = useState(false);
  const [reportsCsatSummary, setReportsCsatSummary] = useState(null);
  const [reportsActiveTab, setReportsActiveTab] = useState("summary"); // "summary" | "csat"

  // Dynamic Teams State (Phase 7)
  const [teamsList, setTeamsList] = useState([]);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [showCreateTeamModal, setShowCreateTeamModal] = useState(false);
  const [editingTeam, setEditingTeam] = useState(null);
  const [managingMembersTeam, setManagingMembersTeam] = useState(null);
  const [selectedMemberIds, setSelectedMemberIds] = useState([]);
  const [teamStatusModal, setTeamStatusModal] = useState(null);
  const [teamSearch, setTeamSearch] = useState("");
  const [teamStatusFilter, setTeamStatusFilter] = useState("all");
  const [newTeam, setNewTeam] = useState({
    name: "",
    description: "",
    team_lead_id: "",
    business_hours_start: "08:00",
    business_hours_end: "18:00",
    timezone: "America/New_York",
    work_days: "MON,TUE,WED,THU,FRI",
    is_active: true
  });

  // Phase 9: Knowledge Base & Self-Service Portal State
  const [kbArticles, setKbArticles] = useState([]);
  const [kbCategories, setKbCategories] = useState([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbSearchQuery, setKbSearchQuery] = useState("");
  const [kbSelectedCategory, setKbSelectedCategory] = useState("all");
  const [kbVisibilityFilter, setKbVisibilityFilter] = useState("all"); // "all" | "public" | "internal"
  const [kbStatusFilter, setKbStatusFilter] = useState("all"); // "all" | "published" | "draft" | "archived"
  const [kbActiveArticle, setKbActiveArticle] = useState(null);
  const [kbAnalyticsData, setKbAnalyticsData] = useState(null);
  const [kbActiveTab, setKbActiveTab] = useState("articles"); // "articles" | "analytics" | "categories"

  // Article Modal (Create / Edit)
  const [showKbArticleModal, setShowKbArticleModal] = useState(false);
  const [editingKbArticle, setEditingKbArticle] = useState(null);
  const [kbArticleForm, setKbArticleForm] = useState({
    title: "",
    summary: "",
    content: "",
    category_id: "",
    visibility: "public",
    status: "published",
    team_id: "",
    tags: "",
    change_summary: "Initial version"
  });
  const [kbSavingArticle, setKbSavingArticle] = useState(false);

  // Article Versions Modal
  const [showKbVersionsModal, setShowKbVersionsModal] = useState(false);
  const [kbVersionsArticle, setKbVersionsArticle] = useState(null);
  const [kbVersionsList, setKbVersionsList] = useState([]);
  const [kbVersionsLoading, setKbVersionsLoading] = useState(false);

  // Category Modal
  const [showKbCategoryModal, setShowKbCategoryModal] = useState(false);
  const [editingKbCategory, setEditingKbCategory] = useState(null);
  const [kbCategoryForm, setKbCategoryForm] = useState({
    name: "",
    description: "",
    icon: "book",
    display_order: 0,
    is_active: true
  });
  const [kbSavingCategory, setKbSavingCategory] = useState(false);

  // Customer Portal KB State
  const [portalKbArticles, setPortalKbArticles] = useState([]);
  const [portalKbCategories, setPortalKbCategories] = useState([]);
  const [portalKbLoading, setPortalKbLoading] = useState(false);
  const [portalKbSearch, setPortalKbSearch] = useState("");
  const [portalKbCategory, setPortalKbCategory] = useState("all");
  const [portalKbActiveArticle, setPortalKbActiveArticle] = useState(null);
  const [portalKbFeedbackGiven, setPortalKbFeedbackGiven] = useState({}); // map articleId -> bool
  const [portalKbFeedbackComment, setPortalKbFeedbackComment] = useState("");
  const [portalKbFeedbackSubmitting, setPortalKbFeedbackSubmitting] = useState(false);

  // Ticket Deflection Suggestions in portal-new
  const [portalKbSuggestions, setPortalKbSuggestions] = useState([]);
  const [portalKbSuggesting, setPortalKbSuggesting] = useState(false);
  const [previewingSuggestedArticle, setPreviewingSuggestedArticle] = useState(null);
  const [copiedSolutionId, setCopiedSolutionId] = useState(null);

  const getAuthHeaders = (extraHeaders = {}) => {
    const headers = { ...extraHeaders };
    if (auth?.token) {
      headers["Authorization"] = `Bearer ${auth.token}`;
    }
    return headers;
  };

  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [currentPage, setCurrentPage] = useState(() =>
    typeof window !== "undefined" ? getRouteFromPath(window.location.pathname) : "dashboard"
  );
  const [rules, setRules] = useState([]);
const [showCreateRuleModal, setShowCreateRuleModal] = useState(false);

const [newRule, setNewRule] = useState({
  category: "",
  team: "Service Desk",
  priority: "medium",
  keywords: "",
  description: ""
});
const [analytics, setAnalytics] = useState(null);
const [analyticsLoading, setAnalyticsLoading] = useState(false);
const [rulesLoading, setRulesLoading] = useState(false);
const [editingRule, setEditingRule] = useState(null);
const [savingRule, setSavingRule] = useState(false);

const [updatingStatus, setUpdatingStatus] = useState(false);
const [updatingTeam, setUpdatingTeam] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
const [search, setSearch] = useState("");
const [priorityFilter, setPriorityFilter] = useState("all");
const [teamFilter, setTeamFilter] = useState("all");
const [slaFilter, setSlaFilter] = useState("all");
const [selectedTicket, setSelectedTicket] = useState(null);
const [routingAnalysis, setRoutingAnalysis] = useState(null);
const [routingHistory, setRoutingHistory] = useState([]);
const [activityHistory, setActivityHistory] = useState([]);

// Notification states
const [notifications, setNotifications] = useState([]);
const [unreadCount, setUnreadCount] = useState(0);
const [showNotifications, setShowNotifications] = useState(false);
const [notifFilter, setNotifFilter] = useState("all");
const [notifScope, setNotifScope] = useState("all");
const [ticketNotifications, setTicketNotifications] = useState([]);
const [toasts, setToasts] = useState([]);
const seenToastIdsRef = useRef(new Set());
const isInitialNotifLoadRef = useRef(true);

const dismissToast = (toastId) => {
  setToasts((prev) => prev.filter((t) => t.toastId !== toastId));
};

const handleToastClick = async (toast) => {
  dismissToast(toast.toastId);
  if (toast.notificationId) {
    markNotificationRead(toast.notificationId);
  }
  if (toast.ticketId) {
    const existing = tickets.find((t) => t.id === toast.ticketId);
    if (existing) {
      setSelectedTicket(existing);
    } else {
      try {
        const response = await fetch(`${API_URL}/tickets/${toast.ticketId}`, {
          headers: getAuthHeaders()
        });
        const data = await response.json();
        if (response.ok && !data.error) {
          setSelectedTicket(data);
        }
      } catch (err) {
        console.error("Failed to load toast ticket:", err);
      }
    }
  }
};

const triggerToastsForNewNotifications = (incomingList) => {
  if (!incomingList || incomingList.length === 0) return;

  // On initial load, seed seen IDs so we don't display a storm of historical toasts
  if (isInitialNotifLoadRef.current) {
    incomingList.forEach((n) => seenToastIdsRef.current.add(n.id));
    isInitialNotifLoadRef.current = false;
    return;
  }

  const newUnread = incomingList.filter(
    (n) => !n.is_read && !seenToastIdsRef.current.has(n.id)
  );

  if (newUnread.length === 0) return;

  const newToasts = [];
  newUnread.forEach((n) => {
    seenToastIdsRef.current.add(n.id);
    const toastId = `${n.id}-${Date.now()}-${Math.random()}`;
    newToasts.push({
      toastId,
      notificationId: n.id,
      ticketId: n.ticket_id,
      type: n.type,
      severity: n.severity || "info",
      title: n.title,
      message: n.message,
      created_at: n.created_at
    });

    // Auto-dismiss after 6 seconds
    setTimeout(() => {
      dismissToast(toastId);
    }, 6000);
  });

  setToasts((prev) => [...newToasts, ...prev].slice(0, 5));
};

const getEffectiveNotifScope = (scope = notifScope) => {
  if (auth?.user?.role === "technician" && scope === "all") {
    return "my_team";
  }
  return scope || "all";
};

const loadNotifications = async (scope = notifScope) => {
  try {
    const effectiveScope = getEffectiveNotifScope(scope);
    const response = await fetch(`${API_URL}/notifications/?scope=${encodeURIComponent(effectiveScope)}`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      const incoming = data.notifications || [];
      setNotifications(incoming);
      setUnreadCount(data.unread_count || 0);

      // Trigger toasts for newly detected notifications in real-time
      if (auth?.user?.role !== "customer") {
        triggerToastsForNewNotifications(incoming);
      }
    }
  } catch (error) {
    console.error("Failed to load notifications:", error);
  }
};

const loadUnreadCount = async (scope = notifScope) => {
  if (!auth?.token || auth?.user?.role === "customer") return;
  try {
    const effectiveScope = getEffectiveNotifScope(scope);
    const response = await fetch(`${API_URL}/notifications/unread-count?scope=${encodeURIComponent(effectiveScope)}`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      setUnreadCount(data.unread_count || 0);
    }
  } catch (error) {
    console.error("Failed to load unread count:", error);
  }
};

const loadTicketNotifications = async (ticketId) => {
  try {
    const response = await fetch(`${API_URL}/tickets/${ticketId}/notifications`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      setTicketNotifications(data.notifications || []);
    }
  } catch (error) {
    console.error("Failed to load ticket notifications:", error);
    setTicketNotifications([]);
  }
};

const markNotificationRead = async (notificationId) => {
  try {
    const effectiveScope = getEffectiveNotifScope(notifScope);
    const response = await fetch(`${API_URL}/notifications/${notificationId}/read?scope=${encodeURIComponent(effectiveScope)}`, {
      method: "PATCH",
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      setTicketNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      if (typeof data.unread_count === "number") {
        setUnreadCount(data.unread_count);
      } else {
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    }
  } catch (error) {
    console.error("Failed to mark notification as read:", error);
  }
};

const markAllNotificationsRead = async () => {
  try {
    const effectiveScope = getEffectiveNotifScope(notifScope);
    const response = await fetch(`${API_URL}/notifications/read-all?scope=${encodeURIComponent(effectiveScope)}`, {
      method: "PATCH",
      headers: getAuthHeaders()
    });
    if (response.ok) {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setTicketNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    }
  } catch (error) {
    console.error("Failed to mark all as read:", error);
  }
};

const clearReadNotifications = async () => {
  try {
    const response = await fetch(`${API_URL}/notifications/clear-read`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      setNotifications((prev) => prev.filter((n) => !n.is_read));
      setTicketNotifications((prev) => prev.filter((n) => !n.is_read));
    }
  } catch (error) {
    console.error("Failed to clear read notifications:", error);
  }
};

const handleNotificationClick = async (notif) => {
  if (!notif.is_read) {
    markNotificationRead(notif.id);
  }
  setShowNotifications(false);

  if (notif.ticket_id) {
    const existing = tickets.find((t) => t.id === notif.ticket_id);
    if (existing) {
      setSelectedTicket(existing);
    } else {
      try {
        const response = await fetch(`${API_URL}/tickets/${notif.ticket_id}`, {
          headers: getAuthHeaders()
        });
        const data = await response.json();
        if (response.ok && !data.error) {
          setSelectedTicket(data);
        }
      } catch (err) {
        console.error("Failed to fetch ticket for notification:", err);
      }
    }
  }
};

const loadRoutingAudit = async (ticketId) => {
  try {
    const response = await fetch(
      `${API_URL}/tickets/${ticketId}/audit`
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      setRoutingAnalysis(null);
      return;
    }

    setRoutingAnalysis({
      rule: data.rule,
      matchedKeywords: data.matched_keywords || [],
      matchLocation: data.match_location,
      score: data.score,
      confidence: data.confidence,
      team: data.team,
      priority: data.priority,
      category: data.category,
      routingMethod: data.routing_method,
      reason: data.reason
    });

  } catch (error) {
    console.error(
      "Failed to load routing audit:",
      error
    );

    setRoutingAnalysis(null);
  }
};
const loadRoutingHistory = async (ticketId) => {
  try {
    const response = await fetch(
      `${API_URL}/tickets/${ticketId}/audit/history`
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      setRoutingHistory([]);
      return;
    }

    setRoutingHistory(data.history || []);

  } catch (error) {
    console.error(
      "Failed to load routing history:",
      error
    );

    setRoutingHistory([]);
  }
};
const loadActivityHistory = async (ticketId) => {
  try {
    const response = await fetch(
      `${API_URL}/tickets/${ticketId}/audit/history`
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      setActivityHistory([]);
      return;
    }

    setActivityHistory(data.history || []);

  } catch (error) {
    console.error(
      "Failed to load activity history:",
      error
    );

    setActivityHistory([]);
  }
};
// Workbench & Notes state
const [notes, setNotes] = useState([]);
const [notesLoading, setNotesLoading] = useState(false);
const [notesFilter, setNotesFilter] = useState("all"); // "all", "internal", "customer"
const [newNoteType, setNewNoteType] = useState("internal");
const [newNoteContent, setNewNoteContent] = useState("");
const [newNoteAuthor, setNewNoteAuthor] = useState(() => auth?.user?.name || "MSP Technician");
const [editingNoteId, setEditingNoteId] = useState(null);
const [editingContent, setEditingContent] = useState("");
const [postingNote, setPostingNote] = useState(false);

const [resolutionSummary, setResolutionSummary] = useState("");
const [resolutionDetails, setResolutionDetails] = useState("");
const [resolvingTicket, setResolvingTicket] = useState(false);

// Technician & Escalation states
const [technicians, setTechnicians] = useState([]);
const [techniciansLoading, setTechniciansLoading] = useState(false);
const [wbTechFilter, setWbTechFilter] = useState("all");
const [wbEscalationFilter, setWbEscalationFilter] = useState("all");

const [assignModalTicket, setAssignModalTicket] = useState(null);
const [selectedTechId, setSelectedTechId] = useState("");
const [assigningTech, setAssigningTech] = useState(false);

const [escalateModalTicket, setEscalateModalTicket] = useState(null);
const [targetEscalationLevel, setTargetEscalationLevel] = useState(2);
const [escalationReason, setEscalationReason] = useState("");
const [escalatedBy, setEscalatedBy] = useState(() => auth?.user?.name || "MSP Technician");
const [escalating, setEscalating] = useState(false);

// Synchronize author and escalator when logged in user changes
useEffect(() => {
  if (auth?.user?.name) {
    setNewNoteAuthor(auth.user.name);
    setEscalatedBy(auth.user.name);
  }
}, [auth?.user?.name]);

// Workbench Filters
const [wbSearch, setWbSearch] = useState("");
const [wbPriorityFilter, setWbPriorityFilter] = useState("all");
const [wbTeamFilter, setWbTeamFilter] = useState("all");
const [wbStatusFilter, setWbStatusFilter] = useState("open"); // "open", "all", "new", "in_progress", "resolved"
const [wbSlaFilter, setWbSlaFilter] = useState("all");
const [wbRoutingFilter, setWbRoutingFilter] = useState("all");

const loadTechnicians = async () => {
  setTechniciansLoading(true);
  try {
    const response = await fetch(`${API_URL}/technicians/`);
    const data = await response.json();
    if (response.ok) {
      setTechnicians(data.technicians || []);
    }
  } catch (error) {
    console.error("Failed to load technicians:", error);
  } finally {
    setTechniciansLoading(false);
  }
};

const handleAssignTechnician = async (ticketId, techId, customAssignedBy = "MSP Dispatcher") => {
  setAssigningTech(true);
  try {
    const assignedBy = auth?.user?.name || customAssignedBy;
    const response = await fetch(`${API_URL}/tickets/${ticketId}/technician`, {
      method: "PATCH",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        technician_id: techId ? Number(techId) : null,
        assigned_by: assignedBy
      })
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      alert(data.error || "Failed to assign technician");
      return;
    }
    loadTickets();
    loadTechnicians();
    if (selectedTicket && selectedTicket.id === ticketId) {
      setSelectedTicket((prev) => ({
        ...prev,
        assigned_technician_id: data.assigned_technician_id,
        assigned_technician: data.assigned_technician
      }));
      loadActivityHistory(ticketId);
      loadTicketNotifications(ticketId);
    }
    setAssignModalTicket(null);
  } catch (error) {
    console.error("Error assigning technician:", error);
    alert(error.message);
  } finally {
    setAssigningTech(false);
  }
};

const handleEscalateTicket = async (e) => {
  if (e) e.preventDefault();
  if (!escalateModalTicket || !escalationReason.trim()) {
    alert("Please provide an escalation reason.");
    return;
  }
  setEscalating(true);
  try {
    const escalator = auth?.user?.name || escalatedBy || "MSP Technician";
    const response = await fetch(`${API_URL}/tickets/${escalateModalTicket.id}/escalate`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        escalation_level: Number(targetEscalationLevel),
        escalation_reason: escalationReason.trim(),
        escalated_by: escalator
      })
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      alert(data.error || "Failed to escalate ticket");
      return;
    }
    loadTickets();
    if (selectedTicket && selectedTicket.id === escalateModalTicket.id) {
      setSelectedTicket((prev) => ({
        ...prev,
        escalation_level: data.escalation_level,
        escalation_reason: data.escalation_reason,
        escalated_at: data.escalated_at,
        escalated_by: data.escalated_by
      }));
      loadActivityHistory(escalateModalTicket.id);
      loadTicketNotifications(escalateModalTicket.id);
    }
    setEscalateModalTicket(null);
    setEscalationReason("");
  } catch (error) {
    console.error("Error escalating ticket:", error);
    alert(error.message);
  } finally {
    setEscalating(false);
  }
};

const loadTicketNotes = async (ticketId) => {
  setNotesLoading(true);
  try {
    const response = await fetch(`${API_URL}/tickets/${ticketId}/notes`, {
      headers: getAuthHeaders()
    });
    const data = await response.json();
    if (response.ok) {
      setNotes(data.notes || []);
    } else {
      setNotes([]);
    }
  } catch (error) {
    console.error("Failed to load notes:", error);
    setNotes([]);
  } finally {
    setNotesLoading(false);
  }
};

const handleAddNote = async (e) => {
  e.preventDefault();
  if (!selectedTicket || !newNoteContent.trim()) return;

  setPostingNote(true);
  try {
    const authorToSend = auth?.user?.name || newNoteAuthor || "MSP Technician";
    const response = await fetch(`${API_URL}/tickets/${selectedTicket.id}/notes`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        note_type: newNoteType,
        content: newNoteContent.trim(),
        author: authorToSend
      })
    });
    const data = await response.json();
    if (response.ok && !data.error) {
      setNewNoteContent("");
      loadTicketNotes(selectedTicket.id);
      loadActivityHistory(selectedTicket.id);
    } else {
      alert(data.error || "Failed to add note");
    }
  } catch (error) {
    console.error("Failed to post note:", error);
    alert(error.message);
  } finally {
    setPostingNote(false);
  }
};

const handleUpdateNote = async (noteId) => {
  if (!selectedTicket || !editingContent.trim()) return;

  try {
    const response = await fetch(`${API_URL}/tickets/${selectedTicket.id}/notes/${noteId}`, {
      method: "PUT",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        content: editingContent.trim(),
        author: auth?.user?.name
      })
    });
    const data = await response.json();
    if (response.ok && !data.error) {
      setEditingNoteId(null);
      setEditingContent("");
      loadTicketNotes(selectedTicket.id);
    } else {
      alert(data.error || "Failed to update note");
    }
  } catch (error) {
    console.error("Failed to update note:", error);
    alert(error.message);
  }
};

const handleDeleteNote = async (noteId) => {
  if (!selectedTicket || !window.confirm("Are you sure you want to delete this note?")) return;

  try {
    const response = await fetch(`${API_URL}/tickets/${selectedTicket.id}/notes/${noteId}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    if (response.ok) {
      loadTicketNotes(selectedTicket.id);
    }
  } catch (error) {
    console.error("Failed to delete note:", error);
  }
};

const handleResolveTicket = async (e) => {
  e.preventDefault();
  if (!selectedTicket) return;
  if (!resolutionSummary.trim()) {
    alert("Please provide a resolution summary.");
    return;
  }

  setResolvingTicket(true);
  try {
    const response = await fetch(`${API_URL}/tickets/${selectedTicket.id}/status`, {
      method: "PATCH",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        status: "resolved",
        resolution_summary: resolutionSummary.trim(),
        resolution_details: resolutionDetails.trim()
      })
    });
    const data = await response.json();
    if (response.ok && !data.error) {
      setSelectedTicket((prev) => ({
        ...prev,
        status: "resolved",
        resolved_at: data.resolved_at,
        resolution_summary: data.resolution_summary,
        resolution_details: data.resolution_details,
        sla_status: data.sla_status,
        sla: data.sla
      }));
      loadTickets();
      loadActivityHistory(selectedTicket.id);
      loadTicketNotifications(selectedTicket.id);
    } else {
      alert(data.error || "Failed to resolve ticket");
    }
  } catch (error) {
    console.error("Failed to resolve ticket:", error);
    alert(error.message);
  } finally {
    setResolvingTicket(false);
  }
};

const handleReopenTicket = async () => {
  if (!selectedTicket) return;

  try {
    const response = await fetch(`${API_URL}/tickets/${selectedTicket.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "in_progress"
      })
    });
    const data = await response.json();
    if (response.ok && !data.error) {
      setSelectedTicket((prev) => ({
        ...prev,
        status: "in_progress",
        resolved_at: null,
        sla_status: data.sla_status,
        sla: data.sla
      }));
      loadTickets();
      loadActivityHistory(selectedTicket.id);
      loadTicketNotifications(selectedTicket.id);
    }
  } catch (error) {
    console.error("Failed to reopen ticket:", error);
  }
};

const handleStartWorking = async (ticketToStart) => {
  try {
    const response = await fetch(`${API_URL}/tickets/${ticketToStart.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "in_progress" })
    });
    const data = await response.json();
    if (response.ok) {
      loadTickets();
      if (selectedTicket && selectedTicket.id === ticketToStart.id) {
        setSelectedTicket((prev) => ({
          ...prev,
          status: "in_progress",
          responded_at: data.responded_at,
          sla_status: data.sla_status,
          sla: data.sla
        }));
      }
    }
  } catch (error) {
    console.error("Failed to start working on ticket:", error);
  }
};

  const loadReportsData = async (customFilters = reportFilters) => {
    setReportsLoading(true);
    try {
      const params = new URLSearchParams();
      if (customFilters.startDate) params.append("start_date", customFilters.startDate);
      if (customFilters.endDate) params.append("end_date", customFilters.endDate);
      if (customFilters.customerId) params.append("customer_id", customFilters.customerId);
      if (customFilters.team) params.append("team", customFilters.team);
      if (customFilters.technicianId) params.append("technician_id", customFilters.technicianId);
      if (customFilters.priority) params.append("priority", customFilters.priority);
      if (customFilters.category) params.append("category", customFilters.category);
      if (customFilters.status) params.append("status", customFilters.status);

      const [sumRes, slaRes, tickRes, csatRes] = await Promise.all([
        fetch(`${API_URL}/reports/summary?${params.toString()}`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/reports/sla?${params.toString()}`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/reports/tickets?${params.toString()}&limit=100`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/reports/csat/summary?${params.toString()}`, { headers: getAuthHeaders() })
      ]);

      const sumData = await sumRes.json();
      const slaData = await slaRes.json();
      const tickData = await tickRes.json();
      const csatData = await csatRes.json();

      if (sumRes.ok) setReportsSummary(sumData);
      if (slaRes.ok) setReportsSla(slaData.sla);
      if (tickRes.ok) setReportsTickets(tickData.tickets || []);
      if (csatRes.ok) setReportsCsatSummary(csatData);
    } catch (err) {
      console.error("Failed to load reports:", err);
    } finally {
      setReportsLoading(false);
    }
  };

  const loadPortalReportsData = async (customFilters = portalReportFilters) => {
    setPortalReportsLoading(true);
    try {
      const params = new URLSearchParams();
      if (customFilters.startDate) params.append("start_date", customFilters.startDate);
      if (customFilters.endDate) params.append("end_date", customFilters.endDate);
      if (customFilters.status) params.append("status", customFilters.status);

      const res = await fetch(`${API_URL}/reports/summary?${params.toString()}`, { headers: getAuthHeaders() });
      const data = await res.json();
      if (res.ok) setPortalReportsSummary(data);
    } catch (err) {
      console.error("Failed to load portal reports:", err);
    } finally {
      setPortalReportsLoading(false);
    }
  };

  const downloadReportFile = async (format, isPortal = false) => {
    const currentF = isPortal ? portalReportFilters : reportFilters;
    const params = new URLSearchParams();
    if (currentF.startDate) params.append("start_date", currentF.startDate);
    if (currentF.endDate) params.append("end_date", currentF.endDate);
    if (!isPortal && currentF.customerId) params.append("customer_id", currentF.customerId);
    if (!isPortal && currentF.team) params.append("team", currentF.team);
    if (!isPortal && currentF.technicianId) params.append("technician_id", currentF.technicianId);
    if (!isPortal && currentF.priority) params.append("priority", currentF.priority);
    if (!isPortal && currentF.category) params.append("category", currentF.category);
    if (currentF.status) params.append("status", currentF.status);

    const endpoint = format === "pdf" ? "/reports/export/pdf" : "/reports/export/csv";
    try {
      const res = await fetch(`${API_URL}${endpoint}?${params.toString()}`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`Download failed with status ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "pdf" ? `msp_executive_report_${Date.now()}.pdf` : `msp_ticket_report_${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Report download error:", err);
      alert(`Could not download ${format.toUpperCase()} report: ` + err.message);
    }
  };

  const applyQuickDateRange = (rangeKey, isPortal = false) => {
    const now = new Date();
    let start = "";
    let end = now.toISOString().split("T")[0];

    if (rangeKey === "today") {
      start = now.toISOString().split("T")[0];
    } else if (rangeKey === "7d") {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      start = d.toISOString().split("T")[0];
    } else if (rangeKey === "30d") {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      start = d.toISOString().split("T")[0];
    } else if (rangeKey === "this_month") {
      const d = new Date(now.getFullYear(), now.getMonth(), 1);
      start = d.toISOString().split("T")[0];
    } else if (rangeKey === "all") {
      start = "";
      end = "";
    }

    if (isPortal) {
      const updated = { ...portalReportFilters, quickRange: rangeKey, startDate: start, endDate: end };
      setPortalReportFilters(updated);
      loadPortalReportsData(updated);
    } else {
      const updated = { ...reportFilters, quickRange: rangeKey, startDate: start, endDate: end };
      setReportFilters(updated);
      loadReportsData(updated);
    }
  };

  // =========================================================================
  // KNOWLEDGE BASE & SELF-SERVICE PORTAL API HANDLERS (Phase 9)
  // =========================================================================

  const renderSimpleMarkdown = (text) => {
    if (!text) return null;
    const lines = text.split("\n");
    const elements = [];
    let inCodeBlock = false;
    let codeBuffer = [];

    lines.forEach((line, idx) => {
      if (line.startsWith("```")) {
        if (inCodeBlock) {
          elements.push(
            <pre key={`code-${idx}`} className="kb-markdown-codeblock">
              <code>{codeBuffer.join("\n")}</code>
            </pre>
          );
          codeBuffer = [];
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
        }
        return;
      }

      if (inCodeBlock) {
        codeBuffer.push(line);
        return;
      }

      const trimmed = line.trim();
      if (!trimmed) {
        elements.push(<div key={`spacer-${idx}`} className="kb-markdown-spacer" />);
        return;
      }

      if (trimmed.startsWith("# ")) {
        elements.push(<h1 key={`h1-${idx}`} className="kb-md-h1">{trimmed.replace("# ", "")}</h1>);
      } else if (trimmed.startsWith("## ")) {
        elements.push(<h2 key={`h2-${idx}`} className="kb-md-h2">{trimmed.replace("## ", "")}</h2>);
      } else if (trimmed.startsWith("### ")) {
        elements.push(<h3 key={`h3-${idx}`} className="kb-md-h3">{trimmed.replace("### ", "")}</h3>);
      } else if (trimmed.startsWith("> [!TIP]")) {
        elements.push(<div key={`alert-tip-${idx}`} className="kb-alert-box kb-alert-tip">💡 <strong>Tip:</strong> {trimmed.replace("> [!TIP]", "").trim()}</div>);
      } else if (trimmed.startsWith("> [!NOTE]")) {
        elements.push(<div key={`alert-note-${idx}`} className="kb-alert-box kb-alert-note">ℹ️ <strong>Note:</strong> {trimmed.replace("> [!NOTE]", "").trim()}</div>);
      } else if (trimmed.startsWith("> [!WARNING]") || trimmed.startsWith("> [!CAUTION]")) {
        elements.push(<div key={`alert-warn-${idx}`} className="kb-alert-box kb-alert-warning">⚠️ <strong>Warning:</strong> {trimmed.replace(/> \[(WARNING|CAUTION)\]/, "").trim()}</div>);
      } else if (trimmed.startsWith("> ")) {
        elements.push(<blockquote key={`quote-${idx}`} className="kb-blockquote">{trimmed.replace("> ", "")}</blockquote>);
      } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        elements.push(<li key={`li-${idx}`} className="kb-md-li">{trimmed.substring(2)}</li>);
      } else if (/^\d+\.\s/.test(trimmed)) {
        elements.push(<li key={`num-li-${idx}`} className="kb-md-num-li">{trimmed.replace(/^\d+\.\s/, "")}</li>);
      } else {
        elements.push(<p key={`p-${idx}`} className="kb-md-p">{trimmed}</p>);
      }
    });

    if (inCodeBlock && codeBuffer.length > 0) {
      elements.push(
        <pre key="code-end" className="kb-markdown-codeblock">
          <code>{codeBuffer.join("\n")}</code>
        </pre>
      );
    }

    return <div className="kb-markdown-body">{elements}</div>;
  };

  const loadInternalKb = async (customFilters = {}) => {
    setKbLoading(true);
    try {
      const q = customFilters.query !== undefined ? customFilters.query : kbSearchQuery;
      const cat = customFilters.category !== undefined ? customFilters.category : kbSelectedCategory;
      const vis = customFilters.visibility !== undefined ? customFilters.visibility : kbVisibilityFilter;
      const stat = customFilters.status !== undefined ? customFilters.status : kbStatusFilter;

      const params = new URLSearchParams();
      if (q && q.trim()) params.append("query", q.trim());
      if (cat && cat !== "all") params.append("category_id", cat);
      if (vis && vis !== "all") params.append("visibility", vis);
      if (stat && stat !== "all") params.append("status", stat);

      const [resArts, resCats, resAnalytics] = await Promise.all([
        fetch(`${API_URL}/kb/articles?${params.toString()}`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/kb/categories`, { headers: getAuthHeaders() }),
        (isAdmin || isManager) ? fetch(`${API_URL}/kb/analytics`, { headers: getAuthHeaders() }) : Promise.resolve(null)
      ]);

      if (resArts.ok) {
        const dataArts = await resArts.json();
        setKbArticles(dataArts.articles || []);
      }
      if (resCats.ok) {
        const dataCats = await resCats.json();
        setKbCategories(dataCats.categories || []);
      }
      if (resAnalytics && resAnalytics.ok) {
        const dataAnalytics = await resAnalytics.json();
        setKbAnalyticsData(dataAnalytics);
      }
    } catch (err) {
      console.error("Error loading internal KB data:", err);
    } finally {
      setKbLoading(false);
    }
  };

  const loadPortalKb = async (query = "", categorySlug = "all") => {
    setPortalKbLoading(true);
    try {
      const params = new URLSearchParams();
      if (query && query.trim()) params.append("query", query.trim());
      if (categorySlug && categorySlug !== "all") params.append("category_slug", categorySlug);

      const [resCats, resArts] = await Promise.all([
        fetch(`${API_URL}/portal/kb/categories`, { headers: getAuthHeaders() }),
        fetch(`${API_URL}/portal/kb/articles?${params.toString()}`, { headers: getAuthHeaders() })
      ]);

      if (resCats.ok) {
        const dataCats = await resCats.json();
        setPortalKbCategories(dataCats.categories || []);
      }
      if (resArts.ok) {
        const dataArts = await resArts.json();
        setPortalKbArticles(dataArts.articles || []);
      }
    } catch (err) {
      console.error("Error loading Portal KB:", err);
    } finally {
      setPortalKbLoading(false);
    }
  };

  const loadPortalArticleDetail = async (idOrSlug) => {
    try {
      const res = await fetch(`${API_URL}/portal/kb/articles/${idOrSlug}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setPortalKbActiveArticle(data.article);
      } else {
        alert("Could not load article content.");
      }
    } catch (err) {
      console.error("Error loading portal article detail:", err);
    }
  };

  const handlePortalSubmitFeedback = async (articleId, isHelpful) => {
    setPortalKbFeedbackSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/portal/kb/articles/${articleId}/feedback`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          is_helpful: isHelpful,
          comment: portalKbFeedbackComment || null
        })
      });
      if (res.ok) {
        const data = await res.json();
        setPortalKbFeedbackGiven((prev) => ({ ...prev, [articleId]: isHelpful }));
        setPortalKbFeedbackComment("");
        if (portalKbActiveArticle && portalKbActiveArticle.id === articleId) {
          setPortalKbActiveArticle((prev) => ({
            ...prev,
            helpful_count: data.helpful_count,
            not_helpful_count: data.not_helpful_count
          }));
        }
      }
    } catch (err) {
      console.error("Error submitting feedback:", err);
    } finally {
      setPortalKbFeedbackSubmitting(false);
    }
  };

  const handlePortalKbSuggest = async (q, cat) => {
    if (!q || q.trim().length < 2) {
      setPortalKbSuggestions([]);
      return;
    }
    setPortalKbSuggesting(true);
    try {
      const params = new URLSearchParams({ q: q.trim() });
      if (cat) params.append("category", cat);
      const res = await fetch(`${API_URL}/portal/kb/suggest?${params.toString()}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setPortalKbSuggestions(data.suggestions || []);
      }
    } catch (err) {
      console.error("Error suggesting articles:", err);
    } finally {
      setPortalKbSuggesting(false);
    }
  };

  const handleOpenCreateKbArticle = () => {
    setEditingKbArticle(null);
    setKbArticleForm({
      title: "",
      summary: "",
      content: "",
      category_id: kbCategories[0]?.id ? String(kbCategories[0].id) : "",
      visibility: "public",
      status: "published",
      team_id: "",
      tags: "",
      change_summary: "Initial publication"
    });
    setShowKbArticleModal(true);
  };

  const handleOpenEditKbArticle = async (article) => {
    setEditingKbArticle(article);
    try {
      const res = await fetch(`${API_URL}/kb/articles/${article.id}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        const a = data.article;
        setKbArticleForm({
          title: a.title,
          summary: a.summary || "",
          content: a.content || "",
          category_id: a.category_id ? String(a.category_id) : "",
          visibility: a.visibility || "public",
          status: a.status || "published",
          team_id: a.team_id ? String(a.team_id) : "",
          tags: Array.isArray(a.tags) ? a.tags.join(", ") : (a.tags || ""),
          change_summary: `Updated to version ${a.current_version + 1}`
        });
        setShowKbArticleModal(true);
      }
    } catch (err) {
      console.error("Error fetching article for edit:", err);
    }
  };

  const handleSaveKbArticle = async (e) => {
    e.preventDefault();
    if (!kbArticleForm.title || !kbArticleForm.content) {
      alert("Please fill in both article title and content.");
      return;
    }
    setKbSavingArticle(true);
    try {
      const payload = {
        title: kbArticleForm.title,
        summary: kbArticleForm.summary || null,
        content: kbArticleForm.content,
        category_id: kbArticleForm.category_id ? parseInt(kbArticleForm.category_id) : null,
        visibility: kbArticleForm.visibility,
        status: kbArticleForm.status,
        team_id: kbArticleForm.team_id ? parseInt(kbArticleForm.team_id) : null,
        tags: kbArticleForm.tags || null,
        change_summary: kbArticleForm.change_summary || "Article update"
      };

      const url = editingKbArticle
        ? `${API_URL}/kb/articles/${editingKbArticle.id}`
        : `${API_URL}/kb/articles`;
      const method = editingKbArticle ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        setShowKbArticleModal(false);
        setEditingKbArticle(null);
        loadInternalKb();
      } else {
        alert(data.detail || "Failed to save article.");
      }
    } catch (err) {
      console.error("Error saving article:", err);
      alert("Failed to save article: " + err.message);
    } finally {
      setKbSavingArticle(false);
    }
  };

  const handleDeleteKbArticle = async (id) => {
    if (!window.confirm("Are you sure you want to permanently delete this knowledge article?")) {
      return;
    }
    try {
      const res = await fetch(`${API_URL}/kb/articles/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        if (kbActiveArticle && kbActiveArticle.id === id) setKbActiveArticle(null);
        loadInternalKb();
      } else {
        const data = await res.json();
        alert(data.detail || "Failed to delete article.");
      }
    } catch (err) {
      console.error("Error deleting article:", err);
    }
  };

  const handleOpenKbVersions = async (article) => {
    setKbVersionsArticle(article);
    setShowKbVersionsModal(true);
    setKbVersionsLoading(true);
    try {
      const res = await fetch(`${API_URL}/kb/articles/${article.id}/versions`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setKbVersionsList(data.versions || []);
      }
    } catch (err) {
      console.error("Error loading article versions:", err);
    } finally {
      setKbVersionsLoading(false);
    }
  };

  const handleOpenCreateKbCategory = () => {
    setEditingKbCategory(null);
    setKbCategoryForm({
      name: "",
      description: "",
      icon: "book",
      display_order: kbCategories.length + 1,
      is_active: true
    });
    setShowKbCategoryModal(true);
  };

  const handleOpenEditKbCategory = (cat) => {
    setEditingKbCategory(cat);
    setKbCategoryForm({
      name: cat.name,
      description: cat.description || "",
      icon: cat.icon || "book",
      display_order: cat.display_order || 0,
      is_active: cat.is_active
    });
    setShowKbCategoryModal(true);
  };

  const handleSaveKbCategory = async (e) => {
    e.preventDefault();
    if (!kbCategoryForm.name) return;
    setKbSavingCategory(true);
    try {
      const payload = {
        name: kbCategoryForm.name,
        description: kbCategoryForm.description || null,
        icon: kbCategoryForm.icon || "book",
        display_order: parseInt(kbCategoryForm.display_order) || 0,
        is_active: kbCategoryForm.is_active
      };
      const url = editingKbCategory
        ? `${API_URL}/kb/categories/${editingKbCategory.id}`
        : `${API_URL}/kb/categories`;
      const method = editingKbCategory ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        setShowKbCategoryModal(false);
        setEditingKbCategory(null);
        loadInternalKb();
      } else {
        alert(data.detail || "Failed to save category.");
      }
    } catch (err) {
      console.error("Error saving category:", err);
    } finally {
      setKbSavingCategory(false);
    }
  };

  const handleDeleteKbCategory = async (id) => {
    if (!window.confirm("Are you sure you want to delete this category?")) return;
    try {
      const res = await fetch(`${API_URL}/kb/categories/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        loadInternalKb();
      } else {
        const data = await res.json();
        alert(data.detail || "Failed to delete category.");
      }
    } catch (err) {
      console.error("Error deleting category:", err);
    }
  };

  const handleCopySolution = (content, id = null) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(content);
      setCopiedSolutionId(id || "temp");
      setTimeout(() => setCopiedSolutionId(null), 2500);
    }
  };

const navigateTo = (page, ticketToSelect = null) => {
  setCurrentPage(page);
  setSelectedTicket(ticketToSelect);
  if (!page.startsWith("portal-") || page === "portal-tickets") {
    if (!ticketToSelect) {
      setPortalSelectedTicket(null);
    }
  }
  let targetPath = "/";
  if (page === "portal-dashboard") targetPath = "/portal";
  else if (page === "portal-tickets") targetPath = "/portal/tickets";
  else if (page === "portal-new") targetPath = "/portal/new-ticket";
  else if (page === "portal-notifications") targetPath = "/portal/notifications";
  else if (page === "portal-profile") targetPath = "/portal/profile";
  else if (page === "portal-reports") {
    targetPath = "/portal/reports";
    loadPortalReportsData();
  }
  else if (page === "portal-kb") {
    targetPath = "/portal/kb";
    loadPortalKb();
  }
  else if (page === "workbench") targetPath = "/workbench";
  else if (page === "tickets") targetPath = "/tickets";
  else if (page === "rules") targetPath = "/rules";
  else if (page === "teams") {
    targetPath = "/teams";
    loadTeamsList();
  }
  else if (page === "knowledge-base") {
    targetPath = "/knowledge-base";
    loadInternalKb();
  }
  else if (page === "analytics") {
    targetPath = "/analytics";
    loadAnalytics();
  } else if (page === "reports") {
    targetPath = "/reports";
    loadReportsData();
  } else if (page === "users") {
    targetPath = "/users";
    loadUsersList();
  }
  if (typeof window !== "undefined" && window.location.pathname !== targetPath) {
    window.history.pushState({ page }, "", targetPath);
  }
};

const handleLogin = async (e, directCreds = null) => {
  if (e) e.preventDefault();
  setLoginError("");
  setLoginLoading(true);

  const email = (directCreds?.email || loginEmail).trim();
  const password = directCreds?.password || loginPassword;

  try {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) {
      setLoginError(data.detail || "Invalid email or password.");
      setLoginLoading(false);
      return;
    }

    const authData = {
      token: data.access_token,
      user: data.user,
      isAuthenticated: true
    };
    setAuth(authData);
    localStorage.setItem("jace_auth", JSON.stringify(authData));

    // Role-based routing and tenant state initialization
    if (data.user.role === "customer") {
      const custObj = {
        id: data.user.customer_id,
        name: data.user.name,
        email: data.user.email,
        company: data.user.company || "Customer"
      };
      setActiveCustomer(custObj);
      navigateTo("portal-dashboard");
    } else if (data.user.role === "technician") {
      navigateTo("workbench");
    } else {
      navigateTo("dashboard");
    }
  } catch (err) {
    console.error("Login request error:", err);
    setLoginError("Could not connect to backend server. Please verify backend is running.");
  } finally {
    setLoginLoading(false);
  }
};

const handleLogout = () => {
  localStorage.removeItem("jace_auth");
  setAuth({ token: null, user: null, isAuthenticated: false });
  setActiveCustomer(null);
  navigateTo("dashboard");
};

const loadUsersList = async () => {
  setUsersLoading(true);
  try {
    const res = await fetch(`${API_URL}/auth/users`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      setUsersList(data.users || []);
    }
  } catch (e) {
    console.error("Failed to load users list:", e);
  } finally {
    setUsersLoading(false);
  }
};

const handleCreateUser = async (e) => {
  e.preventDefault();
  if (!newUserForm.name.trim() || !newUserForm.email.trim() || !newUserForm.password) {
    alert("Please fill in all required fields.");
    return;
  }
  setCreatingUser(true);
  try {
    const payload = {
      name: newUserForm.name.trim(),
      email: newUserForm.email.trim(),
      password: newUserForm.password,
      role: newUserForm.role,
      technician_id: newUserForm.technician_id ? parseInt(newUserForm.technician_id) : null,
      customer_id: newUserForm.customer_id ? parseInt(newUserForm.customer_id) : null
    };
    const res = await fetch(`${API_URL}/auth/users`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      alert("User created successfully!");
      setShowCreateUserModal(false);
      setNewUserForm({
        name: "",
        email: "",
        password: "",
        role: "technician",
        technician_id: "",
        customer_id: ""
      });
      loadUsersList();
    } else {
      alert(data.detail || "Failed to create user");
    }
  } catch (err) {
    console.error("Error creating user:", err);
    alert(err.message);
  } finally {
    setCreatingUser(false);
  }
};

const handleToggleUserStatus = async (user) => {
  const newStatus = !user.is_active;
  try {
    const res = await fetch(`${API_URL}/auth/users/${user.id}`, {
      method: "PATCH",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ is_active: newStatus })
    });
    const data = await res.json();
    if (res.ok) {
      loadUsersList();
    } else {
      alert(data.detail || "Failed to update user status");
    }
  } catch (err) {
    console.error("Error updating user status:", err);
  }
};

const handleResetPassword = async (e) => {
  e.preventDefault();
  if (!resetPasswordModalUser || !newResetPassword || newResetPassword.length < 6) {
    alert("Password must be at least 6 characters long.");
    return;
  }
  setSavingResetPassword(true);
  try {
    const res = await fetch(`${API_URL}/auth/users/${resetPasswordModalUser.id}`, {
      method: "PATCH",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ password: newResetPassword })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Password for '${resetPasswordModalUser.name}' reset successfully!`);
      setResetPasswordModalUser(null);
      setNewResetPassword("");
    } else {
      alert(data.detail || "Failed to reset password");
    }
  } catch (err) {
    console.error("Error resetting password:", err);
    alert(err.message);
  } finally {
    setSavingResetPassword(false);
  }
};



// =========================================================================
// CUSTOMER PORTAL STATE & HANDLERS
// =========================================================================
const [portalCustomers, setPortalCustomers] = useState([]);
const [activeCustomer, setActiveCustomer] = useState(() => {
  if (auth?.user?.role === "customer") {
    return {
      id: auth.user.customer_id,
      name: auth.user.name,
      email: auth.user.email,
      company: auth.user.company || "Customer"
    };
  }
  return null;
});

// Synchronize customer identity when auth session changes
useEffect(() => {
  if (auth?.user?.role === "customer") {
    const custObj = {
      id: auth.user.customer_id,
      name: auth.user.name,
      email: auth.user.email,
      company: auth.user.company || "Customer"
    };
    setActiveCustomer(custObj);
  }
}, [auth?.user?.id, auth?.user?.role, auth?.user?.customer_id, auth?.user?.name, auth?.user?.company]);

const [portalDashboard, setPortalDashboard] = useState(null);
const [portalDashboardLoading, setPortalDashboardLoading] = useState(false);
const [portalTickets, setPortalTickets] = useState([]);
const [portalTicketsLoading, setPortalTicketsLoading] = useState(false);
const [portalSelectedTicket, setPortalSelectedTicket] = useState(null);
const [portalTicketDetailLoading, setPortalTicketDetailLoading] = useState(false);
const [portalTicketUpdates, setPortalTicketUpdates] = useState([]);
const [portalTicketActivity, setPortalTicketActivity] = useState([]);
const [portalNotifications, setPortalNotifications] = useState([]);
const [portalUnreadCount, setPortalUnreadCount] = useState(0);

// Portal New Ticket Form State
const [portalNewTitle, setPortalNewTitle] = useState("");
const [portalNewDescription, setPortalNewDescription] = useState("");
const [portalNewCategory, setPortalNewCategory] = useState("Network");
const [portalNewPriority, setPortalNewPriority] = useState("medium");
const [portalSubmitting, setPortalSubmitting] = useState(false);

// Portal Reply State
const [portalReplyText, setPortalReplyText] = useState("");
const [portalReplying, setPortalReplying] = useState(false);

// Portal Filters
const [portalSearch, setPortalSearch] = useState("");
const [portalStatusFilter, setPortalStatusFilter] = useState("all");
const [portalPriorityFilter, setPortalPriorityFilter] = useState("all");
const [portalCategoryFilter, setPortalCategoryFilter] = useState("all");
const [portalSlaFilter, setPortalSlaFilter] = useState("all");

// Portal Profile State
const [portalProfile, setPortalProfile] = useState(null);
const [portalProfileName, setPortalProfileName] = useState("");
const [portalProfilePhone, setPortalProfilePhone] = useState("");
const [portalProfileCompany, setPortalProfileCompany] = useState("");
const [portalSavingProfile, setPortalSavingProfile] = useState(false);

const loadPortalCustomers = async () => {
  try {
    const res = await fetch(`${API_URL}/portal/customers`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (res.ok && data.customers?.length) {
      setPortalCustomers(data.customers);
      if (auth?.user?.role === "customer") {
        const matching = data.customers.find(
          (c) => (auth.user.customer_id && c.id === auth.user.customer_id) ||
                 (auth.user.email && c.email?.toLowerCase() === auth.user.email.toLowerCase()) ||
                 (auth.user.company && c.company?.toLowerCase() === auth.user.company.toLowerCase())
        );
        if (matching) {
          setActiveCustomer(matching);
          return;
        }
      }
      if (!activeCustomer && auth?.user?.role !== "customer") {
        setActiveCustomer(data.customers[0]);
      }
    }
  } catch (err) {
    console.error("Failed to load portal customers:", err);
  }
};

const loadPortalDashboard = async (cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust) return;
  setPortalDashboardLoading(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/dashboard`, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalDashboard(data);
    }
  } catch (err) {
    console.error("Failed to load portal dashboard:", err);
  } finally {
    setPortalDashboardLoading(false);
  }
};

const loadPortalTickets = async (cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust) return;
  setPortalTicketsLoading(true);
  try {
    const params = new URLSearchParams();
    if (portalStatusFilter && portalStatusFilter !== "all") params.append("status", portalStatusFilter);
    if (portalPriorityFilter && portalPriorityFilter !== "all") params.append("priority", portalPriorityFilter);
    if (portalCategoryFilter && portalCategoryFilter !== "all") params.append("category", portalCategoryFilter);
    if (portalSlaFilter && portalSlaFilter !== "all") params.append("sla_status", portalSlaFilter);
    if (portalSearch.trim()) params.append("search", portalSearch.trim());

    const url = `${API_URL}/portal/tickets?${params.toString()}`;
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(url, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalTickets(data.tickets || []);
    }
  } catch (err) {
    console.error("Failed to load portal tickets:", err);
  } finally {
    setPortalTicketsLoading(false);
  }
};

const loadPortalTicketCsat = async (ticketId, cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust || !ticketId) return;
  setPortalCsatLoading(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/csat/ticket/${ticketId}`, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalTicketCsat(data);
      if (data.has_rated && data.csat) {
        setPortalCsatRating(data.csat.rating);
        setPortalCsatFeedback(data.csat.feedback || "");
      } else {
        setPortalCsatRating(5);
        setPortalCsatFeedback("");
      }
    }
  } catch (err) {
    console.error("Failed to load portal ticket CSAT:", err);
  } finally {
    setPortalCsatLoading(false);
  }
};

const handlePortalSubmitCsat = async () => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!portalSelectedTicket || !currentCust) return;
  setPortalCsatSubmitting(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/csat/ticket/${portalSelectedTicket.id}`, {
      method: "POST",
      headers: getAuthHeaders({ ...custHeader, "Content-Type": "application/json" }),
      body: JSON.stringify({
        rating: portalCsatRating,
        feedback: portalCsatFeedback
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert("Thank you! Your satisfaction rating has been recorded.");
      loadPortalTicketCsat(portalSelectedTicket.id, currentCust);
      loadPortalTicketDetail(portalSelectedTicket.id, currentCust);
    } else {
      alert(data.detail || "Failed to submit rating.");
    }
  } catch (err) {
    console.error("Error submitting CSAT rating:", err);
    alert("Error submitting rating.");
  } finally {
    setPortalCsatSubmitting(false);
  }
};

const loadPortalTicketDetail = async (ticketId, cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust || !ticketId) return;
  setPortalTicketDetailLoading(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/tickets/${ticketId}`, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalSelectedTicket(data.ticket);
      setPortalTicketUpdates(data.updates || []);
      setPortalTicketActivity(data.activity || []);
      if (data.ticket?.status === "resolved") {
        loadPortalTicketCsat(ticketId, currentCust);
      } else {
        setPortalTicketCsat(null);
      }
    } else {
      alert(data.detail || "Failed to load ticket details");
    }
  } catch (err) {
    console.error("Failed to load portal ticket detail:", err);
  } finally {
    setPortalTicketDetailLoading(false);
  }
};

const loadPortalNotifications = async (cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/notifications`, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalNotifications(data.notifications || []);
      setPortalUnreadCount(data.unread_count || 0);
    }
  } catch (err) {
    console.error("Failed to load portal notifications:", err);
  }
};

const loadPortalProfile = async (cust = activeCustomer) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || cust || activeCustomer;
  if (!currentCust) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/profile`, {
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      setPortalProfile(data);
      setPortalProfileName(data.name || "");
      setPortalProfilePhone(data.phone || "");
      setPortalProfileCompany(data.company || "");
    }
  } catch (err) {
    console.error("Failed to load portal profile:", err);
  }
};

const handlePortalCreateTicket = async (e) => {
  if (e) e.preventDefault();
  if (!portalNewTitle.trim() || !portalNewDescription.trim()) {
    alert("Please enter both a subject and description.");
    return;
  }
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!currentCust) {
    alert("Please select a customer account first.");
    return;
  }
  setPortalSubmitting(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/tickets`, {
      method: "POST",
      headers: getAuthHeaders({
        "Content-Type": "application/json",
        ...custHeader
      }),
      body: JSON.stringify({
        title: portalNewTitle.trim(),
        description: portalNewDescription.trim(),
        category: portalNewCategory,
        priority: portalNewPriority
      })
    });
    const data = await res.json();
    if (res.ok) {
      setPortalNewTitle("");
      setPortalNewDescription("");
      loadPortalTickets(currentCust);
      loadPortalDashboard(currentCust);
      loadPortalNotifications(currentCust);
      loadTickets(); // Refresh internal view as well
      navigateTo("portal-tickets");
      if (data.ticket?.id) {
        loadPortalTicketDetail(data.ticket.id, currentCust);
      }
    } else {
      alert(data.detail || "Failed to create ticket");
    }
  } catch (err) {
    console.error("Error creating portal ticket:", err);
    alert(err.message);
  } finally {
    setPortalSubmitting(false);
  }
};

const handlePortalSendReply = async (e) => {
  if (e) e.preventDefault();
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!portalReplyText.trim() || !portalSelectedTicket || !currentCust) return;
  setPortalReplying(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/tickets/${portalSelectedTicket.id}/updates`, {
      method: "POST",
      headers: getAuthHeaders({
        "Content-Type": "application/json",
        ...custHeader
      }),
      body: JSON.stringify({ content: portalReplyText.trim() })
    });
    const data = await res.json();
    if (res.ok) {
      setPortalReplyText("");
      loadPortalTicketDetail(portalSelectedTicket.id, currentCust);
      loadPortalDashboard(currentCust);
      loadTickets();
    } else {
      alert(data.detail || "Failed to send update");
    }
  } catch (err) {
    console.error("Error sending portal update:", err);
  } finally {
    setPortalReplying(false);
  }
};

const handlePortalConfirmResolution = async () => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!portalSelectedTicket || !currentCust) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/tickets/${portalSelectedTicket.id}/confirm-resolution`, {
      method: "POST",
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || "Resolution confirmed!");
      loadPortalTicketDetail(portalSelectedTicket.id, currentCust);
    }
  } catch (err) {
    console.error("Error confirming resolution:", err);
  }
};

const handlePortalReopenTicket = async () => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!portalSelectedTicket || !currentCust) return;
  if (!window.confirm("Are you sure you want to reopen this ticket?")) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/tickets/${portalSelectedTicket.id}/reopen`, {
      method: "POST",
      headers: getAuthHeaders(custHeader)
    });
    const data = await res.json();
    if (res.ok) {
      loadPortalTicketDetail(portalSelectedTicket.id, currentCust);
      loadPortalDashboard(currentCust);
      loadPortalTickets(currentCust);
      loadTickets();
    } else {
      alert(data.detail || "Failed to reopen ticket");
    }
  } catch (err) {
    console.error("Error reopening ticket:", err);
  }
};

const handlePortalUpdateProfile = async (e) => {
  if (e) e.preventDefault();
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!currentCust) return;
  setPortalSavingProfile(true);
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    const res = await fetch(`${API_URL}/portal/profile`, {
      method: "PATCH",
      headers: getAuthHeaders({
        "Content-Type": "application/json",
        ...custHeader
      }),
      body: JSON.stringify({
        name: portalProfileName.trim(),
        phone: portalProfilePhone.trim(),
        company: portalProfileCompany.trim()
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert("Profile updated successfully!");
      loadPortalProfile(currentCust);
      loadPortalCustomers();
    } else {
      alert(data.detail || "Failed to update profile");
    }
  } catch (err) {
    console.error("Error updating profile:", err);
  } finally {
    setPortalSavingProfile(false);
  }
};

const handlePortalMarkNotificationRead = async (notifId) => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!currentCust) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    await fetch(`${API_URL}/portal/notifications/${notifId}/read`, {
      method: "PATCH",
      headers: getAuthHeaders(custHeader)
    });
    loadPortalNotifications(currentCust);
  } catch (err) {
    console.error("Error marking notification read:", err);
  }
};

const handlePortalMarkAllNotificationsRead = async () => {
  const currentCust = (auth?.user?.role === "customer" ? auth.user : null) || activeCustomer;
  if (!currentCust) return;
  try {
    const custHeader = currentCust.id ? { "X-Customer-Id": String(currentCust.id) } : {};
    await fetch(`${API_URL}/portal/notifications/mark-all-read`, {
      method: "POST",
      headers: getAuthHeaders(custHeader)
    });
    loadPortalNotifications(currentCust);
  } catch (err) {
    console.error("Error marking all notifications read:", err);
  }
};

// -------------------------------------------------------------
// Team Management Handlers (Phase 7)
// -------------------------------------------------------------
const loadTeamsList = async () => {
  try {
    setTeamsLoading(true);
    const res = await fetch(`${API_URL}/teams/`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (res.ok && data.teams) {
      setTeamsList(data.teams);
    }
  } catch (err) {
    console.error("Failed to load teams list", err);
  } finally {
    setTeamsLoading(false);
  }
};

const handleCreateTeam = async (e) => {
  if (e) e.preventDefault();
  if (!newTeam.name.trim()) {
    alert("Team name is required.");
    return;
  }
  try {
    const payload = {
      name: newTeam.name.trim(),
      description: newTeam.description.trim(),
      team_lead_id: newTeam.team_lead_id ? parseInt(newTeam.team_lead_id, 10) : null,
      business_hours_start: newTeam.business_hours_start || "08:00",
      business_hours_end: newTeam.business_hours_end || "18:00",
      timezone: newTeam.timezone || "America/New_York",
      work_days: newTeam.work_days || "MON,TUE,WED,THU,FRI",
      is_active: newTeam.is_active
    };
    const res = await fetch(`${API_URL}/teams/`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      setShowCreateTeamModal(false);
      setNewTeam({
        name: "",
        description: "",
        team_lead_id: "",
        business_hours_start: "08:00",
        business_hours_end: "18:00",
        timezone: "America/New_York",
        work_days: "MON,TUE,WED,THU,FRI",
        is_active: true
      });
      loadTeamsList();
      loadTechnicians();
    } else {
      alert(data.detail || "Failed to create team.");
    }
  } catch (err) {
    console.error("Error creating team:", err);
  }
};

const handleUpdateTeam = async (e) => {
  if (e) e.preventDefault();
  if (!editingTeam) return;
  try {
    const payload = {
      name: editingTeam.name.trim(),
      description: editingTeam.description.trim(),
      team_lead_id: editingTeam.team_lead_id ? parseInt(editingTeam.team_lead_id, 10) : 0,
      business_hours_start: editingTeam.business_hours_start,
      business_hours_end: editingTeam.business_hours_end,
      timezone: editingTeam.timezone,
      work_days: editingTeam.work_days,
      is_active: editingTeam.is_active
    };
    const res = await fetch(`${API_URL}/teams/${editingTeam.id}`, {
      method: "PUT",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      setEditingTeam(null);
      loadTeamsList();
      loadTechnicians();
      loadRules();
    } else {
      alert(data.detail || "Failed to update team.");
    }
  } catch (err) {
    console.error("Error updating team:", err);
  }
};

const handleToggleTeamStatus = async (team, force = false) => {
  try {
    const res = await fetch(`${API_URL}/teams/${team.id}/status`, {
      method: "PATCH",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ is_active: !team.is_active, force })
    });
    const data = await res.json();
    if (res.ok) {
      setTeamStatusModal(null);
      loadTeamsList();
    } else {
      if (data.detail && typeof data.detail === "object" && data.detail.requires_force) {
        setTeamStatusModal({
          team,
          warning: data.detail.error,
          openTicketsCount: data.detail.open_tickets_count,
          activeRulesCount: data.detail.active_rules_count
        });
      } else {
        alert(data.detail || "Failed to update team status.");
      }
    }
  } catch (err) {
    console.error("Error toggling team status:", err);
  }
};

const handleSaveTeamMembers = async () => {
  if (!managingMembersTeam) return;
  try {
    const res = await fetch(`${API_URL}/teams/${managingMembersTeam.id}/members`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ technician_ids: selectedMemberIds })
    });
    const data = await res.json();
    if (res.ok) {
      setManagingMembersTeam(null);
      loadTeamsList();
      loadTechnicians();
    } else {
      alert(data.detail || "Failed to update team members.");
    }
  } catch (err) {
    console.error("Error updating team members:", err);
  }
};

const handleDeleteTeam = async (team) => {
  if (!window.confirm(`Are you sure you want to permanently delete team '${team.name}'?`)) return;
  try {
    const res = await fetch(`${API_URL}/teams/${team.id}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      loadTeamsList();
      loadTechnicians();
      loadRules();
    } else {
      alert(data.detail || "Failed to delete team.");
    }
  } catch (err) {
    console.error("Error deleting team:", err);
  }
};

useEffect(() => {
  const handlePopState = () => {
    const page = getRouteFromPath(window.location.pathname);
    setCurrentPage(page);
    setSelectedTicket(null);
    if (page === "analytics") {
      loadAnalytics();
    } else if (page === "reports") {
      loadReportsData();
    } else if (page === "teams") {
      loadTeamsList();
    } else if (page === "portal-reports") {
      loadPortalReportsData();
    } else if (page === "knowledge-base") {
      loadInternalKb();
    } else if (page === "portal-kb") {
      loadPortalKb();
    }
  };

  window.addEventListener("popstate", handlePopState);
  return () => window.removeEventListener("popstate", handlePopState);
}, []);

useEffect(() => {
  if (!selectedTicket) {
    setRoutingAnalysis(null);
    setRoutingHistory([]);
    setActivityHistory([]);
    setTicketNotifications([]);
    setNotes([]);
    setResolutionSummary("");
    setResolutionDetails("");
    return;
  }

  loadRoutingAudit(selectedTicket.id);
  loadRoutingHistory(selectedTicket.id);
  loadActivityHistory(selectedTicket.id);
  loadTicketNotifications(selectedTicket.id);
  loadTicketNotes(selectedTicket.id);
  setResolutionSummary(selectedTicket.resolution_summary || "");
  setResolutionDetails(selectedTicket.resolution_details || "");

}, [selectedTicket]);

useEffect(() => {
  loadTickets();
  loadRules();
  loadTechnicians();
  loadTeamsList();
  loadUnreadCount();
  loadPortalCustomers();

  const initialRoute = getRouteFromPath(window.location.pathname);
  if (initialRoute === "analytics") {
    loadAnalytics();
  } else if (initialRoute === "reports") {
    loadReportsData();
  } else if (initialRoute === "teams") {
    loadTeamsList();
  } else if (initialRoute === "portal-reports") {
    loadPortalReportsData();
  } else if (initialRoute === "knowledge-base") {
    loadInternalKb();
  } else if (initialRoute === "portal-kb") {
    loadPortalKb();
  }

  const interval = setInterval(() => {
    loadUnreadCount();
  }, 10000);

  return () => clearInterval(interval);
}, []);

useEffect(() => {
  if (activeCustomer) {
    if (currentPage === "portal-dashboard") {
      loadPortalDashboard(activeCustomer);
      loadPortalNotifications(activeCustomer);
    } else if (currentPage === "portal-tickets") {
      loadPortalTickets(activeCustomer);
    } else if (currentPage === "portal-notifications") {
      loadPortalNotifications(activeCustomer);
    } else if (currentPage === "portal-profile") {
      loadPortalProfile(activeCustomer);
    } else if (currentPage === "portal-reports") {
      loadPortalReportsData();
    }
  }
}, [activeCustomer, currentPage, portalStatusFilter, portalPriorityFilter, portalCategoryFilter, portalSlaFilter, portalSearch]);
  const loadTickets = () => {
    setLoading(true);

    fetch(`${API_URL}/tickets/`, {
      headers: getAuthHeaders()
    })
      .then((response) => response.json())
      .then((data) => {
        setTickets(data.tickets || []);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Failed to load tickets:", error);
        setLoading(false);
      });
  };
const loadRules = () => {
  setRulesLoading(true);

  fetch(`${API_URL}/rules/`, {
    headers: getAuthHeaders()
  })
    .then((response) => response.json())
    .then((data) => {
      setRules(data.rules || []);
      setRulesLoading(false);
    })
    .catch((error) => {
      console.error("Failed to load routing rules:", error);
      setRulesLoading(false);
    });
};
const createRule = async (event) => {
  event.preventDefault();

  if (!newRule.category.trim()) {
    alert("Please enter a rule name.");
    return;
  }

  if (!newRule.description.trim()) {
    alert("Please enter a description.");
    return;
  }

  try {
    const response = await fetch(`${API_URL}/rules/`, {
      method: "POST",
      headers: getAuthHeaders({
        "Content-Type": "application/json"
      }),
      body: JSON.stringify({
        category: newRule.category.trim(),
        team: newRule.team,
        priority: newRule.priority,
        keywords: newRule.keywords
          .split(",")
          .map((keyword) => keyword.trim().toLowerCase())
          .filter(Boolean),
        description: newRule.description.trim()
      })
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(
        data.error || "Failed to create routing rule"
      );
    }

    // Close modal
    setShowCreateRuleModal(false);

    // Reset form
    setNewRule({
      category: "",
      team: "Service Desk",
      priority: "medium",
      keywords: "",
      description: ""
    });

    // Reload rules from database
    loadRules();

    alert("Routing rule created successfully.");

  } catch (error) {
    console.error("Failed to create routing rule:", error);
    alert(error.message);
  }
};
const loadAnalytics = () => {
  setAnalyticsLoading(true);

  fetch(`${API_URL}/analytics/`, {
    headers: getAuthHeaders()
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Failed to load analytics");
      }

      return response.json();
    })
    .then((data) => {
      setAnalytics(data);
      setAnalyticsLoading(false);
    })
    .catch((error) => {
      console.error("Analytics error:", error);
      setAnalyticsLoading(false);
    });
};
const updateRule = async (event) => {
  event.preventDefault();

  if (!editingRule) return;

  setSavingRule(true);

  try {
    const response = await fetch(
      `${API_URL}/rules/${editingRule.id}`,
      {
        method: "PUT",
        headers: getAuthHeaders({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          team: editingRule.team,
          priority: editingRule.priority,
          keywords: editingRule.keywords,
          description: editingRule.description,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(
        data.error || "Failed to update routing rule"
      );
    }
    const reEvaluateResponse = await fetch(
      `${API_URL}/rules/${editingRule.id}/re-evaluate`,
      {
        method: "POST",
        headers: getAuthHeaders(),
      }
    );

    const reEvaluateData = await reEvaluateResponse.json();

    if (!reEvaluateResponse.ok || reEvaluateData.error) {
      console.error(
        "Rule saved, but ticket re-evaluation failed:",
        reEvaluateData.error
      );
    }

    // Refresh tickets after rule re-evaluation
    await loadTickets();

    // Update the rule in the frontend
    setRules((previousRules) =>
      previousRules.map((rule) =>
        rule.name === editingRule.name
          ? data.rule
          : rule
      )
    );
    setEditingRule(null);

  } catch (error) {
    console.error(
      "Failed to update routing rule:",
      error
    );

    alert(error.message);

  } finally {
    setSavingRule(false);
  }
};
const toggleRuleStatus = async (rule) => {
  try {
    const newStatus = rule.status !== "active";

    const response = await fetch(
      `${API_URL}/rules/${rule.id}/status`,
      {
        method: "PATCH",
        headers: getAuthHeaders({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          is_active: newStatus,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail
          ? JSON.stringify(data.detail)
          : data.error || "Failed to update rule status"
      );
    }

    // Reload rules from PostgreSQL
    loadRules();

  } catch (error) {
    console.error("Failed to update rule status:", error);
    alert(error.message);
  }
};
  // Create ticket
  const createTicket = async (event) => {
    event.preventDefault();

    if (!title.trim() || !description.trim()) {
      setMessage("Please enter both title and description.");
      return;
    }

    setSubmitting(true);
    setMessage("");

    try {
      const response = await fetch(`${API_URL}/tickets/route`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: title,
          description: description,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to create ticket");
      }

      setMessage(
        `Ticket #${data.ticket_id} created successfully!`
      );

      setTitle("");
      setDescription("");

      // Reload tickets
      loadTickets();

      // Close form after short delay
      setTimeout(() => {
        setShowForm(false);
        setMessage("");
      }, 1200);
    } catch (error) {
      console.error(error);
      setMessage(error.message);
    } finally {
      setSubmitting(false);
    }
  };
const updateTicketStatus = async (status) => {
  if (!selectedTicket) return;

  setUpdatingStatus(true);

  try {
    const newStatus = String(status);

    console.log("Sending status:", newStatus);

    const response = await fetch(
      `${API_URL}/tickets/${selectedTicket.id}/status`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          status: newStatus,
        }),
      }
    );

    const data = await response.json();

    console.log("Status update response:", data);

    if (!response.ok) {
      const errorMessage =
        data.detail?.[0]?.msg ||
        data.error ||
        JSON.stringify(data);

      throw new Error(errorMessage);
    }

    // Update the ticket currently being viewed
    setSelectedTicket((previous) => ({
      ...previous,
      status: data.status,
      responded_at: data.responded_at,
      resolved_at: data.resolved_at,
      sla_status: data.sla_status,
      sla: data.sla,
    }));

    // Update ticket in the ticket list
    setTickets((previousTickets) =>
      previousTickets.map((ticket) =>
        ticket.id === selectedTicket.id
          ? {
              ...ticket,
              status: data.status,
              responded_at: data.responded_at,
              resolved_at: data.resolved_at,
              sla_status: data.sla_status,
              sla: data.sla,
            }
          : ticket
      )
    );

  } catch (error) {
    console.error(
      "Failed to update ticket status:",
      error
    );

    alert(error.message);

  } finally {
    setUpdatingStatus(false);
  }
};
const updateTicketTeam = async (team) => {
  if (!selectedTicket) return;

  setUpdatingTeam(true);

  try {
    const response = await fetch(
      `${API_URL}/tickets/${selectedTicket.id}/team`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          team: team,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail ||
        data.error ||
        "Failed to re-route ticket"
      );
    }

    // Update selected ticket
    setSelectedTicket((previous) => ({
      ...previous,
      assigned_team: data.assigned_team,
      routing_method: data.routing_method,
    }));

    // Update ticket in the list
    setTickets((previousTickets) =>
      previousTickets.map((ticket) =>
        ticket.id === selectedTicket.id
          ? {
              ...ticket,
              assigned_team: data.assigned_team,
              routing_method: data.routing_method,
            }
          : ticket
      )
    );

  } catch (error) {
    console.error(
      "Failed to re-route ticket:",
      error
    );

    alert(error.message);

  } finally {
    setUpdatingTeam(false);
  }
};
const updateTicketPriority = async (ticketId, newPriority) => {
  try {
    const response = await fetch(
      `${API_URL}/tickets/${ticketId}/priority`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          priority: newPriority
        })
      }
    );

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(
        data.error || "Failed to update ticket priority"
      );
    }

    // Update selected ticket immediately
    setSelectedTicket((current) =>
      current
        ? {
            ...current,
            priority: data.priority,
            response_due_at: data.response_due_at,
            resolution_due_at: data.resolution_due_at,
            sla_status: data.sla_status,
            sla: data.sla,
          }
        : current
    );

    // Refresh ticket list
    loadTickets();

    // Refresh activity timeline
    if (selectedTicket) {
      loadActivityHistory(selectedTicket.id);
    }

  } catch (error) {
    console.error(
      "Failed to update ticket priority:",
      error
    );

    alert(error.message);
  }
};
const filteredTickets = tickets.filter((ticket) => {
  const searchText = search.toLowerCase();

  const matchesSearch =
    ticket.title.toLowerCase().includes(searchText) ||
    ticket.description.toLowerCase().includes(searchText);

  const matchesPriority =
    priorityFilter === "all" ||
    ticket.priority === priorityFilter;

  const matchesTeam =
    teamFilter === "all" ||
    ticket.assigned_team === teamFilter;

  const ticketSlaStatus = ticket.sla_status || ticket.sla?.overall_status || "on_track";
  const matchesSla =
    slaFilter === "all" ||
    ticketSlaStatus === slaFilter;

  return matchesSearch && matchesPriority && matchesTeam && matchesSla;
});

const filteredNotifications = notifications.filter((notif) => {
  if (notifFilter === "unread") return !notif.is_read;
  if (notifFilter === "escalation") return notif.type === "ESCALATION";
  if (notifFilter === "sla") return notif.type === "SLA_AT_RISK" || notif.type === "SLA_BREACHED";
  return true;
});

// Workbench Filtered Queue
const wbFilteredTickets = tickets.filter((ticket) => {
  const q = wbSearch.toLowerCase().trim();
  const matchesSearch =
    !q ||
    String(ticket.id).includes(q) ||
    `#${ticket.id}`.includes(q) ||
    ticket.title.toLowerCase().includes(q) ||
    ticket.description.toLowerCase().includes(q) ||
    (ticket.category || "").toLowerCase().includes(q);

  const matchesPriority =
    wbPriorityFilter === "all" || ticket.priority === wbPriorityFilter;

  const matchesTeam =
    wbTeamFilter === "all" || ticket.assigned_team === wbTeamFilter;

  const tStatus = ticket.status || "new";
  const matchesStatus =
    wbStatusFilter === "all"
      ? true
      : wbStatusFilter === "open"
      ? tStatus !== "resolved"
      : tStatus === wbStatusFilter;

  const ticketSlaStatus = ticket.sla_status || ticket.sla?.overall_status || "on_track";
  const matchesSla =
    wbSlaFilter === "all" || ticketSlaStatus === wbSlaFilter;

  const matchesRouting =
    wbRoutingFilter === "all" || ticket.routing_method === wbRoutingFilter;

  const matchesTech =
    wbTechFilter === "all"
      ? true
      : wbTechFilter === "unassigned"
      ? !ticket.assigned_technician_id && !ticket.assigned_technician
      : String(ticket.assigned_technician_id) === String(wbTechFilter) || ticket.assigned_technician === wbTechFilter;

  const escLevel = ticket.escalation_level || 1;
  const matchesEscalation =
    wbEscalationFilter === "all"
      ? true
      : wbEscalationFilter === "escalated"
      ? escLevel > 1
      : String(escLevel) === String(wbEscalationFilter);

  return (
    matchesSearch &&
    matchesPriority &&
    matchesTeam &&
    matchesStatus &&
    matchesSla &&
    matchesRouting &&
    matchesTech &&
    matchesEscalation
  );
});

// Workbench KPIs
const openTicketsList = tickets.filter((t) => (t.status || "new") !== "resolved");
const openTicketsCount = openTicketsList.length;
const criticalOpenCount = openTicketsList.filter((t) => t.priority === "critical").length;
const highOpenCount = openTicketsList.filter((t) => t.priority === "high").length;
const atRiskCount = tickets.filter((t) => (t.sla_status || t.sla?.overall_status) === "at_risk").length;
const breachedCount = tickets.filter((t) => (t.sla_status || t.sla?.overall_status) === "breached").length;
const resolvedTodayCount = tickets.filter((t) => {
  if (t.status !== "resolved" || !t.resolved_at) return false;
  const rDate = new Date(t.resolved_at).toDateString();
  const today = new Date().toDateString();
  return rDate === today;
}).length;

// Filtered Notes for Selected Ticket
const filteredNotes = notes.filter((n) => {
  if (notesFilter === "internal") return n.note_type === "internal";
  if (notesFilter === "customer") return n.note_type === "customer";
  return true;
});

  const critical = tickets.filter(
    (ticket) => ticket.priority === "critical"
  ).length;

  const high = tickets.filter(
    (ticket) => ticket.priority === "high"
  ).length;

  const automated = tickets.filter(
    (ticket) => ticket.routing_method === "rule_engine"
  ).length;
  const medium = tickets.filter(
  (ticket) => ticket.priority === "medium"
).length;

const low = tickets.filter(
  (ticket) => ticket.priority === "low"
).length;

const m365Tickets = tickets.filter(
  (ticket) => ticket.assigned_team === "M365 Support"
).length;

const networkTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Network Team"
).length;

const securityTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Security Team"
).length;

const endpointTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Endpoint Team"
).length;

const backupTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Backup Team"
).length;
const applicationSupportTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Application Support"
).length;
const serviceDeskTickets = tickets.filter(
  (ticket) => ticket.assigned_team === "Service Desk"
).length;

const automationRate =
  tickets.length > 0
    ? Math.round((automated / tickets.length) * 100)
    : 0;

  // 1. If not authenticated, render Login Page
  if (!auth.isAuthenticated) {
    return (
      <div className="login-page-wrapper">
        <div className="login-card-container">
          <div className="login-brand-header">
            <div className="login-brand-logo">
              JACE <span>HAUS</span>
            </div>
            <p className="login-brand-subtitle">
              MSP Ticket Intelligence &bull; Role-Based Access
            </p>
          </div>

          {loginError && (
            <div className="login-error-alert">
              <span>⚠️</span>
              <span>{loginError}</span>
            </div>
          )}

          <form onSubmit={handleLogin}>
            <div className="login-form-group">
              <label>Email Address</label>
              <input
                type="email"
                placeholder="name@company.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="login-form-group">
              <label>Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="btn-login-submit"
              disabled={loginLoading}
            >
              {loginLoading ? "Authenticating..." : "Sign In to MSP System"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const isCustomer = auth.user?.role === "customer";
  const isAdmin = auth.user?.role === "admin";
  const isManager = auth.user?.role === "manager";
  const isTechnician = auth.user?.role === "technician";

  // Check if current user has permission to view currentPage
  const isPageUnauthorized = () => {
    if (isCustomer && !currentPage.startsWith("portal-")) return true;
    if (!isCustomer && currentPage.startsWith("portal-") && !isAdmin) return true;
    if (isTechnician && ["rules", "analytics", "users", "reports", "teams"].includes(currentPage)) return true;
    if (isManager && ["users"].includes(currentPage)) return true;
    return false;
  };

  if (currentPage.startsWith("portal-")) {
    if (isPageUnauthorized()) {
      return (
        <div className="unauthorized-view-wrapper">
          <div className="unauthorized-card">
            <div className="unauthorized-icon">🔒</div>
            <h2>403 — Unauthorized Access</h2>
            <p>
              Your account role (<strong>{(auth.user?.role || "").toUpperCase()}</strong>) does not have permission to access the Customer Portal.
            </p>
            <button
              className="btn-portal-primary"
              onClick={() => navigateTo(isTechnician ? "workbench" : "dashboard")}
            >
              Return to {isTechnician ? "Technician Workbench" : "Dashboard"}
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="portal-app">
        {/* Portal Top Navbar */}
        <header className="portal-navbar">
          <div className="portal-nav-brand" onClick={() => navigateTo("portal-dashboard")}>
            <span className="portal-brand-logo">JACE <strong>HAUS</strong></span>
            <span className="portal-tag">CLIENT PORTAL</span>
          </div>

          <nav className="portal-nav-links">
            <button
              className={`portal-nav-link ${currentPage === "portal-dashboard" ? "active" : ""}`}
              onClick={() => navigateTo("portal-dashboard")}
            >
              📊 Dashboard
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-tickets" && !portalSelectedTicket ? "active" : ""}`}
              onClick={() => navigateTo("portal-tickets")}
            >
              🎫 My Tickets
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-new" ? "active" : ""}`}
              onClick={() => navigateTo("portal-new")}
            >
              ➕ New Ticket
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-kb" ? "active" : ""}`}
              onClick={() => {
                setPortalKbActiveArticle(null);
                navigateTo("portal-kb");
              }}
            >
              📚 Knowledge Base
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-reports" ? "active" : ""}`}
              onClick={() => navigateTo("portal-reports")}
            >
              📈 SLA Reports
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-notifications" ? "active" : ""}`}
              onClick={() => navigateTo("portal-notifications")}
            >
              🔔 Notifications
              {portalUnreadCount > 0 && (
                <span className="portal-notif-pill">{portalUnreadCount}</span>
              )}
            </button>
            <button
              className={`portal-nav-link ${currentPage === "portal-profile" ? "active" : ""}`}
              onClick={() => navigateTo("portal-profile")}
            >
              👤 Profile
            </button>
          </nav>

          <div className="portal-nav-right">
            {/* User Profile Badge */}
            {auth.user && (
              <div className="header-user-profile">
                <div className="header-user-avatar">
                  {auth.user.name?.charAt(0).toUpperCase() || "C"}
                </div>
                <div className="header-user-details">
                  <div className="header-user-name-row">
                    <span className="header-user-fullname">{auth.user.name}</span>
                    <span className={`user-role-badge role-${auth.user.role}`}>
                      {auth.user.role}
                    </span>
                  </div>
                  <span className="header-user-subtext">
                    {auth.user.company || auth.user.email}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn-header-logout"
                  onClick={handleLogout}
                  title="Sign Out"
                >
                  Sign Out
                </button>
              </div>
            )}

            {/* Admin Switcher & View Switch */}
            {isAdmin && (
              <>
                <div className="customer-switcher-box" title="Select active customer account">
                  <span className="switcher-icon">🏢</span>
                  <select
                    value={activeCustomer?.id || ""}
                    onChange={(e) => {
                      const found = portalCustomers.find((c) => String(c.id) === e.target.value);
                      if (found) {
                        setActiveCustomer(found);
                      }
                    }}
                    className="customer-select-dropdown"
                  >
                    {portalCustomers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} — {c.company}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  className="btn-switch-workspace"
                  onClick={() => navigateTo("workbench")}
                  title="Switch to Internal MSP Technician Workspace"
                >
                  🛠 Technician View →
                </button>
              </>
            )}
          </div>
        </header>

        {/* Main Portal Body */}
        <main className="portal-main-container">
          {/* CUSTOMER TICKET DETAIL VIEW */}
          {portalSelectedTicket ? (
            <section className="portal-ticket-detail-view">
              <div className="portal-detail-header-bar">
                <button
                  className="portal-back-btn"
                  onClick={() => setPortalSelectedTicket(null)}
                >
                  ← Back to My Tickets
                </button>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  <span className={`status-pill ${portalSelectedTicket.status}`}>
                    {portalSelectedTicket.status?.replace("_", " ")}
                  </span>
                  <span className={`priority-tag ${portalSelectedTicket.priority}`}>
                    {portalSelectedTicket.priority?.toUpperCase()}
                  </span>
                  {renderSlaBadge(portalSelectedTicket.sla_status)}
                </div>
              </div>

              {/* Ticket Summary Card */}
              <div className="portal-card">
                <div className="portal-card-header">
                  <div>
                    <h3 style={{ fontSize: "18px" }}>{portalSelectedTicket.title}</h3>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>
                      Ticket #{portalSelectedTicket.id} • Created on {portalSelectedTicket.created_at ? new Date(portalSelectedTicket.created_at).toLocaleString() : "N/A"}
                    </span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{ fontSize: "12px", color: "#64748b", display: "block" }}>Assigned Team</span>
                    <strong style={{ color: "#0f172a", fontSize: "14px" }}>{portalSelectedTicket.assigned_team}</strong>
                  </div>
                </div>

                <div style={{ background: "#f8fafc", padding: "14px 16px", borderRadius: "8px", border: "1px solid #e2e8f0", marginTop: "12px" }}>
                  <strong style={{ fontSize: "12px", color: "#64748b", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>
                    Description
                  </strong>
                  <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.5", color: "#1e293b", whiteSpace: "pre-wrap" }}>
                    {portalSelectedTicket.description}
                  </p>
                </div>

                {/* SLA Target Cards */}
                <div className="portal-detail-meta-grid">
                  <div className="portal-meta-item">
                    <span className="meta-label">Category</span>
                    <span className="meta-val">{portalSelectedTicket.category}</span>
                  </div>
                  <div className="portal-meta-item">
                    <span className="meta-label">Response SLA Target</span>
                    <span className="meta-val">
                      {portalSelectedTicket.sla?.response_sla || "N/A"} ({portalSelectedTicket.sla?.response_status?.replace("_", " ")})
                    </span>
                  </div>
                  <div className="portal-meta-item">
                    <span className="meta-label">Resolution SLA Target</span>
                    <span className="meta-val">
                      {portalSelectedTicket.sla?.resolution_sla || "N/A"} ({portalSelectedTicket.sla?.resolution_status?.replace("_", " ")})
                    </span>
                  </div>
                  <div className="portal-meta-item">
                    <span className="meta-label">Company</span>
                    <span className="meta-val">{portalSelectedTicket.customer_company || activeCustomer?.company}</span>
                  </div>
                </div>
              </div>

              {/* Resolution Notice & Actions (if resolved) */}
              {portalSelectedTicket.status === "resolved" && (
                <div className="portal-resolution-box">
                  <h4>✓ Support Ticket Resolved</h4>
                  <p>Our engineering team has marked this ticket as resolved. Please verify the fix or reply if you need further assistance.</p>
                  <div className="portal-resolution-actions">
                    <button className="btn-confirm-resolution" onClick={handlePortalConfirmResolution}>
                      ✓ Confirm Resolution
                    </button>
                    <button className="btn-reopen-ticket" onClick={handlePortalReopenTicket}>
                      ↻ Reopen Ticket
                    </button>
                  </div>
                </div>
              )}

              {/* CSAT Resolution Rating Survey (Phase 8) */}
              {portalSelectedTicket.status === "resolved" && (
                portalTicketCsat?.has_rated && portalTicketCsat?.csat ? (
                  <div className="portal-csat-confirmed-card">
                    <div className="csat-card-header">
                      <span className="csat-check-icon">✓</span>
                      <div>
                        <h4>Customer Satisfaction Feedback Submitted</h4>
                        <p>Thank you for rating our support service on this ticket.</p>
                      </div>
                    </div>
                    <div className="csat-rating-display">
                      <div className="csat-stars-row">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <span key={star} className={`star-item ${star <= portalTicketCsat.csat.rating ? "filled" : "empty"}`}>
                            ★
                          </span>
                        ))}
                        <span className="csat-score-label">
                          {portalTicketCsat.csat.rating} — {portalTicketCsat.csat.rating_label}
                        </span>
                      </div>
                      {portalTicketCsat.csat.feedback && (
                        <div className="csat-feedback-quote">
                          "{portalTicketCsat.csat.feedback}"
                        </div>
                      )}
                      <small className="csat-timestamp">
                        Submitted on {portalTicketCsat.csat.submitted_at ? new Date(portalTicketCsat.csat.submitted_at).toLocaleString() : "Recently"}
                      </small>
                    </div>
                  </div>
                ) : (
                  <div className="portal-csat-survey-card">
                    <div className="csat-survey-header">
                      <h4>⭐ How did we do?</h4>
                      <p>Please take a moment to rate your resolution experience for this support request.</p>
                    </div>

                    <div className="csat-stars-selector">
                      <div className="stars-picker-row">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            className={`star-pick-btn ${star <= (portalCsatHover || portalCsatRating) ? "active" : ""}`}
                            onMouseEnter={() => setPortalCsatHover(star)}
                            onMouseLeave={() => setPortalCsatHover(0)}
                            onClick={() => setPortalCsatRating(star)}
                            title={`${star} Star${star > 1 ? 's' : ''}`}
                          >
                            ★
                          </button>
                        ))}
                      </div>
                      <div className="csat-rating-desc">
                        {portalCsatRating === 1 && "1 — Very Dissatisfied"}
                        {portalCsatRating === 2 && "2 — Dissatisfied"}
                        {portalCsatRating === 3 && "3 — Neutral"}
                        {portalCsatRating === 4 && "4 — Satisfied"}
                        {portalCsatRating === 5 && "5 — Very Satisfied"}
                      </div>
                    </div>

                    <div className="csat-feedback-field">
                      <label>Additional Feedback (Optional)</label>
                      <textarea
                        className="csat-textarea"
                        placeholder="Share details about what went well or how our support team can improve (optional)..."
                        value={portalCsatFeedback}
                        onChange={(e) => setPortalCsatFeedback(e.target.value)}
                        rows={3}
                      />
                    </div>

                    <div className="csat-actions-row">
                      <button
                        type="button"
                        className="btn-portal-primary btn-submit-csat"
                        onClick={handlePortalSubmitCsat}
                        disabled={portalCsatSubmitting}
                      >
                        {portalCsatSubmitting ? "Submitting..." : "Submit Rating"}
                      </button>
                    </div>
                  </div>
                )
              )}

              {/* Conversation / Public Updates Stream */}
              <div className="portal-card">
                <div className="portal-card-header">
                  <h3>💬 Support Conversation & Updates ({portalTicketUpdates.length})</h3>
                </div>

                {portalTicketUpdates.length === 0 ? (
                  <p style={{ color: "#64748b", fontSize: "13.5px", fontStyle: "italic", margin: "10px 0" }}>
                    No updates posted yet. You can post a message below to communicate with the assigned support engineers.
                  </p>
                ) : (
                  <div className="portal-conversation-list">
                    {portalTicketUpdates.map((u) => {
                      const isCustomerMsg = u.author?.includes(activeCustomer?.name) || u.author?.includes(activeCustomer?.company);
                      return (
                        <div
                          key={u.id}
                          className={`portal-msg-bubble ${isCustomerMsg ? "" : "from-tech"}`}
                        >
                          <div className="portal-msg-header">
                            <div>
                              <span className="portal-msg-author">{u.author}</span>
                              <span className={`portal-author-badge ${isCustomerMsg ? "customer" : "tech"}`}>
                                {isCustomerMsg ? "Client" : "MSP Engineer"}
                              </span>
                            </div>
                            <span className="portal-msg-time">
                              {u.created_at ? new Date(u.created_at).toLocaleString() : ""}
                            </span>
                          </div>
                          <div className="portal-msg-body">{u.content}</div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Reply Box */}
                <form onSubmit={handlePortalSendReply} className="portal-reply-box">
                  <textarea
                    className="portal-reply-textarea"
                    placeholder="Type an update or reply to the support team..."
                    value={portalReplyText}
                    onChange={(e) => setPortalReplyText(e.target.value)}
                  />
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "10px" }}>
                    <button
                      type="submit"
                      className="btn-portal-primary"
                      disabled={portalReplying || !portalReplyText.trim()}
                    >
                      {portalReplying ? "Sending..." : "Post Update"}
                    </button>
                  </div>
                </form>
              </div>

              {/* Public Activity Timeline */}
              <div className="portal-card">
                <div className="portal-card-header">
                  <h3>📋 Ticket Progress History</h3>
                </div>
                <div className="portal-table-container">
                  <table className="portal-table">
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>Details</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portalTicketActivity.map((act) => (
                        <tr key={act.id}>
                          <td>
                            <strong>{act.icon} {act.title}</strong>
                          </td>
                          <td>{act.description}</td>
                          <td style={{ fontSize: "12px", color: "#64748b" }}>
                            {act.created_at ? new Date(act.created_at).toLocaleString() : "N/A"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          ) : currentPage === "portal-dashboard" ? (
            <section className="portal-dashboard-view">
              {/* Greeting Banner */}
              <div className="portal-header-banner">
                <div>
                  <h2>Welcome, {activeCustomer?.name || "Client"}</h2>
                  <p>Support & Service Portal for {activeCustomer?.company}</p>
                </div>
                <button
                  className="btn-portal-primary"
                  onClick={() => navigateTo("portal-new")}
                >
                  ➕ Submit Support Request
                </button>
              </div>

              {/* KPI Stats */}
              <div className="portal-stats-grid">
                <div className="portal-stat-card">
                  <div className="portal-stat-icon total">🎫</div>
                  <div className="portal-stat-info">
                    <div className="count">{portalDashboard?.metrics?.total_tickets ?? 0}</div>
                    <div className="label">Total Tickets</div>
                  </div>
                </div>
                <div className="portal-stat-card">
                  <div className="portal-stat-icon open">📂</div>
                  <div className="portal-stat-info">
                    <div className="count">{portalDashboard?.metrics?.open_tickets ?? 0}</div>
                    <div className="label">Open Tickets</div>
                  </div>
                </div>
                <div className="portal-stat-card">
                  <div className="portal-stat-icon progress">⚡</div>
                  <div className="portal-stat-info">
                    <div className="count">{portalDashboard?.metrics?.in_progress_tickets ?? 0}</div>
                    <div className="label">In Progress</div>
                  </div>
                </div>
                <div className="portal-stat-card">
                  <div className="portal-stat-icon awaiting">⏳</div>
                  <div className="portal-stat-info">
                    <div className="count">{portalDashboard?.metrics?.awaiting_customer_tickets ?? 0}</div>
                    <div className="label">Awaiting Action</div>
                  </div>
                </div>
                <div className="portal-stat-card">
                  <div className="portal-stat-icon resolved">✓</div>
                  <div className="portal-stat-info">
                    <div className="count">{portalDashboard?.metrics?.resolved_tickets ?? 0}</div>
                    <div className="label">Resolved</div>
                  </div>
                </div>
              </div>

              {/* Dashboard 2-Col Layout */}
              <div className="portal-dashboard-grid">
                {/* Left Col: Recent Tickets */}
                <div className="portal-card">
                  <div className="portal-card-header">
                    <h3>Recent Support Tickets</h3>
                    <button
                      className="btn-portal-secondary"
                      onClick={() => navigateTo("portal-tickets")}
                    >
                      View All ({portalDashboard?.metrics?.total_tickets ?? 0}) →
                    </button>
                  </div>

                  {portalDashboard?.recent_tickets?.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "30px 0", color: "#64748b" }}>
                      <p>No support tickets yet.</p>
                      <button
                        className="btn-portal-primary"
                        onClick={() => navigateTo("portal-new")}
                      >
                        Create Your First Ticket
                      </button>
                    </div>
                  ) : (
                    <div className="portal-table-container">
                      <table className="portal-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>Subject</th>
                            <th>Priority</th>
                            <th>Status</th>
                            <th>SLA</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {portalDashboard?.recent_tickets?.map((t) => (
                            <tr key={t.id}>
                              <td><strong>#{t.id}</strong></td>
                              <td>
                                <div className="portal-table-ticket-title">{t.title}</div>
                                <div className="portal-table-ticket-cat">{t.category} • {t.assigned_team}</div>
                              </td>
                              <td>
                                <span className={`priority-tag ${t.priority}`}>
                                  {t.priority?.toUpperCase()}
                                </span>
                              </td>
                              <td>
                                <span className={`status-pill ${t.status}`}>
                                  {t.status?.replace("_", " ")}
                                </span>
                              </td>
                              <td>{renderSlaBadge(t.sla_status)}</td>
                              <td>
                                <button
                                  className="portal-btn-view"
                                  onClick={() => loadPortalTicketDetail(t.id, activeCustomer)}
                                >
                                  View →
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Right Col: Recent Activity */}
                <div className="portal-card">
                  <div className="portal-card-header">
                    <h3>Recent Activity</h3>
                  </div>
                  {portalDashboard?.recent_activity?.length === 0 ? (
                    <p style={{ color: "#64748b", fontSize: "13px" }}>No recent activity.</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {portalDashboard?.recent_activity?.map((act) => (
                        <div
                          key={act.id}
                          style={{
                            padding: "10px 12px",
                            background: "#f8fafc",
                            borderRadius: "6px",
                            border: "1px solid #f1f5f9",
                            fontSize: "12.5px"
                          }}
                        >
                          <div style={{ fontWeight: 700, color: "#0f172a", marginBottom: "2px" }}>
                            {act.icon} {act.title}
                          </div>
                          <div style={{ color: "#475569", lineHeight: "1.4" }}>{act.description}</div>
                          <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "4px" }}>
                            {act.created_at ? new Date(act.created_at).toLocaleString() : ""}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          ) : currentPage === "portal-tickets" ? (
            <section className="portal-tickets-view">
              <div className="portal-header-banner">
                <div>
                  <h2>My Support Tickets</h2>
                  <p>Review and filter tickets for {activeCustomer?.company}</p>
                </div>
                <button
                  className="btn-portal-primary"
                  onClick={() => navigateTo("portal-new")}
                >
                  ➕ New Ticket
                </button>
              </div>

              {/* Filter Bar */}
              <div className="portal-filter-bar">
                <input
                  type="text"
                  className="portal-search-input"
                  placeholder="Search by ticket ID, subject, or description..."
                  value={portalSearch}
                  onChange={(e) => setPortalSearch(e.target.value)}
                />
                <select
                  className="portal-filter-select"
                  value={portalStatusFilter}
                  onChange={(e) => setPortalStatusFilter(e.target.value)}
                >
                  <option value="all">All Statuses</option>
                  <option value="open">Open Only (New / In Progress)</option>
                  <option value="new">New</option>
                  <option value="in_progress">In Progress</option>
                  <option value="awaiting_customer">Awaiting Customer</option>
                  <option value="resolved">Resolved</option>
                </select>
                <select
                  className="portal-filter-select"
                  value={portalPriorityFilter}
                  onChange={(e) => setPortalPriorityFilter(e.target.value)}
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select
                  className="portal-filter-select"
                  value={portalCategoryFilter}
                  onChange={(e) => setPortalCategoryFilter(e.target.value)}
                >
                  <option value="all">All Categories</option>
                  <option value="Network">Network</option>
                  <option value="M365">M365</option>
                  <option value="Security">Security</option>
                  <option value="Endpoint">Endpoint</option>
                  <option value="Backup">Backup</option>
                  <option value="Application Support">Application Support</option>
                  <option value="Service Desk">Service Desk</option>
                </select>
                <select
                  className="portal-filter-select"
                  value={portalSlaFilter}
                  onChange={(e) => setPortalSlaFilter(e.target.value)}
                >
                  <option value="all">All SLA States</option>
                  <option value="on_track">On Track</option>
                  <option value="at_risk">At Risk</option>
                  <option value="breached">Breached</option>
                  <option value="met">Met</option>
                </select>
              </div>

              {/* Tickets Table */}
              <div className="portal-card">
                {portalTicketsLoading ? (
                  <p style={{ textAlign: "center", padding: "20px" }}>Loading tickets...</p>
                ) : portalTickets.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "40px 0", color: "#64748b" }}>
                    <p>No tickets match your filters.</p>
                  </div>
                ) : (
                  <div className="portal-table-container">
                    <table className="portal-table">
                      <thead>
                        <tr>
                          <th>Ticket ID</th>
                          <th>Subject & Category</th>
                          <th>Priority</th>
                          <th>Team</th>
                          <th>Status</th>
                          <th>SLA Status</th>
                          <th>Created Date</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {portalTickets.map((t) => (
                          <tr key={t.id}>
                            <td><strong>#{t.id}</strong></td>
                            <td>
                              <div className="portal-table-ticket-title">{t.title}</div>
                              <div className="portal-table-ticket-cat">{t.category}</div>
                            </td>
                            <td>
                              <span className={`priority-tag ${t.priority}`}>
                                {t.priority?.toUpperCase()}
                              </span>
                            </td>
                            <td>{t.assigned_team}</td>
                            <td>
                              <span className={`status-pill ${t.status}`}>
                                {t.status?.replace("_", " ")}
                              </span>
                            </td>
                            <td>{renderSlaBadge(t.sla_status)}</td>
                            <td style={{ fontSize: "12px", color: "#64748b" }}>
                              {t.created_at ? new Date(t.created_at).toLocaleDateString() : "N/A"}
                            </td>
                            <td>
                              <button
                                className="portal-btn-view"
                                onClick={() => loadPortalTicketDetail(t.id, activeCustomer)}
                              >
                                View Ticket →
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          ) : currentPage === "portal-new" ? (
            <section className="portal-new-ticket-view">
              <div className="portal-card" style={{ maxWidth: "760px", margin: "0 auto" }}>
                <div className="portal-card-header">
                  <div>
                    <h3 style={{ fontSize: "18px" }}>➕ Submit a Support Request</h3>
                    <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#64748b" }}>
                      Your request will be classified by our automated routing engine and assigned to the specialized MSP team.
                    </p>
                  </div>
                </div>

                <form onSubmit={handlePortalCreateTicket} style={{ marginTop: "16px" }}>
                  <div className="portal-form-group">
                    <label>Subject / Issue Title *</label>
                    <input
                      type="text"
                      placeholder="e.g., Office VPN gateway not responding for remote team"
                      value={portalNewTitle}
                      onChange={(e) => {
                        const val = e.target.value;
                        setPortalNewTitle(val);
                        handlePortalKbSuggest(val, portalNewCategory);
                      }}
                      required
                    />
                  </div>

                  {/* Live Ticket Deflection Callout */}
                  {portalKbSuggestions.length > 0 && (
                    <div className="kb-deflection-banner">
                      <div className="kb-deflection-title-row">
                        <span className="kb-deflection-icon">💡</span>
                        <div>
                          <strong style={{ color: "#0f172a", fontSize: "14px" }}>Recommended Self-Service Solutions:</strong>
                          <p style={{ margin: "2px 0 0", fontSize: "12px", color: "#64748b" }}>
                            Save time! Check these step-by-step guides before submitting your ticket:
                          </p>
                        </div>
                      </div>
                      <div className="kb-deflection-items">
                        {portalKbSuggestions.map((sug) => (
                          <div
                            key={sug.id}
                            className="kb-deflection-item"
                            onClick={() => {
                              setPreviewingSuggestedArticle(sug);
                              loadPortalArticleDetail(sug.id);
                            }}
                          >
                            <div className="kb-deflection-item-info">
                              <span className="kb-deflection-badge">{sug.category_name}</span>
                              <span className="kb-deflection-item-title">{sug.title}</span>
                            </div>
                            <button
                              type="button"
                              className="kb-deflection-view-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewingSuggestedArticle(sug);
                                loadPortalArticleDetail(sug.id);
                              }}
                            >
                              Read Solution →
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="portal-form-grid">
                    <div className="portal-form-group">
                      <label>Category</label>
                      <select
                        value={portalNewCategory}
                        onChange={(e) => setPortalNewCategory(e.target.value)}
                      >
                        <option value="Network">Network Infrastructure</option>
                        <option value="M365">Microsoft 365 / Cloud</option>
                        <option value="Security">Security & Access</option>
                        <option value="Endpoint">Workstation / Endpoint</option>
                        <option value="Backup">Backup & Recovery</option>
                        <option value="Application Support">Business Applications</option>
                        <option value="Service Desk">General Service Desk</option>
                      </select>
                    </div>

                    <div className="portal-form-group">
                      <label>Priority</label>
                      <select
                        value={portalNewPriority}
                        onChange={(e) => setPortalNewPriority(e.target.value)}
                      >
                        <option value="low">Low (General Inquiry - 4h response / 24h resolution)</option>
                        <option value="medium">Medium (Standard Issue - 1h response / 8h resolution)</option>
                        <option value="high">High (Major Work Impact - 30m response / 4h resolution)</option>
                        <option value="critical">Critical (Complete Outage - 15m response / 2h resolution)</option>
                      </select>
                    </div>
                  </div>

                  <div className="portal-form-group">
                    <label>Detailed Description *</label>
                    <textarea
                      rows={6}
                      placeholder="Please explain the issue, affected users, error messages, and steps already taken..."
                      value={portalNewDescription}
                      onChange={(e) => setPortalNewDescription(e.target.value)}
                      required
                    />
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
                    <button
                      type="button"
                      className="btn-portal-secondary"
                      onClick={() => navigateTo("portal-dashboard")}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn-portal-primary"
                      disabled={portalSubmitting}
                    >
                      {portalSubmitting ? "Submitting..." : "🚀 Submit Request"}
                    </button>
                  </div>
                </form>
              </div>
            </section>
          ) : currentPage === "portal-notifications" ? (
            <section className="portal-notifications-view">
              <div className="portal-card" style={{ maxWidth: "840px", margin: "0 auto" }}>
                <div className="portal-card-header">
                  <div>
                    <h3 style={{ fontSize: "18px" }}>🔔 Notifications ({portalNotifications.length})</h3>
                    <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#64748b" }}>
                      Updates, status changes, and SLA targets for your support tickets.
                    </p>
                  </div>
                  {portalUnreadCount > 0 && (
                    <button
                      className="btn-portal-secondary"
                      onClick={handlePortalMarkAllNotificationsRead}
                    >
                      Mark All as Read
                    </button>
                  )}
                </div>

                {portalNotifications.length === 0 ? (
                  <p style={{ color: "#64748b", textAlign: "center", padding: "30px 0" }}>
                    No notifications to display.
                  </p>
                ) : (
                  <div style={{ marginTop: "14px" }}>
                    {portalNotifications.map((n) => (
                      <div
                        key={n.id}
                        className={`portal-notif-item ${!n.is_read ? "unread" : ""}`}
                      >
                        <div>
                          <div className="portal-notif-title">
                            {!n.is_read && <span style={{ color: "#2563eb", marginRight: "6px" }}>●</span>}
                            {n.title}
                          </div>
                          <div className="portal-notif-msg">{n.message}</div>
                          <div className="portal-notif-meta">
                            {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                          </div>
                        </div>
                        {!n.is_read && (
                          <button
                            className="portal-btn-view"
                            onClick={() => handlePortalMarkNotificationRead(n.id)}
                            style={{ marginLeft: "12px", whiteSpace: "nowrap" }}
                          >
                            Mark Read
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          ) : currentPage === "portal-profile" ? (
            <section className="portal-profile-view">
              <div className="portal-card" style={{ maxWidth: "680px", margin: "0 auto" }}>
                <div className="portal-card-header">
                  <h3 style={{ fontSize: "18px" }}>👤 Customer Account Profile</h3>
                </div>

                <form onSubmit={handlePortalUpdateProfile} style={{ marginTop: "16px" }}>
                  <div className="portal-form-group">
                    <label>Full Name</label>
                    <input
                      type="text"
                      value={portalProfileName}
                      onChange={(e) => setPortalProfileName(e.target.value)}
                      required
                    />
                  </div>

                  <div className="portal-form-group">
                    <label>Email Address (Account ID)</label>
                    <input
                      type="email"
                      value={portalProfile?.email || ""}
                      disabled
                      style={{ background: "#f1f5f9", cursor: "not-allowed" }}
                    />
                  </div>

                  <div className="portal-form-group">
                    <label>Company / Organization</label>
                    <input
                      type="text"
                      value={portalProfileCompany}
                      onChange={(e) => setPortalProfileCompany(e.target.value)}
                      required
                    />
                  </div>

                  <div className="portal-form-group">
                    <label>Phone Number</label>
                    <input
                      type="tel"
                      placeholder="+1 555-0100"
                      value={portalProfilePhone}
                      onChange={(e) => setPortalProfilePhone(e.target.value)}
                    />
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
                    <button
                      type="submit"
                      className="btn-portal-primary"
                      disabled={portalSavingProfile}
                    >
                      {portalSavingProfile ? "Saving..." : "Save Profile Changes"}
                    </button>
                  </div>
                </form>
              </div>
            </section>
          ) : currentPage === "portal-reports" ? (
            <section className="portal-reports-container">
              <div className="portal-reports-hero">
                <div className="portal-hero-text">
                  <h2>SLA &amp; Service Delivery Reports</h2>
                  <p>Executive service performance and compliance auditing for <strong>{portalReportsSummary?.organization_name || activeCustomer?.company || "Your Organization"}</strong></p>
                </div>
                <div className="portal-hero-actions">
                  <button
                    className="btn-portal-primary"
                    onClick={() => downloadReportFile("pdf", true)}
                    disabled={portalReportsLoading}
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                  >
                    <span>📄</span> Download Company SLA Report (PDF)
                  </button>
                  <button
                    className="btn-portal-secondary"
                    onClick={() => downloadReportFile("csv", true)}
                    disabled={portalReportsLoading}
                    style={{ display: "flex", alignItems: "center", gap: "8px" }}
                  >
                    <span>📊</span> Export Ticket Data (CSV)
                  </button>
                </div>
              </div>

              {/* Date & Status Filter Bar */}
              <div className="portal-filter-bar" style={{ marginTop: "16px", marginBottom: "20px" }}>
                <div className="portal-quick-chips">
                  {[
                    { id: "all", label: "All Time" },
                    { id: "7d", label: "Last 7 Days" },
                    { id: "30d", label: "Last 30 Days" },
                    { id: "this_month", label: "This Month" },
                  ].map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`portal-chip ${portalReportFilters.quickRange === c.id ? "active" : ""}`}
                      onClick={() => applyQuickDateRange(c.id, true)}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>

                <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    type="date"
                    className="portal-input"
                    value={portalReportFilters.startDate}
                    onChange={(e) => {
                      const updated = { ...portalReportFilters, startDate: e.target.value, quickRange: "custom" };
                      setPortalReportFilters(updated);
                      loadPortalReportsData(updated);
                    }}
                  />
                  <span style={{ color: "#94a3b8" }}>to</span>
                  <input
                    type="date"
                    className="portal-input"
                    value={portalReportFilters.endDate}
                    onChange={(e) => {
                      const updated = { ...portalReportFilters, endDate: e.target.value, quickRange: "custom" };
                      setPortalReportFilters(updated);
                      loadPortalReportsData(updated);
                    }}
                  />
                  <select
                    className="portal-select"
                    value={portalReportFilters.status}
                    onChange={(e) => {
                      const updated = { ...portalReportFilters, status: e.target.value };
                      setPortalReportFilters(updated);
                      loadPortalReportsData(updated);
                    }}
                  >
                    <option value="">All Statuses</option>
                    <option value="new">New</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </div>
              </div>

              {portalReportsLoading ? (
                <div className="portal-loading-card">
                  <div className="spinner"></div>
                  <p>Loading SLA performance summary...</p>
                </div>
              ) : portalReportsSummary ? (
                <>
                  {/* KPI Cards */}
                  <div className="portal-kpi-grid">
                    <div className="portal-kpi-card">
                      <div className="portal-kpi-icon">🎫</div>
                      <div className="portal-kpi-info">
                        <span className="portal-kpi-label">Total Support Requests</span>
                        <strong className="portal-kpi-value">{portalReportsSummary.summary?.total_tickets || 0}</strong>
                        <small className="portal-kpi-sub">Total company tickets</small>
                      </div>
                    </div>

                    <div className="portal-kpi-card highlight-portal-card">
                      <div className="portal-kpi-icon">🛡</div>
                      <div className="portal-kpi-info">
                        <span className="portal-kpi-label">SLA Compliance Rate</span>
                        <strong className="portal-kpi-value text-success">{portalReportsSummary.summary?.sla_compliance_rate || 100}%</strong>
                        <small className="portal-kpi-sub">Contractual SLA standard</small>
                      </div>
                    </div>

                    <div className="portal-kpi-card">
                      <div className="portal-kpi-icon">⚡</div>
                      <div className="portal-kpi-info">
                        <span className="portal-kpi-label">Avg First Response</span>
                        <strong className="portal-kpi-value">{portalReportsSummary.summary?.avg_response_time_label || "N/A"}</strong>
                        <small className="portal-kpi-sub">Engineer response speed</small>
                      </div>
                    </div>

                    <div className="portal-kpi-card">
                      <div className="portal-kpi-icon">✓</div>
                      <div className="portal-kpi-info">
                        <span className="portal-kpi-label">Avg Time to Resolve</span>
                        <strong className="portal-kpi-value">{portalReportsSummary.summary?.avg_resolution_time_label || "N/A"}</strong>
                        <small className="portal-kpi-sub">Completed resolutions</small>
                      </div>
                    </div>
                  </div>

                  {/* SLA Performance Matrix */}
                  <div className="portal-card" style={{ marginTop: "20px" }}>
                    <div className="portal-card-header">
                      <h3>SLA Compliance by Priority</h3>
                      <span style={{ fontSize: "12px", color: "#64748b" }}>Active SLA Guarantees</span>
                    </div>
                    <div className="reports-table-wrapper">
                      <table className="reports-data-table">
                        <thead>
                          <tr>
                            <th>Priority</th>
                            <th>Target Response</th>
                            <th>Target Resolution</th>
                            <th>On Track</th>
                            <th>At Risk</th>
                            <th>Breached</th>
                            <th>Met</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[
                            { key: "critical", label: "Critical", resp: "15 minutes", res: "2 hours", badge: "priority critical" },
                            { key: "high", label: "High", resp: "30 minutes", res: "4 hours", badge: "priority high" },
                            { key: "medium", label: "Medium", resp: "1 hour", res: "8 hours", badge: "priority medium" },
                            { key: "low", label: "Low", resp: "4 hours", res: "24 hours", badge: "priority low" },
                          ].map((p) => {
                            const row = portalReportsSummary.summary?.sla_by_priority?.[p.key] || { on_track: 0, at_risk: 0, breached: 0, met: 0 };
                            return (
                              <tr key={p.key}>
                                <td><span className={p.badge}>{p.label.toUpperCase()}</span></td>
                                <td><small>{p.resp}</small></td>
                                <td><small>{p.res}</small></td>
                                <td><span className="badge-pill on_track">{row.on_track}</span></td>
                                <td><span className="badge-pill at_risk">{row.at_risk}</span></td>
                                <td><span className={`badge-pill breached ${row.breached > 0 ? 'highlight-breach' : ''}`}>{row.breached}</span></td>
                                <td><span className="badge-pill met">{row.met}</span></td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Category Breakdown */}
                  <div className="portal-card" style={{ marginTop: "20px" }}>
                    <div className="portal-card-header">
                      <h3>Issue Categories Breakdown</h3>
                    </div>
                    <div className="reports-breakdown-list">
                      {Object.entries(portalReportsSummary.summary?.tickets_by_category || {}).map(([cat, cnt]) => {
                        const pct = portalReportsSummary.summary?.total_tickets > 0
                          ? Math.round((cnt / portalReportsSummary.summary.total_tickets) * 100)
                          : 0;
                        return (
                          <div className="breakdown-row" key={cat}>
                            <div className="breakdown-info">
                              <span className="breakdown-name">{cat}</span>
                              <span className="breakdown-count">{cnt} tickets ({pct}%)</span>
                            </div>
                            <div className="breakdown-bar-track">
                              <div className="breakdown-bar-fill" style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </>
              ) : null}
            </section>
          ) : currentPage === "portal-kb" ? (
            <section className="portal-kb-container">
              {portalKbActiveArticle ? (
                <div className="portal-kb-reader-card">
                  <div className="portal-kb-reader-header">
                    <button
                      type="button"
                      className="portal-kb-back-btn"
                      onClick={() => setPortalKbActiveArticle(null)}
                    >
                      ← Back to All Guides
                    </button>
                    <div className="portal-kb-breadcrumbs">
                      <span>Knowledge Base</span>
                      <span>›</span>
                      <span>{portalKbActiveArticle.category_name}</span>
                      <span>›</span>
                      <span className="current-crumb">{portalKbActiveArticle.title}</span>
                    </div>
                  </div>

                  <div className="portal-kb-article-header">
                    <div className="portal-kb-meta-badges">
                      <span className="portal-kb-cat-pill">
                        {portalKbActiveArticle.category_icon === "cloud" ? "☁️" :
                         portalKbActiveArticle.category_icon === "network" ? "🌐" :
                         portalKbActiveArticle.category_icon === "shield" ? "🛡️" :
                         portalKbActiveArticle.category_icon === "laptop" ? "💻" :
                         portalKbActiveArticle.category_icon === "database" ? "💾" : "📖"} {portalKbActiveArticle.category_name}
                      </span>
                      <span className="portal-kb-views-pill">👁 {portalKbActiveArticle.view_count} views</span>
                      <span className="portal-kb-helpful-pill">⭐ {portalKbActiveArticle.helpfulness_score}% helpful</span>
                    </div>
                    <h1 className="portal-kb-article-title">{portalKbActiveArticle.title}</h1>
                    {portalKbActiveArticle.summary && (
                      <p className="portal-kb-article-summary">{portalKbActiveArticle.summary}</p>
                    )}
                    <div className="portal-kb-author-row">
                      <span>Published by <strong>{portalKbActiveArticle.author_name || "MSP Engineering"}</strong></span>
                      <span>•</span>
                      <span>Updated {portalKbActiveArticle.updated_at ? new Date(portalKbActiveArticle.updated_at).toLocaleDateString() : "Recently"}</span>
                    </div>
                  </div>

                  <div className="portal-kb-article-body">
                    {renderSimpleMarkdown(portalKbActiveArticle.content)}
                  </div>

                  {/* Feedback Section */}
                  <div className="portal-kb-feedback-widget">
                    {portalKbFeedbackGiven[portalKbActiveArticle.id] !== undefined ? (
                      <div className="feedback-thank-you">
                        🎉 <strong>Thank you for your feedback!</strong> Your rating helps improve our documentation.
                      </div>
                    ) : (
                      <>
                        <h4>Was this guide helpful?</h4>
                        <p>Let us know if this resolved your question or issue:</p>
                        <div className="feedback-btn-group">
                          <button
                            type="button"
                            className="btn-feedback btn-feedback-yes"
                            onClick={() => handlePortalSubmitFeedback(portalKbActiveArticle.id, true)}
                            disabled={portalKbFeedbackSubmitting}
                          >
                            👍 Yes, this helped!
                          </button>
                          <button
                            type="button"
                            className="btn-feedback btn-feedback-no"
                            onClick={() => handlePortalSubmitFeedback(portalKbActiveArticle.id, false)}
                            disabled={portalKbFeedbackSubmitting}
                          >
                            👎 No, I need more help
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Still need help CTA */}
                  <div className="portal-kb-need-help-card">
                    <div>
                      <h4 style={{ margin: "0 0 4px", fontSize: "16px", color: "#0f172a" }}>Still having trouble?</h4>
                      <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>Our 24/7 dedicated engineering support desk is ready to assist your team.</p>
                    </div>
                    <button
                      type="button"
                      className="btn-portal-primary"
                      onClick={() => navigateTo("portal-new")}
                    >
                      🚀 Open a Support Ticket
                    </button>
                  </div>
                </div>
              ) : (
                <div className="portal-kb-browse-view">
                  {/* Hero Banner */}
                  <div className="portal-kb-hero">
                    <h2>📚 Knowledge Base &amp; Self-Service Help Center</h2>
                    <p>Find step-by-step guides, VPN connection tutorials, email setup, and security SOPs</p>
                    
                    <div className="portal-kb-search-bar">
                      <span className="search-icon">🔍</span>
                      <input
                        type="text"
                        placeholder="Search for guides, error codes, VPN setup, email sync..."
                        value={portalKbSearch}
                        onChange={(e) => {
                          const q = e.target.value;
                          setPortalKbSearch(q);
                          loadPortalKb(q, portalKbCategory);
                        }}
                      />
                      {portalKbSearch && (
                        <button
                          type="button"
                          className="clear-search-btn"
                          onClick={() => {
                            setPortalKbSearch("");
                            loadPortalKb("", portalKbCategory);
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Category Filter Chips */}
                  <div className="portal-kb-category-chips">
                    <button
                      type="button"
                      className={`portal-kb-chip ${portalKbCategory === "all" ? "active" : ""}`}
                      onClick={() => {
                        setPortalKbCategory("all");
                        loadPortalKb(portalKbSearch, "all");
                      }}
                    >
                      🌟 All Categories
                    </button>
                    {portalKbCategories.map((cat) => (
                      <button
                        key={cat.id}
                        type="button"
                        className={`portal-kb-chip ${portalKbCategory === cat.slug ? "active" : ""}`}
                        onClick={() => {
                          setPortalKbCategory(cat.slug);
                          loadPortalKb(portalKbSearch, cat.slug);
                        }}
                      >
                        {cat.icon === "cloud" ? "☁️" :
                         cat.icon === "network" ? "🌐" :
                         cat.icon === "shield" ? "🛡️" :
                         cat.icon === "laptop" ? "💻" :
                         cat.icon === "database" ? "💾" : "📖"} {cat.name} ({cat.article_count})
                      </button>
                    ))}
                  </div>

                  {/* Articles Grid */}
                  <div className="portal-kb-grid-header">
                    <h3>
                      {portalKbCategory !== "all"
                        ? portalKbCategories.find(c => c.slug === portalKbCategory)?.name || "Articles"
                        : "Featured Help Guides"}{" "}
                      <span className="count-tag">{portalKbArticles.length} guides</span>
                    </h3>
                  </div>

                  {portalKbLoading ? (
                    <div className="portal-loading-state">
                      <div className="portal-spinner" />
                      <p>Loading knowledge base guides...</p>
                    </div>
                  ) : portalKbArticles.length === 0 ? (
                    <div className="portal-empty-card" style={{ padding: "48px 24px", textAlign: "center" }}>
                      <div style={{ fontSize: "40px", marginBottom: "12px" }}>🔍</div>
                      <h4 style={{ margin: "0 0 6px", color: "#0f172a" }}>No help guides found</h4>
                      <p style={{ color: "#64748b", margin: "0 0 16px" }}>
                        Try searching with different keywords or open a support request.
                      </p>
                      <button
                        type="button"
                        className="btn-portal-primary"
                        onClick={() => navigateTo("portal-new")}
                      >
                        ➕ Submit a Support Request
                      </button>
                    </div>
                  ) : (
                    <div className="portal-kb-cards-grid">
                      {portalKbArticles.map((art) => (
                        <div
                          key={art.id}
                          className="portal-kb-card"
                          onClick={() => loadPortalArticleDetail(art.id)}
                        >
                          <div className="portal-kb-card-top">
                            <span className="portal-kb-card-cat">
                              {art.category_icon === "cloud" ? "☁️" :
                               art.category_icon === "network" ? "🌐" :
                               art.category_icon === "shield" ? "🛡️" :
                               art.category_icon === "laptop" ? "💻" :
                               art.category_icon === "database" ? "💾" : "📖"} {art.category_name}
                            </span>
                            <span className="portal-kb-rating-pill">⭐ {art.helpfulness_score}%</span>
                          </div>
                          <h4 className="portal-kb-card-title">{art.title}</h4>
                          <p className="portal-kb-card-desc">{art.summary || "Click to read full troubleshooting steps and guide."}</p>
                          <div className="portal-kb-card-footer">
                            <span className="views-count">👁 {art.view_count} views</span>
                            <span className="read-more-link">Read Guide →</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          ) : null}

          {/* Customer Ticket Deflection Guide Preview Modal (Phase 9) */}
          {previewingSuggestedArticle && (
            <div
              className="kb-modal-overlay"
              onClick={() => {
                setPreviewingSuggestedArticle(null);
                setPortalKbActiveArticle(null);
              }}
              role="dialog"
              aria-modal="true"
              aria-labelledby="kb-preview-modal-title"
            >
              <div
                className="kb-modal-card"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header: Title, Category, Helpfulness %, View Count, Non-overlapping Close Button */}
                <div className="kb-modal-header">
                  <div className="kb-modal-header-main">
                    <div className="kb-modal-pretitle-row">
                      <span className="kb-modal-tag">💡 Self-Service Solution</span>
                      {portalKbActiveArticle && (
                        <div className="kb-modal-meta-badges">
                          <span className="kb-modal-meta-cat">
                            {portalKbActiveArticle.category_name}
                          </span>
                          <span className="kb-modal-meta-helpful">
                            ⭐ {portalKbActiveArticle.helpfulness_score}% helpful
                          </span>
                          <span className="kb-modal-meta-views">
                            👁 {portalKbActiveArticle.view_count} views
                          </span>
                        </div>
                      )}
                    </div>
                    <h2 id="kb-preview-modal-title" className="kb-modal-title">
                      {portalKbActiveArticle?.title || previewingSuggestedArticle.title}
                    </h2>
                  </div>

                  <button
                    type="button"
                    className="kb-modal-close-btn"
                    onClick={() => {
                      setPreviewingSuggestedArticle(null);
                      setPortalKbActiveArticle(null);
                    }}
                    title="Close solution preview"
                    aria-label="Close solution preview"
                  >
                    ✕
                  </button>
                </div>

                {/* Dedicated Scrollable Content Area */}
                <div className="kb-modal-scroll-body">
                  {portalKbActiveArticle ? (
                    <div className="kb-modal-article-container">
                      {portalKbActiveArticle.summary && (
                        <div className="kb-modal-summary-banner">
                          <span className="summary-icon">ℹ️</span>
                          <p className="summary-text">{portalKbActiveArticle.summary}</p>
                        </div>
                      )}

                      <div className="kb-modal-markdown-content">
                        {renderSimpleMarkdown(portalKbActiveArticle.content)}
                      </div>
                    </div>
                  ) : (
                    <div className="kb-modal-loading-state">
                      <div className="portal-spinner" />
                      <p>Loading full step-by-step solution...</p>
                    </div>
                  )}
                </div>

                {/* Fixed Footer: Balanced Action Buttons */}
                <div className="kb-modal-footer">
                  <button
                    type="button"
                    className="kb-modal-btn-secondary"
                    onClick={() => {
                      setPreviewingSuggestedArticle(null);
                      setPortalKbActiveArticle(null);
                    }}
                  >
                    ← Continue Submitting Ticket
                  </button>

                  <button
                    type="button"
                    className="kb-modal-btn-primary"
                    onClick={() => {
                      const artId = portalKbActiveArticle?.id || previewingSuggestedArticle.id;
                      handlePortalSubmitFeedback(artId, true);
                      setPreviewingSuggestedArticle(null);
                      setPortalKbActiveArticle(null);
                      setPortalNewTitle("");
                      setPortalNewDescription("");
                      setPortalKbSuggestions([]);
                      alert("Glad this guide solved your issue! Your support request has been dismissed.");
                      navigateTo("portal-dashboard");
                    }}
                  >
                    ✅ This Solved My Issue — Cancel Ticket
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      {/* Toast Alert Notifications (Phase 4) */}
      {auth?.token && auth?.user?.role !== "customer" && toasts.length > 0 && (
        <div className="toast-notifications-container" aria-live="polite">
          {toasts.map((toast) => (
            <div
              key={toast.toastId}
              className={`toast-alert toast-severity-${toast.severity}`}
              onClick={() => handleToastClick(toast)}
            >
              <div className="toast-icon">
                {toast.type === "ESCALATION" ? "🚨" :
                 toast.type === "SLA_BREACHED" ? "⏱️" :
                 toast.type === "SLA_AT_RISK" ? "⚠️" :
                 toast.type === "CUSTOMER_UPDATE" ? "💬" :
                 toast.severity === "critical" ? "🔴" :
                 toast.severity === "warning" ? "🟠" : "🔔"}
              </div>
              <div className="toast-content">
                <div className="toast-header-row">
                  {toast.ticketId && (
                    <span className="toast-ticket-badge">#{toast.ticketId}</span>
                  )}
                  <span className="toast-title">{toast.title}</span>
                </div>
                <p className="toast-message">{toast.message}</p>
              </div>
              <button
                className="toast-close-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  dismissToast(toast.toastId);
                }}
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          JACE <span>HAUS</span>
        </div>

        <nav>
          <div
            className={`nav-item ${currentPage === "dashboard" ? "active" : ""}`}
            onClick={() => navigateTo("dashboard")}
          >
            Dashboard
          </div>

          <div
            className={`nav-item ${currentPage === "workbench" ? "active" : ""}`}
            onClick={() => navigateTo("workbench")}
          >
            Workbench
            {openTicketsCount > 0 && (
              <span className="sidebar-badge">{openTicketsCount}</span>
            )}
          </div>

          <div
            className={`nav-item ${currentPage === "tickets" ? "active" : ""}`}
            onClick={() => navigateTo("tickets")}
          >
            Tickets
          </div>

          <div
            className={`nav-item ${currentPage === "knowledge-base" ? "active" : ""}`}
            onClick={() => navigateTo("knowledge-base")}
          >
            📚 Knowledge Base
          </div>

          {(isAdmin || isManager) && (
            <div
              className={`nav-item ${currentPage === "rules" ? "active" : ""}`}
              onClick={() => navigateTo("rules")}
            >
              Routing Rules
            </div>
          )}

          {(isAdmin || isManager) && (
            <div
              className={`nav-item ${currentPage === "teams" ? "active" : ""}`}
              onClick={() => navigateTo("teams")}
            >
              🛡 Team Management
            </div>
          )}

          {(isAdmin || isManager) && (
            <div
              className={`nav-item ${currentPage === "analytics" ? "active" : ""}`}
              onClick={() => navigateTo("analytics")}
            >
              Analytics
            </div>
          )}

          {(isAdmin || isManager) && (
            <div
              className={`nav-item ${currentPage === "reports" ? "active" : ""}`}
              onClick={() => navigateTo("reports")}
            >
              📊 Reports
            </div>
          )}

          {isAdmin && (
            <div
              className={`nav-item ${currentPage === "users" ? "active" : ""}`}
              onClick={() => navigateTo("users")}
            >
              👥 User Management
            </div>
          )}

          {isAdmin && (
            <div
              className="nav-item nav-item-portal"
              onClick={() => navigateTo("portal-dashboard")}
              title="Switch to Client / Customer Portal"
            >
              🌐 Client Portal →
            </div>
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot"></span>
            System Online
          </div>
        </div>
      </aside>


      {/* Main */}
      <main className="main">

        <header className="header">
          <div>
            <h1>
              {currentPage === "dashboard"
                ? "Ticket Intelligence"
                : currentPage === "workbench"
                ? "Technician Workbench"
                : currentPage === "tickets"
                ? "Tickets"
                : currentPage === "rules"
                ? "Routing Rules"
                : currentPage === "teams"
                ? "Team Management"
                : currentPage === "users"
                ? "User Management"
                : currentPage === "reports"
                ? "Executive & Client SLA Reporting"
                : currentPage === "knowledge-base"
                ? "Knowledge Base & Runbooks"
                : "Analytics"}
            </h1>

            <p>
              {currentPage === "dashboard"
                ? "MSP automation & routing dashboard"
                : currentPage === "workbench"
                ? "Operational work queue, ticket triage, and SLA resolution workspace"
                : currentPage === "tickets"
                ? "All tickets processed by the system"
                : currentPage === "rules"
                ? "Deterministic rules used to automatically route tickets"
                : currentPage === "teams"
                ? "Configure operational teams, member assignments, operating business hours, and routing targets"
                : currentPage === "users"
                ? "Manage system user credentials, roles, and account statuses"
                : currentPage === "reports"
                ? "Executive KPI summaries, SLA performance tracking, and client-scoped QBR reporting"
                : currentPage === "knowledge-base"
                ? "Centralized repository for customer self-service guides, technician SOPs, and resolution templates"
                : "Ticket routing and operational analytics"}
            </p>
          </div>

          <div className="header-actions">
            {/* User Profile Badge */}
            {auth.user && (
              <div className="header-user-profile">
                <div className="header-user-avatar">
                  {auth.user.name?.charAt(0).toUpperCase() || "U"}
                </div>
                <div className="header-user-details">
                  <div className="header-user-name-row">
                    <span className="header-user-fullname">{auth.user.name}</span>
                    <span className={`user-role-badge role-${auth.user.role}`}>
                      {auth.user.role}
                    </span>
                  </div>
                  <span className="header-user-subtext">
                    {auth.user.team || auth.user.company || auth.user.email}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn-header-logout"
                  onClick={handleLogout}
                  title="Sign Out"
                >
                  Sign Out
                </button>
              </div>
            )}

            {/* Notification Bell & Dropdown */}
            <div className="notification-bell-wrapper">
              <button
                className={`notification-bell-btn ${showNotifications ? "active" : ""}`}
                onClick={() => {
                  const nextState = !showNotifications;
                  setShowNotifications(nextState);
                  if (nextState) {
                    loadNotifications();
                  }
                }}
                title="Notifications & Escalations"
              >
                <span className="bell-emoji">🔔</span>
                {unreadCount > 0 && (
                  <span className="bell-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
                )}
              </button>

              {showNotifications && (
                <div className="notification-dropdown-panel">
                  <div className="dropdown-header">
                    <div className="dropdown-title-group">
                      <h4>Notifications</h4>
                      {unreadCount > 0 && (
                        <span className="unread-count-pill">{unreadCount} unread</span>
                      )}
                    </div>

                    <div className="dropdown-header-btns">
                      {unreadCount > 0 && (
                        <button
                          className="mark-all-btn"
                          onClick={markAllNotificationsRead}
                        >
                          Mark all as read
                        </button>
                      )}
                      {["admin", "manager"].includes(auth?.user?.role) && (
                        <button
                          className="clear-read-btn"
                          onClick={clearReadNotifications}
                          title="Remove all read notifications from system"
                        >
                          Clear read
                        </button>
                      )}
                      <button
                        className="close-dropdown-btn"
                        onClick={() => setShowNotifications(false)}
                      >
                        ✕
                      </button>
                    </div>
                  </div>

                  {/* Role-Aware Scopes (Phase 3) */}
                  <div className="notification-scopes">
                    {auth?.user?.role !== "technician" && (
                      <button
                        className={`notif-scope-tab ${notifScope === "all" ? "active" : ""}`}
                        onClick={() => {
                          setNotifScope("all");
                          loadNotifications("all");
                        }}
                      >
                        🌐 All Alerts
                      </button>
                    )}
                    <button
                      className={`notif-scope-tab ${notifScope === "my_team" ? "active" : ""}`}
                      onClick={() => {
                        setNotifScope("my_team");
                        loadNotifications("my_team");
                      }}
                    >
                      👥 My Team
                    </button>
                    <button
                      className={`notif-scope-tab ${notifScope === "my_tickets" ? "active" : ""}`}
                      onClick={() => {
                        setNotifScope("my_tickets");
                        loadNotifications("my_tickets");
                      }}
                    >
                      👤 My Queue
                    </button>
                  </div>

                  <div className="notification-filters">
                    <button
                      className={`notif-filter-tab ${notifFilter === "all" ? "active" : ""}`}
                      onClick={() => setNotifFilter("all")}
                    >
                      All ({notifications.length})
                    </button>
                    <button
                      className={`notif-filter-tab ${notifFilter === "unread" ? "active" : ""}`}
                      onClick={() => setNotifFilter("unread")}
                    >
                      Unread ({notifications.filter((n) => !n.is_read).length})
                    </button>
                    <button
                      className={`notif-filter-tab ${notifFilter === "escalation" ? "active" : ""}`}
                      onClick={() => setNotifFilter("escalation")}
                    >
                      Escalations ({notifications.filter((n) => n.type === "ESCALATION").length})
                    </button>
                    <button
                      className={`notif-filter-tab ${notifFilter === "sla" ? "active" : ""}`}
                      onClick={() => setNotifFilter("sla")}
                    >
                      SLA ({notifications.filter((n) => n.type === "SLA_AT_RISK" || n.type === "SLA_BREACHED").length})
                    </button>
                  </div>

                  <div className="notification-list-scroll">
                    {filteredNotifications.length === 0 ? (
                      <div className="notif-empty-state">
                        <span className="empty-icon">🔔</span>
                        <p>No notifications matching this filter</p>
                      </div>
                    ) : (
                      filteredNotifications.map((notif) => (
                        <div
                          key={notif.id}
                          className={`notif-card severity-${notif.severity} ${notif.is_read ? "is-read" : "is-unread"}`}
                          onClick={() => handleNotificationClick(notif)}
                        >
                          <div className="notif-type-icon">
                            {notif.type === "ESCALATION" ? "🚨" :
                             notif.type === "SLA_BREACHED" ? "🔴" :
                             notif.type === "SLA_AT_RISK" ? "⚠️" :
                             notif.type === "PRIORITY_CHANGED" ? "⚡" :
                             notif.type === "TICKET_ASSIGNED" ? "📌" : "ℹ️"}
                          </div>

                          <div className="notif-card-main">
                            <div className="notif-card-heading">
                              <span className="notif-card-title">{notif.title}</span>
                              {!notif.is_read && <span className="notif-unread-glow"></span>}
                            </div>

                            <p className="notif-card-body">{notif.message}</p>

                            <div className="notif-card-footer">
                              {notif.ticket_id && (
                                <span className="notif-ticket-badge">Ticket #{notif.ticket_id}</span>
                              )}
                              <span className={`notif-type-label label-${notif.type.toLowerCase()}`}>
                                {notif.type.replace(/_/g, " ")}
                              </span>
                              <span className="notif-timestamp">
                                {notif.created_at ? new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' }) : ""}
                              </span>
                            </div>
                          </div>

                          {!notif.is_read && (
                            <button
                              className="notif-check-btn"
                              title="Mark as read"
                              onClick={(e) => {
                                e.stopPropagation();
                                markNotificationRead(notif.id);
                              }}
                            >
                              ✓
                            </button>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {currentPage === "knowledge-base" ? (
              (isAdmin || isManager) && (
                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleOpenCreateKbCategory}
                  >
                    📁 Categories
                  </button>
                  <button
                    type="button"
                    className="new-ticket"
                    onClick={handleOpenCreateKbArticle}
                  >
                    + New Article
                  </button>
                </div>
              )
            ) : currentPage === "rules" ? (
              isAdmin && (
                <button
                  className="new-ticket"
                  onClick={() => {
                    setNewRule({
                      category: "",
                      team: "Service Desk",
                      priority: "medium",
                      keywords: "",
                      description: ""
                    });

                    setShowCreateRuleModal(true);
                  }}
                >
                  + New Rule
                </button>
              )
            ) : currentPage === "teams" ? (
              isAdmin && (
                <button
                  className="new-ticket"
                  onClick={() => setShowCreateTeamModal(true)}
                >
                  + New Team
                </button>
              )
            ) : currentPage === "users" ? (
              isAdmin && (
                <button
                  className="new-ticket"
                  onClick={() => setShowCreateUserModal(true)}
                >
                  + New User
                </button>
              )
            ) : (
              <button
                className="new-ticket"
                onClick={() => setShowForm(true)}
              >
                + New Ticket
              </button>
            )}
          </div>
        </header>

      {/* ========================================================================= */}
      {/* 403 UNAUTHORIZED ACCESS VIEW */}
      {/* ========================================================================= */}
      {isPageUnauthorized() && (
        <div className="unauthorized-view-wrapper">
          <div className="unauthorized-card">
            <div className="unauthorized-icon">🔒</div>
            <h2>403 — Unauthorized Access</h2>
            <p>
              Your account role (<strong>{(auth.user?.role || "").toUpperCase()}</strong>) does not have permission to access the <code>/{currentPage}</code> section.
            </p>
            <button
              className="btn-portal-primary"
              onClick={() => navigateTo(isTechnician ? "workbench" : "dashboard")}
            >
              Return to {isTechnician ? "Technician Workbench" : "Dashboard"}
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TEAM MANAGEMENT PAGE (ADMIN & MANAGER) (Phase 7) */}
      {/* ========================================================================= */}
      {!isPageUnauthorized() && currentPage === "teams" && !selectedTicket && (
        <section className="teams-management-view">
          <div className="teams-header-toolbar">
            <div>
              <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", margin: 0 }}>
                Operational Teams &amp; Business Hours
              </h2>
              <p style={{ fontSize: "13px", color: "#64748b", margin: "4px 0 0 0" }}>
                Configure team directory, lead assignments, active membership, operating schedules, and workloads
              </p>
            </div>
            {isAdmin && (
              <button
                className="btn-portal-primary"
                onClick={() => setShowCreateTeamModal(true)}
              >
                ➕ Create New Team
              </button>
            )}
          </div>

          <div className="teams-stats-strip">
            <div className="team-stat-card">
              <div className="team-stat-icon">🛡️</div>
              <div className="team-stat-info">
                <div className="stat-num">{teamsList.length}</div>
                <div className="stat-lbl">Total Operational Teams</div>
              </div>
            </div>
            <div className="team-stat-card">
              <div className="team-stat-icon">✅</div>
              <div className="team-stat-info">
                <div className="stat-num">{teamsList.filter((t) => t.is_active).length}</div>
                <div className="stat-lbl">Active Routing Targets</div>
              </div>
            </div>
            <div className="team-stat-card">
              <div className="team-stat-icon">👑</div>
              <div className="team-stat-info">
                <div className="stat-num">{teamsList.filter((t) => t.team_lead_id).length}</div>
                <div className="stat-lbl">Team Leads Assigned</div>
              </div>
            </div>
            <div className="team-stat-card">
              <div className="team-stat-icon">⚡</div>
              <div className="team-stat-info">
                <div className="stat-num">{teamsList.reduce((acc, t) => acc + (t.active_workload || 0), 0)}</div>
                <div className="stat-lbl">Active Open Tickets</div>
              </div>
            </div>
          </div>

          <div className="teams-filter-toolbar">
            <div className="teams-search-box">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                placeholder="Search teams by name or description..."
                value={teamSearch}
                onChange={(e) => setTeamSearch(e.target.value)}
                className="teams-search-input"
              />
            </div>
            <div className="teams-status-filter">
              <label>Status:</label>
              <select
                value={teamStatusFilter}
                onChange={(e) => setTeamStatusFilter(e.target.value)}
                className="teams-select"
              >
                <option value="all">All Teams ({teamsList.length})</option>
                <option value="active">Active Only ({teamsList.filter((t) => t.is_active).length})</option>
                <option value="inactive">Inactive ({teamsList.filter((t) => !t.is_active).length})</option>
              </select>
            </div>
          </div>

          {teamsLoading ? (
            <div className="teams-loading-box">Loading operational teams...</div>
          ) : (
            <div className="teams-cards-grid">
              {teamsList
                .filter((t) => {
                  const matchSearch =
                    !teamSearch ||
                    t.name.toLowerCase().includes(teamSearch.toLowerCase()) ||
                    (t.description || "").toLowerCase().includes(teamSearch.toLowerCase());
                  const matchStatus =
                    teamStatusFilter === "all" ||
                    (teamStatusFilter === "active" ? t.is_active : !t.is_active);
                  return matchSearch && matchStatus;
                })
                .map((t) => (
                  <div key={t.id} className={`team-card ${t.is_active ? "active-team" : "inactive-team"}`}>
                    <div className="team-card-header">
                      <div>
                        <div className="team-card-title-row">
                          <h3 className="team-card-name">{t.name}</h3>
                          <span className={`team-status-badge ${t.is_active ? "status-active" : "status-inactive"}`}>
                            {t.is_active ? "Active" : "Inactive"}
                          </span>
                        </div>
                        <span className="team-card-slug">/{t.slug}</span>
                      </div>
                      <div className="team-workload-chip" title="Active Tickets (New / In Progress)">
                        ⚡ <strong>{t.active_workload || 0}</strong> tickets
                      </div>
                    </div>

                    <p className="team-card-description">{t.description || "No description provided."}</p>

                    <div className="team-schedule-box">
                      <div className="schedule-row">
                        <span className="schedule-icon">🕒</span>
                        <span className="schedule-time">
                          {t.business_hours_start || "08:00"} - {t.business_hours_end || "18:00"} ({t.timezone || "America/New_York"})
                        </span>
                      </div>
                      <div className="schedule-row">
                        <span className="schedule-icon">📅</span>
                        <span className="schedule-days">{t.work_days || "MON,TUE,WED,THU,FRI"}</span>
                      </div>
                    </div>

                    <div className="team-lead-box">
                      <span className="lead-label">Team Lead</span>
                      <div className="lead-info">
                        <span className="lead-icon">👑</span>
                        <div>
                          <strong className="lead-name">{t.team_lead_name || "Unassigned"}</strong>
                          {t.team_lead_email && <small className="lead-email"> • {t.team_lead_email}</small>}
                        </div>
                      </div>
                    </div>

                    <div className="team-members-box">
                      <div className="members-header-row">
                        <span className="members-label">Members ({t.member_count || 0})</span>
                        {(isAdmin || isManager) && (
                          <button
                            type="button"
                            className="btn-manage-members-link"
                            onClick={() => {
                              setManagingMembersTeam(t);
                              setSelectedMemberIds((t.members || []).map((m) => m.id));
                            }}
                          >
                            Manage Members
                          </button>
                        )}
                      </div>
                      <div className="members-chips-list">
                        {(t.members || []).length === 0 ? (
                          <span className="no-members-text">No technicians assigned</span>
                        ) : (
                          (t.members || []).map((m) => (
                            <span key={m.id} className={`member-chip ${m.is_lead ? "lead-chip" : ""}`}>
                              {m.is_lead && "👑 "}
                              {m.name}
                            </span>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="team-card-actions">
                      {(isAdmin || isManager) && (
                        <button
                          type="button"
                          className="btn-team-action btn-team-edit"
                          onClick={() => setEditingTeam({ ...t })}
                        >
                          ✏️ Edit
                        </button>
                      )}

                      {isAdmin && (
                        <button
                          type="button"
                          className={`btn-team-action ${t.is_active ? "btn-team-deactivate" : "btn-team-activate"}`}
                          onClick={() => handleToggleTeamStatus(t)}
                        >
                          {t.is_active ? "Deactivate" : "Activate"}
                        </button>
                      )}

                      {isAdmin && (
                        <button
                          type="button"
                          className="btn-team-action btn-team-delete"
                          onClick={() => handleDeleteTeam(t)}
                        >
                          🗑 Delete
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>
      )}

      {/* ========================================================================= */}
      {/* ADMIN USER MANAGEMENT PAGE */}
      {/* ========================================================================= */}
      {!isPageUnauthorized() && currentPage === "users" && !selectedTicket && (
        <section className="users-management-view">
          <div className="users-header-toolbar">
            <div>
              <h2 style={{ fontSize: "20px", fontWeight: "800", color: "#0f172a", margin: 0 }}>
                User Accounts &amp; Access Control
              </h2>
              <p style={{ fontSize: "13px", color: "#64748b", margin: "4px 0 0 0" }}>
                Manage administrative, technician, management, and client credentials
              </p>
            </div>
            <button
              className="btn-portal-primary"
              onClick={() => setShowCreateUserModal(true)}
            >
              ➕ Create New User
            </button>
          </div>

          <div className="users-stats-strip">
            <div className="user-stat-card">
              <div className="user-stat-icon">👥</div>
              <div className="user-stat-info">
                <div className="stat-num">{usersList.length}</div>
                <div className="stat-lbl">Total Registered Users</div>
              </div>
            </div>
            <div className="user-stat-card">
              <div className="user-stat-icon">👑</div>
              <div className="user-stat-info">
                <div className="stat-num">{usersList.filter((u) => u.role === "admin").length}</div>
                <div className="stat-lbl">Admins</div>
              </div>
            </div>
            <div className="user-stat-card">
              <div className="user-stat-icon">🛠</div>
              <div className="user-stat-info">
                <div className="stat-num">{usersList.filter((u) => u.role === "technician").length}</div>
                <div className="stat-lbl">Technicians</div>
              </div>
            </div>
            <div className="user-stat-card">
              <div className="user-stat-icon">🌐</div>
              <div className="user-stat-info">
                <div className="stat-num">{usersList.filter((u) => u.role === "customer").length}</div>
                <div className="stat-lbl">Customer Accounts</div>
              </div>
            </div>
          </div>

          <div className="portal-card">
            <div className="portal-table-container">
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>User Name</th>
                    <th>Email Address</th>
                    <th>Role</th>
                    <th>Organization / Team</th>
                    <th>Account Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {usersLoading ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "20px", color: "#64748b" }}>Loading users...</td>
                    </tr>
                  ) : usersList.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "20px", color: "#64748b" }}>No users registered.</td>
                    </tr>
                  ) : (
                    usersList.map((u) => (
                      <tr key={u.id}>
                        <td><strong>#{u.id}</strong></td>
                        <td><strong>{u.name}</strong></td>
                        <td>{u.email}</td>
                        <td>
                          <span className={`user-role-badge role-${u.role}`}>
                            {u.role.toUpperCase()}
                          </span>
                        </td>
                        <td>{u.team || u.company || "—"}</td>
                        <td>
                          <span className={`status-pill ${u.is_active ? "new" : "resolved"}`} style={{ fontSize: "11.5px" }}>
                            {u.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center" }}>
                            <button
                              className={`btn-user-toggle ${u.is_active ? "active-btn" : "inactive-btn"}`}
                              onClick={() => handleToggleUserStatus(u)}
                            >
                              {u.is_active ? "Deactivate" : "Activate"}
                            </button>
                            <button
                              className="btn-user-reset-pw"
                              onClick={() => {
                                setResetPasswordModalUser(u);
                                setNewResetPassword("");
                              }}
                            >
                              Reset PW
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ========================================================================= */}
      {/* KNOWLEDGE BASE MANAGEMENT PAGE (Phase 9) */}
      {/* ========================================================================= */}
      {!isPageUnauthorized() && currentPage === "knowledge-base" && !selectedTicket && (
        <section className="kb-management-view">
          {/* Internal Top Bar / Sub-tabs */}
          <div className="kb-subtab-bar">
            <button
              type="button"
              className={`kb-subtab-btn ${kbActiveTab === "articles" ? "active" : ""}`}
              onClick={() => setKbActiveTab("articles")}
            >
              📚 All Articles ({kbArticles.length})
            </button>
            {(isAdmin || isManager) && (
              <button
                type="button"
                className={`kb-subtab-btn ${kbActiveTab === "analytics" ? "active" : ""}`}
                onClick={() => setKbActiveTab("analytics")}
              >
                📊 KB Analytics &amp; Deflections
              </button>
            )}
            <button
              type="button"
              className={`kb-subtab-btn ${kbActiveTab === "categories" ? "active" : ""}`}
              onClick={() => setKbActiveTab("categories")}
            >
              📁 Categories ({kbCategories.length})
            </button>
          </div>

          {/* TAB 1: ARTICLES LIST */}
          {kbActiveTab === "articles" && (
            <div>
              {/* Filter Toolbar */}
              <div className="kb-filter-toolbar">
                <div className="kb-search-box">
                  <span className="search-icon">🔍</span>
                  <input
                    type="text"
                    placeholder="Search articles by title, tags, or content..."
                    value={kbSearchQuery}
                    onChange={(e) => {
                      const val = e.target.value;
                      setKbSearchQuery(val);
                      loadInternalKb({ query: val });
                    }}
                    className="kb-search-input"
                  />
                  {kbSearchQuery && (
                    <button
                      type="button"
                      className="clear-search-btn"
                      onClick={() => {
                        setKbSearchQuery("");
                        loadInternalKb({ query: "" });
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>

                <div className="kb-filter-select-group">
                  <select
                    value={kbSelectedCategory}
                    onChange={(e) => {
                      const val = e.target.value;
                      setKbSelectedCategory(val);
                      loadInternalKb({ category: val });
                    }}
                    className="kb-select"
                  >
                    <option value="all">All Categories</option>
                    {kbCategories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>

                  <select
                    value={kbVisibilityFilter}
                    onChange={(e) => {
                      const val = e.target.value;
                      setKbVisibilityFilter(val);
                      loadInternalKb({ visibility: val });
                    }}
                    className="kb-select"
                  >
                    <option value="all">All Visibility (Public &amp; Internal)</option>
                    <option value="public">🌐 Public (Client-Facing)</option>
                    <option value="internal">🔒 Internal (MSP Staff Only)</option>
                  </select>

                  <select
                    value={kbStatusFilter}
                    onChange={(e) => {
                      const val = e.target.value;
                      setKbStatusFilter(val);
                      loadInternalKb({ status: val });
                    }}
                    className="kb-select"
                  >
                    <option value="all">All Statuses</option>
                    <option value="published">Published</option>
                    <option value="draft">Draft</option>
                    <option value="archived">Archived</option>
                  </select>
                </div>
              </div>

              {/* Articles Grid / Table */}
              {kbLoading ? (
                <div className="kb-loading-box">
                  <div className="portal-spinner" />
                  <p>Loading knowledge base...</p>
                </div>
              ) : kbArticles.length === 0 ? (
                <div className="portal-empty-card" style={{ padding: "48px 24px", textAlign: "center", background: "#fff", borderRadius: "12px", border: "1px solid #e2e8f0", marginTop: "16px" }}>
                  <div style={{ fontSize: "36px", marginBottom: "10px" }}>📖</div>
                  <h4 style={{ margin: "0 0 6px", color: "#0f172a" }}>No articles found</h4>
                  <p style={{ color: "#64748b", margin: "0 0 16px", fontSize: "13px" }}>
                    Try clearing filters or create a new article.
                  </p>
                  {(isAdmin || isManager) && (
                    <button
                      type="button"
                      className="btn-portal-primary"
                      onClick={handleOpenCreateKbArticle}
                    >
                      + Create First Article
                    </button>
                  )}
                </div>
              ) : (
                <div className="kb-articles-grid">
                  {kbArticles.map((art) => (
                    <div key={art.id} className={`kb-internal-card ${art.visibility === "internal" ? "is-internal" : "is-public"}`}>
                      <div className="kb-card-header-row">
                        <div className="kb-badge-group">
                          <span className={`kb-vis-badge ${art.visibility === "internal" ? "badge-internal" : "badge-public"}`}>
                            {art.visibility === "internal" ? "🔒 Internal Staff" : "🌐 Public Portal"}
                          </span>
                          <span className={`kb-status-badge status-${art.status}`}>
                            {art.status}
                          </span>
                          <span className="kb-version-badge">v{art.current_version}</span>
                        </div>
                        <div className="kb-rating-pill-sm">
                          ⭐ {art.helpfulness_score}% ({art.helpful_count} / {art.helpful_count + art.not_helpful_count})
                        </div>
                      </div>

                      <h3 className="kb-card-title">{art.title}</h3>
                      <p className="kb-card-summary">{art.summary || "No summary provided. Click view to inspect full documentation."}</p>

                      <div className="kb-card-meta-row">
                        <span className="kb-meta-item">📁 {art.category_name}</span>
                        {art.team_name && <span className="kb-meta-item">🛡️ {art.team_name}</span>}
                        <span className="kb-meta-item">👁 {art.view_count} views</span>
                      </div>

                      {art.tags && art.tags.length > 0 && (
                        <div className="kb-card-tags">
                          {art.tags.slice(0, 4).map((tag, tIdx) => (
                            <span key={tIdx} className="kb-tag-pill">#{tag}</span>
                          ))}
                        </div>
                      )}

                      <div className="kb-card-actions">
                        <button
                          type="button"
                          className="btn-kb-action btn-kb-view"
                          onClick={async () => {
                            try {
                              const res = await fetch(`${API_URL}/kb/articles/${art.id}`, { headers: getAuthHeaders() });
                              if (res.ok) {
                                const d = await res.json();
                                setKbActiveArticle(d.article);
                              }
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                        >
                          📖 Read &amp; Copy
                        </button>
                        <button
                          type="button"
                          className={`btn-kb-action btn-kb-copy ${copiedSolutionId === art.id ? "copied" : ""}`}
                          onClick={async () => {
                            try {
                              const res = await fetch(`${API_URL}/kb/articles/${art.id}`, { headers: getAuthHeaders() });
                              if (res.ok) {
                                const d = await res.json();
                                handleCopySolution(d.article.content, art.id);
                              }
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                          title="Copy solution markdown to clipboard for ticket notes"
                        >
                          {copiedSolutionId === art.id ? "✓ Copied!" : "📋 Copy Solution"}
                        </button>
                        {(isAdmin || isManager) && (
                          <button
                            type="button"
                            className="btn-kb-action btn-kb-edit"
                            onClick={() => handleOpenEditKbArticle(art)}
                          >
                            ✏️ Edit
                          </button>
                        )}
                        {(isAdmin || isManager) && (
                          <button
                            type="button"
                            className="btn-kb-action btn-kb-history"
                            onClick={() => handleOpenKbVersions(art)}
                            title="View Audit Version History"
                          >
                            🕒 History
                          </button>
                        )}
                        {isAdmin && (
                          <button
                            type="button"
                            className="btn-kb-action btn-kb-delete"
                            onClick={() => handleDeleteKbArticle(art.id)}
                            title="Permanently Delete Article"
                          >
                            🗑️
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: KB ANALYTICS (ADMIN / MANAGER) */}
          {kbActiveTab === "analytics" && (isAdmin || isManager) && (
            <div className="kb-analytics-view">
              <div className="kb-kpi-grid">
                <div className="kb-kpi-card">
                  <div className="kb-kpi-icon">📚</div>
                  <div className="kb-kpi-info">
                    <span className="kb-kpi-label">Total Articles</span>
                    <strong className="kb-kpi-val">{kbAnalyticsData?.total_articles || kbArticles.length}</strong>
                    <small>
                      {kbAnalyticsData?.public_articles || 0} public • {kbAnalyticsData?.internal_articles || 0} internal
                    </small>
                  </div>
                </div>

                <div className="kb-kpi-card">
                  <div className="kb-kpi-icon">👁</div>
                  <div className="kb-kpi-info">
                    <span className="kb-kpi-label">Total Views</span>
                    <strong className="kb-kpi-val">{kbAnalyticsData?.total_views || 0}</strong>
                    <small>Client &amp; engineer reads</small>
                  </div>
                </div>

                <div className="kb-kpi-card">
                  <div className="kb-kpi-icon">⭐</div>
                  <div className="kb-kpi-info">
                    <span className="kb-kpi-label">Helpfulness Score</span>
                    <strong className="kb-kpi-val">{kbAnalyticsData?.overall_helpfulness_percentage || 100}%</strong>
                    <small>
                      {kbAnalyticsData?.total_helpful || 0} helpful / {kbAnalyticsData?.total_not_helpful || 0} unhelpful
                    </small>
                  </div>
                </div>

                <div className="kb-kpi-card">
                  <div className="kb-kpi-icon">🛡️</div>
                  <div className="kb-kpi-info">
                    <span className="kb-kpi-label">Est. Deflections</span>
                    <strong className="kb-kpi-val">{kbAnalyticsData?.estimated_deflections || 0}</strong>
                    <small>Tickets avoided via self-service</small>
                  </div>
                </div>
              </div>

              {/* Leaderboards */}
              <div className="kb-analytics-row" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "24px" }}>
                <div className="kb-analytics-card">
                  <h4 style={{ margin: "0 0 14px", fontSize: "15px", color: "#0f172a" }}>🔥 Most Read Help Guides</h4>
                  <div className="kb-leaderboard-list">
                    {(kbAnalyticsData?.top_viewed_articles || []).map((art, idx) => (
                      <div key={art.id} className="kb-leaderboard-item">
                        <span className="kb-rank">#{idx + 1}</span>
                        <div className="kb-leaderboard-main">
                          <span className="kb-lead-title">{art.title}</span>
                          <span className="kb-lead-sub">{art.category} • {art.visibility === "internal" ? "🔒 Internal" : "🌐 Public"}</span>
                        </div>
                        <span className="kb-lead-stat">👁 {art.views}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="kb-analytics-card">
                  <h4 style={{ margin: "0 0 14px", fontSize: "15px", color: "#0f172a" }}>👍 Highest Customer Ratings</h4>
                  <div className="kb-leaderboard-list">
                    {(kbAnalyticsData?.top_helpful_articles || []).map((art, idx) => (
                      <div key={art.id} className="kb-leaderboard-item">
                        <span className="kb-rank">#{idx + 1}</span>
                        <div className="kb-leaderboard-main">
                          <span className="kb-lead-title">{art.title}</span>
                          <span className="kb-lead-sub">{art.category} • {art.visibility === "internal" ? "🔒 Internal" : "🌐 Public"}</span>
                        </div>
                        <span className="kb-lead-stat" style={{ color: "#16a34a" }}>👍 {art.helpful}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Flagged Articles */}
              {(kbAnalyticsData?.articles_needing_review || []).length > 0 && (
                <div className="kb-flagged-card" style={{ marginTop: "24px", background: "#fff", border: "1px solid #fed7aa", borderRadius: "10px", padding: "18px" }}>
                  <h4 style={{ margin: "0 0 8px", color: "#c2410c", display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>⚠️</span> Guides Needing Content Review (Low Helpfulness or High Downvotes)
                  </h4>
                  <p style={{ fontSize: "12px", color: "#78350f", margin: "0 0 14px" }}>
                    The following articles have received feedback indicating the steps may be unclear or outdated:
                  </p>
                  <table className="users-table" style={{ width: "100%" }}>
                    <thead>
                      <tr>
                        <th>Article</th>
                        <th>Category</th>
                        <th>Helpful</th>
                        <th>Unhelpful</th>
                        <th>Score</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kbAnalyticsData.articles_needing_review.map((item) => (
                        <tr key={item.id}>
                          <td><strong>{item.title}</strong></td>
                          <td>{item.category_name}</td>
                          <td style={{ color: "#16a34a" }}>👍 {item.helpful_count}</td>
                          <td style={{ color: "#dc2626" }}>👎 {item.not_helpful_count}</td>
                          <td><span className="priority-tag high">{item.helpfulness_score}%</span></td>
                          <td>
                            <button
                              type="button"
                              className="btn-user-reset-pw"
                              onClick={() => {
                                const targetArt = kbArticles.find((a) => a.id === item.id);
                                if (targetArt) handleOpenEditKbArticle(targetArt);
                              }}
                            >
                              Revise Guide
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: CATEGORIES MANAGEMENT */}
          {kbActiveTab === "categories" && (
            <div className="kb-categories-view">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ margin: 0, fontSize: "16px", color: "#0f172a" }}>
                  Knowledge Base Categories ({kbCategories.length})
                </h3>
                {(isAdmin || isManager) && (
                  <button
                    type="button"
                    className="new-ticket"
                    onClick={handleOpenCreateKbCategory}
                  >
                    + Add Category
                  </button>
                )}
              </div>

              <div className="kb-categories-grid">
                {kbCategories.map((cat) => (
                  <div key={cat.id} className="kb-category-admin-card">
                    <div className="kb-cat-icon-lg">
                      {cat.icon === "cloud" ? "☁️" :
                       cat.icon === "network" ? "🌐" :
                       cat.icon === "shield" ? "🛡️" :
                       cat.icon === "laptop" ? "💻" :
                       cat.icon === "database" ? "💾" :
                       cat.icon === "lock" ? "🔒" : "📖"}
                    </div>
                    <div className="kb-cat-admin-info">
                      <h4>{cat.name}</h4>
                      <p>{cat.description || "No description provided."}</p>
                      <div className="kb-cat-admin-meta">
                        <span className="kb-cat-meta-item">Slug: <code>{cat.slug}</code></span>
                        <span className="kb-cat-meta-item">Order: {cat.display_order}</span>
                        <span className="kb-cat-meta-item">Articles: <strong>{cat.article_count}</strong></span>
                      </div>
                    </div>
                    {(isAdmin || isManager) && (
                      <div className="kb-cat-admin-actions">
                        <button
                          type="button"
                          className="btn-kb-action btn-kb-edit"
                          onClick={() => handleOpenEditKbCategory(cat)}
                        >
                          ✏️ Edit
                        </button>
                        {isAdmin && (
                          <button
                            type="button"
                            className="btn-kb-action btn-kb-delete"
                            onClick={() => handleDeleteKbCategory(cat.id)}
                          >
                            🗑️ Delete
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ========================================================================= */}
      {/* TECHNICIAN WORKBENCH PAGE */}
      {/* ========================================================================= */}
      {currentPage === "workbench" && !selectedTicket && (
        <section className="workbench-section">
          {/* KPI Cards */}
          <div className="wb-kpi-grid">
            <div className="wb-kpi-card kpi-open">
              <div className="wb-kpi-icon">📋</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">Open Workload</span>
                <strong className="wb-kpi-val">{openTicketsCount}</strong>
                <small>Active tickets</small>
              </div>
            </div>

            <div className="wb-kpi-card kpi-critical">
              <div className="wb-kpi-icon">🔥</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">Critical Open</span>
                <strong className="wb-kpi-val">{criticalOpenCount}</strong>
                <small>15m resp / 2h res</small>
              </div>
            </div>

            <div className="wb-kpi-card kpi-high">
              <div className="wb-kpi-icon">⚡</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">High Priority</span>
                <strong className="wb-kpi-val">{highOpenCount}</strong>
                <small>30m resp / 4h res</small>
              </div>
            </div>

            <div className="wb-kpi-card kpi-atrisk">
              <div className="wb-kpi-icon">⚠️</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">SLA At Risk</span>
                <strong className="wb-kpi-val">{atRiskCount}</strong>
                <small>&le; 25% window left</small>
              </div>
            </div>

            <div className="wb-kpi-card kpi-breached">
              <div className="wb-kpi-icon">🚨</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">SLA Breached</span>
                <strong className="wb-kpi-val">{breachedCount}</strong>
                <small>Missed target</small>
              </div>
            </div>

            <div className="wb-kpi-card kpi-resolved">
              <div className="wb-kpi-icon">✅</div>
              <div className="wb-kpi-data">
                <span className="wb-kpi-label">Resolved Today</span>
                <strong className="wb-kpi-val">{resolvedTodayCount}</strong>
                <small>Completed today</small>
              </div>
            </div>
          </div>

          {/* Technician Workload Strip */}
          <div className="wb-workload-strip">
            <div className="wb-workload-header">
              <div className="wb-workload-title">
                <span className="wb-workload-icon">👥</span>
                <strong>Technician Workload</strong>
                <small>Live active tickets ({technicians.reduce((acc, t) => acc + (t.active_workload || 0), 0)} assigned)</small>
              </div>
              {wbTechFilter !== "all" && (
                <button
                  type="button"
                  className="wb-workload-reset-btn"
                  onClick={() => setWbTechFilter("all")}
                >
                  Clear Tech Filter
                </button>
              )}
            </div>

            <div className="wb-tech-chips-scroll">
              {technicians
                .filter((t) => wbTeamFilter === "all" || t.team === wbTeamFilter)
                .map((tech) => {
                  const isSelected = String(wbTechFilter) === String(tech.id) || wbTechFilter === tech.name;
                  const count = tech.active_workload || 0;
                  return (
                    <div
                      key={tech.id}
                      className={`wb-tech-chip ${isSelected ? "selected" : ""} ${count > 3 ? "chip-busy" : count > 0 ? "chip-active" : "chip-idle"}`}
                      onClick={() => setWbTechFilter(isSelected ? "all" : tech.id)}
                      title={`Filter by ${tech.name} (${tech.team}) — ${count} active tickets`}
                    >
                      <span className="tech-chip-avatar">👤</span>
                      <div className="tech-chip-info">
                        <strong className="tech-chip-name">{tech.name}</strong>
                        <span className="tech-chip-team">{tech.team}</span>
                      </div>
                      <span className={`tech-workload-badge ${count > 0 ? "badge-has-load" : "badge-zero"}`}>
                        {count} {count === 1 ? "ticket" : "tickets"}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Work Queue Container */}
          <div className="wb-queue-card">
            <div className="wb-queue-header">
              <div>
                <h2>Technician Work Queue</h2>
                <p>Prioritized operational ticket queue with real-time technician assignments and escalation status</p>
              </div>
              <div className="wb-queue-meta">
                <span className="wb-queue-count-pill">{wbFilteredTickets.length} of {tickets.length} tickets</span>
                <button className="wb-refresh-btn" onClick={() => { loadTickets(); loadTechnicians(); }} title="Refresh tickets">↻ Refresh</button>
              </div>
            </div>

            {/* Filter & Search Toolbar */}
            <div className="wb-filter-toolbar">
              <div className="wb-search-box">
                <span className="wb-search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search by ID, title, description, category, technician..."
                  value={wbSearch}
                  onChange={(e) => setWbSearch(e.target.value)}
                />
                {wbSearch && (
                  <button className="wb-search-clear" onClick={() => setWbSearch("")}>✕</button>
                )}
              </div>

              <div className="wb-filter-group">
                <select
                  value={wbTeamFilter}
                  onChange={(e) => setWbTeamFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All Teams</option>
                  {(teamsList.length > 0
                    ? teamsList.filter((t) => t.is_active)
                    : [
                        { id: 1, name: "M365 Support" },
                        { id: 2, name: "Network Team" },
                        { id: 3, name: "Security Team" },
                        { id: 4, name: "Endpoint Team" },
                        { id: 5, name: "Backup Team" },
                        { id: 6, name: "Application Support" },
                        { id: 7, name: "Service Desk" }
                      ]
                  ).map((t) => (
                    <option key={t.id} value={t.name}>
                      {t.name}
                    </option>
                  ))}
                </select>

                <select
                  value={wbTechFilter}
                  onChange={(e) => setWbTechFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All Technicians</option>
                  <option value="unassigned">⚠️ Unassigned Only</option>
                  {technicians
                    .filter((t) => wbTeamFilter === "all" || t.team === wbTeamFilter)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.team}) — {t.active_workload} active
                      </option>
                    ))}
                </select>

                <select
                  value={wbEscalationFilter}
                  onChange={(e) => setWbEscalationFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All Escalations</option>
                  <option value="1">Level 1 (Normal)</option>
                  <option value="2">⚡ Level 2 (Team)</option>
                  <option value="3">🚨 Level 3 (Specialist)</option>
                  <option value="escalated">🔥 Any Escalated (L2 & L3)</option>
                </select>

                <select
                  value={wbPriorityFilter}
                  onChange={(e) => setWbPriorityFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">🔥 Critical</option>
                  <option value="high">⚡ High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>

                <select
                  value={wbStatusFilter}
                  onChange={(e) => setWbStatusFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="open">Open Only (New & In Progress)</option>
                  <option value="all">All Statuses</option>
                  <option value="new">New</option>
                  <option value="in_progress">In Progress</option>
                  <option value="resolved">Resolved</option>
                </select>

                <select
                  value={wbSlaFilter}
                  onChange={(e) => setWbSlaFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All SLA States</option>
                  <option value="on_track">⏱ On Track</option>
                  <option value="at_risk">⚠️ At Risk</option>
                  <option value="breached">🚨 Breached</option>
                  <option value="met">✓ Met</option>
                </select>

                <select
                  value={wbRoutingFilter}
                  onChange={(e) => setWbRoutingFilter(e.target.value)}
                  className="wb-select"
                >
                  <option value="all">All Routing</option>
                  <option value="rule_engine">Automated (Rule)</option>
                  <option value="manual">Manual Reassigned</option>
                </select>

                {(wbSearch || wbPriorityFilter !== "all" || wbTeamFilter !== "all" || wbTechFilter !== "all" || wbEscalationFilter !== "all" || wbStatusFilter !== "open" || wbSlaFilter !== "all" || wbRoutingFilter !== "all") && (
                  <button
                    className="wb-clear-btn"
                    onClick={() => {
                      setWbSearch("");
                      setWbPriorityFilter("all");
                      setWbTeamFilter("all");
                      setWbTechFilter("all");
                      setWbEscalationFilter("all");
                      setWbStatusFilter("open");
                      setWbSlaFilter("all");
                      setWbRoutingFilter("all");
                    }}
                  >
                    Reset Filters
                  </button>
                )}
              </div>
            </div>

            {/* Queue Table */}
            {loading ? (
              <div className="loading">Loading technician work queue...</div>
            ) : wbFilteredTickets.length === 0 ? (
              <div className="wb-empty-queue">
                <span className="wb-empty-icon">🎉</span>
                <h3>No tickets found</h3>
                <p>No tickets currently match the selected workbench filters.</p>
              </div>
            ) : (
              <div className="wb-table-wrapper">
                <div className="wb-table-header">
                  <span>ID</span>
                  <span>TICKET & CATEGORY</span>
                  <span>PRIORITY</span>
                  <span>TEAM</span>
                  <span>TECHNICIAN</span>
                  <span>ESCALATION</span>
                  <span>STATUS</span>
                  <span>SLA STATE & TIMER</span>
                  <span>ACTIONS</span>
                </div>

                <div className="wb-table-body">
                  {wbFilteredTickets.map((ticket) => {
                    const isCritOrHigh = ticket.priority === "critical" || ticket.priority === "high";
                    const slaStatus = ticket.sla_status || ticket.sla?.overall_status || "on_track";
                    const isBreached = slaStatus === "breached";
                    const isAtRisk = slaStatus === "at_risk";
                    const escLevel = ticket.escalation_level || 1;

                    return (
                      <div
                        key={ticket.id}
                        className={`wb-table-row priority-${ticket.priority} ${isBreached ? "row-breached" : isAtRisk ? "row-atrisk" : ""} ${escLevel > 1 ? `row-esc-${escLevel}` : ""}`}
                        onClick={() => setSelectedTicket(ticket)}
                      >
                        <div className="wb-cell-id">
                          <strong>#{ticket.id}</strong>
                        </div>

                        <div className="wb-cell-title">
                          <span className="wb-ticket-name">{ticket.title}</span>
                          <div className="wb-ticket-sub">
                            <span className="wb-category-tag">{ticket.category || "General"}</span>
                            {ticket.source === "email" ? (
                              <span className="source-badge-email" title={`Email from ${ticket.email_sender || ticket.customer_email || 'client'}`}>
                                📧 Email
                              </span>
                            ) : (
                              <span className="source-badge-portal" title="Submitted via Portal / Internal">
                                🌐 Portal
                              </span>
                            )}
                            {ticket.customer_company && (
                              <span className="wb-cust-company-tag">🏢 {ticket.customer_company}</span>
                            )}
                            <small className="wb-time-created">
                              Created {new Date(ticket.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}
                            </small>
                          </div>
                        </div>

                        <div className="wb-cell-priority">
                          <span className={`priority ${ticket.priority || "medium"} ${isCritOrHigh ? "prio-glow" : ""}`}>
                            {(ticket.priority || "medium").toUpperCase()}
                          </span>
                        </div>

                        <div className="wb-cell-team">
                          <span className="team-badge">{ticket.assigned_team || "Unassigned"}</span>
                        </div>

                        <div className="wb-cell-tech" onClick={(e) => e.stopPropagation()}>
                          {ticket.assigned_technician ? (
                            <span
                              className="tech-assigned-pill"
                              onClick={() => {
                                setAssignModalTicket(ticket);
                                setSelectedTechId(ticket.assigned_technician_id || "");
                              }}
                              title="Click to reassign technician"
                            >
                              👤 {ticket.assigned_technician}
                            </span>
                          ) : (
                            <button
                              className="btn-quick-assign"
                              onClick={() => {
                                setAssignModalTicket(ticket);
                                setSelectedTechId("");
                              }}
                              title="Assign a technician"
                            >
                              + Assign Tech
                            </button>
                          )}
                        </div>

                        <div className="wb-cell-esc">
                          {escLevel === 3 ? (
                            <span className="esc-badge level-3" title={ticket.escalation_reason || "Specialist Escalation"}>
                              🚨 Level 3
                            </span>
                          ) : escLevel === 2 ? (
                            <span className="esc-badge level-2" title={ticket.escalation_reason || "Team Escalation"}>
                              ⚡ Level 2
                            </span>
                          ) : (
                            <span className="esc-badge level-1">
                              Level 1
                            </span>
                          )}
                        </div>

                        <div className="wb-cell-status">
                          <span className={`status-badge status-${ticket.status || "new"}`}>
                            {(ticket.status || "new").replace("_", " ")}
                          </span>
                        </div>

                        <div className="wb-cell-sla">
                          <div className="wb-sla-stack">
                            {renderSlaBadge(ticket.sla_status || ticket.sla?.overall_status)}
                            <small className="wb-sla-timer">
                              {ticket.status === "resolved"
                                ? (ticket.resolved_at ? `Resolved at ${new Date(ticket.resolved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : "Resolved")
                                : (ticket.sla?.resolution_remaining_label || ticket.sla?.response_remaining_label || "Active")}
                            </small>
                          </div>
                        </div>

                        <div className="wb-cell-actions" onClick={(e) => e.stopPropagation()}>
                          {ticket.status === "new" ? (
                            <button
                              className="wb-act-btn btn-start"
                              onClick={() => handleStartWorking(ticket)}
                              title="Mark In Progress"
                            >
                              ▶ Start
                            </button>
                          ) : ticket.status === "in_progress" ? (
                            <button
                              className="wb-act-btn btn-resolve"
                              onClick={() => setSelectedTicket(ticket)}
                              title="Go to Resolution"
                            >
                              ✓ Resolve
                            </button>
                          ) : null}

                          {ticket.status !== "resolved" && escLevel < 3 && (
                            <button
                              className="wb-act-btn btn-escalate"
                              onClick={() => {
                                setEscalateModalTicket(ticket);
                                setTargetEscalationLevel(escLevel === 1 ? 2 : 3);
                                setEscalationReason("");
                              }}
                              title="Escalate ticket"
                            >
                              🔥 Escalate
                            </button>
                          )}

                          <button
                            className="wb-act-btn btn-open"
                            onClick={() => setSelectedTicket(ticket)}
                          >
                            Open →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {currentPage === "dashboard" && !selectedTicket && (
  <>
    {/* Statistics */}
    <section className="stats">

      <div className="stat-card">
        <div className="stat-label">
          TOTAL TICKETS
        </div>

        <div className="stat-number">
          {tickets.length}
        </div>

        <div className="stat-description">
          Tickets processed
        </div>
      </div>


      <div className="stat-card">
        <div className="stat-label">
          CRITICAL
        </div>

        <div className="stat-number critical">
          {critical}
        </div>

        <div className="stat-description">
          Immediate attention
        </div>
      </div>


      <div className="stat-card">
        <div className="stat-label">
          HIGH PRIORITY
        </div>

        <div className="stat-number high">
          {high}
        </div>

        <div className="stat-description">
          Requires attention
        </div>
      </div>


      <div className="stat-card">
        <div className="stat-label">
          AUTOMATED
        </div>

        <div className="stat-number">
          {automated}
        </div>

        <div className="stat-description">
          Rule engine routed
        </div>
      </div>

    </section>


    {/* Recent Tickets */}
    <section className="tickets-section">

      <div className="section-header">
        <div>
          <h2>Recent Tickets</h2>

          <p>
            Latest tickets processed by the system
          </p>
        </div>
      </div>


      {loading ? (
        <div className="loading">
          Loading tickets...
        </div>
      ) : tickets.length === 0 ? (
        <div className="empty">
          No tickets found.
        </div>
      ) : (
        <div className="ticket-table">

          <div className="table-header">
            <span>ID</span>
            <span>TICKET</span>
            <span>TEAM</span>
            <span>PRIORITY</span>
            <span>STATUS</span>
            <span>SLA</span>
            <span>ROUTING</span>
          </div>


          {tickets.slice(0, 5).map((ticket) => (

           <div
  className="ticket-row"
  key={ticket.id}
  onClick={() => setSelectedTicket(ticket)}
>

              <span className="ticket-id">
                #{ticket.id}
              </span>


              <div className="ticket-title">

                <strong>
                  {ticket.title}
                </strong>

                <small>
                  {ticket.description}
                </small>

              </div>


              <span>
                {ticket.assigned_team}
              </span>


              <span
                className={`priority ${ticket.priority}`}
              >
                {ticket.priority}
              </span>


              <span className="status">
                {ticket.status}
              </span>

              <span>
                {renderSlaBadge(ticket.sla_status || ticket.sla?.overall_status)}
              </span>

              <span className="routing">
                {ticket.routing_method}
              </span>

            </div>

          ))}

        </div>
      )}

    </section>
  </>
)}


{currentPage === "tickets" && !selectedTicket && (
  <section className="tickets-section">

    <div className="section-header">

      <div>
        <h2>All Tickets</h2>

        <p>
          View and manage all tickets processed by the system
        </p>
      </div>

    </div>
<div className="ticket-filters">

  <input
    type="text"
    placeholder="Search tickets..."
    value={search}
    onChange={(event) => setSearch(event.target.value)}
  />

  <select
    value={priorityFilter}
    onChange={(event) => setPriorityFilter(event.target.value)}
  >
    <option value="all">All Priorities</option>
    <option value="critical">Critical</option>
    <option value="high">High</option>
    <option value="medium">Medium</option>
    <option value="low">Low</option>
  </select>

 <select
  value={teamFilter}
  onChange={(event) => setTeamFilter(event.target.value)}
>
  <option value="all">All Teams</option>
  {(teamsList.length > 0
    ? teamsList.filter((t) => t.is_active)
    : [
        { id: 1, name: "M365 Support" },
        { id: 2, name: "Network Team" },
        { id: 3, name: "Security Team" },
        { id: 4, name: "Endpoint Team" },
        { id: 5, name: "Backup Team" },
        { id: 6, name: "Application Support" },
        { id: 7, name: "Service Desk" }
      ]
  ).map((t) => (
    <option key={t.id} value={t.name}>
      {t.name}
    </option>
  ))}
</select>

  <select
    value={slaFilter}
    onChange={(event) => setSlaFilter(event.target.value)}
  >
    <option value="all">All SLA Statuses</option>
    <option value="on_track">⏱ On Track</option>
    <option value="at_risk">⚠️ At Risk</option>
    <option value="met">✓ Met</option>
    <option value="breached">🚨 Breached</option>
  </select>

</div>

    {loading ? (
      <div className="loading">
        Loading tickets...
      </div>
    ) : tickets.length === 0 ? (
      <div className="empty">
        No tickets found.
      </div>
    ) : (
      <div className="ticket-table">

        <div className="table-header">
          <span>ID</span>
          <span>TICKET</span>
          <span>TEAM</span>
          <span>PRIORITY</span>
          <span>STATUS</span>
          <span>SLA</span>
          <span>ROUTING</span>
        </div>


       {filteredTickets.map((ticket) => (

         <div
  className="ticket-row"
  key={ticket.id}
  onClick={() => setSelectedTicket(ticket)}
>

            <span className="ticket-id">
              #{ticket.id}
            </span>


            <div className="ticket-title">
              <div className="ticket-title-row">
                <strong>
                  {ticket.title}
                </strong>
                {ticket.source === "email" && (
                  <span className="source-badge-email" title={`Email from ${ticket.email_sender || ticket.customer_email || 'client'}`}>
                    📧 Email
                  </span>
                )}
                {ticket.customer_company && (
                  <span className="wb-cust-company-tag">🏢 {ticket.customer_company}</span>
                )}
              </div>

              <small>
                {ticket.description}
              </small>
            </div>


            <span>
              {ticket.assigned_team}
            </span>


            <span
              className={`priority ${ticket.priority}`}
            >
              {ticket.priority}
            </span>


            <span className="status">
              {ticket.status}
            </span>

            <span>
              {renderSlaBadge(ticket.sla_status || ticket.sla?.overall_status)}
            </span>

            <span className="routing">
              {ticket.routing_method}
            </span>

          </div>

        ))}

      </div>
    )}

  </section>
)}
{currentPage === "rules" && (
  <section className="rules-section">

    <div className="rules-intro">
      <div className="rules-intro-text">
        <h2>Automated Routing Rules</h2>
        <p>
          The rule engine analyzes ticket titles and descriptions
          and automatically assigns the appropriate team and priority.
        </p>
      </div>
      {isManager && !isAdmin && (
        <div className="rules-manager-notice">
          <span className="notice-icon">🔒</span>
          <div>
            <strong>Manager Read-Only Access</strong>
            <small>Rule modification and re-evaluation are reserved for Administrators.</small>
          </div>
        </div>
      )}
    </div>

    {rulesLoading ? (
      <div className="loading">
        Loading routing rules...
      </div>
    ) : rules.length === 0 ? (
      <div className="empty">
        No routing rules found.
      </div>
    ) : (
      <div className="rules-grid">

        {rules.map((rule, index) => (
          <div className="rule-card" key={rule.id || index}>

            <div className="rule-card-header">
              <div>
                <h3>{rule.name}</h3>

                <span className={`rule-status ${rule.status}`}>
                  {rule.status === "active" ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>

              {isAdmin && (
                <div className="rule-actions">
                  <button
                    className="edit-rule-button"
                    onClick={() =>
                      setEditingRule({
                        ...rule,
                        keywords: [...(rule.keywords || [])],
                      })
                    }
                  >
                    Edit Rule
                  </button>

                  <button
                    className="rule-action-button"
                    onClick={() => toggleRuleStatus(rule)}
                  >
                    {rule.status === "active" ? "Disable" : "Enable"}
                  </button>
                </div>
              )}
            </div>

            <p className="rule-description">
              {rule.description}
            </p>

            <div className="rule-keywords">
              {rule.keywords?.map((keyword, keywordIndex) => (
                <span key={keywordIndex}>
                  {keyword}
                </span>
              ))}
            </div>

            <div className="rule-result">

              <div>
                <small>TEAM</small>
                <strong>
                  {rule.team}
                </strong>
              </div>

              <div>
                <small>PRIORITY</small>

                <strong
                  className={`priority ${rule.priority}`}
                >
                  {rule.priority?.toUpperCase()}
                </strong>
              </div>

            </div>

          </div>
        ))}

      </div>
    )}

  </section>
)}
{selectedTicket && (
  <section className="ticket-details">

   <button
  className="back-button"
 onClick={() => {
  setSelectedTicket(null);
  setRoutingAnalysis(null);
  setRoutingHistory([]);
}}
>
      ← Back to Tickets
    </button>

    <div className="details-card">

      <div className="details-header">
        <div>
          <span className="ticket-id">
            #{selectedTicket.id}
          </span>

          <h2>{selectedTicket.title}</h2>

          <p>
            Ticket processed by the Jace Haus routing engine
          </p>
        </div>

        <span
          className={`priority ${selectedTicket.priority}`}
        >
          {selectedTicket.priority}
        </span>
      </div>


      <div className="details-section">

        <h3>Description</h3>

        <p>
          {selectedTicket.description}
        </p>

      </div>


      <div className="details-grid">

       <div className="detail-item">
  <span>Assigned Team</span>

  <select
    value={selectedTicket.assigned_team || "Service Desk"}
    onChange={(event) =>
      updateTicketTeam(event.target.value)
    }
    disabled={updatingTeam}
    className="team-select"
  >
    {(teamsList.length > 0
      ? teamsList.filter((t) => t.is_active)
      : [
          { id: 1, name: "M365 Support" },
          { id: 2, name: "Network Team" },
          { id: 3, name: "Security Team" },
          { id: 4, name: "Endpoint Team" },
          { id: 5, name: "Backup Team" },
          { id: 6, name: "Application Support" },
          { id: 7, name: "Service Desk" }
        ]
    ).map((t) => (
      <option key={t.id} value={t.name}>
        {t.name}
      </option>
    ))}
  </select>

  {updatingTeam && (
    <small className="status-updating">
      Re-routing...
    </small>
  )}
</div>


        <div className="detail-item">
          <span>Category</span>
          <strong>
            {selectedTicket.category}
          </strong>
        </div>


     <div className="detail-item">
  <span>Priority</span>

  <select
    className={`priority-select ${selectedTicket.priority}`}
    value={selectedTicket.priority}
    onChange={(event) =>
      updateTicketPriority(
        selectedTicket.id,
        event.target.value
      )
    }
  >
    <option value="critical">Critical</option>
    <option value="high">High</option>
    <option value="medium">Medium</option>
    <option value="low">Low</option>
  </select>
</div>

      <div className="detail-item">
  <span>Status</span>

  <div className="status-control">
    <select
      value={selectedTicket.status || "new"}
      onChange={(event) =>
        updateTicketStatus(event.target.value)
      }
      disabled={updatingStatus}
      className={`status-select ${
        selectedTicket.status || "new"
      }`}
    >
      <option value="new">
        New
      </option>

      <option value="in_progress">
        In Progress
      </option>

      <option value="resolved">
        Resolved
      </option>
    </select>

    {updatingStatus && (
      <small className="status-updating">
        Updating...
      </small>
    )}
  </div>
</div>

<div className="detail-item">
  <span>Assigned Technician</span>

  <div className="tech-assign-control">
    <select
      value={selectedTicket.assigned_technician_id || ""}
      onChange={(e) =>
        handleAssignTechnician(
          selectedTicket.id,
          e.target.value ? Number(e.target.value) : null
        )
      }
      disabled={assigningTech}
      className="tech-select-input"
    >
      <option value="">-- Unassigned --</option>
      {technicians
        .filter((t) => t.team === selectedTicket.assigned_team)
        .map((t) => (
          <option key={t.id} value={t.id}>
            {t.name} ({t.active_workload} active)
          </option>
        ))}
    </select>

    {assigningTech && (
      <small className="status-updating">
        Assigning...
      </small>
    )}
  </div>
</div>

<div className="detail-item esc-detail-item">
  <span>Escalation Status</span>
  <div className="esc-status-display">
    <div className="esc-status-row">
      {(selectedTicket.escalation_level || 1) === 3 ? (
        <span className="esc-badge level-3">🚨 Level 3 (Specialist Escalation)</span>
      ) : (selectedTicket.escalation_level || 1) === 2 ? (
        <span className="esc-badge level-2">⚡ Level 2 (Team Escalation)</span>
      ) : (
        <span className="esc-badge level-1">✓ Level 1 (Normal)</span>
      )}

      {selectedTicket.status !== "resolved" && (selectedTicket.escalation_level || 1) < 3 && (
        <button
          type="button"
          className="btn-esc-action"
          onClick={() => {
            setEscalateModalTicket(selectedTicket);
            setTargetEscalationLevel((selectedTicket.escalation_level || 1) === 1 ? 2 : 3);
            setEscalationReason("");
          }}
        >
          🔥 Escalate Ticket
        </button>
      )}
    </div>

    {(selectedTicket.escalation_level || 1) > 1 && (
      <div className="esc-history-box">
        <div className="esc-meta-row">
          <small>Escalated by: <strong>{selectedTicket.escalated_by || "Technician"}</strong></small>
          <small>
            {selectedTicket.escalated_at ? new Date(selectedTicket.escalated_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : ""}
          </small>
        </div>
        <p className="esc-reason-text">"{selectedTicket.escalation_reason}"</p>
      </div>
    )}
  </div>
</div>

<div className="sla-detail-panel">
  <div className="sla-detail-header">
    <div>
      <h3>SLA & Breach Tracking</h3>
      <p>
        Guaranteed SLA targets for <strong>{(selectedTicket.priority || "medium").toUpperCase()}</strong> priority
      </p>
    </div>

    <div>
      {renderSlaBadge(selectedTicket.sla_status || selectedTicket.sla?.overall_status)}
    </div>
  </div>

  <div className="sla-cards-grid">
    {/* Response SLA Card */}
    <div className={`sla-metric-card sla-card-${selectedTicket.sla?.response_status || (selectedTicket.responded_at ? 'met' : selectedTicket.sla_status || 'on_track')}`}>
      <div className="sla-card-header">
        <span className="sla-card-type">⚡ Response SLA</span>
        <span className={`sla-chip sla-chip-${selectedTicket.sla?.response_status || (selectedTicket.responded_at ? 'met' : selectedTicket.sla_status || 'on_track')}`}>
          {(selectedTicket.sla?.response_status || (selectedTicket.responded_at ? 'met' : selectedTicket.sla_status || 'on_track')).replace('_', ' ').toUpperCase()}
        </span>
      </div>

      <div className="sla-card-body">
        <div className="sla-metric-row">
          <span>Target Window:</span>
          <strong>{selectedTicket.sla?.response_sla || (selectedTicket.priority === 'critical' ? '15m' : selectedTicket.priority === 'high' ? '30m' : selectedTicket.priority === 'low' ? '4h' : '1h')}</strong>
        </div>

        <div className="sla-metric-row">
          <span>Deadline:</span>
          <strong>
            {selectedTicket.response_due_at || selectedTicket.sla?.response_due_at
              ? new Date(selectedTicket.response_due_at || selectedTicket.sla?.response_due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
              : 'Auto-calculated'}
          </strong>
        </div>

        <div className="sla-metric-row sla-metric-highlight">
          <span>Timer / Status:</span>
          <strong className="sla-countdown-text">
            {selectedTicket.responded_at
              ? `Responded (${new Date(selectedTicket.responded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`
              : selectedTicket.sla?.response_remaining_label || (selectedTicket.status !== 'new' ? 'Responded' : 'Active Countdown')}
          </strong>
        </div>
      </div>
    </div>

    {/* Resolution SLA Card */}
    <div className={`sla-metric-card sla-card-${selectedTicket.sla?.resolution_status || (selectedTicket.status === 'resolved' ? 'met' : selectedTicket.sla_status || 'on_track')}`}>
      <div className="sla-card-header">
        <span className="sla-card-type">🎯 Resolution SLA</span>
        <span className={`sla-chip sla-chip-${selectedTicket.sla?.resolution_status || (selectedTicket.status === 'resolved' ? 'met' : selectedTicket.sla_status || 'on_track')}`}>
          {(selectedTicket.sla?.resolution_status || (selectedTicket.status === 'resolved' ? 'met' : selectedTicket.sla_status || 'on_track')).replace('_', ' ').toUpperCase()}
        </span>
      </div>

      <div className="sla-card-body">
        <div className="sla-metric-row">
          <span>Target Window:</span>
          <strong>{selectedTicket.sla?.resolution_sla || (selectedTicket.priority === 'critical' ? '2h' : selectedTicket.priority === 'high' ? '4h' : selectedTicket.priority === 'low' ? '24h' : '8h')}</strong>
        </div>

        <div className="sla-metric-row">
          <span>Deadline:</span>
          <strong>
            {selectedTicket.resolution_due_at || selectedTicket.sla?.resolution_due_at
              ? new Date(selectedTicket.resolution_due_at || selectedTicket.sla?.resolution_due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
              : 'Auto-calculated'}
          </strong>
        </div>

        <div className="sla-metric-row sla-metric-highlight">
          <span>Timer / Status:</span>
          <strong className="sla-countdown-text">
            {selectedTicket.resolved_at
              ? `Resolved (${new Date(selectedTicket.resolved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`
              : selectedTicket.sla?.resolution_remaining_label || (selectedTicket.status === 'resolved' ? 'Resolved' : 'Active Countdown')}
          </strong>
        </div>
      </div>
    </div>
  </div>

  <div className="sla-policy-footnote">
    <span>ℹ️ SLA Policy: Critical (15m resp / 2h res) • High (30m resp / 4h res) • Medium (1h resp / 8h res) • Low (4h resp / 24h res)</span>
  </div>
</div>

{/* 3. Alerts & Notifications Panel for this Ticket */}
<div className="ticket-alerts-panel">
  <div className="ticket-alerts-header">
    <div>
      <h3>Alerts & Notifications</h3>
      <p>System alerts, SLA threshold warnings, and escalations recorded for this ticket</p>
    </div>

    <span className={`alerts-summary-pill ${ticketNotifications.some(n => n.severity === 'critical') ? 'pill-critical' : ticketNotifications.some(n => n.severity === 'warning') ? 'pill-warning' : 'pill-info'}`}>
      {ticketNotifications.length} {ticketNotifications.length === 1 ? 'EVENT' : 'EVENTS'}
    </span>
  </div>

  <div className="ticket-alerts-content">
    {ticketNotifications.length === 0 ? (
      <div className="ticket-alerts-empty">
        <span className="alerts-empty-icon">✓</span>
        <p>No active alerts, SLA breaches, or escalations recorded for this ticket.</p>
      </div>
    ) : (
      <div className="ticket-alerts-timeline">
        {ticketNotifications.map((alert) => (
          <div
            key={alert.id}
            className={`ticket-alert-row severity-${alert.severity}`}
          >
            <div className="alert-row-icon">
              {alert.type === "ESCALATION" ? "🚨" :
               alert.type === "SLA_BREACHED" ? "🔴" :
               alert.type === "SLA_AT_RISK" ? "⚠️" :
               alert.type === "PRIORITY_CHANGED" ? "⚡" :
               alert.type === "TICKET_ASSIGNED" ? "📌" : "ℹ️"}
            </div>

            <div className="alert-row-body">
              <div className="alert-row-header">
                <strong>{alert.title}</strong>
                <span className="alert-row-time">
                  {alert.created_at ? new Date(alert.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : ""}
                </span>
              </div>

              <p className="alert-row-msg">{alert.message}</p>

              <div className="alert-row-tags">
                <span className={`alert-type-badge type-${alert.type.toLowerCase()}`}>
                  {alert.type.replace(/_/g, ' ')}
                </span>
                <span className={`alert-sev-badge sev-${alert.severity}`}>
                  {alert.severity.toUpperCase()}
                </span>
                {alert.is_read ? (
                  <span className="alert-read-badge">Read</span>
                ) : (
                  <span className="alert-unread-badge">Unread</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
</div>

<div className="routing-analysis">
  <div className="routing-analysis-header">
    <div>
      <h3>Routing Analysis</h3>
      <p>
        Why this ticket was routed to the assigned team
      </p>
    </div>

   <span className="analysis-badge">
  {routingAnalysis?.routingMethod === "manual"
    ? "MANUAL"
    : "AUTOMATED"}
</span>
  </div>

  <div className="analysis-content">

    <div className="analysis-item">
      <span>Matched Rule</span>
      <strong>
        {routingAnalysis?.rule || "General"}
      </strong>
    </div>

    <div className="analysis-item">
      <span>Matched Keywords</span>

      <div className="analysis-keywords">
        {routingAnalysis?.matchedKeywords?.length > 0 ? (
          routingAnalysis.matchedKeywords.map(
            (keyword, index) => (
              <span
                key={index}
                className="analysis-keyword"
              >
                {keyword}
              </span>
            )
          )
        ) : (
          <span>No matching keywords</span>
        )}
      </div>
    </div>

    <div className="analysis-item">
      <span>Match Location</span>

      <strong>
        {routingAnalysis?.matchLocation ===
        "title_and_description"
          ? "Title + Description"
          : routingAnalysis?.matchLocation === "title"
          ? "Title"
          : routingAnalysis?.matchLocation === "description"
          ? "Description"
          : "None"}
      </strong>
    </div>

    <div className="analysis-item analysis-reason">
      <span>Routing Reason</span>

      <p>
        {routingAnalysis?.reason ||
          "No routing information available."}
      </p>
    </div>

  </div>
</div>

{/* ========================================================================= */}
{/* RESOLUTION WORKFLOW SECTION */}
{/* ========================================================================= */}
<div className="ticket-resolution-panel">
  <div className="resolution-panel-header">
    <div>
      <h3>Ticket Resolution Workflow</h3>
      <p>Document root cause, actions taken, and mark ticket as resolved</p>
    </div>
    {selectedTicket.status === "resolved" ? (
      <span className="res-status-pill pill-resolved">✅ RESOLVED</span>
    ) : (
      <span className="res-status-pill pill-active">⚡ ACTIVE WORK</span>
    )}
  </div>

  {selectedTicket.status === "resolved" ? (
    <div className="resolved-summary-box">
      <div className="resolved-banner">
        <span className="resolved-banner-icon">✓</span>
        <div className="resolved-banner-text">
          <h4>Ticket Successfully Resolved</h4>
          <p className="resolved-timestamp">
            Resolved on {selectedTicket.resolved_at ? new Date(selectedTicket.resolved_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Recently"}
          </p>
        </div>
        <button
          className="reopen-ticket-btn"
          onClick={handleReopenTicket}
          title="Reopen ticket for further investigation"
        >
          ↻ Reopen Ticket
        </button>
      </div>

      {selectedTicket.resolution_summary && (
        <div className="res-field-display">
          <span>Resolution Summary:</span>
          <strong>{selectedTicket.resolution_summary}</strong>
        </div>
      )}

      {selectedTicket.resolution_details && (
        <div className="res-field-display">
          <span>Technical Resolution Details:</span>
          <p>{selectedTicket.resolution_details}</p>
        </div>
      )}
    </div>
  ) : (
    <form className="resolution-form" onSubmit={handleResolveTicket}>
      <div className="form-group">
        <label>Resolution Summary *</label>
        <input
          type="text"
          placeholder="Brief summary of resolution (e.g., Replaced failed NIC cable, reset MFA token)..."
          value={resolutionSummary}
          onChange={(e) => setResolutionSummary(e.target.value)}
          required
        />
      </div>

      <div className="form-group">
        <label>Resolution Details / Root Cause (Optional)</label>
        <textarea
          rows={3}
          placeholder="Detailed description of troubleshooting steps, root cause analysis, and preventative recommendations..."
          value={resolutionDetails}
          onChange={(e) => setResolutionDetails(e.target.value)}
        />
      </div>

      <div className="resolution-form-actions">
        <button
          type="submit"
          className="resolve-submit-btn"
          disabled={resolvingTicket}
        >
          {resolvingTicket ? "Resolving Ticket..." : "✓ Complete & Resolve Ticket"}
        </button>
      </div>
    </form>
  )}
</div>

{/* ========================================================================= */}
{/* WORK NOTES & CUSTOMER UPDATES SECTION */}
{/* ========================================================================= */}
<div className="ticket-notes-panel">
  <div className="notes-panel-header">
    <div>
      <h3>Work Notes & Customer Updates</h3>
      <p>Internal technician annotations and customer-facing communication</p>
    </div>

    <div className="notes-tabs">
      <button
        type="button"
        className={`notes-tab ${notesFilter === "all" ? "active" : ""}`}
        onClick={() => setNotesFilter("all")}
      >
        All Notes ({notes.length})
      </button>
      <button
        type="button"
        className={`notes-tab ${notesFilter === "internal" ? "active" : ""}`}
        onClick={() => setNotesFilter("internal")}
      >
        🔒 Internal ({notes.filter((n) => n.note_type === "internal").length})
      </button>
      <button
        type="button"
        className={`notes-tab ${notesFilter === "customer" ? "active" : ""}`}
        onClick={() => setNotesFilter("customer")}
      >
        📢 Customer ({notes.filter((n) => n.note_type === "customer").length})
      </button>
    </div>
  </div>

  {/* Add Note Form */}
  <form className="add-note-form" onSubmit={handleAddNote}>
    <div className="note-type-toggle">
      <button
        type="button"
        className={`type-toggle-btn type-internal ${newNoteType === "internal" ? "selected" : ""}`}
        onClick={() => setNewNoteType("internal")}
      >
        🔒 Internal Work Note <small>(Technician Only)</small>
      </button>
      <button
        type="button"
        className={`type-toggle-btn type-customer ${newNoteType === "customer" ? "selected" : ""}`}
        onClick={() => setNewNoteType("customer")}
      >
        📢 Customer Update <small>(Public)</small>
      </button>
    </div>

    <div className="note-inputs-row">
      <textarea
        className={`note-textarea ${newNoteType === "internal" ? "textarea-internal" : "textarea-customer"}`}
        rows={3}
        placeholder={
          newNoteType === "internal"
            ? "Write an internal technical note (visible to technicians only)..."
            : "Write an update for the customer regarding this ticket..."
        }
        value={newNoteContent}
        onChange={(e) => setNewNoteContent(e.target.value)}
        required
      />
    </div>

    <div className="note-form-footer">
      <div className="author-input-wrapper">
        <span>Author:</span>
        <div className="author-identity-pill" title="Author is automatically stamped from your authenticated session">
          <span className="author-icon">👤</span>
          <strong className="author-name">{auth?.user?.name || newNoteAuthor || "MSP Technician"}</strong>
          {auth?.user?.role && (
            <span className={`author-role-chip role-${auth.user.role}`}>
              {auth.user.role}
            </span>
          )}
        </div>
      </div>

      <button
        type="submit"
        className={`post-note-btn ${newNoteType === "internal" ? "btn-post-internal" : "btn-post-customer"}`}
        disabled={postingNote || !newNoteContent.trim()}
      >
        {postingNote
          ? "Posting..."
          : newNoteType === "internal"
          ? "🔒 Add Work Note"
          : "📢 Send Customer Update"}
      </button>
    </div>
  </form>

  {/* Notes List */}
  <div className="notes-list">
    {notesLoading ? (
      <div className="notes-loading">Loading notes...</div>
    ) : filteredNotes.length === 0 ? (
      <div className="notes-empty">
        <span>📝</span>
        <p>No notes found for this filter.</p>
      </div>
    ) : (
      filteredNotes.map((note) => {
        const isInternal = note.note_type === "internal";
        const isEditing = editingNoteId === note.id;

        return (
          <div
            key={note.id}
            className={`note-card ${isInternal ? "note-internal" : "note-customer"}`}
          >
            <div className="note-card-header">
              <div className="note-author-group">
                <span className={`note-type-badge ${isInternal ? "badge-internal" : "badge-customer"}`}>
                  {isInternal ? "🔒 INTERNAL WORK NOTE" : "📢 CUSTOMER UPDATE"}
                </span>
                <strong className="note-author">{note.author}</strong>
              </div>

              <div className="note-meta-actions">
                <span className="note-date">
                  {note.created_at
                    ? new Date(note.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })
                    : ""}
                </span>
                <button
                  type="button"
                  className="note-action-link"
                  onClick={() => {
                    setEditingNoteId(note.id);
                    setEditingContent(note.content);
                  }}
                  title="Edit note"
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="note-action-link link-delete"
                  onClick={() => handleDeleteNote(note.id)}
                  title="Delete note"
                >
                  Delete
                </button>
              </div>
            </div>

            {isEditing ? (
              <div className="note-edit-box">
                <textarea
                  rows={3}
                  value={editingContent}
                  onChange={(e) => setEditingContent(e.target.value)}
                />
                <div className="note-edit-btns">
                  <button
                    type="button"
                    className="save-edit-btn"
                    onClick={() => handleUpdateNote(note.id)}
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    className="cancel-edit-btn"
                    onClick={() => {
                      setEditingNoteId(null);
                      setEditingContent("");
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="note-content-text">{note.content}</p>
            )}
          </div>
        );
      })
    )}
  </div>
</div>
 
{/* ========================================================================= */}
{/* ACTIVITY TIMELINE */}
{/* ========================================================================= */}
<div className="activity-panel">
  <div className="activity-header">
    <div>
      <h3>Activity Timeline</h3>
      <p>Complete activity history for this ticket</p>
    </div>

    <span className="analysis-badge">
      {activityHistory.length} EVENTS
    </span>
  </div>

  <div className="activity-content">
    {activityHistory.length === 0 ? (
      <div className="activity-empty">
        No activity recorded yet.
      </div>
    ) : (
      activityHistory.map((activity) => {
        const isManual = activity.routing_method === "manual";
        const isStatusChange = activity.routing_method === "status_update";

        let activityTitle = activity.rule || "Automated Routing";
        let markerIcon = "⚙";

        if (activity.rule === "Work Note Added") {
          activityTitle = "Internal Work Note Added";
          markerIcon = "🔒";
        } else if (activity.rule === "Customer Update Added") {
          activityTitle = "Customer Update Added";
          markerIcon = "📢";
        } else if (activity.rule === "Technician Assigned") {
          activityTitle = "Technician Assigned";
          markerIcon = "👤";
        } else if (activity.rule === "Technician Unassigned") {
          activityTitle = "Technician Unassigned";
          markerIcon = "👤";
        } else if (activity.rule === "Ticket Escalated") {
          activityTitle = "Ticket Escalated";
          markerIcon = "🔥";
        } else if (activity.rule === "Ticket Resolved") {
          activityTitle = "Ticket Resolved";
          markerIcon = "✅";
        } else if (activity.rule === "Ticket Reopened") {
          activityTitle = "Ticket Reopened";
          markerIcon = "↻";
        } else if (activity.rule === "Response SLA Breached" || activity.rule === "Resolution SLA Breached") {
          activityTitle = activity.rule;
          markerIcon = "🚨";
        } else if (activity.rule === "Escalation Triggered") {
          activityTitle = "Escalation Triggered";
          markerIcon = "🔥";
        } else if (isStatusChange) {
          activityTitle = "Status Change";
          markerIcon = "↻";
        } else if (isManual) {
          activityTitle = "Manual Reassignment";
          markerIcon = "👤";
        }

        return (
          <div
            className="activity-item"
            key={activity.id}
          >
            <div className="activity-marker">
              {markerIcon}
            </div>

            <div className="activity-details">
              <div className="activity-top">
                <strong>
                  {activityTitle}
                </strong>

                <span>
                  {activity.created_at
                    ? new Date(
                        activity.created_at
                      ).toLocaleString()
                    : ""}
                </span>
              </div>

              <div className="activity-info">
                <span>Team</span>
                <strong>
                  {activity.team}
                </strong>
              </div>

              <div className="activity-info">
                <span>Priority</span>
                <strong className={`priority ${activity.priority}`}>
                  {activity.priority?.toUpperCase()}
                </strong>
              </div>

              <p className="activity-reason">
                {activity.reason ||
                  "No activity description available."}
              </p>
            </div>
          </div>
        );
      })
    )}
  </div>
</div>
        <div className="detail-item">
          <span>Source / Channel</span>
          <strong>
            {selectedTicket.source === "email" ? (
              <span className="source-badge-email" style={{ fontSize: "12px", padding: "3px 8px" }}>
                📧 Email ({selectedTicket.email_sender || selectedTicket.customer_email || "Incoming"})
              </span>
            ) : (
              <span className="source-badge-portal" style={{ fontSize: "12px", padding: "3px 8px" }}>
                🌐 Client Portal / Internal
              </span>
            )}
          </strong>
        </div>

        {selectedTicket.customer_company && (
          <div className="detail-item">
            <span>Customer Organization</span>
            <strong>
              🏢 {selectedTicket.customer_company} ({selectedTicket.customer_name || "Account"})
            </strong>
          </div>
        )}

        <div className="detail-item">
          <span>Routing Method</span>
          <strong>
            {selectedTicket.routing_method}
          </strong>
        </div>

        <div className="detail-item">
          <span>Ticket ID</span>
          <strong>
            #{selectedTicket.id}
          </strong>
        </div>

      </div>

    </div>

  </section>
)}
{currentPage === "analytics" && (
  <section className="analytics-section">

    <div className="analytics-intro-header">
      <div className="analytics-intro">
        <h2>Operational Analytics</h2>
        <p>
          Real-time performance metrics, ticket routing intelligence, and workload distribution.
        </p>
      </div>

      <button
        className="analytics-refresh-button"
        onClick={loadAnalytics}
        disabled={analyticsLoading}
      >
        {analyticsLoading ? "Refreshing..." : "↻ Refresh Metrics"}
      </button>
    </div>

    {analyticsLoading && !analytics ? (
      <div className="analytics-loading">
        Loading analytics from database...
      </div>
    ) : analytics ? (

      <>
        {/* 1. Main KPI summary cards */}
        <div className="analytics-cards analytics-cards-sla">

          <div className="analytics-card">
            <span>Total Tickets</span>
            <strong>
              {analytics.total_tickets}
            </strong>
            <small>
              All processed tickets
            </small>
          </div>

          <div className="analytics-card sla-compliance-card">
            <span>SLA Compliance</span>
            <strong className={(analytics.sla_compliance_rate || 0) >= 80 ? "sla-good" : (analytics.sla_compliance_rate || 0) >= 50 ? "sla-warning" : "sla-danger"}>
              {analytics.sla_compliance_rate}%
            </strong>
            <small>
              {analytics.total_tickets - (analytics.total_breached_tickets || 0)} of {analytics.total_tickets} met/compliant
            </small>
          </div>

          <div className="analytics-card sla-breached-card">
            <span>SLA Breaches</span>
            <strong className="critical">
              {analytics.total_breached_tickets || 0}
            </strong>
            <small>
              Target deadlines missed
            </small>
          </div>

          <div className="analytics-card sla-at-risk-card">
            <span>At Risk Tickets</span>
            <strong className="warning">
              {analytics.total_at_risk_tickets || 0}
            </strong>
            <small>
              Near breach deadline
            </small>
          </div>

          <div className="analytics-card">
            <span>Avg Response</span>
            <strong className="highlight">
              {analytics.avg_response_time_label || "N/A"}
            </strong>
            <small>
              First response speed
            </small>
          </div>

          <div className="analytics-card">
            <span>Avg Resolution</span>
            <strong className="resolved-highlight">
              {analytics.avg_resolution_time_label || "N/A"}
            </strong>
            <small>
              Average resolution time
            </small>
          </div>

          <div className="analytics-card">
            <span>Automation Rate</span>
            <strong className="automation-highlight">
              {analytics.automation_rate}%
            </strong>
            <small>
              {analytics.automated_count || 0} of {analytics.total_tickets} automated
            </small>
          </div>

        </div>


        {/* 2. SLA Management & Breach Detection Overview Panel */}
        <div className="analytics-panel sla-analytics-panel">
          <div className="panel-header">
            <div>
              <h3>SLA Management & Breach Detection</h3>
              <p className="panel-subtitle">Performance compliance across response and resolution deadlines</p>
            </div>
            <span className={`panel-badge ${analytics.total_breached_tickets > 0 ? 'badge-danger' : 'badge-success'}`}>
              {analytics.total_breached_tickets > 0 ? `${analytics.total_breached_tickets} BREACHED` : 'ALL COMPLIANT'}
            </span>
          </div>

          <div className="sla-overview-grid">
            <div className="sla-overview-status-cards">
              <div className="sla-status-box sla-box-met">
                <div className="sla-box-icon">✓</div>
                <div className="sla-box-content">
                  <span>SLA Met</span>
                  <strong>{analytics.total_met_tickets || 0}</strong>
                  <small>Completed on time</small>
                </div>
              </div>

              <div className="sla-status-box sla-box-ontrack">
                <div className="sla-box-icon">⏱</div>
                <div className="sla-box-content">
                  <span>On Track</span>
                  <strong>{analytics.total_on_track_tickets || 0}</strong>
                  <small>Active within target</small>
                </div>
              </div>

              <div className="sla-status-box sla-box-atrisk">
                <div className="sla-box-icon">⚠️</div>
                <div className="sla-box-content">
                  <span>At Risk</span>
                  <strong>{analytics.total_at_risk_tickets || 0}</strong>
                  <small>&le; 25% window remaining</small>
                </div>
              </div>

              <div className="sla-status-box sla-box-breached">
                <div className="sla-box-icon">🚨</div>
                <div className="sla-box-content">
                  <span>Breached</span>
                  <strong>{analytics.total_breached_tickets || 0}</strong>
                  <small>Deadline exceeded</small>
                </div>
              </div>
            </div>

            <div className="sla-priority-matrix">
              <h4>SLA Performance by Priority Level</h4>
              <div className="sla-matrix-list">
                {[
                  { label: "Critical (15m resp / 2h res)", key: "critical", badgeClass: "priority critical" },
                  { label: "High (30m resp / 4h res)", key: "high", badgeClass: "priority high" },
                  { label: "Medium (1h resp / 8h res)", key: "medium", badgeClass: "priority medium" },
                  { label: "Low (4h resp / 24h res)", key: "low", badgeClass: "priority low" },
                ].map(({ label, key, badgeClass }) => {
                  const pData = analytics.sla_by_priority?.[key] || { on_track: 0, at_risk: 0, breached: 0, met: 0 };
                  const totalP = (pData.on_track || 0) + (pData.at_risk || 0) + (pData.breached || 0) + (pData.met || 0);

                  return (
                    <div className="sla-matrix-row" key={key}>
                      <div className="sla-matrix-label">
                        <span className={badgeClass}>{key.toUpperCase()}</span>
                        <small>{label}</small>
                      </div>

                      <div className="sla-matrix-badges">
                        {totalP === 0 ? (
                          <span className="sla-matrix-empty">No tickets</span>
                        ) : (
                          <>
                            {pData.met > 0 && <span className="sla-matrix-tag tag-met">{pData.met} Met</span>}
                            {pData.on_track > 0 && <span className="sla-matrix-tag tag-ontrack">{pData.on_track} On Track</span>}
                            {pData.at_risk > 0 && <span className="sla-matrix-tag tag-atrisk">{pData.at_risk} At Risk</span>}
                            {pData.breached > 0 && <span className="sla-matrix-tag tag-breached">{pData.breached} Breached</span>}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Notifications & Escalation Intelligence Panel */}
        <div className="analytics-panel notif-analytics-panel">
          <div className="panel-header">
            <div>
              <h3>Notifications & Escalations</h3>
              <p className="panel-subtitle">Real-time alert volume, critical escalations, and severity breakdown</p>
            </div>
            <span className={`panel-badge ${analytics.escalations_count > 0 ? 'badge-danger' : analytics.unread_notifications > 0 ? 'badge-warning' : 'badge-info'}`}>
              {analytics.total_notifications || 0} TOTAL ALERTS
            </span>
          </div>

          <div className="notif-analytics-grid">
            <div className="notif-stat-cards">
              <div className="notif-kpi-box box-total">
                <span className="kpi-icon">🔔</span>
                <div className="kpi-info">
                  <span className="kpi-label">Total Alerts</span>
                  <strong className="kpi-value">{analytics.total_notifications || 0}</strong>
                  <small className="kpi-sub">All system events</small>
                </div>
              </div>

              <div className="notif-kpi-box box-unread">
                <span className="kpi-icon">📬</span>
                <div className="kpi-info">
                  <span className="kpi-label">Unread Alerts</span>
                  <strong className="kpi-value">{analytics.unread_notifications || 0}</strong>
                  <small className="kpi-sub">Awaiting review</small>
                </div>
              </div>

              <div className="notif-kpi-box box-atrisk">
                <span className="kpi-icon">⚠️</span>
                <div className="kpi-info">
                  <span className="kpi-label">SLA At-Risk</span>
                  <strong className="kpi-value">{analytics.sla_at_risk_alerts || 0}</strong>
                  <small className="kpi-sub">Warning alerts</small>
                </div>
              </div>

              <div className="notif-kpi-box box-breach">
                <span className="kpi-icon">🔴</span>
                <div className="kpi-info">
                  <span className="kpi-label">SLA Breaches</span>
                  <strong className="kpi-value">{analytics.sla_breaches_alerts || 0}</strong>
                  <small className="kpi-sub">Missed SLA alerts</small>
                </div>
              </div>

              <div className="notif-kpi-box box-escalation">
                <span className="kpi-icon">🚨</span>
                <div className="kpi-info">
                  <span className="kpi-label">Escalations</span>
                  <strong className="kpi-value">{analytics.escalations_count || 0}</strong>
                  <small className="kpi-sub">Automatic escalations</small>
                </div>
              </div>
            </div>

            <div className="notif-severity-panel">
              <h4>Alert Severity & Event Breakdown</h4>
              <div className="notif-severity-bars">
                {[
                  { label: "Critical Severity (Breaches & Escalations)", count: analytics.notifications_by_severity?.critical || 0, colorClass: "critical-bar" },
                  { label: "Warning Severity (SLA At-Risk & High Priority)", count: analytics.notifications_by_severity?.warning || 0, colorClass: "warning-bar" },
                  { label: "Info Severity (Assignments & Status Changes)", count: analytics.notifications_by_severity?.info || 0, colorClass: "info-bar" },
                ].map((item, idx) => {
                  const totalN = analytics.total_notifications || 0;
                  const pct = totalN > 0 ? Math.round((item.count / totalN) * 100) : 0;
                  return (
                    <div className="bar-item" key={idx}>
                      <div className="bar-header">
                        <span>{item.label}</span>
                        <span className="bar-count">{item.count} ({pct}%)</span>
                      </div>
                      <div className="bar-track">
                        <div className={`bar-fill ${item.colorClass}`} style={{ width: `${pct}%` }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* 4. Row 1: Priority Distribution + Category Distribution */}
        <div className="analytics-grid">

          <div className="analytics-panel">
            <div className="panel-header">
              <h3>Tickets by Priority</h3>
              <span className="panel-badge">
                {analytics.total_tickets} TOTAL
              </span>
            </div>

            <div className="bar-list">
              {[
                ["Critical", "critical", "critical-bar"],
                ["High", "high", "high-bar"],
                ["Medium", "medium", "medium-bar"],
                ["Low", "low", "low-bar"]
              ].map(([label, key, barClass]) => {
                const count = analytics.tickets_by_priority?.[key] || 0;
                const percentage = analytics.total_tickets > 0
                  ? Math.round((count / analytics.total_tickets) * 100)
                  : 0;

                return (
                  <div className="bar-item" key={key}>
                    <div className="bar-label">
                      <span>{label}</span>
                      <strong>{count} <small>({percentage}%)</small></strong>
                    </div>

                    <div className="bar-background">
                      <div
                        className={`bar ${barClass}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>


          <div className="analytics-panel">
            <div className="panel-header">
              <h3>Tickets by Category</h3>
              <span className="panel-badge">
                {Object.keys(analytics.tickets_by_category || {}).length} CATEGORIES
              </span>
            </div>

            {Object.keys(analytics.tickets_by_category || {}).length === 0 ? (
              <div className="activity-empty">No category data available.</div>
            ) : (
              <div className="bar-list">
                {Object.entries(analytics.tickets_by_category || {})
                  .sort(([, a], [, b]) => b - a)
                  .map(([category, count]) => {
                    const percentage = analytics.total_tickets > 0
                      ? Math.round((count / analytics.total_tickets) * 100)
                      : 0;

                    return (
                      <div className="bar-item" key={category}>
                        <div className="bar-label">
                          <span>{category}</span>
                          <strong>{count} <small>({percentage}%)</small></strong>
                        </div>

                        <div className="bar-background">
                          <div
                            className="bar category-bar"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>

        </div>


        {/* 3. Row 2: Assigned Team + Ticket Status */}
        <div className="analytics-grid">

          <div className="analytics-panel">
            <div className="panel-header">
              <h3>Tickets by Assigned Team</h3>
              <span className="panel-badge">
                {Object.keys(analytics.tickets_by_team || {}).length} TEAMS
              </span>
            </div>

            {Object.keys(analytics.tickets_by_team || {}).length === 0 ? (
              <div className="activity-empty">No team assignments yet.</div>
            ) : (
              <div className="team-list">
                {Object.entries(analytics.tickets_by_team || {})
                  .sort(([, a], [, b]) => b - a)
                  .map(([team, count]) => {
                    const percentage = analytics.total_tickets > 0
                      ? Math.round((count / analytics.total_tickets) * 100)
                      : 0;

                    return (
                      <div className="team-row-analytics" key={team}>
                        <div className="team-info-left">
                          <span className="team-name">{team}</span>
                          <div className="team-bar-mini">
                            <div
                              className="team-bar-fill"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                        <div className="team-info-right">
                          <strong>{count}</strong>
                          <small>{percentage}%</small>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>


          <div className="analytics-panel">
            <div className="panel-header">
              <h3>Tickets by Status</h3>
              <span className="panel-badge">LIFECYCLE</span>
            </div>

            <div className="status-analytics-container">
              {[
                { label: "New", key: "new", class: "status-new-card", dotClass: "dot-new", barClass: "bar-new" },
                { label: "In Progress", key: "in_progress", class: "status-inprogress-card", dotClass: "dot-inprogress", barClass: "bar-inprogress" },
                { label: "Resolved", key: "resolved", class: "status-resolved-card", dotClass: "dot-resolved", barClass: "bar-resolved" }
              ].map(({ label, key, class: cardClass, dotClass, barClass }) => {
                const count = analytics.tickets_by_status?.[key] || 0;
                const percentage = analytics.total_tickets > 0
                  ? Math.round((count / analytics.total_tickets) * 100)
                  : 0;

                return (
                  <div className={`status-kpi-card ${cardClass}`} key={key}>
                    <div className="status-card-header">
                      <span className={`status-dot-indicator ${dotClass}`} />
                      <span className="status-kpi-title">{label}</span>
                      <strong className="status-kpi-number">{count}</strong>
                    </div>

                    <div className="status-progress-track">
                      <div
                        className={`status-progress-bar ${barClass}`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>

                    <div className="status-card-footer">
                      <small>{percentage}% of all tickets</small>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>


        {/* 4. Row 3: Routing Distribution + System Insights */}
        <div className="analytics-grid">

          <div className="analytics-panel">
            <div className="panel-header">
              <h3>Routing Method Distribution</h3>
              <span className="panel-badge">DECISIONS</span>
            </div>

            <div className="routing-methods-list">
              <div className="routing-method-card">
                <div className="routing-method-header">
                  <div>
                    <strong>Rule Engine (Automated)</strong>
                    <p>Deterministic keyword & rule matches</p>
                  </div>
                  <div className="routing-method-stats">
                    <span className="routing-count">{analytics.automated_count || 0}</span>
                    <span className="routing-share">{analytics.automation_rate}%</span>
                  </div>
                </div>
                <div className="bar-background">
                  <div
                    className="bar automated-bar"
                    style={{ width: `${analytics.automation_rate}%` }}
                  />
                </div>
              </div>

              <div className="routing-method-card">
                <div className="routing-method-header">
                  <div>
                    <strong>Manual Assignment</strong>
                    <p>Operator reassigned or overridden</p>
                  </div>
                  <div className="routing-method-stats">
                    <span className="routing-count">{analytics.manual_count || 0}</span>
                    <span className="routing-share">
                      {analytics.total_tickets > 0
                        ? Math.round(((analytics.manual_count || 0) / analytics.total_tickets) * 100)
                        : 0}%
                    </span>
                  </div>
                </div>
                <div className="bar-background">
                  <div
                    className="bar manual-bar"
                    style={{
                      width: `${
                        analytics.total_tickets > 0
                          ? Math.round(((analytics.manual_count || 0) / analytics.total_tickets) * 100)
                          : 0
                      }%`
                    }}
                  />
                </div>
              </div>
            </div>

            <div className="automation-summary-footer">
              <strong>Automation Efficiency: {analytics.automation_rate}%</strong>
              <small>
                {analytics.automated_count || 0} tickets auto-routed with zero manual intervention required.
              </small>
            </div>
          </div>


          <div className="analytics-panel">
            <div className="panel-header">
              <h3>System Insights</h3>
              <span className="insights-badge">INTELLIGENCE</span>
            </div>

            <div className="insights-list">
              {analytics.insights?.length > 0 ? (
                analytics.insights.map((insight, index) => (
                  <div className="insight-item" key={index}>
                    <div className="insight-icon">✓</div>
                    <p>{insight}</p>
                  </div>
                ))
              ) : (
                <div className="insight-item">
                  <div className="insight-icon">✓</div>
                  <p>No insights available yet.</p>
                </div>
              )}
            </div>
          </div>

        </div>


        {/* 5. Row 4: Recent Ticket Activity Feed */}
        <div className="analytics-panel recent-activity-section">
          <div className="panel-header">
            <div>
              <h3>Recent Ticket Activity</h3>
              <p className="panel-subtitle">Latest routing and lifecycle events across all tickets</p>
            </div>
            <span className="panel-badge">
              {analytics.recent_activity?.length || 0} RECENT EVENTS
            </span>
          </div>

          {!analytics.recent_activity || analytics.recent_activity.length === 0 ? (
            <div className="activity-empty">No activity recorded yet.</div>
          ) : (
            <div className="recent-activity-table">
              <div className="activity-table-header">
                <span>EVENT</span>
                <span>TICKET</span>
                <span>TEAM</span>
                <span>PRIORITY</span>
                <span>REASON / DETAILS</span>
                <span>TIME</span>
              </div>

              {analytics.recent_activity.map((event) => {
                const isManual = event.routing_method === "manual";
                const isStatusChange = event.routing_method === "status_update";
                const isPriorityChange = event.routing_method === "priority_update";

                let eventLabel = "Auto-Routed";
                let eventIcon = "⚙";
                let eventClass = "event-automated";

                if (isManual) {
                  eventLabel = "Manual";
                  eventIcon = "👤";
                  eventClass = "event-manual";
                } else if (isStatusChange) {
                  eventLabel = "Status";
                  eventIcon = "↻";
                  eventClass = "event-status";
                } else if (isPriorityChange) {
                  eventLabel = "Priority";
                  eventIcon = "⚡";
                  eventClass = "event-priority";
                }

                return (
                  <div className="activity-table-row" key={event.id}>
                    <div className="activity-event-type">
                      <span className={`activity-event-badge ${eventClass}`}>
                        {eventIcon} {eventLabel}
                      </span>
                    </div>

                    <span className="activity-ticket-id">
                      #{event.ticket_id}
                    </span>

                    <span className="activity-team">
                      {event.team}
                    </span>

                    <span className={`priority ${event.priority}`}>
                      {event.priority}
                    </span>

                    <span className="activity-reason-text">
                      {event.reason || `${event.rule || "General"} rule applied`}
                    </span>

                    <span className="activity-time">
                      {event.created_at
                        ? new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })
                        : "Just now"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </>

    ) : (
      <div className="analytics-loading">
        No analytics data available.
      </div>
    )}

  </section>
)}

{/* ========================================================================= */}
{/* 6. REPORTS VIEW (Phase 6: Executive & Client SLA Reporting) */}
{/* ========================================================================= */}
{currentPage === "reports" && (
  <section className="reports-section">
    <div className="reports-header-card">
      <div className="reports-header-left">
        <h2>Executive &amp; Client SLA Reporting</h2>
        <p>Comprehensive service performance metrics, SLA compliance audits, and scheduled exports for internal and client reviews.</p>
      </div>
      <div className="reports-header-actions">
        <button
          className="btn-report-export btn-export-pdf"
          onClick={() => downloadReportFile("pdf", false)}
          disabled={reportsLoading}
          title="Download executive-ready PDF report"
        >
          📄 Export Executive PDF
        </button>
        <button
          className="btn-report-export btn-export-csv"
          onClick={() => downloadReportFile("csv", false)}
          disabled={reportsLoading}
          title="Export sanitized CSV ticket data"
        >
          📊 Export CSV
        </button>
      </div>
    </div>

    {/* Filter Toolbar */}
    <div className="reports-filter-bar">
      <div className="reports-filter-group">
        <label>Timeframe</label>
        <div className="quick-date-chips">
          {[
            { id: "all", label: "All Time" },
            { id: "today", label: "Today" },
            { id: "7d", label: "Last 7 Days" },
            { id: "30d", label: "Last 30 Days" },
            { id: "this_month", label: "This Month" },
          ].map((c) => (
            <button
              key={c.id}
              type="button"
              className={`chip-btn ${reportFilters.quickRange === c.id ? "active" : ""}`}
              onClick={() => applyQuickDateRange(c.id, false)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="reports-filter-row">
        <div className="reports-filter-item">
          <label>From Date</label>
          <input
            type="date"
            value={reportFilters.startDate}
            onChange={(e) => {
              const updated = { ...reportFilters, startDate: e.target.value, quickRange: "custom" };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          />
        </div>

        <div className="reports-filter-item">
          <label>To Date</label>
          <input
            type="date"
            value={reportFilters.endDate}
            onChange={(e) => {
              const updated = { ...reportFilters, endDate: e.target.value, quickRange: "custom" };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          />
        </div>

        <div className="reports-filter-item">
          <label>Customer Organization</label>
          <select
            value={reportFilters.customerId}
            onChange={(e) => {
              const updated = { ...reportFilters, customerId: e.target.value };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          >
            <option value="">All Organizations</option>
            {portalCustomers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.company || c.name}
              </option>
            ))}
          </select>
        </div>

        <div className="reports-filter-item">
          <label>Assigned Team</label>
          <select
            value={reportFilters.team}
            onChange={(e) => {
              const updated = { ...reportFilters, team: e.target.value };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          >
            <option value="">All Teams</option>
            {(teamsList.length > 0
              ? teamsList.filter((t) => t.is_active)
              : [
                  { id: 1, name: "M365 Support" },
                  { id: 2, name: "Network Team" },
                  { id: 3, name: "Security Team" },
                  { id: 4, name: "Endpoint Team" },
                  { id: 5, name: "Backup Team" },
                  { id: 6, name: "Application Support" },
                  { id: 7, name: "Service Desk" }
                ]
            ).map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        <div className="reports-filter-item">
          <label>Priority</label>
          <select
            value={reportFilters.priority}
            onChange={(e) => {
              const updated = { ...reportFilters, priority: e.target.value };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          >
            <option value="">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="reports-filter-item">
          <label>Status</label>
          <select
            value={reportFilters.status}
            onChange={(e) => {
              const updated = { ...reportFilters, status: e.target.value };
              setReportFilters(updated);
              loadReportsData(updated);
            }}
          >
<option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {(reportFilters.startDate || reportFilters.endDate || reportFilters.customerId || reportFilters.team || reportFilters.priority || reportFilters.category || reportFilters.status || reportFilters.quickRange !== "all") && (
          <button
            className="reports-reset-btn"
            onClick={() => {
              const reset = { startDate: "", endDate: "", customerId: "", team: "", technicianId: "", priority: "", category: "", status: "", quickRange: "all" };
              setReportFilters(reset);
              loadReportsData(reset);
            }}
          >
            Reset Filters
          </button>
        )}
      </div>
    </div>

    {/* Reports Sub-Tab Navigation */}
    <div className="reports-tab-nav">
      <button
        type="button"
        className={`report-tab-btn ${reportsActiveTab === "summary" ? "active" : ""}`}
        onClick={() => setReportsActiveTab("summary")}
      >
        📊 Executive Summary &amp; SLA Performance
      </button>
      <button
        type="button"
        className={`report-tab-btn ${reportsActiveTab === "csat" ? "active" : ""}`}
        onClick={() => setReportsActiveTab("csat")}
      >
        ⭐ Customer CSAT &amp; Satisfaction ({reportsCsatSummary?.total_responses || 0})
      </button>
    </div>

    {reportsLoading ? (
      <div className="reports-loading-spinner">
        <div className="spinner"></div>
        <p style={{ marginTop: "12px" }}>Calculating SLA metrics and generating report dataset...</p>
      </div>
    ) : reportsSummary ? (
      reportsActiveTab === "csat" ? (
        <div className="reports-csat-view">
          {/* CSAT KPI Cards */}
          <div className="reports-kpi-grid">
            <div className="reports-kpi-card highlight-kpi">
              <span className="kpi-icon">⭐</span>
              <div className="kpi-content">
                <span className="kpi-label">Overall CSAT Score</span>
                <strong className={`kpi-val ${(reportsCsatSummary?.overall_csat_percentage || 0) >= 85 ? 'text-success' : 'text-warning'}`}>
                  {reportsCsatSummary?.overall_csat_percentage ?? 0}%
                </strong>
                <small className="kpi-hint">4★ &amp; 5★ Satisfied Responses</small>
              </div>
            </div>

            <div className="reports-kpi-card">
              <span className="kpi-icon">🌟</span>
              <div className="kpi-content">
                <span className="kpi-label">Average Rating</span>
                <strong className="kpi-val">
                  {reportsCsatSummary?.average_rating ? `${reportsCsatSummary.average_rating} / 5.0` : "N/A"}
                </strong>
                <small className="kpi-hint">Mean score across all surveys</small>
              </div>
            </div>

            <div className="reports-kpi-card">
              <span className="kpi-icon">📋</span>
              <div className="kpi-content">
                <span className="kpi-label">Total Survey Responses</span>
                <strong className="kpi-val">{reportsCsatSummary?.total_responses ?? 0}</strong>
                <small className="kpi-hint">Out of {reportsCsatSummary?.eligible_tickets_count ?? 0} resolved tickets</small>
              </div>
            </div>

            <div className="reports-kpi-card">
              <span className="kpi-icon">📈</span>
              <div className="kpi-content">
                <span className="kpi-label">Survey Response Rate</span>
                <strong className="kpi-val">{reportsCsatSummary?.response_rate ?? 0}%</strong>
                <small className="kpi-hint">Client participation rate</small>
              </div>
            </div>

            <div className="reports-kpi-card breach-kpi">
              <span className="kpi-icon">⚠️</span>
              <div className="kpi-content">
                <span className="kpi-label">Low CSAT Alerts</span>
                <strong className={`kpi-val ${(reportsCsatSummary?.low_rating_count || 0) > 0 ? 'text-danger' : 'text-success'}`}>
                  {reportsCsatSummary?.low_rating_count ?? 0}
                </strong>
                <small className="kpi-hint">1★ and 2★ Dissatisfied ratings</small>
              </div>
            </div>
          </div>

          {/* Star Distribution Breakdown */}
          <div className="portal-card" style={{ marginTop: "20px" }}>
            <div className="portal-card-header">
              <div>
                <h3 style={{ margin: 0 }}>📊 Star Rating Distribution</h3>
                <p style={{ margin: "2px 0 0 0", fontSize: "13px", color: "#64748b" }}>
                  Breakdown of customer sentiment from 1 (Very Dissatisfied) to 5 (Very Satisfied)
                </p>
              </div>
            </div>
            <div className="csat-distribution-card">
              {[
                { stars: 5, label: "5 Stars (Very Satisfied)", count: reportsCsatSummary?.star_breakdown?.["5_star"] || 0, pct: reportsCsatSummary?.star_percentages?.["5_star"] || 0, color: "#10b981" },
                { stars: 4, label: "4 Stars (Satisfied)", count: reportsCsatSummary?.star_breakdown?.["4_star"] || 0, pct: reportsCsatSummary?.star_percentages?.["4_star"] || 0, color: "#3b82f6" },
                { stars: 3, label: "3 Stars (Neutral)", count: reportsCsatSummary?.star_breakdown?.["3_star"] || 0, pct: reportsCsatSummary?.star_percentages?.["3_star"] || 0, color: "#f59e0b" },
                { stars: 2, label: "2 Stars (Dissatisfied)", count: reportsCsatSummary?.star_breakdown?.["2_star"] || 0, pct: reportsCsatSummary?.star_percentages?.["2_star"] || 0, color: "#f97316" },
                { stars: 1, label: "1 Star (Very Dissatisfied)", count: reportsCsatSummary?.star_breakdown?.["1_star"] || 0, pct: reportsCsatSummary?.star_percentages?.["1_star"] || 0, color: "#ef4444" },
              ].map((row) => (
                <div key={row.stars} className="csat-dist-row">
                  <span className="dist-label">
                    {"★".repeat(row.stars)} <small>({row.label})</small>
                  </span>
                  <div className="dist-bar-track">
                    <div className="dist-bar-fill" style={{ width: `${row.pct}%`, background: row.color }}></div>
                  </div>
                  <span className="dist-stats">
                    <strong>{row.count}</strong> <small>({row.pct}%)</small>
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Dimension Breakdown Tables Grid */}
          <div className="reports-tables-grid" style={{ marginTop: "20px" }}>
            {/* CSAT by Customer */}
            {reportsCsatSummary?.csat_by_customer && Object.keys(reportsCsatSummary.csat_by_customer).length > 0 && (
              <div className="reports-table-card">
                <h3>🏢 CSAT by Customer Organization</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Customer</th>
                      <th>Responses</th>
                      <th>Avg Rating</th>
                      <th>CSAT %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsCsatSummary.csat_by_customer).map(([cust, data]) => (
                      <tr key={cust}>
                        <td><strong>{cust}</strong></td>
                        <td>{data.total_responses}</td>
                        <td>⭐ {data.avg_rating}</td>
                        <td><span className={`compliance-tag ${data.csat_percentage >= 80 ? 'comp-high' : 'comp-low'}`}>{data.csat_percentage}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* CSAT by Team */}
            {reportsCsatSummary?.csat_by_team && Object.keys(reportsCsatSummary.csat_by_team).length > 0 && (
              <div className="reports-table-card">
                <h3>👥 CSAT by Support Team</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Responses</th>
                      <th>Avg Rating</th>
                      <th>CSAT %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsCsatSummary.csat_by_team).map(([team, data]) => (
                      <tr key={team}>
                        <td><strong>{team}</strong></td>
                        <td>{data.total_responses}</td>
                        <td>⭐ {data.avg_rating}</td>
                        <td><span className={`compliance-tag ${data.csat_percentage >= 80 ? 'comp-high' : 'comp-low'}`}>{data.csat_percentage}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* CSAT by Technician */}
            {reportsCsatSummary?.csat_by_technician && Object.keys(reportsCsatSummary.csat_by_technician).length > 0 && (
              <div className="reports-table-card">
                <h3>👤 CSAT by Assigned Technician</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Technician</th>
                      <th>Responses</th>
                      <th>Avg Rating</th>
                      <th>CSAT %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsCsatSummary.csat_by_technician).map(([tech, data]) => (
                      <tr key={tech}>
                        <td><strong>{tech}</strong></td>
                        <td>{data.total_responses}</td>
                        <td>⭐ {data.avg_rating}</td>
                        <td><span className={`compliance-tag ${data.csat_percentage >= 80 ? 'comp-high' : 'comp-low'}`}>{data.csat_percentage}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* CSAT by Priority */}
            {reportsCsatSummary?.csat_by_priority && Object.keys(reportsCsatSummary.csat_by_priority).length > 0 && (
              <div className="reports-table-card">
                <h3>🎯 CSAT by Ticket Priority</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Priority</th>
                      <th>Responses</th>
                      <th>Avg Rating</th>
                      <th>CSAT %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsCsatSummary.csat_by_priority).map(([prio, data]) => (
                      <tr key={prio}>
                        <td><span className={`priority-tag ${prio}`}>{prio.toUpperCase()}</span></td>
                        <td>{data.total_responses}</td>
                        <td>⭐ {data.avg_rating}</td>
                        <td><span className={`compliance-tag ${data.csat_percentage >= 80 ? 'comp-high' : 'comp-low'}`}>{data.csat_percentage}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Feedback Log Table */}
          <div className="reports-table-card" style={{ marginTop: "20px" }}>
            <div className="table-card-header">
              <h3>💬 Recent Customer Feedback Log ({reportsCsatSummary?.recent_ratings?.length || 0})</h3>
            </div>
            {!reportsCsatSummary?.recent_ratings || reportsCsatSummary.recent_ratings.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "#64748b" }}>
                No customer satisfaction ratings submitted for this timeframe.
              </div>
            ) : (
              <div className="reports-table-container">
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Ticket</th>
                      <th>Client</th>
                      <th>Team / Specialist</th>
                      <th>Rating</th>
                      <th>Customer Written Feedback</th>
                      <th>Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportsCsatSummary.recent_ratings.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <strong>#{r.ticket_id}</strong>
                          <div style={{ fontSize: "12px", color: "#64748b" }}>{r.ticket_title}</div>
                        </td>
                        <td>
                          <strong>{r.customer_company || r.customer_name || "Client"}</strong>
                        </td>
                        <td>
                          <div>{r.assigned_team}</div>
                          <small style={{ color: "#64748b" }}>{r.assigned_technician}</small>
                        </td>
                        <td>
                          <span className={`csat-stars-badge score-${r.rating}`}>
                            {"★".repeat(r.rating)} ({r.rating}/5)
                          </span>
                        </td>
                        <td>
                          {r.feedback ? (
                            <span style={{ fontStyle: "italic", color: "#1e293b" }}>"{r.feedback}"</span>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>&mdash; No written comments</span>
                          )}
                        </td>
                        <td>
                          <small style={{ color: "#64748b" }}>
                            {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : "N/A"}
                          </small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Executive KPI Summary Cards */}
          <div className="reports-kpi-grid">
            <div className="reports-kpi-card">
              <span className="kpi-icon">🎫</span>
              <div className="kpi-content">
                <span className="kpi-label">Total Evaluated Tickets</span>
                <strong className="kpi-val">{reportsSummary.summary?.total_tickets || 0}</strong>
                <small className="kpi-hint">Across {reportsSummary.organization_name || "all clients"}</small>
              </div>
            </div>

            <div className="reports-kpi-card highlight-kpi">
              <span className="kpi-icon">🛡</span>
              <div className="kpi-content">
                <span className="kpi-label">SLA Compliance Rate</span>
                <strong className={`kpi-val ${(reportsSummary.summary?.sla_compliance_rate || 0) >= 95 ? 'text-success' : 'text-danger'}`}>
                  {reportsSummary.summary?.sla_compliance_rate || 100}%
                </strong>
                <small className="kpi-hint">Contractual Target: &ge; 95%</small>
              </div>
            </div>

            <div className="reports-kpi-card">
              <span className="kpi-icon">⚡</span>
              <div className="kpi-content">
                <span className="kpi-label">Avg Response Speed</span>
                <strong className="kpi-val">{reportsSummary.summary?.avg_response_time_label || "N/A"}</strong>
                <small className="kpi-hint">First technician interaction</small>
              </div>
            </div>

            <div className="reports-kpi-card">
              <span className="kpi-icon">✓</span>
              <div className="kpi-content">
                <span className="kpi-label">Avg Resolution Time</span>
                <strong className="kpi-val">{reportsSummary.summary?.avg_resolution_time_label || "N/A"}</strong>
                <small className="kpi-hint">Resolved tickets duration</small>
              </div>
            </div>

            <div className="reports-kpi-card breach-kpi">
              <span className="kpi-icon">🚨</span>
              <div className="kpi-content">
                <span className="kpi-label">SLA Breaches</span>
                <strong className="kpi-val text-danger">{reportsSummary.summary?.sla_breaches || 0}</strong>
                <small className="kpi-hint">
                  Resp: {reportsSummary.summary?.response_sla_breaches || 0} | Resol: {reportsSummary.summary?.resolution_sla_breaches || 0}
                </small>
              </div>
            </div>

            <div className="reports-kpi-card escalation-kpi">
              <span className="kpi-icon">🔥</span>
              <div className="kpi-content">
                <span className="kpi-label">Critical Escalations</span>
                <strong className="kpi-val text-warning">{reportsSummary.summary?.escalation_count || 0}</strong>
                <small className="kpi-hint">Level 2 / Level 3 escalations</small>
              </div>
            </div>
          </div>

          {/* SLA Performance Overview */}
          <div className="reports-sla-overview-grid">
            <div className="reports-sla-card">
              <div className="sla-card-header">
                <h3>⚡ Response SLA Performance</h3>
                <span className="sla-target-badge">Target: 95%</span>
              </div>
              <div className="sla-progress-block">
                <div className="sla-rate-row">
                  <span>Compliance</span>
                  <strong>{reportsSummary.sla_performance?.response?.compliance_rate || 100}%</strong>
                </div>
                <div className="sla-progress-track">
                  <div
                    className={`sla-progress-fill ${(reportsSummary.sla_performance?.response?.compliance_rate || 0) >= 95 ? 'fill-good' : 'fill-warn'}`}
                    style={{ width: `${reportsSummary.sla_performance?.response?.compliance_rate || 100}%` }}
                  ></div>
                </div>
                <div className="sla-counts-row">
                  <span className="met-count">✓ Met: {reportsSummary.sla_performance?.response?.met || 0}</span>
                  <span className="breached-count">✗ Breached: {reportsSummary.sla_performance?.response?.breached || 0}</span>
                  <span className="total-evaluated">Total: {reportsSummary.sla_performance?.response?.total_evaluated || 0}</span>
                </div>
              </div>
            </div>

            <div className="reports-sla-card">
              <div className="sla-card-header">
                <h3>✓ Resolution SLA Performance</h3>
                <span className="sla-target-badge">Target: 95%</span>
              </div>
              <div className="sla-progress-block">
                <div className="sla-rate-row">
                  <span>Compliance</span>
                  <strong>{reportsSummary.sla_performance?.resolution?.compliance_rate || 100}%</strong>
                </div>
                <div className="sla-progress-track">
                  <div
                    className={`sla-progress-fill ${(reportsSummary.sla_performance?.resolution?.compliance_rate || 0) >= 95 ? 'fill-good' : 'fill-warn'}`}
                    style={{ width: `${reportsSummary.sla_performance?.resolution?.compliance_rate || 100}%` }}
                  ></div>
                </div>
                <div className="sla-counts-row">
                  <span className="met-count">✓ Met: {reportsSummary.sla_performance?.resolution?.met || 0}</span>
                  <span className="breached-count">✗ Breached: {reportsSummary.sla_performance?.resolution?.breached || 0}</span>
                  <span className="total-evaluated">Total: {reportsSummary.sla_performance?.resolution?.total_evaluated || 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown Tables Grid */}
          <div className="reports-tables-grid">
            {reportsSummary.breakdowns?.by_client && Object.keys(reportsSummary.breakdowns.by_client).length > 0 && (
              <div className="reports-table-card">
                <h3>🏢 Client Organization Breakdown</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Client</th>
                      <th>Total</th>
                      <th>Breaches</th>
                      <th>SLA %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsSummary.breakdowns.by_client).map(([client, data]) => (
                      <tr key={client}>
                        <td><strong>{client}</strong></td>
                        <td>{data.total}</td>
                        <td className={data.breaches > 0 ? "text-danger" : ""}>{data.breaches}</td>
                        <td><span className={`compliance-tag ${data.compliance_rate >= 95 ? 'comp-high' : 'comp-low'}`}>{data.compliance_rate}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {reportsSummary.breakdowns?.by_team && Object.keys(reportsSummary.breakdowns.by_team).length > 0 && (
              <div className="reports-table-card">
                <h3>👥 Assigned Team Breakdown</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Total</th>
                      <th>Breaches</th>
                      <th>SLA %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsSummary.breakdowns.by_team).map(([team, data]) => (
                      <tr key={team}>
                        <td><strong>{team}</strong></td>
                        <td>{data.total}</td>
                        <td className={data.breaches > 0 ? "text-danger" : ""}>{data.breaches}</td>
                        <td><span className={`compliance-tag ${data.compliance_rate >= 95 ? 'comp-high' : 'comp-low'}`}>{data.compliance_rate}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {reportsSummary.breakdowns?.by_priority && Object.keys(reportsSummary.breakdowns.by_priority).length > 0 && (
              <div className="reports-table-card">
                <h3>🎯 Priority Breakdown</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Priority</th>
                      <th>Total</th>
                      <th>Breaches</th>
                      <th>SLA %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsSummary.breakdowns.by_priority).map(([prio, data]) => (
                      <tr key={prio}>
                        <td><span className={`priority-tag ${prio}`}>{prio.toUpperCase()}</span></td>
                        <td>{data.total}</td>
                        <td className={data.breaches > 0 ? "text-danger" : ""}>{data.breaches}</td>
                        <td><span className={`compliance-tag ${data.compliance_rate >= 95 ? 'comp-high' : 'comp-low'}`}>{data.compliance_rate}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {reportsSummary.breakdowns?.by_category && Object.keys(reportsSummary.breakdowns.by_category).length > 0 && (
              <div className="reports-table-card">
                <h3>📁 Category Breakdown</h3>
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Total</th>
                      <th>Breaches</th>
                      <th>SLA %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(reportsSummary.breakdowns.by_category).map(([cat, data]) => (
                      <tr key={cat}>
                        <td>{cat}</td>
                        <td>{data.total}</td>
                        <td className={data.breaches > 0 ? "text-danger" : ""}>{data.breaches}</td>
                        <td><span className={`compliance-tag ${data.compliance_rate >= 95 ? 'comp-high' : 'comp-low'}`}>{data.compliance_rate}%</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Ticket Listing Table */}
          <div className="reports-table-card" style={{ marginTop: "24px" }}>
            <div className="table-card-header">
              <h3>📋 Evaluated Tickets ({reportsTickets.length})</h3>
              <small>Showing most recent tickets matching filter criteria</small>
            </div>
            {reportsTickets.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "#64748b" }}>
                No tickets found matching the selected report filters.
              </div>
            ) : (
              <div className="reports-table-container">
                <table className="reports-data-table">
                  <thead>
                    <tr>
                      <th>Ticket ID</th>
                      <th>Created</th>
                      <th>Client</th>
                      <th>Subject</th>
                      <th>Priority</th>
                      <th>Status</th>
                      <th>Assigned Team</th>
                      <th>SLA State</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportsTickets.map((t) => (
                      <tr key={t.id}>
                        <td><strong>#{t.id}</strong></td>
                        <td><small>{t.created_at ? new Date(t.created_at).toLocaleDateString() : "-"}</small></td>
                        <td>{t.customer_company || t.customer_name || "N/A"}</td>
                        <td className="cell-truncate" title={t.title}>{t.title}</td>
                        <td><span className={`priority-tag ${t.priority}`}>{t.priority?.toUpperCase()}</span></td>
                        <td><span className={`status-pill ${t.status}`}>{t.status?.replace("_", " ")}</span></td>
                        <td>{t.assigned_team}</td>
                        <td>{renderSlaBadge(t.sla_status)}</td>
                        <td>
                          <button
                            className="btn-view-report-ticket"
                            onClick={() => {
                              const found = tickets.find((tk) => tk.id === t.id);
                              if (found) setSelectedTicket(found);
                              navigateTo("tickets");
                            }}
                          >
                            View Ticket
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )
    ) : (
      <div className="reports-empty">Select filters and generate a report.</div>
    )}
  </section>
)}
      </main>


      {/* New Ticket Modal */}
      {showForm && (

        <div
          className="modal-overlay"
          onClick={() => setShowForm(false)}
        >

          <div
            className="modal"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <div className="modal-header">

              <div>
                <h2>Create New Ticket</h2>

                <p>
                  The rule engine will automatically
                  route this ticket.
                </p>
              </div>

              <button
                className="close-button"
                onClick={() => setShowForm(false)}
              >
                ×
              </button>

            </div>


            <form onSubmit={createTicket}>

              <label>
                Ticket Title
              </label>

              <input
                type="text"
                placeholder="Example: Outlook is not opening"
                value={title}
                onChange={(event) =>
                  setTitle(event.target.value)
                }
              />


              <label>
                Description
              </label>

              <textarea
                rows="6"
                placeholder="Describe the problem..."
                value={description}
                onChange={(event) =>
                  setDescription(event.target.value)
                }
              />


              {message && (
                <div className="form-message">
                  {message}
                </div>
              )}


              <button
                type="submit"
                className="submit-ticket"
                disabled={submitting}
              >
                {submitting
                  ? "Routing Ticket..."
                  : "Create & Route Ticket"}
              </button>

            </form>

          </div>

        </div>

      )}
      {showCreateRuleModal && (
  <div
    className="modal-overlay"
    onClick={() => setShowCreateRuleModal(false)}
  >
    <div
      className="modal rule-edit-modal"
      onClick={(e) => e.stopPropagation()}
    >

      <div className="modal-header">
        <div>
          <h2>Create Routing Rule</h2>

          <p>
            Create a rule for automatic ticket routing.
          </p>
        </div>

        <button
          className="close-button"
          onClick={() => setShowCreateRuleModal(false)}
        >
          ×
        </button>
      </div>

      <form onSubmit={createRule}>

        <label>Rule Name</label>

        <input
          type="text"
          placeholder="Example: Application Support"
          value={newRule.category}
          onChange={(e) =>
            setNewRule({
              ...newRule,
              category: e.target.value
            })
          }
        />

        <label>Assigned Team</label>

        <select
          value={newRule.team}
          onChange={(e) =>
            setNewRule({
              ...newRule,
              team: e.target.value
            })
          }
        >
          {(teamsList.length > 0
            ? teamsList.filter((t) => t.is_active)
            : [
                { id: 1, name: "M365 Support" },
                { id: 2, name: "Network Team" },
                { id: 3, name: "Security Team" },
                { id: 4, name: "Endpoint Team" },
                { id: 5, name: "Backup Team" },
                { id: 6, name: "Application Support" },
                { id: 7, name: "Service Desk" }
              ]
          ).map((t) => (
            <option key={t.id} value={t.name}>
              {t.name}
            </option>
          ))}
        </select>

        <label>Priority</label>

        <select
          value={newRule.priority}
          onChange={(e) =>
            setNewRule({
              ...newRule,
              priority: e.target.value
            })
          }
        >
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <label>Keywords</label>

        <input
          type="text"
          placeholder="sap, salesforce, crm, application"
          value={newRule.keywords}
          onChange={(e) =>
            setNewRule({
              ...newRule,
              keywords: e.target.value
            })
          }
        />

        <small>
          Separate keywords with commas.
        </small>

        <label>Description</label>

        <textarea
          rows="4"
          placeholder="Describe what this rule should route."
          value={newRule.description}
          onChange={(e) =>
            setNewRule({
              ...newRule,
              description: e.target.value
            })
          }
        />

        <button
          type="submit"
          className="submit-ticket"
        >
          Create Rule
        </button>

      </form>

    </div>
  </div>
)}
     {editingRule && (
  <div
    className="modal-overlay"
    onClick={() => setEditingRule(null)}
  >
    <div
      className="modal rule-edit-modal"
      onClick={(event) =>
        event.stopPropagation()
      }
    >

      <div className="modal-header">
        <div>
          <h2>Edit Routing Rule</h2>

          <p>
            Modify how the rule engine routes tickets.
          </p>
        </div>

        <button
          className="close-button"
          onClick={() => setEditingRule(null)}
        >
          ×
        </button>
      </div>

      <form onSubmit={updateRule}>

        <label>
          Rule Name
        </label>

        <input
          type="text"
          value={editingRule.name}
          disabled
        />

        <label>
          Assigned Team
        </label>

        <select
          value={editingRule.team}
          onChange={(event) =>
            setEditingRule({
              ...editingRule,
              team: event.target.value,
            })
          }
        >
          {(teamsList.length > 0
            ? teamsList.filter((t) => t.is_active)
            : [
                { id: 1, name: "M365 Support" },
                { id: 2, name: "Network Team" },
                { id: 3, name: "Security Team" },
                { id: 4, name: "Endpoint Team" },
                { id: 5, name: "Backup Team" },
                { id: 6, name: "Application Support" },
                { id: 7, name: "Service Desk" }
              ]
          ).map((t) => (
            <option key={t.id} value={t.name}>
              {t.name}
            </option>
          ))}
        </select>

        <label>
          Priority
        </label>

        <select
          value={editingRule.priority}
          onChange={(event) =>
            setEditingRule({
              ...editingRule,
              priority: event.target.value,
            })
          }
        >
          <option value="critical">
            Critical
          </option>

          <option value="high">
            High
          </option>

          <option value="medium">
            Medium
          </option>

          <option value="low">
            Low
          </option>
        </select>

        <label>
          Keywords
        </label>

        <input
          type="text"
          value={editingRule.keywords.join(", ")}
          onChange={(event) =>
            setEditingRule({
              ...editingRule,
              keywords: event.target.value
                .split(",")
                .map((keyword) => keyword.trim())
                .filter(Boolean),
            })
          }
        />

        <label>
          Description
        </label>

        <textarea
          rows="4"
          value={editingRule.description}
          onChange={(event) =>
            setEditingRule({
              ...editingRule,
              description: event.target.value,
            })
          }
        />

        <button
          type="submit"
          className="submit-ticket"
          disabled={savingRule}
        >
          {savingRule
            ? "Saving Rule..."
            : "Save Rule"}
        </button>

      </form>

    </div>
  </div>
)}

{/* ========================================================================= */}
{/* ASSIGN TECHNICIAN MODAL */}
{/* ========================================================================= */}
{assignModalTicket && (
  <div
    className="modal-overlay"
    onClick={() => setAssignModalTicket(null)}
  >
    <div
      className="modal assign-tech-modal"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Assign Technician</h2>
          <p>
            Ticket #{assignModalTicket.id} &bull; {assignModalTicket.title}
          </p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setAssignModalTicket(null)}
        >
          ×
        </button>
      </div>

      <div className="modal-team-banner">
        <span>Designated Team:</span>
        <strong>{assignModalTicket.assigned_team || "Unassigned"}</strong>
      </div>

      <div className="tech-selection-list">
        <label
          className={`tech-radio-item ${!selectedTechId ? "selected" : ""}`}
        >
          <input
            type="radio"
            name="technicianSelect"
            value=""
            checked={!selectedTechId}
            onChange={() => setSelectedTechId("")}
          />
          <div className="tech-radio-info">
            <strong>-- Unassigned --</strong>
            <small>Leave ticket unassigned in team work queue</small>
          </div>
        </label>

        {technicians
          .filter((t) => (t.team || "").toLowerCase() === (assignModalTicket.assigned_team || "").toLowerCase())
          .map((tech) => {
            const isChecked = String(selectedTechId) === String(tech.id);
            const count = tech.active_workload || 0;
            return (
              <label
                key={tech.id}
                className={`tech-radio-item ${isChecked ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="technicianSelect"
                  value={tech.id}
                  checked={isChecked}
                  onChange={() => setSelectedTechId(tech.id)}
                />
                <div className="tech-radio-info">
                  <div className="tech-radio-top">
                    <strong>{tech.name}</strong>
                    <span className={`tech-radio-load ${count > 3 ? "load-high" : count > 0 ? "load-active" : "load-idle"}`}>
                      {count} active {count === 1 ? "ticket" : "tickets"}
                    </span>
                  </div>
                  <small>{tech.email}</small>
                </div>
              </label>
            );
          })}
      </div>

      <div className="modal-actions-footer">
        <button
          type="button"
          className="modal-cancel-btn"
          onClick={() => setAssignModalTicket(null)}
          disabled={assigningTech}
        >
          Cancel
        </button>

        <button
          type="button"
          className="modal-confirm-btn"
          onClick={() => handleAssignTechnician(assignModalTicket.id, selectedTechId)}
          disabled={assigningTech}
        >
          {assigningTech ? "Saving..." : "Save Assignment"}
        </button>
      </div>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* ESCALATE TICKET MODAL */}
{/* ========================================================================= */}
{escalateModalTicket && (
  <div
    className="modal-overlay"
    onClick={() => setEscalateModalTicket(null)}
  >
    <div
      className="modal escalate-modal"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>🚨 Escalate Ticket #{escalateModalTicket.id}</h2>
          <p>
            {escalateModalTicket.title} &bull; Priority: {(escalateModalTicket.priority || "medium").toUpperCase()}
          </p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setEscalateModalTicket(null)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleEscalateTicket}>
        <div className="esc-current-level-notice">
          <span>Current Escalation Level:</span>
          <strong>
            {(escalateModalTicket.escalation_level || 1) === 2
              ? "⚡ Level 2 (Team Escalation)"
              : (escalateModalTicket.escalation_level || 1) === 3
              ? "🚨 Level 3 (Specialist Escalation)"
              : "Level 1 (Normal)"}
          </strong>
        </div>

        <label className="modal-field-label">Target Escalation Level</label>
        <div className="esc-level-toggle-group">
          {(escalateModalTicket.escalation_level || 1) < 2 && (
            <button
              type="button"
              className={`esc-level-btn level-2-btn ${targetEscalationLevel === 2 ? "active" : ""}`}
              onClick={() => setTargetEscalationLevel(2)}
            >
              <strong>⚡ Level 2</strong>
              <small>Team Escalation (Senior Engineers & Leads)</small>
            </button>
          )}

          <button
            type="button"
            className={`esc-level-btn level-3-btn ${targetEscalationLevel === 3 ? "active" : ""}`}
            onClick={() => setTargetEscalationLevel(3)}
          >
            <strong>🚨 Level 3</strong>
            <small>Specialist Escalation (Tier-3 & Vendor Experts)</small>
          </button>
        </div>

        <label className="modal-field-label">Escalation Reason Presets</label>
        <div className="esc-preset-chips">
          {[
            "SLA at risk",
            "SLA breached",
            "Requires specialist expertise",
            "Customer impact increased",
            "Technician unavailable",
            "Requires higher-level support"
          ].map((preset) => (
            <button
              key={preset}
              type="button"
              className="esc-preset-chip"
              onClick={() => setEscalationReason(preset)}
            >
              + {preset}
            </button>
          ))}
        </div>

        <label className="modal-field-label">Detailed Escalation Reason *</label>
        <textarea
          rows={3}
          required
          placeholder="Explain why this ticket requires higher-level escalation..."
          value={escalationReason}
          onChange={(e) => setEscalationReason(e.target.value)}
        />

        <label className="modal-field-label">Escalated By</label>
        <div className="author-identity-pill" title="Escalator is automatically stamped from your authenticated session">
          <span className="author-icon">👤</span>
          <strong className="author-name">{auth?.user?.name || escalatedBy || "MSP Technician"}</strong>
          {auth?.user?.role && (
            <span className={`author-role-chip role-${auth.user.role}`}>
              {auth.user.role}
            </span>
          )}
        </div>

        <div className="modal-actions-footer">
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setEscalateModalTicket(null)}
            disabled={escalating}
          >
            Cancel
          </button>

          <button
            type="submit"
            className="modal-confirm-btn btn-danger-escalate"
            disabled={escalating || !escalationReason.trim()}
          >
            {escalating ? "Escalating..." : `🔥 Confirm Level ${targetEscalationLevel} Escalation`}
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* CREATE USER MODAL */}
{/* ========================================================================= */}
{showCreateUserModal && (
  <div
    className="modal-overlay"
    onClick={() => setShowCreateUserModal(false)}
  >
    <div
      className="modal"
      style={{ maxWidth: "480px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Create New User</h2>
          <p>Add a new system user with designated role and permissions</p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setShowCreateUserModal(false)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleCreateUser}>
        <label className="modal-field-label">Full Name *</label>
        <input
          type="text"
          required
          placeholder="e.g. Jane Doe"
          value={newUserForm.name}
          onChange={(e) => setNewUserForm({ ...newUserForm, name: e.target.value })}
        />

        <label className="modal-field-label">Email Address *</label>
        <input
          type="email"
          required
          placeholder="e.g. user@company.com"
          value={newUserForm.email}
          onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
        />

        <label className="modal-field-label">Password *</label>
        <input
          type="password"
          required
          placeholder="Min 6 characters"
          value={newUserForm.password}
          onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
        />

        <label className="modal-field-label">Role *</label>
        <select
          value={newUserForm.role}
          onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
        >
          <option value="technician">Technician (Workbench &amp; Tickets)</option>
          <option value="manager">Manager (Dashboard, WB, Analytics &amp; Rules View)</option>
          <option value="admin">Administrator (Full Access &amp; User Mgmt)</option>
          <option value="customer">Customer (Customer Portal Only)</option>
        </select>

        {newUserForm.role === "technician" && (
          <>
            <label className="modal-field-label">Link to Technician Profile (Optional)</label>
            <select
              value={newUserForm.technician_id}
              onChange={(e) => setNewUserForm({ ...newUserForm, technician_id: e.target.value })}
            >
              <option value="">-- Select Technician --</option>
              {technicians.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.team})</option>
              ))}
            </select>
          </>
        )}

        {newUserForm.role === "customer" && (
          <>
            <label className="modal-field-label">Link to Customer Account (Optional)</label>
            <select
              value={newUserForm.customer_id}
              onChange={(e) => setNewUserForm({ ...newUserForm, customer_id: e.target.value })}
            >
              <option value="">-- Select Customer Organization --</option>
              {portalCustomers.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.company})</option>
              ))}
            </select>
          </>
        )}

        <div className="modal-actions-footer">
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setShowCreateUserModal(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
            disabled={creatingUser}
          >
            {creatingUser ? "Creating..." : "Create User Account"}
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* RESET PASSWORD MODAL */}
{/* ========================================================================= */}
{resetPasswordModalUser && (
  <div
    className="modal-overlay"
    onClick={() => setResetPasswordModalUser(null)}
  >
    <div
      className="modal"
      style={{ maxWidth: "420px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Reset Password</h2>
          <p>
            Update password for {resetPasswordModalUser.name} ({resetPasswordModalUser.email})
          </p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setResetPasswordModalUser(null)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleResetPassword}>
        <label className="modal-field-label">New Password *</label>
        <input
          type="password"
          required
          placeholder="Enter new password (min 6 chars)"
          value={newResetPassword}
          onChange={(e) => setNewResetPassword(e.target.value)}
          autoFocus
        />

        <div className="modal-actions-footer">
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setResetPasswordModalUser(null)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
            disabled={savingResetPassword || newResetPassword.length < 6}
          >
            {savingResetPassword ? "Saving..." : "Update Password"}
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* CREATE TEAM MODAL (Phase 7) */}
{/* ========================================================================= */}
{showCreateTeamModal && (
  <div
    className="modal-overlay"
    onClick={() => setShowCreateTeamModal(false)}
  >
    <div
      className="modal"
      style={{ maxWidth: "520px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Create New Team</h2>
          <p>Add a dynamic operational team with business hours and routing configuration</p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setShowCreateTeamModal(false)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleCreateTeam}>
        <label className="modal-field-label">Team Name *</label>
        <input
          type="text"
          required
          placeholder="e.g. Cloud Infrastructure"
          value={newTeam.name}
          onChange={(e) => setNewTeam({ ...newTeam, name: e.target.value })}
        />

        <label className="modal-field-label">Description</label>
        <textarea
          rows="2"
          placeholder="e.g. Handles AWS, Azure, and private cloud tickets"
          value={newTeam.description}
          onChange={(e) => setNewTeam({ ...newTeam, description: e.target.value })}
        />

        <label className="modal-field-label">Team Lead</label>
        <select
          value={newTeam.team_lead_id}
          onChange={(e) => setNewTeam({ ...newTeam, team_lead_id: e.target.value })}
        >
          <option value="">-- No Team Lead Assigned --</option>
          {technicians.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.team || "No Team"})
            </option>
          ))}
        </select>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
          <div>
            <label className="modal-field-label">Hours Start</label>
            <input
              type="text"
              placeholder="08:00"
              value={newTeam.business_hours_start}
              onChange={(e) => setNewTeam({ ...newTeam, business_hours_start: e.target.value })}
            />
          </div>
          <div>
            <label className="modal-field-label">Hours End</label>
            <input
              type="text"
              placeholder="18:00"
              value={newTeam.business_hours_end}
              onChange={(e) => setNewTeam({ ...newTeam, business_hours_end: e.target.value })}
            />
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
          <div>
            <label className="modal-field-label">Timezone</label>
            <select
              value={newTeam.timezone}
              onChange={(e) => setNewTeam({ ...newTeam, timezone: e.target.value })}
            >
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="America/Chicago">America/Chicago (CST)</option>
              <option value="America/Denver">America/Denver (MST)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
              <option value="UTC">UTC</option>
              <option value="Europe/London">Europe/London (GMT/BST)</option>
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
            </select>
          </div>
          <div>
            <label className="modal-field-label">Work Days</label>
            <input
              type="text"
              placeholder="MON,TUE,WED,THU,FRI"
              value={newTeam.work_days}
              onChange={(e) => setNewTeam({ ...newTeam, work_days: e.target.value })}
            />
          </div>
        </div>

        <div className="modal-actions-footer" style={{ marginTop: "20px" }}>
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setShowCreateTeamModal(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
          >
            Create Team
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* EDIT TEAM MODAL (Phase 7) */}
{/* ========================================================================= */}
{editingTeam && (
  <div
    className="modal-overlay"
    onClick={() => setEditingTeam(null)}
  >
    <div
      className="modal"
      style={{ maxWidth: "520px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Edit Team: {editingTeam.name}</h2>
          <p>Update team information, operational hours, and designated lead</p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setEditingTeam(null)}
        >
          ×
        </button>
      </div>

      <form onSubmit={handleUpdateTeam}>
        <label className="modal-field-label">Team Name *</label>
        <input
          type="text"
          required
          value={editingTeam.name}
          onChange={(e) => setEditingTeam({ ...editingTeam, name: e.target.value })}
        />

        <label className="modal-field-label">Description</label>
        <textarea
          rows="2"
          value={editingTeam.description || ""}
          onChange={(e) => setEditingTeam({ ...editingTeam, description: e.target.value })}
        />

        <label className="modal-field-label">Team Lead</label>
        <select
          value={editingTeam.team_lead_id || ""}
          onChange={(e) => setEditingTeam({ ...editingTeam, team_lead_id: e.target.value })}
        >
          <option value="">-- No Team Lead Assigned --</option>
          {technicians.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.team || "No Team"})
            </option>
          ))}
        </select>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
          <div>
            <label className="modal-field-label">Hours Start</label>
            <input
              type="text"
              value={editingTeam.business_hours_start || "08:00"}
              onChange={(e) => setEditingTeam({ ...editingTeam, business_hours_start: e.target.value })}
            />
          </div>
          <div>
            <label className="modal-field-label">Hours End</label>
            <input
              type="text"
              value={editingTeam.business_hours_end || "18:00"}
              onChange={(e) => setEditingTeam({ ...editingTeam, business_hours_end: e.target.value })}
            />
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginTop: "12px" }}>
          <div>
            <label className="modal-field-label">Timezone</label>
            <select
              value={editingTeam.timezone || "America/New_York"}
              onChange={(e) => setEditingTeam({ ...editingTeam, timezone: e.target.value })}
            >
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="America/Chicago">America/Chicago (CST)</option>
              <option value="America/Denver">America/Denver (MST)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
              <option value="UTC">UTC</option>
              <option value="Europe/London">Europe/London (GMT/BST)</option>
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
            </select>
          </div>
          <div>
            <label className="modal-field-label">Work Days</label>
            <input
              type="text"
              value={editingTeam.work_days || "MON,TUE,WED,THU,FRI"}
              onChange={(e) => setEditingTeam({ ...editingTeam, work_days: e.target.value })}
            />
          </div>
        </div>

        <div style={{ marginTop: "16px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontWeight: "600" }}>
            <input
              type="checkbox"
              checked={editingTeam.is_active}
              onChange={(e) => setEditingTeam({ ...editingTeam, is_active: e.target.checked })}
            />
            <span>Active Team (Available as Routing Target)</span>
          </label>
        </div>

        <div className="modal-actions-footer" style={{ marginTop: "20px" }}>
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setEditingTeam(null)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
          >
            Save Changes
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* MANAGE TEAM MEMBERS MODAL (Phase 7) */}
{/* ========================================================================= */}
{managingMembersTeam && (
  <div
    className="modal-overlay"
    onClick={() => setManagingMembersTeam(null)}
  >
    <div
      className="modal"
      style={{ maxWidth: "560px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2>Manage Members: {managingMembersTeam.name}</h2>
          <p>Assign technicians to this team's work queue and workload rotation</p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setManagingMembersTeam(null)}
        >
          ×
        </button>
      </div>

      <div style={{ padding: "16px 0" }}>
        <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 12px 0" }}>
          Select the technicians who belong to <strong>{managingMembersTeam.name}</strong>:
        </p>

        <div style={{ maxHeight: "280px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "8px" }}>
          {technicians.length === 0 ? (
            <div style={{ padding: "16px", textAlign: "center", color: "#94a3b8" }}>No technicians registered.</div>
          ) : (
            technicians.map((tech) => {
              const isSelected = selectedMemberIds.includes(tech.id);
              const isLead = managingMembersTeam.team_lead_id === tech.id;
              return (
                <label
                  key={tech.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    background: isSelected ? "#f8fafc" : "transparent",
                    cursor: "pointer",
                    borderBottom: "1px solid #f1f5f9"
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedMemberIds([...selectedMemberIds, tech.id]);
                      } else {
                        setSelectedMemberIds(selectedMemberIds.filter((id) => id !== tech.id));
                      }
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: "600", fontSize: "14px", color: "#0f172a" }}>
                      {isLead && "👑 "}
                      {tech.name}
                      {isLead && <span style={{ fontSize: "11px", color: "#6366f1", marginLeft: "6px" }}>(Team Lead)</span>}
                    </div>
                    <div style={{ fontSize: "12px", color: "#64748b" }}>
                      {tech.email} • Current Team: {tech.team || "None"}
                    </div>
                  </div>
                </label>
              );
            })
          )}
        </div>
      </div>

      <div className="modal-actions-footer">
        <button
          type="button"
          className="modal-cancel-btn"
          onClick={() => setManagingMembersTeam(null)}
        >
          Cancel
        </button>
        <button
          type="button"
          className="modal-confirm-btn"
          onClick={handleSaveTeamMembers}
        >
          Save Members ({selectedMemberIds.length})
        </button>
      </div>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* TEAM STATUS DEACTIVATION SAFETY MODAL (Phase 7) */}
{/* ========================================================================= */}
{teamStatusModal && (
  <div
    className="modal-overlay"
    onClick={() => setTeamStatusModal(null)}
  >
    <div
      className="modal"
      style={{ maxWidth: "480px" }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="modal-header">
        <div>
          <h2 style={{ color: "#b91c1c" }}>⚠️ Team Deactivation Warning</h2>
          <p>Active workload or routing rules detected for <strong>{teamStatusModal.team?.name}</strong></p>
        </div>
        <button
          type="button"
          className="close-button"
          onClick={() => setTeamStatusModal(null)}
        >
          ×
        </button>
      </div>

      <div style={{ padding: "16px 0" }}>
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px", padding: "14px", color: "#991b1b", fontSize: "13px" }}>
          <p style={{ margin: "0 0 8px 0", fontWeight: "700" }}>{teamStatusModal.warning}</p>
          <ul style={{ margin: 0, paddingLeft: "18px" }}>
            {teamStatusModal.openTicketsCount > 0 && (
              <li><strong>{teamStatusModal.openTicketsCount}</strong> active tickets currently assigned to this team</li>
            )}
            {teamStatusModal.activeRulesCount > 0 && (
              <li><strong>{teamStatusModal.activeRulesCount}</strong> active routing rules targeting this team</li>
            )}
          </ul>
        </div>
        <p style={{ fontSize: "13px", color: "#64748b", marginTop: "12px" }}>
          Deactivating this team will prevent new tickets from being routed to it. Are you sure you want to force deactivation?
        </p>
      </div>

      <div className="modal-actions-footer">
        <button
          type="button"
          className="modal-cancel-btn"
          onClick={() => setTeamStatusModal(null)}
        >
          Cancel
        </button>
        <button
          type="button"
          className="modal-confirm-btn"
          style={{ background: "#dc2626" }}
          onClick={() => handleToggleTeamStatus(teamStatusModal.team, true)}
        >
          Force Deactivate
        </button>
      </div>
    </div>
  </div>
)}

{/* ========================================================================= */}
{/* PHASE 9: KNOWLEDGE BASE MODALS */}
{/* ========================================================================= */}

{/* 1. KB ARTICLE CREATE / EDIT MODAL */}
{showKbArticleModal && (
  <div className="modal-overlay" onClick={() => setShowKbArticleModal(false)}>
    <div className="modal-content" style={{ maxWidth: "800px" }} onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <div className="modal-title">
          <h3>{editingKbArticle ? "✏️ Edit Knowledge Article" : "➕ Create New Knowledge Article"}</h3>
          <p>{editingKbArticle ? `Modifying version ${editingKbArticle.current_version} • Changes will generate an audit revision.` : "Author a new self-service guide or internal engineering SOP."}</p>
        </div>
        <button type="button" className="close-btn" onClick={() => setShowKbArticleModal(false)}>✕</button>
      </div>

      <form onSubmit={handleSaveKbArticle}>
        <div style={{ padding: "16px 0", maxHeight: "70vh", overflowY: "auto" }}>
          <div className="form-group">
            <label>Article Title *</label>
            <input
              type="text"
              placeholder="e.g. How to Configure Outlook Desktop Sync"
              value={kbArticleForm.title}
              onChange={(e) => setKbArticleForm({ ...kbArticleForm, title: e.target.value })}
              required
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div className="form-group">
              <label>Category *</label>
              <select
                value={kbArticleForm.category_id}
                onChange={(e) => setKbArticleForm({ ...kbArticleForm, category_id: e.target.value })}
              >
                <option value="">General</option>
                {kbCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Visibility Scope *</label>
              <select
                value={kbArticleForm.visibility}
                onChange={(e) => setKbArticleForm({ ...kbArticleForm, visibility: e.target.value })}
              >
                <option value="public">🌐 Public (Customer Portal &amp; Staff)</option>
                <option value="internal">🔒 Internal (MSP Engineering Only)</option>
              </select>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div className="form-group">
              <label>Publish Status</label>
              <select
                value={kbArticleForm.status}
                onChange={(e) => setKbArticleForm({ ...kbArticleForm, status: e.target.value })}
              >
                <option value="published">Published</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            <div className="form-group">
              <label>Assigned Team (Optional)</label>
              <select
                value={kbArticleForm.team_id}
                onChange={(e) => setKbArticleForm({ ...kbArticleForm, team_id: e.target.value })}
              >
                <option value="">None / General Desk</option>
                {teamsList.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Short Summary / Preview</label>
            <input
              type="text"
              placeholder="Brief 1-2 sentence description shown in search results"
              value={kbArticleForm.summary}
              onChange={(e) => setKbArticleForm({ ...kbArticleForm, summary: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Search Keywords / Tags (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g. vpn, globalprotect, network, tunnel, remote work"
              value={kbArticleForm.tags}
              onChange={(e) => setKbArticleForm({ ...kbArticleForm, tags: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Article Content (Markdown Supported) *</label>
            <textarea
              rows={10}
              placeholder="Write guide content in Markdown (# Heading, ## Section, 1. Step, > [!TIP])..."
              value={kbArticleForm.content}
              onChange={(e) => setKbArticleForm({ ...kbArticleForm, content: e.target.value })}
              style={{ fontFamily: "monospace", fontSize: "13px" }}
              required
            />
          </div>

          {editingKbArticle && (
            <div className="form-group">
              <label>Change Log Note (Audit History)</label>
              <input
                type="text"
                placeholder="e.g. Updated IPsec gateway IP and troubleshooting commands"
                value={kbArticleForm.change_summary}
                onChange={(e) => setKbArticleForm({ ...kbArticleForm, change_summary: e.target.value })}
              />
            </div>
          )}
        </div>

        <div className="modal-actions-footer">
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setShowKbArticleModal(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
            disabled={kbSavingArticle}
          >
            {kbSavingArticle ? "Saving..." : editingKbArticle ? "Save Revisions" : "Publish Article"}
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* 2. KB ARTICLE REVISION HISTORY MODAL */}
{showKbVersionsModal && kbVersionsArticle && (
  <div className="modal-overlay" onClick={() => setShowKbVersionsModal(false)}>
    <div className="modal-content" style={{ maxWidth: "700px" }} onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <div className="modal-title">
          <h3>🕒 Audit Revision History</h3>
          <p>{kbVersionsArticle.title} • Current version: v{kbVersionsArticle.current_version}</p>
        </div>
        <button type="button" className="close-btn" onClick={() => setShowKbVersionsModal(false)}>✕</button>
      </div>

      <div style={{ padding: "16px 0", maxHeight: "60vh", overflowY: "auto" }}>
        {kbVersionsLoading ? (
          <div className="portal-loading-state"><div className="portal-spinner" /><p>Loading audit versions...</p></div>
        ) : kbVersionsList.length === 0 ? (
          <p style={{ color: "#64748b", textAlign: "center" }}>No previous revisions found.</p>
        ) : (
          <div className="kb-timeline">
            {kbVersionsList.map((ver) => (
              <div key={ver.id} className="kb-timeline-item">
                <div className="kb-timeline-marker">v{ver.version_number}</div>
                <div className="kb-timeline-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong style={{ fontSize: "14px", color: "#0f172a" }}>{ver.change_summary || "Version Update"}</strong>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>
                      {ver.created_at ? new Date(ver.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                  <div style={{ fontSize: "12px", color: "#475569", marginTop: "4px" }}>
                    Author / Editor: <strong>{ver.edited_by_name || "System"}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="modal-actions-footer">
        <button
          type="button"
          className="modal-cancel-btn"
          onClick={() => setShowKbVersionsModal(false)}
        >
          Close
        </button>
      </div>
    </div>
  </div>
)}

{/* 3. KB CATEGORY MODAL */}
{showKbCategoryModal && (
  <div className="modal-overlay" onClick={() => setShowKbCategoryModal(false)}>
    <div className="modal-content" style={{ maxWidth: "520px" }} onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <div className="modal-title">
          <h3>{editingKbCategory ? "📁 Edit Category" : "➕ Add Category"}</h3>
          <p>Organize self-service and engineering runbooks.</p>
        </div>
        <button type="button" className="close-btn" onClick={() => setShowKbCategoryModal(false)}>✕</button>
      </div>

      <form onSubmit={handleSaveKbCategory}>
        <div style={{ padding: "16px 0" }}>
          <div className="form-group">
            <label>Category Name *</label>
            <input
              type="text"
              placeholder="e.g. Network &amp; VPN"
              value={kbCategoryForm.name}
              onChange={(e) => setKbCategoryForm({ ...kbCategoryForm, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <input
              type="text"
              placeholder="Brief explanation of topics covered in this category"
              value={kbCategoryForm.description}
              onChange={(e) => setKbCategoryForm({ ...kbCategoryForm, description: e.target.value })}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            <div className="form-group">
              <label>Icon Style</label>
              <select
                value={kbCategoryForm.icon}
                onChange={(e) => setKbCategoryForm({ ...kbCategoryForm, icon: e.target.value })}
              >
                <option value="cloud">☁️ Cloud (M365)</option>
                <option value="network">🌐 Network</option>
                <option value="shield">🛡️ Security / MFA</option>
                <option value="laptop">💻 Hardware</option>
                <option value="database">💾 Backup / BDR</option>
                <option value="lock">🔒 Internal SOP</option>
                <option value="book">📖 General Guide</option>
              </select>
            </div>

            <div className="form-group">
              <label>Display Order</label>
              <input
                type="number"
                value={kbCategoryForm.display_order}
                onChange={(e) => setKbCategoryForm({ ...kbCategoryForm, display_order: e.target.value })}
              />
            </div>
          </div>
        </div>

        <div className="modal-actions-footer">
          <button
            type="button"
            className="modal-cancel-btn"
            onClick={() => setShowKbCategoryModal(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="modal-confirm-btn"
            disabled={kbSavingCategory}
          >
            {kbSavingCategory ? "Saving..." : editingKbCategory ? "Save Changes" : "Create Category"}
          </button>
        </div>
      </form>
    </div>
  </div>
)}

{/* 4. INTERNAL ARTICLE DETAIL VIEWER MODAL */}
{kbActiveArticle && (
  <div className="modal-overlay" onClick={() => setKbActiveArticle(null)}>
    <div className="modal-content" style={{ maxWidth: "840px" }} onClick={(e) => e.stopPropagation()}>
      <div className="modal-header">
        <div>
          <div className="kb-badge-group" style={{ marginBottom: "6px" }}>
            <span className={`kb-vis-badge ${kbActiveArticle.visibility === "internal" ? "badge-internal" : "badge-public"}`}>
              {kbActiveArticle.visibility === "internal" ? "🔒 Internal Runbook" : "🌐 Public Article"}
            </span>
            <span className="kb-version-badge">v{kbActiveArticle.current_version}</span>
            <span className="kb-meta-item">📁 {kbActiveArticle.category_name}</span>
          </div>
          <h2 style={{ fontSize: "18px", color: "#0f172a", margin: 0 }}>{kbActiveArticle.title}</h2>
        </div>
        <button type="button" className="close-btn" onClick={() => setKbActiveArticle(null)}>✕</button>
      </div>

      <div style={{ padding: "16px 0", maxHeight: "65vh", overflowY: "auto" }}>
        {renderSimpleMarkdown(kbActiveArticle.content)}
      </div>

      <div className="modal-actions-footer" style={{ justifyContent: "space-between" }}>
        <div style={{ fontSize: "12px", color: "#64748b" }}>
          👁 {kbActiveArticle.view_count} views • ⭐ {kbActiveArticle.helpfulness_score}% helpful
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            type="button"
            className={`btn-portal-secondary ${copiedSolutionId === kbActiveArticle.id ? "copied" : ""}`}
            onClick={() => handleCopySolution(kbActiveArticle.content, kbActiveArticle.id)}
          >
            {copiedSolutionId === kbActiveArticle.id ? "✓ Copied to Clipboard!" : "📋 Copy Solution to Clipboard"}
          </button>
          {(isAdmin || isManager) && (
            <button
              type="button"
              className="btn-portal-primary"
              onClick={() => {
                const target = kbActiveArticle;
                setKbActiveArticle(null);
                handleOpenEditKbArticle(target);
              }}
            >
              ✏️ Edit Article
            </button>
          )}
        </div>
      </div>
    </div>
  </div>
)}

    </div>
  );
}

export default App;