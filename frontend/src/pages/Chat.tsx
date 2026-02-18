import { useCallback, useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import Avatar from "@mui/material/Avatar";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import SendOutlined from "@mui/icons-material/SendOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import SmartToyOutlined from "@mui/icons-material/SmartToyOutlined";
import { useApi } from "../hooks/useApi";
import { sendChatMessage, getChatHistory, clearChatHistory } from "../lib/api";
import type { ChatMessage } from "../types";

export default function Chat() {
  const { data: history, refresh } = useApi(
    useCallback(() => getChatHistory(), [])
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (history) setMessages(history);
  }, [history]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const userMessage = input.trim();
    setInput("");
    setSending(true);

    const tempUserMsg: ChatMessage = {
      id: "temp-" + Date.now(),
      user_id: "",
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const { reply } = await sendChatMessage(userMessage);
      const tempAssistantMsg: ChatMessage = {
        id: "temp-" + Date.now() + "-reply",
        user_id: "",
        role: "assistant",
        content: reply,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempAssistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: "error-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleClear = async () => {
    await clearChatHistory();
    setMessages([]);
    refresh();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", pb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <SmartToyOutlined sx={{ color: "primary.main" }} />
          <Typography variant="h6" fontWeight={600}>
            Recruiting Assistant
          </Typography>
        </Box>
        {messages.length > 0 && (
          <Button
            size="small"
            variant="outlined"
            color="inherit"
            startIcon={<DeleteOutline />}
            onClick={handleClear}
            sx={{ color: "text.secondary" }}
          >
            Clear Chat
          </Button>
        )}
      </Box>

      {/* Messages */}
      <Paper
        variant="outlined"
        sx={{ flexGrow: 1, overflowY: "auto", p: 2, display: "flex", flexDirection: "column", gap: 2 }}
      >
        {messages.length === 0 && !sending && (
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexGrow: 1, textAlign: "center" }}>
            <SmartToyOutlined sx={{ fontSize: 48, color: "grey.300" }} />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
              Ask me about your candidates, jobs, or recruiting strategy.
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 1, mt: 2 }}>
              {[
                "Which candidates have the highest match scores?",
                "Should I send a follow-up email?",
                "Summarize my current pipeline",
              ].map((q) => (
                <Chip
                  key={q}
                  label={q}
                  variant="outlined"
                  size="small"
                  onClick={() => setInput(q)}
                  sx={{ cursor: "pointer" }}
                />
              ))}
            </Box>
          </Box>
        )}

        {messages.map((msg) => (
          <Box
            key={msg.id}
            sx={{ display: "flex", gap: 1.5, justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}
          >
            {msg.role === "assistant" && (
              <Avatar sx={{ bgcolor: "primary.light", width: 28, height: 28 }}>
                <SmartToyOutlined sx={{ fontSize: 16 }} />
              </Avatar>
            )}
            <Paper
              elevation={0}
              sx={{
                maxWidth: "80%",
                px: 2,
                py: 1.5,
                borderRadius: 3,
                bgcolor: msg.role === "user" ? "primary.main" : "grey.50",
                color: msg.role === "user" ? "white" : "text.primary",
              }}
            >
              <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                {msg.content}
              </Typography>
            </Paper>
          </Box>
        ))}

        {sending && (
          <Box sx={{ display: "flex", gap: 1.5 }}>
            <Avatar sx={{ bgcolor: "primary.light", width: 28, height: 28 }}>
              <SmartToyOutlined sx={{ fontSize: 16 }} />
            </Avatar>
            <Paper elevation={0} sx={{ px: 2, py: 1.5, borderRadius: 3, bgcolor: "grey.50" }}>
              <CircularProgress size={16} />
            </Paper>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Paper>

      {/* Input */}
      <Box sx={{ pt: 2 }}>
        <Box sx={{ display: "flex", gap: 1 }}>
          <TextField
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about candidates, jobs, or get recruiting advice..."
            multiline
            rows={2}
            fullWidth
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={sending || !input.trim()}
            sx={{ bgcolor: "primary.main", color: "white", borderRadius: 2, width: 48, "&:hover": { bgcolor: "primary.dark" }, "&.Mui-disabled": { bgcolor: "grey.300", color: "white" } }}
          >
            <SendOutlined />
          </IconButton>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", mt: 0.5 }}>
          Enter to send, Shift+Enter for new line
        </Typography>
      </Box>
    </Box>
  );
}
