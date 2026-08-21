import { useCallback, useEffect, useRef, useState } from "react";
import {
  SaveOutlined, UploadOutlined, DescriptionOutlined, CheckOutlined, CloseOutlined, AddOutlined,
} from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
import { useTranslation } from "react-i18next";
import { useApi } from "../hooks/useApi";
import { getMyProfile, updateMyProfile, uploadResumeForProfile } from "../lib/api";
import type { JobSeekerProfile } from "../types";

/* ── Field helper ──────────────────────────────────────────────────────── */

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder = "",
}: {
  label: string;
  value: string | number | null;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-600">
        {label}
      </label>
      <input
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm
          focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
      />
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────────────── */

export default function JobSeekerProfilePage() {
  const { t } = useTranslation();
  const { data: profile, loading, refresh } = useApi(
    useCallback(() => getMyProfile(), []),
  );

  const [form, setForm] = useState<Partial<JobSeekerProfile>>({});
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newSkill, setNewSkill] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // Reset form when profile loads (fresh from server)
  useEffect(() => {
    setForm({});
  }, [profile]);

  const merged: Partial<JobSeekerProfile> = { ...profile, ...form };

  const handleChange = (field: keyof JobSeekerProfile, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateMyProfile(form);
      refresh();
      setForm({});
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadResumeForProfile(file);
      refresh();
      setForm({});
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleAddSkill = () => {
    if (!newSkill.trim()) return;
    const current = (merged.skills as string[]) || [];
    handleChange("skills", [...current, newSkill.trim()]);
    setNewSkill("");
  };

  const handleRemoveSkill = (index: number) => {
    const current = (merged.skills as string[]) || [];
    handleChange(
      "skills",
      current.filter((_, i) => i !== index),
    );
  };

  /* ── Loading ──────────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <CircularProgress size={24} sx={{ color: 'rgb(244 114 182)' }} />
      </div>
    );
  }

  const hasProfile = profile && profile.id;
  const dirty = Object.keys(form).length > 0;

  /* ── Render ───────────────────────────────────────────────────────── */

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">{t("jobSeekerProfile.myProfile")}</h1>
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-pink-300
              bg-pink-50 px-4 py-2 text-sm font-medium text-pink-700
              hover:bg-pink-100 disabled:opacity-50"
          >
            {uploading ? (
              <CircularProgress size={16} />
            ) : (
              <UploadOutlined className="h-4 w-4" />
            )}
            {uploading
              ? t("jobSeekerProfile.parsing")
              : hasProfile
                ? t("jobSeekerProfile.reUploadResume")
                : t("jobSeekerProfile.uploadResume")}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="inline-flex items-center gap-1.5 rounded-lg bg-pink-500 px-4 py-2
              text-sm font-medium text-white hover:bg-pink-600 disabled:opacity-50"
          >
            {saving ? (
              <CircularProgress size={16} />
            ) : saved ? (
              <CheckOutlined className="h-4 w-4" />
            ) : (
              <SaveOutlined className="h-4 w-4" />
            )}
            {saving ? t("common.saving") : saved ? t("jobSeekerProfile.saved") : t("jobSeekerProfile.saveChanges")}
          </button>
        </div>
      </div>

      {/* Empty state */}
      {!hasProfile && (
        <div className="rounded-xl border border-pink-200 bg-pink-50 p-6 text-center">
          <DescriptionOutlined className="mx-auto h-10 w-10 text-pink-400" />
          <h2 className="mt-3 text-lg font-semibold text-gray-700">
            {t("jobSeekerProfile.noProfileYet")}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {t("jobSeekerProfile.noProfileHint")}
          </p>
        </div>
      )}

      {/* Basic info */}
      <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-700">
          {t("jobSeekerProfile.basicInfo")}
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <Field
            label={t("jobSeekerProfile.fieldName")}
            value={merged.name ?? ""}
            onChange={(v) => handleChange("name", v)}
            placeholder={t("jobSeekerProfile.namePlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldEmail")}
            value={merged.email ?? ""}
            onChange={(v) => handleChange("email", v)}
            placeholder={t("jobSeekerProfile.emailPlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldPhone")}
            value={merged.phone ?? ""}
            onChange={(v) => handleChange("phone", v)}
            placeholder={t("jobSeekerProfile.phonePlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldLocation")}
            value={merged.location ?? ""}
            onChange={(v) => handleChange("location", v)}
            placeholder={t("jobSeekerProfile.locationPlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldTitle")}
            value={merged.current_title ?? ""}
            onChange={(v) => handleChange("current_title", v)}
            placeholder={t("jobSeekerProfile.titlePlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldCompany")}
            value={merged.current_company ?? ""}
            onChange={(v) => handleChange("current_company", v)}
            placeholder={t("jobSeekerProfile.companyPlaceholder")}
          />
          <Field
            label={t("jobSeekerProfile.fieldExperience")}
            value={merged.experience_years ?? ""}
            onChange={(v) =>
              handleChange(
                "experience_years",
                v === "" ? null : parseInt(v, 10) || null,
              )
            }
            type="number"
            placeholder={t("jobSeekerProfile.experiencePlaceholder")}
          />
        </div>
      </div>

      {/* Skills */}
      <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-700">{t("jobSeekerProfile.skills")}</h2>
        <div className="flex flex-wrap gap-2">
          {((merged.skills as string[]) || []).map((skill, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-full bg-pink-50
                px-3 py-1 text-sm font-medium text-pink-700"
            >
              {skill}
              <button
                onClick={() => handleRemoveSkill(i)}
                className="ml-0.5 rounded-full p-0.5 hover:bg-pink-200"
              >
                <CloseOutlined className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddSkill();
              }
            }}
            placeholder={t("jobSeekerProfile.addSkillPlaceholder")}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm
              focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
          />
          <button
            onClick={handleAddSkill}
            disabled={!newSkill.trim()}
            className="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-2
              text-sm font-medium text-gray-600 hover:bg-gray-200 disabled:opacity-50"
          >
            <AddOutlined className="h-4 w-4" />
            {t("jobSeekerProfile.add")}
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-gray-700">
          {t("jobSeekerProfile.professionalSummary")}
        </h2>
        <textarea
          value={merged.resume_summary ?? ""}
          onChange={(e) => handleChange("resume_summary", e.target.value)}
          rows={6}
          placeholder={t("jobSeekerProfile.summaryPlaceholder")}
          className="w-full resize-none rounded-lg border border-gray-300 px-4 py-3 text-sm
            focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
        />
      </div>
    </div>
  );
}
