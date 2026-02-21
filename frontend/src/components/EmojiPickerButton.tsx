import { useState, useRef, useEffect } from "react";
import EmojiPicker, { EmojiClickData, Theme } from "emoji-picker-react";
import { EmojiEmotionsOutlined } from "@mui/icons-material";

interface Props {
  onEmojiSelect: (emoji: string) => void;
  buttonClassName?: string;
  /** MUI-style button (blue) vs tailwind-style (custom class) */
  variant?: "mui" | "tailwind";
}

export default function EmojiPickerButton({ onEmojiSelect, buttonClassName, variant = "mui" }: Props) {
  const [open, setOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Close picker when clicking outside
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleEmojiClick = (emojiData: EmojiClickData) => {
    onEmojiSelect(emojiData.emoji);
    setOpen(false);
  };

  return (
    <div className="relative" ref={pickerRef}>
      {variant === "tailwind" ? (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className={buttonClassName || "flex h-auto items-center justify-center rounded-xl border border-gray-300 px-2 text-gray-400 hover:text-gray-600 hover:border-gray-400"}
        >
          <EmojiEmotionsOutlined className="h-5 w-5" />
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-center justify-center rounded-xl p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
        >
          <EmojiEmotionsOutlined sx={{ fontSize: 20 }} />
        </button>
      )}

      {open && (
        <div className="absolute bottom-full right-0 z-50 mb-2">
          <EmojiPicker
            onEmojiClick={handleEmojiClick}
            theme={Theme.LIGHT}
            width={320}
            height={400}
            searchPlaceHolder="Search emoji..."
            previewConfig={{ showPreview: false }}
          />
        </div>
      )}
    </div>
  );
}
