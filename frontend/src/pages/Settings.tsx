import { useCallback, useEffect, useState } from "react";
import { Save, FlaskConical } from "lucide-react";
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
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
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
    <div className="mx-auto max-w-2xl space-y-6">
      {/* LLM Config */}
      <Section title="LLM Configuration">
        <Field label="Provider">
          <select
            name="llm_provider"
            value={form.llm_provider}
            onChange={handleChange}
            className="input"
          >
            <option value="anthropic">Anthropic</option>
            <option value="openai">OpenAI</option>
          </select>
        </Field>
        <Field label="Model (optional)">
          <input
            name="llm_model"
            value={form.llm_model}
            onChange={handleChange}
            placeholder="e.g. claude-sonnet-4-20250514"
            className="input"
          />
        </Field>
        <Field label="Anthropic API Key">
          <input
            name="anthropic_api_key"
            type="password"
            value={form.anthropic_api_key}
            onChange={handleChange}
            placeholder="sk-ant-..."
            className="input"
          />
        </Field>
        <Field label="OpenAI API Key">
          <input
            name="openai_api_key"
            type="password"
            value={form.openai_api_key}
            onChange={handleChange}
            placeholder="sk-..."
            className="input"
          />
        </Field>
        <button
          onClick={handleTestLlm}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <FlaskConical className="h-4 w-4" /> Test LLM
        </button>
      </Section>

      {/* Email Config */}
      <Section title="Email Configuration">
        <Field label="Backend">
          <select
            name="email_backend"
            value={form.email_backend}
            onChange={handleChange}
            className="input"
          >
            <option value="console">Console (print to terminal)</option>
            <option value="sendgrid">SendGrid</option>
            <option value="gmail">Gmail</option>
          </select>
        </Field>
        <Field label="SendGrid API Key">
          <input
            name="sendgrid_api_key"
            type="password"
            value={form.sendgrid_api_key}
            onChange={handleChange}
            placeholder="SG...."
            className="input"
          />
        </Field>
        <Field label="From Email">
          <input
            name="email_from"
            value={form.email_from}
            onChange={handleChange}
            placeholder="recruiter@company.com"
            className="input"
          />
        </Field>
        <button
          onClick={handleTestEmail}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <FlaskConical className="h-4 w-4" /> Test Email
        </button>
      </Section>

      {/* Personal Info */}
      <Section title="Recruiter Profile">
        <Field label="Name">
          <input
            name="recruiter_name"
            value={form.recruiter_name}
            onChange={handleChange}
            className="input"
          />
        </Field>
        <Field label="Email">
          <input
            name="recruiter_email"
            value={form.recruiter_email}
            onChange={handleChange}
            className="input"
          />
        </Field>
        <Field label="Company">
          <input
            name="recruiter_company"
            value={form.recruiter_company}
            onChange={handleChange}
            className="input"
          />
        </Field>
      </Section>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="h-4 w-4" /> {saving ? "Saving..." : "Save Settings"}
        </button>
        {testResult && (
          <span className="text-sm text-gray-600">{testResult}</span>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <h3 className="mb-4 font-semibold">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  );
}
