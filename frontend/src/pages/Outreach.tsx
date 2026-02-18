import { useCallback, useState } from "react";
import MailOutline from "@mui/icons-material/MailOutline";
import SendOutlined from "@mui/icons-material/SendOutlined";
import CheckOutlined from "@mui/icons-material/CheckOutlined";
import AddOutlined from "@mui/icons-material/AddOutlined";
import CloseOutlined from "@mui/icons-material/CloseOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import {
  Box,
  Stack,
  Button,
  Paper,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  ToggleButtonGroup,
  ToggleButton,
  TextField,
  Alert,
  IconButton,
} from "@mui/material";
import { useApi } from "../hooks/useApi";
import {
  listEmails,
  approveEmail,
  sendEmail,
  composeEmail,
  updateEmailDraft,
  deleteEmail,
} from "../lib/api";
import type { Email, EmailType } from "../types";

// ── Email templates ──────────────────────────────────────────────────────

const EMAIL_TEMPLATES: Record<
  EmailType,
  { subject: string; body: string }
> = {
  outreach: {
    subject: "Exciting Career Opportunity — [Position Title]",
    body: `Hi [Candidate Name],

I hope this message finds you well. I came across your profile and was very impressed by your background and experience.

We are currently looking for talented professionals to join our team, and I believe your skills would be a great fit for a role we have open.

Here are a few highlights:
• Competitive compensation and benefits
• Collaborative and innovative team environment
• Opportunities for growth and career development

Would you be open to a brief conversation to learn more? I'd love to share the details and answer any questions you might have.

Looking forward to hearing from you!

Best regards`,
  },
  followup: {
    subject: "Following Up — Career Opportunity",
    body: `Hi [Candidate Name],

I wanted to follow up on my previous message regarding the opportunity I shared with you.

I understand you may be busy, but I wanted to reiterate my interest in connecting with you. The role is still available and I think it could be a great match for your experience.

Would you have 15 minutes this week for a quick call?

Best regards`,
  },
  interview_invite: {
    subject: "Interview Invitation — [Position Title]",
    body: `Hi [Candidate Name],

Thank you for your interest in the position. We were very impressed with your background and would like to invite you to an interview.

Here are the details:
• Date: [Date]
• Time: [Time]
• Format: [Video call / In-person]
• Duration: Approximately 45 minutes

Please let me know if this works for you, or if you'd prefer an alternative time.

Looking forward to speaking with you!

Best regards`,
  },
  rejection: {
    subject: "Update on Your Application",
    body: `Hi [Candidate Name],

Thank you for taking the time to speak with us about the opportunity. We truly appreciated learning about your experience and accomplishments.

After careful consideration, we have decided to move forward with other candidates whose qualifications more closely align with our current needs.

This decision was not easy, and we encourage you to apply for future openings that match your skills. We will keep your profile on file for future reference.

We wish you all the best in your career journey.

Warm regards`,
  },
};

const EMAIL_TYPE_LABELS: Record<EmailType, string> = {
  outreach: "Outreach",
  followup: "Follow-up",
  interview_invite: "Interview Invite",
  rejection: "Rejection",
};

// ── Compose / Edit Modal ─────────────────────────────────────────────────

interface ComposeModalProps {
  draft?: Email;
  onClose: () => void;
  onDone: () => void;
}

function ComposeModal({ draft, onClose, onDone }: ComposeModalProps) {
  const isEdit = !!draft;

  const [emailType, setEmailType] = useState<EmailType>(
    draft?.email_type ?? "outreach"
  );
  const [toEmail, setToEmail] = useState(draft?.to_email ?? "");
  const [subject, setSubject] = useState(
    draft?.subject ?? EMAIL_TEMPLATES.outreach.subject
  );
  const [body, setBody] = useState(
    draft?.body ?? EMAIL_TEMPLATES.outreach.body
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleTypeChange = (type: EmailType) => {
    setEmailType(type);
    // Only auto-fill template content for new emails
    if (!isEdit) {
      setSubject(EMAIL_TEMPLATES[type].subject);
      setBody(EMAIL_TEMPLATES[type].body);
    }
  };

  const handleSave = async (andSend: boolean) => {
    if (!toEmail.trim()) {
      setError("Recipient email is required");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const payload = {
        to_email: toEmail.trim(),
        subject,
        body,
        email_type: emailType,
      };

      let emailId: string;
      if (isEdit) {
        const updated = await updateEmailDraft(draft.id, payload);
        emailId = updated.id;
      } else {
        const created = await composeEmail(payload);
        emailId = created.id;
      }

      if (andSend) {
        await sendEmail(emailId);
      }
      onDone();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to save email";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={true} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pb: 1,
        }}
      >
        <Typography variant="h6" component="span">
          {isEdit ? "Edit Draft" : "Compose Email"}
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseOutlined />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        <Stack spacing={3} sx={{ pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}

          {/* Email Type */}
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
              Template
            </Typography>
            <ToggleButtonGroup
              value={emailType}
              exclusive
              size="small"
              onChange={(_e, val) => {
                if (val !== null) handleTypeChange(val as EmailType);
              }}
            >
              {(Object.keys(EMAIL_TYPE_LABELS) as EmailType[]).map((type) => (
                <ToggleButton key={type} value={type}>
                  {EMAIL_TYPE_LABELS[type]}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>

          {/* To */}
          <TextField
            label="To"
            type="email"
            value={toEmail}
            onChange={(e) => setToEmail(e.target.value)}
            placeholder="recipient@example.com"
            size="small"
            fullWidth
          />

          {/* Subject */}
          <TextField
            label="Subject"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            size="small"
            fullWidth
          />

          {/* Body */}
          <TextField
            label="Body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            multiline
            rows={14}
            fullWidth
          />
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined" color="inherit">
          Cancel
        </Button>
        <Button
          onClick={() => handleSave(false)}
          disabled={saving}
          variant="outlined"
          color="inherit"
        >
          {isEdit ? "Save Draft" : "Save as Draft"}
        </Button>
        <Button
          onClick={() => handleSave(true)}
          disabled={saving}
          variant="contained"
          startIcon={<SendOutlined />}
        >
          {saving ? "Sending..." : "Send Now"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export default function Outreach() {
  const { data: emails, refresh } = useApi(
    useCallback(() => listEmails(), [])
  );
  const [composeMode, setComposeMode] = useState<
    { open: false } | { open: true; draft?: Email }
  >({ open: false });

  const pending = emails?.filter((e) => !e.sent) ?? [];
  const sent = emails?.filter((e) => e.sent) ?? [];

  const handleApprove = async (id: string) => {
    await approveEmail(id);
    refresh();
  };

  const handleSend = async (id: string) => {
    try {
      await sendEmail(id);
      refresh();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to send";
      alert(msg);
    }
  };

  const handleDelete = async (id: string) => {
    await deleteEmail(id);
    refresh();
  };

  return (
    <Stack spacing={3}>
      {/* Compose / Edit modal */}
      {composeMode.open && (
        <ComposeModal
          draft={composeMode.draft}
          onClose={() => setComposeMode({ open: false })}
          onDone={() => {
            setComposeMode({ open: false });
            refresh();
          }}
        />
      )}

      {/* Header with compose button */}
      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="contained"
          startIcon={<AddOutlined />}
          onClick={() => setComposeMode({ open: true })}
        >
          Compose Email
        </Button>
      </Box>

      {/* Pending queue */}
      <Box>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          Pending{" "}
          <Typography
            component="span"
            variant="body2"
            sx={{ color: "text.secondary" }}
          >
            ({pending.length})
          </Typography>
        </Typography>

        {pending.length > 0 ? (
          <Stack spacing={1.5}>
            {pending.map((e) => (
              <Paper key={e.id} variant="outlined" sx={{ p: 2.5 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                  }}
                >
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <Typography
                        variant="body1"
                        sx={{
                          fontWeight: 500,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {e.subject}
                      </Typography>
                      {!e.approved && (
                        <Chip label="Draft" color="warning" size="small" />
                      )}
                      {e.approved && (
                        <Chip label="Approved" color="success" size="small" />
                      )}
                    </Stack>
                    <Typography
                      variant="body2"
                      sx={{ color: "text.secondary", mt: 0.5 }}
                    >
                      To: {e.to_email || e.candidate_name} &middot;{" "}
                      <Box component="span" sx={{ textTransform: "capitalize" }}>
                        {e.email_type.replace(/_/g, " ")}
                      </Box>
                    </Typography>
                  </Box>

                  <Stack direction="row" spacing={1} sx={{ ml: 2, flexShrink: 0 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      color="inherit"
                      startIcon={<EditOutlined />}
                      onClick={() =>
                        setComposeMode({ open: true, draft: e })
                      }
                    >
                      Edit
                    </Button>
                    {!e.approved && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="inherit"
                        startIcon={<CheckOutlined />}
                        onClick={() => handleApprove(e.id)}
                      >
                        Approve
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={<SendOutlined />}
                      onClick={() => handleSend(e.id)}
                    >
                      Send
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="error"
                      onClick={() => handleDelete(e.id)}
                      title="Delete"
                    >
                      <DeleteOutline sx={{ fontSize: 18 }} />
                    </Button>
                  </Stack>
                </Box>

                <Box
                  sx={{
                    mt: 1.5,
                    whiteSpace: "pre-wrap",
                    bgcolor: "grey.50",
                    borderRadius: 1,
                    p: 1.5,
                  }}
                >
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    {e.body}
                  </Typography>
                </Box>
              </Paper>
            ))}
          </Stack>
        ) : (
          <Paper
            variant="outlined"
            sx={{
              p: 4,
              textAlign: "center",
              borderStyle: "dashed",
            }}
          >
            <MailOutline sx={{ fontSize: 32, color: "grey.400", mx: "auto" }} />
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 1 }}>
              No pending emails. Click "Compose Email" to create one.
            </Typography>
          </Paper>
        )}
      </Box>

      {/* Sent emails */}
      <Box>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          Sent{" "}
          <Typography
            component="span"
            variant="body2"
            sx={{ color: "text.secondary" }}
          >
            ({sent.length})
          </Typography>
        </Typography>

        {sent.length > 0 ? (
          <Stack spacing={1}>
            {sent.map((e) => (
              <Paper
                key={e.id}
                variant="outlined"
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  px: 2,
                  py: 1.5,
                }}
              >
                <Box>
                  <Typography
                    component="span"
                    variant="body2"
                    sx={{ fontWeight: 500 }}
                  >
                    {e.subject}
                  </Typography>
                  <Typography
                    component="span"
                    variant="body2"
                    sx={{ color: "text.secondary", ml: 1 }}
                  >
                    to {e.to_email || e.candidate_name}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    {e.sent_at
                      ? new Date(e.sent_at).toLocaleDateString()
                      : ""}
                  </Typography>
                  {e.reply_received && (
                    <Chip label="Replied" color="success" size="small" />
                  )}
                </Stack>
              </Paper>
            ))}
          </Stack>
        ) : (
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            No sent emails yet.
          </Typography>
        )}
      </Box>
    </Stack>
  );
}
