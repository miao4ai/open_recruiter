import { useState } from "react";
import { useTranslation } from "react-i18next";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import Alert from "@mui/material/Alert";
import Stepper from "@mui/material/Stepper";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import FormHelperText from "@mui/material/FormHelperText";
import SmartToyOutlined from "@mui/icons-material/SmartToyOutlined";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import ArrowForward from "@mui/icons-material/ArrowForward";
import ArrowBack from "@mui/icons-material/ArrowBack";
import ScienceOutlined from "@mui/icons-material/ScienceOutlined";
import { updateSettings, testLlm, testEmail } from "../lib/api";

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
};

const DEFAULT_MODEL: Record<string, string> = {
  anthropic: "claude-sonnet-4-20250514",
  openai: "gpt-5.1",
  gemini: "gemini-2.5-flash",
};

const PROVIDER_INFO = [
  { value: "anthropic", label: "Anthropic (Claude)", color: "#d4a574" },
  { value: "openai", label: "OpenAI (GPT)", color: "#74aa9c" },
  { value: "gemini", label: "Google (Gemini)", color: "#4285f4" },
];

const API_KEY_FIELD: Record<string, string> = {
  anthropic: "anthropic_api_key",
  openai: "openai_api_key",
  gemini: "gemini_api_key",
};

const API_KEY_PLACEHOLDER: Record<string, string> = {
  anthropic: "sk-ant-...",
  openai: "sk-...",
  gemini: "AI...",
};

const LAST_STEP = 3; // 0=provider, 1=api key, 2=email, 3=done

interface Props {
  onComplete: () => void;
}

export default function Onboarding({ onComplete }: Props) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);

  // LLM state
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState(DEFAULT_MODEL["anthropic"]);
  const [apiKey, setApiKey] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Email state
  const [emailBackend, setEmailBackend] = useState("console");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [sendgridApiKey, setSendgridApiKey] = useState("");
  const [testingEmail, setTestingEmail] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    setModel(DEFAULT_MODEL[newProvider] ?? "");
    setApiKey("");
    setTestResult(null);
  };

  const handleTestLlm = async () => {
    setTesting(true);
    setTestResult(null);
    setError("");
    try {
      await updateSettings({
        llm_provider: provider,
        llm_model: model,
        [API_KEY_FIELD[provider]]: apiKey,
      });
      const res = await testLlm();
      if (res.status === "ok") {
        setTestResult({ ok: true, message: res.response });
      } else {
        setTestResult({ ok: false, message: res.message });
      }
    } catch {
      setTestResult({ ok: false, message: "Network error" });
    } finally {
      setTesting(false);
    }
  };

  const handleTestEmail = async () => {
    setTestingEmail(true);
    setEmailTestResult(null);
    setError("");
    try {
      await saveEmailSettings();
      const res = await testEmail();
      if (res.status === "ok") {
        setEmailTestResult({ ok: true, message: res.message || "Email sent!" });
      } else {
        setEmailTestResult({ ok: false, message: res.message });
      }
    } catch {
      setEmailTestResult({ ok: false, message: "Network error" });
    } finally {
      setTestingEmail(false);
    }
  };

  const saveEmailSettings = async () => {
    const data: Record<string, string | number> = { email_backend: emailBackend };
    if (emailBackend === "gmail" || emailBackend === "smtp") {
      data.smtp_password = smtpPassword;
      if (emailBackend === "gmail") {
        data.smtp_host = "smtp.gmail.com";
        data.smtp_port = 587;
      } else {
        data.smtp_host = smtpHost;
        data.smtp_port = parseInt(smtpPort) || 587;
        data.smtp_username = smtpUsername;
      }
    } else if (emailBackend === "sendgrid") {
      data.sendgrid_api_key = sendgridApiKey;
    }
    await updateSettings(data);
  };

  const handleNext = async () => {
    setSaving(true);
    setError("");
    try {
      if (step === 1) {
        // Save LLM settings before moving to email step
        await updateSettings({
          llm_provider: provider,
          llm_model: model,
          [API_KEY_FIELD[provider]]: apiKey,
        });
      } else if (step === 2) {
        // Save email settings before moving to done
        await saveEmailSettings();
      }
      setStep(step + 1);
    } catch {
      setError(t("settings.failedToSave"));
    } finally {
      setSaving(false);
    }
  };

  const canProceed = () => {
    if (step === 0) return true;
    if (step === 1) return apiKey.length > 0;
    if (step === 2) return true; // Email is optional
    return true;
  };

  const steps = [
    t("onboarding.step1Title"),
    t("onboarding.step2Title"),
    t("onboarding.emailStepTitle"),
    t("onboarding.completedTitle"),
  ];

  return (
    <Box
      sx={{
        display: "flex",
        minHeight: "100vh",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "background.default",
        p: 2,
      }}
    >
      <Paper
        elevation={3}
        sx={{ width: "100%", maxWidth: 560, p: 4, borderRadius: 3 }}
      >
        {/* Logo */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 1,
            mb: 3,
          }}
        >
          <SmartToyOutlined sx={{ fontSize: 32, color: "primary.main" }} />
          <Typography variant="h5" fontWeight={700} letterSpacing="-0.02em">
            {t("common.appName")}
          </Typography>
        </Box>

        {/* Stepper */}
        <Stepper activeStep={step} sx={{ mb: 4 }} alternativeLabel>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Step 0: Choose provider */}
        {step === 0 && (
          <Box>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              {t("onboarding.welcome")}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 3 }}
            >
              {t("onboarding.welcomeSubtitle")}
            </Typography>

            <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
              {t("onboarding.selectProvider")}
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              {PROVIDER_INFO.map((p) => (
                <Paper
                  key={p.value}
                  variant="outlined"
                  onClick={() => handleProviderChange(p.value)}
                  sx={{
                    p: 2,
                    cursor: "pointer",
                    borderColor:
                      provider === p.value ? "primary.main" : "divider",
                    borderWidth: provider === p.value ? 2 : 1,
                    bgcolor:
                      provider === p.value
                        ? "action.selected"
                        : "transparent",
                    "&:hover": { bgcolor: "action.hover" },
                    transition: "all 0.15s",
                  }}
                >
                  <Box
                    sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
                  >
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        bgcolor: p.color,
                      }}
                    />
                    <Typography fontWeight={500}>{p.label}</Typography>
                  </Box>
                </Paper>
              ))}
            </Box>
          </Box>
        )}

        {/* Step 1: API Key + Model */}
        {step === 1 && (
          <Box>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              {t("onboarding.step2Title")}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 3 }}
            >
              {t("onboarding.step2Subtitle")}
            </Typography>

            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}
            >
              <TextField
                select
                label={t("onboarding.selectModel")}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                fullWidth
              >
                {(MODEL_OPTIONS[provider] ?? []).map((m) => (
                  <MenuItem key={m.value} value={m.value}>
                    {m.label}
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                label={t("onboarding.apiKeyLabel")}
                type="password"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setTestResult(null);
                }}
                placeholder={API_KEY_PLACEHOLDER[provider]}
                fullWidth
                helperText={
                  t(`onboarding.getKeyHint.${provider}` as const)
                }
              />

              {testResult && (
                <Alert severity={testResult.ok ? "success" : "error"}>
                  {testResult.ok
                    ? t("onboarding.testSuccess")
                    : t("onboarding.testFailed", {
                        message: testResult.message,
                      })}
                </Alert>
              )}

              <Button
                variant="outlined"
                startIcon={<ScienceOutlined />}
                onClick={handleTestLlm}
                disabled={!apiKey || testing}
              >
                {testing
                  ? t("onboarding.testing")
                  : t("onboarding.testConnection")}
              </Button>
            </Box>
          </Box>
        )}

        {/* Step 2: Email Configuration */}
        {step === 2 && (
          <Box>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              {t("onboarding.emailStepTitle")}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 3 }}
            >
              {t("onboarding.emailStepSubtitle")}
            </Typography>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
              <TextField
                select
                label={t("settings.backend")}
                value={emailBackend}
                onChange={(e) => {
                  setEmailBackend(e.target.value);
                  setEmailTestResult(null);
                }}
                fullWidth
              >
                <MenuItem value="console">{t("settings.consoleOption")}</MenuItem>
                <MenuItem value="gmail">{t("settings.gmailOption")}</MenuItem>
                <MenuItem value="smtp">{t("settings.customSmtp")}</MenuItem>
                <MenuItem value="sendgrid">{t("settings.sendgridOption")}</MenuItem>
              </TextField>

              {emailBackend === "sendgrid" && (
                <TextField
                  label={t("settings.sendgridApiKey")}
                  type="password"
                  value={sendgridApiKey}
                  onChange={(e) => setSendgridApiKey(e.target.value)}
                  placeholder="SG...."
                  fullWidth
                />
              )}

              {(emailBackend === "gmail" || emailBackend === "smtp") && (
                <>
                  {emailBackend === "smtp" && (
                    <>
                      <TextField
                        label={t("settings.smtpHost")}
                        value={smtpHost}
                        onChange={(e) => setSmtpHost(e.target.value)}
                        placeholder="smtp.example.com"
                        fullWidth
                      />
                      <TextField
                        label={t("settings.smtpPort")}
                        type="number"
                        value={smtpPort}
                        onChange={(e) => setSmtpPort(e.target.value)}
                        placeholder="587"
                        fullWidth
                      />
                      <TextField
                        label={t("settings.smtpUsername")}
                        value={smtpUsername}
                        onChange={(e) => setSmtpUsername(e.target.value)}
                        placeholder="your-email@example.com"
                        fullWidth
                      />
                    </>
                  )}
                  <Box>
                    <TextField
                      label={emailBackend === "gmail" ? t("settings.gmailAppPassword") : t("settings.smtpPassword")}
                      type="password"
                      value={smtpPassword}
                      onChange={(e) => setSmtpPassword(e.target.value)}
                      placeholder={emailBackend === "gmail" ? "xxxx xxxx xxxx xxxx" : "password"}
                      fullWidth
                    />
                    {emailBackend === "gmail" && (
                      <FormHelperText>
                        {t("settings.gmailAppPasswordHint")}
                      </FormHelperText>
                    )}
                  </Box>
                </>
              )}

              {emailTestResult && (
                <Alert severity={emailTestResult.ok ? "success" : "error"}>
                  {emailTestResult.ok
                    ? t("onboarding.testEmailSuccess")
                    : t("onboarding.testEmailFailed", { message: emailTestResult.message })}
                </Alert>
              )}

              {emailBackend !== "console" && (
                <Button
                  variant="outlined"
                  startIcon={<ScienceOutlined />}
                  onClick={handleTestEmail}
                  disabled={testingEmail}
                >
                  {testingEmail
                    ? t("onboarding.testing")
                    : t("onboarding.testEmailBtn")}
                </Button>
              )}
            </Box>
          </Box>
        )}

        {/* Step 3: Done */}
        {step === LAST_STEP && (
          <Box sx={{ textAlign: "center", py: 2 }}>
            <CheckCircleOutline
              sx={{ fontSize: 64, color: "success.main", mb: 2 }}
            />
            <Typography variant="h6" fontWeight={600} gutterBottom>
              {t("onboarding.completedTitle")}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 1 }}
            >
              {t("onboarding.completedSubtitle")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {PROVIDER_INFO.find((p) => p.value === provider)?.label} —{" "}
              {MODEL_OPTIONS[provider]?.find((m) => m.value === model)
                ?.label ?? model}
            </Typography>
          </Box>
        )}

        {/* Navigation buttons */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            mt: 4,
            gap: 2,
          }}
        >
          {step > 0 && step < LAST_STEP ? (
            <Button
              startIcon={<ArrowBack />}
              onClick={() => setStep(step - 1)}
            >
              {t("onboarding.back")}
            </Button>
          ) : (
            <Box />
          )}

          <Box sx={{ display: "flex", gap: 1 }}>
            {step < LAST_STEP && (
              <Button
                variant="text"
                color="inherit"
                onClick={onComplete}
                sx={{ color: "text.secondary" }}
              >
                {t("onboarding.skip")}
              </Button>
            )}

            {step < LAST_STEP ? (
              <Button
                variant="contained"
                endIcon={<ArrowForward />}
                onClick={handleNext}
                disabled={!canProceed() || saving}
              >
                {saving ? t("common.saving") : t("onboarding.next")}
              </Button>
            ) : (
              <Button
                variant="contained"
                size="large"
                onClick={onComplete}
              >
                {t("onboarding.getStarted")}
              </Button>
            )}
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}
