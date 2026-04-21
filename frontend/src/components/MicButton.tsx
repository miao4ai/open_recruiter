import { useRef, useState } from "react";
import IconButton from "@mui/material/IconButton";
import CircularProgress from "@mui/material/CircularProgress";
import Tooltip from "@mui/material/Tooltip";
import MicNoneOutlined from "@mui/icons-material/MicNoneOutlined";
import StopOutlined from "@mui/icons-material/StopOutlined";
import { transcribeAudio } from "../lib/api";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export default function MicButton({ onTranscript, disabled }: Props) {
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const pickMime = () => {
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    for (const m of candidates) {
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(m)) return m;
    }
    return "";
  };

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMime();
      const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorderRef.current = rec;
      chunksRef.current = [];

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        const type = rec.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        chunksRef.current = [];
        if (blob.size === 0) {
          setState("idle");
          return;
        }
        setState("transcribing");
        try {
          const ext = type.includes("mp4") ? "mp4" : type.includes("ogg") ? "ogg" : "webm";
          const { text } = await transcribeAudio(blob, `voice.${ext}`);
          if (text) onTranscript(text);
          else setError("No speech detected");
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Transcription failed";
          setError(msg);
        } finally {
          setState("idle");
        }
      };
      rec.start();
      setState("recording");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Microphone unavailable";
      setError(msg);
      setState("idle");
    }
  };

  const stop = () => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  };

  const toggle = () => {
    if (state === "idle") start();
    else if (state === "recording") stop();
  };

  const tooltip =
    state === "recording" ? "Stop recording" :
    state === "transcribing" ? "Transcribing…" :
    error ? `Mic: ${error}` : "Voice input";

  return (
    <Tooltip title={tooltip} placement="top">
      <span>
        <IconButton
          onClick={toggle}
          disabled={disabled || state === "transcribing"}
          sx={{
            borderRadius: 3, width: 44,
            color: state === "recording" ? "error.main" : "text.secondary",
            bgcolor: state === "recording" ? "error.lighter" : "transparent",
            "&:hover": { bgcolor: state === "recording" ? "error.light" : "grey.100" },
          }}
        >
          {state === "transcribing" ? (
            <CircularProgress size={18} />
          ) : state === "recording" ? (
            <StopOutlined sx={{ fontSize: 20 }} />
          ) : (
            <MicNoneOutlined sx={{ fontSize: 20 }} />
          )}
        </IconButton>
      </span>
    </Tooltip>
  );
}
