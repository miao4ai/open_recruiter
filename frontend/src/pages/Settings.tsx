import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";
import SaveOutlined from "@mui/icons-material/SaveOutlined";
import ScienceOutlined from "@mui/icons-material/ScienceOutlined";
import { useApi } from "../hooks/useApi";
import {
  getSettings,
  updateSettings,
  testLlm,
  testEmail,
} from "../lib/api";
import type { Settings as SettingsType } from "../types";

export default function Settings() {
  const { data: saved } = useApi(useCallback(() => getSettings(), []));
  const [form, setForm] = useState<SettingsType>({
    llm_provider: "anthropic",
    llm_model: "",
    anthropic_api_key: "",
    openai_api_key: "",
    email_backend: "console",
    sendgrid_api_key: "",
    email_from: "",
    smtp_host: "",
    smtp_port: 587,
    smtp_username: "",
    smtp_password: "",
    imap_host: "",
    imap_port: 993,
    imap_username: "",
    imap_password: "",
    recruiter_name: "",
    recruiter_email: "",
    recruiter_company: "",
  });
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    if (saved) setForm(saved);
  }, [saved]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(form);
      setTestResult("Settings saved.");
    } finally {
      setSaving(false);
    }
  };

  const handleTestLlm = async () => {
    setTestResult("Testing LLM...");
    const res = await testLlm();
    setTestResult(
      res.status === "ok"
        ? `LLM OK — response: "${res.response}"`
        : `LLM Error: ${res.message}`
    );
  };

  const handleTestEmail = async () => {
    setTestResult("Testing Email...");
    const res = await testEmail();
    setTestResult(
      res.status === "ok"
        ? `Email OK (${res.backend}): ${res.message}`
        : `Email Error: ${res.message}`
    );
  };

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Stack spacing={3}>
        {/* LLM Configuration */}
        <Section title="LLM Configuration">
          <TextField
            select
            label="Provider"
            name="llm_provider"
            value={form.llm_provider}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="anthropic">Anthropic</MenuItem>
            <MenuItem value="openai">OpenAI</MenuItem>
          </TextField>
          <TextField
            label="Model (optional)"
            name="llm_model"
            value={form.llm_model}
            onChange={handleChange}
            placeholder="e.g. claude-sonnet-4-20250514"
            fullWidth
          />
          <TextField
            label="Anthropic API Key"
            name="anthropic_api_key"
            type="password"
            value={form.anthropic_api_key}
            onChange={handleChange}
            placeholder="sk-ant-..."
            fullWidth
          />
          <TextField
            label="OpenAI API Key"
            name="openai_api_key"
            type="password"
            value={form.openai_api_key}
            onChange={handleChange}
            placeholder="sk-..."
            fullWidth
          />
          <Button
            variant="outlined"
            startIcon={<ScienceOutlined />}
            onClick={handleTestLlm}
          >
            Test LLM
          </Button>
        </Section>

        {/* Email Configuration */}
        <Section title="Email Configuration">
          <TextField
            select
            label="Backend"
            name="email_backend"
            value={form.email_backend}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="console">Console (print to terminal)</MenuItem>
            <MenuItem value="gmail">Gmail (SMTP)</MenuItem>
            <MenuItem value="smtp">Custom SMTP</MenuItem>
            <MenuItem value="sendgrid">SendGrid</MenuItem>
          </TextField>
          <Box>
            <TextField
              label="From Email"
              name="email_from"
              value={form.email_from}
              onChange={handleChange}
              placeholder="recruiter@company.com"
              fullWidth
              slotProps={{ input: { readOnly: true } }}
            />
            <FormHelperText>Auto-set to your login email</FormHelperText>
          </Box>
          {form.email_backend === "sendgrid" && (
            <TextField
              label="SendGrid API Key"
              name="sendgrid_api_key"
              type="password"
              value={form.sendgrid_api_key}
              onChange={handleChange}
              placeholder="SG...."
              fullWidth
            />
          )}
          {(form.email_backend === "gmail" || form.email_backend === "smtp") && (
            <>
              {form.email_backend === "smtp" && (
                <>
                  <TextField
                    label="SMTP Host"
                    name="smtp_host"
                    value={form.smtp_host}
                    onChange={handleChange}
                    placeholder="smtp.example.com"
                    fullWidth
                  />
                  <TextField
                    label="SMTP Port"
                    name="smtp_port"
                    type="number"
                    value={form.smtp_port}
                    onChange={handleChange}
                    placeholder="587"
                    fullWidth
                  />
                  <TextField
                    label="SMTP Username"
                    name="smtp_username"
                    value={form.smtp_username}
                    onChange={handleChange}
                    placeholder="your-email@example.com"
                    fullWidth
                  />
                </>
              )}
              <TextField
                label={form.email_backend === "gmail" ? "Gmail App Password" : "SMTP Password"}
                name="smtp_password"
                type="password"
                value={form.smtp_password}
                onChange={handleChange}
                placeholder={form.email_backend === "gmail" ? "xxxx xxxx xxxx xxxx" : "password"}
                fullWidth
              />
              {form.email_backend === "gmail" && (
                <FormHelperText>
                  Go to Google Account &rarr; Security &rarr; 2-Step Verification &rarr; App Passwords to generate one.
                </FormHelperText>
              )}
            </>
          )}
          <Button
            variant="outlined"
            startIcon={<ScienceOutlined />}
            onClick={handleTestEmail}
          >
            Test Email
          </Button>
        </Section>

        {/* IMAP Configuration (Reply Detection) */}
        {(form.email_backend === "gmail" || form.email_backend === "smtp") && (
          <Section title="IMAP Configuration (Reply Detection)">
            <Typography variant="body2" color="text.secondary" sx={{ mt: -1, mb: 1 }}>
              Configure IMAP to auto-detect when candidates reply to your emails.
            </Typography>
            {form.email_backend === "gmail" ? (
              <>
                <TextField
                  label="IMAP Host"
                  name="imap_host"
                  value={form.imap_host || "imap.gmail.com"}
                  onChange={handleChange}
                  placeholder="imap.gmail.com"
                  fullWidth
                />
                <Box>
                  <TextField
                    label="IMAP Password"
                    name="imap_password"
                    type="password"
                    value={form.imap_password}
                    onChange={handleChange}
                    placeholder="Same as Gmail App Password"
                    fullWidth
                  />
                  <FormHelperText>Use the same App Password as above</FormHelperText>
                </Box>
              </>
            ) : (
              <>
                <TextField
                  label="IMAP Host"
                  name="imap_host"
                  value={form.imap_host}
                  onChange={handleChange}
                  placeholder="imap.example.com"
                  fullWidth
                />
                <TextField
                  label="IMAP Port"
                  name="imap_port"
                  type="number"
                  value={form.imap_port}
                  onChange={handleChange}
                  placeholder="993"
                  fullWidth
                />
                <TextField
                  label="IMAP Username"
                  name="imap_username"
                  value={form.imap_username}
                  onChange={handleChange}
                  placeholder="your-email@example.com"
                  fullWidth
                />
                <TextField
                  label="IMAP Password"
                  name="imap_password"
                  type="password"
                  value={form.imap_password}
                  onChange={handleChange}
                  placeholder="password"
                  fullWidth
                />
              </>
            )}
          </Section>
        )}

        {/* Recruiter Profile */}
        <Section title="Recruiter Profile">
          <TextField
            label="Name"
            name="recruiter_name"
            value={form.recruiter_name}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label="Email"
            name="recruiter_email"
            value={form.recruiter_email}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label="Company"
            name="recruiter_company"
            value={form.recruiter_company}
            onChange={handleChange}
            fullWidth
          />
        </Section>

        {/* Save */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Button
            variant="contained"
            startIcon={<SaveOutlined />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Settings"}
          </Button>
          {testResult && (
            <Typography variant="body2" color="text.secondary">
              {testResult}
            </Typography>
          )}
        </Box>
      </Stack>
    </Box>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        {title}
      </Typography>
      <Stack spacing={2}>{children}</Stack>
    </Paper>
  );
}
