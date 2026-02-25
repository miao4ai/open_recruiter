import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import SaveOutlined from "@mui/icons-material/SaveOutlined";
import ScienceOutlined from "@mui/icons-material/ScienceOutlined";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import { useSnackbar } from "notistack";
import { useApi } from "../hooks/useApi";
import {
  getSettings,
  updateSettings,
  testLlm,
  testEmail,
  getOllamaStatus,
  pullOllamaModel,
} from "../lib/api";
import type { OllamaStatus } from "../lib/api";
import type { Settings as SettingsType } from "../types";

const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-haiku-4-20250414", label: "Claude Haiku 4" },
    { value: "claude-opus-4-20250514", label: "Claude Opus 4" },
  ],
  openai: [
    { value: "gpt-5.2-pro", label: "GPT-5.2 Pro" },
    { value: "gpt-5.1", label: "GPT-5.1" },
    { value: "gpt-4.1", label: "GPT-4.1" },
    { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
  ],
  gemini: [
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  ],
  ollama: [
    { value: "qwen2.5:3b", label: "Qwen 2.5 3B (2 GB)" },
    { value: "qwen2.5:7b", label: "Qwen 2.5 7B (4.7 GB)" },
    { value: "qwen2.5:14b", label: "Qwen 2.5 14B (9 GB)" },
  ],
};

const DEFAULT_MODEL: Record<string, string> = {
  anthropic: "claude-sonnet-4-20250514",
  openai: "gpt-5.1",
  gemini: "gemini-2.5-flash",
  ollama: "qwen2.5:7b",
};

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "zh", label: "中文（简体）" },
  { value: "zh-TW", label: "中文（繁體）" },
  { value: "es", label: "Español" },
];

export default function Settings() {
  const { t, i18n } = useTranslation();
  const { data: saved } = useApi(useCallback(() => getSettings(), []));
  const [form, setForm] = useState<SettingsType>({
    llm_provider: "anthropic",
    llm_model: "",
    anthropic_api_key: "",
    openai_api_key: "",
    gemini_api_key: "",
    ollama_base_url: "http://localhost:11434",
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
  const { enqueueSnackbar } = useSnackbar();

  // Ollama state
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState(0);
  const [pullStatus, setPullStatus] = useState("");

  useEffect(() => {
    if (saved) setForm(saved);
  }, [saved]);

  // Fetch Ollama status when provider changes to ollama
  useEffect(() => {
    if (form.llm_provider === "ollama") {
      getOllamaStatus().then(setOllamaStatus).catch(() => setOllamaStatus(null));
    }
  }, [form.llm_provider]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    if (name === "llm_provider") {
      const models = MODEL_OPTIONS[value] ?? [];
      const modelExists = models.some((m) => m.value === form.llm_model);
      setForm({
        ...form,
        llm_provider: value,
        llm_model: modelExists ? form.llm_model : (DEFAULT_MODEL[value] ?? ""),
      });
    } else {
      setForm({ ...form, [name]: value });
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(form);
      enqueueSnackbar(t("settings.settingsSaved"), { variant: "success" });
    } catch {
      enqueueSnackbar(t("settings.failedToSave"), { variant: "error", persist: true });
    } finally {
      setSaving(false);
    }
  };

  const handleTestLlm = async () => {
    enqueueSnackbar(t("settings.savingAndTestingLlm"), { variant: "info" });
    try {
      await updateSettings(form);
    } catch {
      enqueueSnackbar(t("settings.failedToSave"), { variant: "error", persist: true });
      return;
    }
    try {
      const res = await testLlm();
      if (res.status === "ok") {
        enqueueSnackbar(t("settings.llmOk", { response: res.response }), { variant: "success" });
      } else {
        enqueueSnackbar(t("settings.llmError", { message: res.message }), { variant: "error", persist: true });
      }
    } catch {
      enqueueSnackbar(t("settings.failedToTestLlm"), { variant: "error", persist: true });
    }
  };

  const handleTestEmail = async () => {
    enqueueSnackbar(t("settings.savingAndTestingEmail"), { variant: "info" });
    try {
      await updateSettings(form);
    } catch {
      enqueueSnackbar(t("settings.failedToSave"), { variant: "error", persist: true });
      return;
    }
    try {
      const res = await testEmail();
      if (res.status === "ok") {
        enqueueSnackbar(t("settings.emailOk", { backend: res.backend, message: res.message }), { variant: "success" });
      } else {
        enqueueSnackbar(t("settings.emailError", { message: res.message }), { variant: "error", persist: true });
      }
    } catch {
      enqueueSnackbar(t("settings.failedToTestEmail"), { variant: "error", persist: true });
    }
  };

  const handlePullModel = async () => {
    setPulling(true);
    setPullProgress(0);
    setPullStatus(t("settings.downloading"));
    try {
      await pullOllamaModel(form.llm_model, (progress) => {
        setPullStatus(progress.status);
        if (progress.total && progress.completed) {
          setPullProgress(Math.round((progress.completed / progress.total) * 100));
        }
      });
      setPullStatus("");
      setPullProgress(100);
      const status = await getOllamaStatus();
      setOllamaStatus(status);
      enqueueSnackbar(t("settings.modelDownloaded"), { variant: "success" });
    } catch {
      enqueueSnackbar(t("settings.modelDownloadFailed"), { variant: "error" });
    } finally {
      setPulling(false);
    }
  };

  const isModelInstalled = ollamaStatus?.running && ollamaStatus.installed_models.some(
    (m) => m === form.llm_model || m.startsWith(form.llm_model.split(":")[0] + ":" + form.llm_model.split(":")[1])
  );

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Stack spacing={3}>
        {/* Language */}
        <Section title={t("settings.language")}>
          <TextField
            select
            label={t("settings.language")}
            value={i18n.language?.startsWith("zh-TW") ? "zh-TW" : (i18n.language?.substring(0, 2) ?? "en")}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
            fullWidth
          >
            {LANGUAGES.map((l) => (
              <MenuItem key={l.value} value={l.value}>
                {l.label}
              </MenuItem>
            ))}
          </TextField>
          <FormHelperText>{t("settings.languageHint")}</FormHelperText>
        </Section>

        {/* LLM Configuration */}
        <Section title={t("settings.llmConfig")}>
          <TextField
            select
            label={t("settings.provider")}
            name="llm_provider"
            value={form.llm_provider}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="anthropic">Anthropic</MenuItem>
            <MenuItem value="openai">OpenAI</MenuItem>
            <MenuItem value="gemini">Google Gemini</MenuItem>
            <MenuItem value="ollama">Ollama ({t("settings.localFree")})</MenuItem>
          </TextField>
          <TextField
            select
            label={t("settings.model")}
            name="llm_model"
            value={form.llm_model}
            onChange={handleChange}
            fullWidth
          >
            {(MODEL_OPTIONS[form.llm_provider] ?? []).map((m) => (
              <MenuItem key={m.value} value={m.value}>
                {m.label}
              </MenuItem>
            ))}
          </TextField>
          {form.llm_provider === "anthropic" && (
            <TextField
              label={t("settings.anthropicApiKey")}
              name="anthropic_api_key"
              type="password"
              value={form.anthropic_api_key}
              onChange={handleChange}
              placeholder="sk-ant-..."
              fullWidth
            />
          )}
          {form.llm_provider === "openai" && (
            <TextField
              label={t("settings.openaiApiKey")}
              name="openai_api_key"
              type="password"
              value={form.openai_api_key}
              onChange={handleChange}
              placeholder="sk-..."
              fullWidth
            />
          )}
          {form.llm_provider === "gemini" && (
            <TextField
              label={t("settings.geminiApiKey")}
              name="gemini_api_key"
              type="password"
              value={form.gemini_api_key}
              onChange={handleChange}
              placeholder="AI..."
              fullWidth
            />
          )}
          {form.llm_provider === "ollama" && (
            <>
              {/* Ollama status */}
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                <Chip
                  label={ollamaStatus?.running ? t("settings.ollamaRunning") : t("settings.ollamaNotRunning")}
                  color={ollamaStatus?.running ? "success" : "error"}
                  size="small"
                />
                {!ollamaStatus?.running && (
                  <Typography variant="body2" color="text.secondary">
                    {t("settings.ollamaInstallHint")}
                  </Typography>
                )}
              </Box>

              {/* Model download */}
              {ollamaStatus?.running && !isModelInstalled && (
                <Box>
                  {pulling ? (
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                        {pullStatus}
                      </Typography>
                      <LinearProgress variant="determinate" value={pullProgress} />
                    </Box>
                  ) : (
                    <Button
                      variant="outlined"
                      startIcon={<DownloadOutlined />}
                      onClick={handlePullModel}
                    >
                      {t("settings.downloadModel")}
                    </Button>
                  )}
                </Box>
              )}

              {/* Model installed */}
              {isModelInstalled && (
                <Chip label={t("settings.modelReady")} color="success" size="small" />
              )}

              <FormHelperText>{t("settings.noApiKeyNeeded")}</FormHelperText>

              {/* Base URL */}
              <TextField
                label={t("settings.ollamaBaseUrl")}
                name="ollama_base_url"
                value={form.ollama_base_url || "http://localhost:11434"}
                onChange={handleChange}
                fullWidth
                size="small"
              />
            </>
          )}
          <Button
            variant="outlined"
            startIcon={<ScienceOutlined />}
            onClick={handleTestLlm}
          >
            {t("settings.testLlm")}
          </Button>
        </Section>

        {/* Email Configuration */}
        <Section title={t("settings.emailConfig")}>
          <TextField
            select
            label={t("settings.backend")}
            name="email_backend"
            value={form.email_backend}
            onChange={handleChange}
            fullWidth
          >
            <MenuItem value="console">{t("settings.consoleOption")}</MenuItem>
            <MenuItem value="gmail">{t("settings.gmailOption")}</MenuItem>
            <MenuItem value="smtp">{t("settings.customSmtp")}</MenuItem>
            <MenuItem value="sendgrid">{t("settings.sendgridOption")}</MenuItem>
          </TextField>
          <Box>
            <TextField
              label={t("settings.fromEmail")}
              name="email_from"
              value={form.email_from}
              onChange={handleChange}
              placeholder="recruiter@company.com"
              fullWidth
              slotProps={{ input: { readOnly: true } }}
            />
            <FormHelperText>{t("settings.autoSetEmail")}</FormHelperText>
          </Box>
          {form.email_backend === "sendgrid" && (
            <TextField
              label={t("settings.sendgridApiKey")}
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
                    label={t("settings.smtpHost")}
                    name="smtp_host"
                    value={form.smtp_host}
                    onChange={handleChange}
                    placeholder="smtp.example.com"
                    fullWidth
                  />
                  <TextField
                    label={t("settings.smtpPort")}
                    name="smtp_port"
                    type="number"
                    value={form.smtp_port}
                    onChange={handleChange}
                    placeholder="587"
                    fullWidth
                  />
                  <TextField
                    label={t("settings.smtpUsername")}
                    name="smtp_username"
                    value={form.smtp_username}
                    onChange={handleChange}
                    placeholder="your-email@example.com"
                    fullWidth
                  />
                </>
              )}
              <TextField
                label={form.email_backend === "gmail" ? t("settings.gmailAppPassword") : t("settings.smtpPassword")}
                name="smtp_password"
                type="password"
                value={form.smtp_password}
                onChange={handleChange}
                placeholder={form.email_backend === "gmail" ? "xxxx xxxx xxxx xxxx" : "password"}
                fullWidth
              />
              {form.email_backend === "gmail" && (
                <FormHelperText>
                  {t("settings.gmailAppPasswordHint")}
                </FormHelperText>
              )}
            </>
          )}
          <Button
            variant="outlined"
            startIcon={<ScienceOutlined />}
            onClick={handleTestEmail}
          >
            {t("settings.testEmail")}
          </Button>
        </Section>

        {/* IMAP Configuration (Reply Detection) */}
        {(form.email_backend === "gmail" || form.email_backend === "smtp") && (
          <Section title={t("settings.imapConfig")}>
            <Typography variant="body2" color="text.secondary" sx={{ mt: -1, mb: 1 }}>
              {t("settings.imapHint")}
            </Typography>
            {form.email_backend === "gmail" ? (
              <>
                <TextField
                  label={t("settings.imapHost")}
                  name="imap_host"
                  value={form.imap_host || "imap.gmail.com"}
                  onChange={handleChange}
                  placeholder="imap.gmail.com"
                  fullWidth
                />
                <Box>
                  <TextField
                    label={t("settings.imapPassword")}
                    name="imap_password"
                    type="password"
                    value={form.imap_password}
                    onChange={handleChange}
                    placeholder={t("settings.sameAsGmail")}
                    fullWidth
                  />
                  <FormHelperText>{t("settings.useAppPassword")}</FormHelperText>
                </Box>
              </>
            ) : (
              <>
                <TextField
                  label={t("settings.imapHost")}
                  name="imap_host"
                  value={form.imap_host}
                  onChange={handleChange}
                  placeholder="imap.example.com"
                  fullWidth
                />
                <TextField
                  label={t("settings.imapPort")}
                  name="imap_port"
                  type="number"
                  value={form.imap_port}
                  onChange={handleChange}
                  placeholder="993"
                  fullWidth
                />
                <TextField
                  label={t("settings.imapUsername")}
                  name="imap_username"
                  value={form.imap_username}
                  onChange={handleChange}
                  placeholder="your-email@example.com"
                  fullWidth
                />
                <TextField
                  label={t("settings.imapPassword")}
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
        <Section title={t("settings.recruiterProfile")}>
          <TextField
            label={t("settings.fieldName")}
            name="recruiter_name"
            value={form.recruiter_name}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label={t("settings.fieldEmail")}
            name="recruiter_email"
            value={form.recruiter_email}
            onChange={handleChange}
            fullWidth
          />
          <TextField
            label={t("settings.fieldCompany")}
            name="recruiter_company"
            value={form.recruiter_company}
            onChange={handleChange}
            fullWidth
          />
        </Section>

        {/* Save */}
        <Box>
          <Button
            variant="contained"
            startIcon={<SaveOutlined />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? t("common.saving") : t("settings.saveSettings")}
          </Button>
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
