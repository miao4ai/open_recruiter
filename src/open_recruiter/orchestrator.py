"""Orchestrator — the brain that coordinates all agents."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from open_recruiter.agents import communication, matching, planning, resume, scheduling
from open_recruiter.config import Config
from open_recruiter.database import Database
from open_recruiter.llm import chat
from open_recruiter.prompts import ORCHESTRATOR
from open_recruiter.schemas import (
    Candidate,
    CandidateStatus,
    Email,
    JobDescription,
    MatchResult,
    PlanStep,
    TaskType,
)
from open_recruiter.tools.email import send_email

console = Console()


class Orchestrator:
    """Coordinates agents and manages the recruitment workflow."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.db = Database(config.db_path)
        self.current_jd: JobDescription | None = None
        self.candidates: list[Candidate] = []
        self.match_results: list[MatchResult] = []
        self.draft_emails: list[Email] = []
        self.conversation: list[dict] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def handle(self, user_input: str) -> str:
        """Process a user message and return the assistant response."""
        self.conversation.append({"role": "user", "content": user_input})

        # Use the LLM to decide what to do
        intent = self._classify_intent(user_input)

        if intent == "add_jd":
            return self._handle_add_jd(user_input)
        elif intent == "add_resume":
            return self._handle_add_resume(user_input)
        elif intent == "match":
            return self._handle_match()
        elif intent == "draft_emails":
            return self._handle_draft_emails(user_input)
        elif intent == "send_emails":
            return self._handle_send_emails(user_input)
        elif intent == "status":
            return self._handle_status()
        elif intent == "plan":
            return self._handle_plan(user_input)
        elif intent == "schedule":
            return self._handle_schedule(user_input)
        else:
            return self._handle_general(user_input)

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def _classify_intent(self, user_input: str) -> str:
        prompt = (
            "Classify the user's intent into exactly one of these categories:\n"
            "- add_jd: user is providing or discussing a job description\n"
            "- add_resume: user is providing candidate resume(s)\n"
            "- match: user wants to match/rank candidates against a JD\n"
            "- draft_emails: user wants to draft outreach/follow-up/rejection emails\n"
            "- send_emails: user confirms sending previously drafted emails\n"
            "- status: user wants to see pipeline/candidate status\n"
            "- plan: user wants a full recruitment plan (multiple steps)\n"
            "- schedule: user wants to schedule interviews\n"
            "- general: anything else (questions, greetings, etc.)\n\n"
            "Respond with ONLY the category name, nothing else."
        )
        result = chat(
            self.config,
            system=prompt,
            messages=[{"role": "user", "content": user_input}],
        ).strip().lower()

        valid = {"add_jd", "add_resume", "match", "draft_emails", "send_emails",
                 "status", "plan", "schedule", "general"}
        return result if result in valid else "general"

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_add_jd(self, user_input: str) -> str:
        """Parse a job description from user input."""
        console.print("[cyan]📋 Analyzing job description...[/cyan]")

        data = _parse_jd_with_llm(self.config, user_input)
        jd = JobDescription(
            title=data.get("title", "Untitled Role"),
            company=data.get("company", ""),
            raw_text=user_input,
            requirements=data.get("requirements", []),
            nice_to_have=data.get("nice_to_have", []),
            summary=data.get("summary", ""),
        )
        self.current_jd = jd
        self.db.save_jd(jd)

        msg = (
            f"✅ Job description saved!\n"
            f"  **Title:** {jd.title}\n"
            f"  **Company:** {jd.company}\n"
            f"  **Key requirements:** {', '.join(jd.requirements[:5])}\n\n"
            f"You can now add candidate resumes or ask me to match existing candidates."
        )
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_add_resume(self, user_input: str) -> str:
        """Parse resume(s) from user input."""
        console.print("[cyan]📄 Parsing resume...[/cyan]")

        candidate = resume.parse_resume(self.config, user_input)
        self.candidates.append(candidate)
        self.db.save_candidate(candidate)

        msg = (
            f"✅ Candidate added!\n"
            f"  **Name:** {candidate.name}\n"
            f"  **Skills:** {', '.join(candidate.skills[:8])}\n"
            f"  **Experience:** {candidate.experience_years} years\n"
            f"  **Summary:** {candidate.summary}\n\n"
            f"Total candidates: {len(self.candidates)}"
        )
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_match(self) -> str:
        """Match all candidates against the current JD."""
        if not self.current_jd:
            return "⚠️ No job description loaded. Please provide a JD first."
        if not self.candidates:
            return "⚠️ No candidates loaded. Please provide resumes first."

        console.print("[cyan]🔍 Matching candidates...[/cyan]")

        self.match_results = matching.rank_candidates(
            self.config, self.current_jd, self.candidates
        )

        # Update candidates with scores
        for result in self.match_results:
            for c in self.candidates:
                if c.id == result.candidate_id:
                    c.match_score = result.score
                    c.match_reasoning = result.reasoning
                    self.db.save_candidate(c)
                    break

        # Build results table
        table = Table(title="Candidate Rankings")
        table.add_column("Rank", style="bold")
        table.add_column("Name")
        table.add_column("Score", justify="right")
        table.add_column("Strengths")
        table.add_column("Gaps")

        for i, r in enumerate(self.match_results, 1):
            name = next((c.name for c in self.candidates if c.id == r.candidate_id), "?")
            table.add_row(
                str(i), name, f"{r.score:.0f}",
                ", ".join(r.strengths[:2]),
                ", ".join(r.gaps[:2]) if r.gaps else "—",
            )

        console.print(table)

        msg = f"✅ Ranked {len(self.match_results)} candidates. Top scorer: {self.match_results[0].score:.0f}/100\n\nWould you like me to draft outreach emails for the top candidates?"
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_draft_emails(self, user_input: str) -> str:
        """Draft emails for top candidates."""
        if not self.current_jd:
            return "⚠️ No job description loaded."

        # Determine how many emails to draft
        top_n = _extract_number(user_input, default=3)
        targets = (self.match_results or [])[:top_n]

        if not targets and self.candidates:
            targets_candidates = self.candidates[:top_n]
        else:
            targets_candidates = []
            for r in targets:
                for c in self.candidates:
                    if c.id == r.candidate_id:
                        targets_candidates.append(c)
                        break

        if not targets_candidates:
            return "⚠️ No candidates to email. Add resumes first."

        console.print(f"[cyan]✉️  Drafting {len(targets_candidates)} emails...[/cyan]")

        self.draft_emails = []
        for c in targets_candidates:
            email = communication.draft_outreach(self.config, self.current_jd, c)
            self.draft_emails.append(email)
            self.db.save_email(email)

        lines = ["✅ Drafted emails:\n"]
        for i, e in enumerate(self.draft_emails, 1):
            lines.append(f"  {i}. **To:** {e.to} — **Subject:** {e.subject}")

        lines.append("\n⏳ Reply **send** or **send emails** to confirm sending.")
        msg = "\n".join(lines)
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_send_emails(self, user_input: str) -> str:
        """Send previously drafted emails after user confirmation."""
        if not self.draft_emails:
            return "⚠️ No draft emails to send. Ask me to draft emails first."

        # Parse which emails to send (all, or specific numbers)
        indices = _extract_indices(user_input, len(self.draft_emails))

        sent_count = 0
        for idx in indices:
            email = self.draft_emails[idx]
            if send_email(self.config, email):
                self.db.mark_email_sent(email.id)
                # Update candidate status
                if email.candidate_id:
                    self.db.update_candidate_status(
                        email.candidate_id, CandidateStatus.CONTACTED
                    )
                sent_count += 1

        msg = f"✅ Sent {sent_count}/{len(indices)} emails."
        if self.config.email_backend == "console":
            msg += " (Console mode — emails printed above)"
        self.conversation.append({"role": "assistant", "content": msg})
        self.draft_emails = []
        return msg

    def _handle_status(self) -> str:
        """Show pipeline status."""
        candidates = self.db.list_candidates()
        if not candidates:
            return "📊 Pipeline is empty. Add a JD and some resumes to get started."

        table = Table(title="Recruitment Pipeline")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Score", justify="right")
        table.add_column("Email")

        for c in candidates:
            table.add_row(c.name, c.status.value, f"{c.match_score:.0f}", c.email)

        console.print(table)

        counts = {}
        for c in candidates:
            counts[c.status.value] = counts.get(c.status.value, 0) + 1
        summary = " | ".join(f"{k}: {v}" for k, v in counts.items())
        msg = f"📊 {len(candidates)} candidates — {summary}"
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_plan(self, user_input: str) -> str:
        """Create a full recruitment plan."""
        console.print("[cyan]🧠 Planning...[/cyan]")

        context_parts = []
        if self.current_jd:
            context_parts.append(f"Current JD: {self.current_jd.title} at {self.current_jd.company}")
        context_parts.append(f"Candidates loaded: {len(self.candidates)}")

        steps = planning.create_plan(
            self.config, user_input, context="\n".join(context_parts)
        )

        if not steps:
            return self._handle_general(user_input)

        lines = ["📋 **Recruitment Plan:**\n"]
        for s in steps:
            deps = f" (after step {', '.join(map(str, s.depends_on))})" if s.depends_on else ""
            lines.append(f"  **Step {s.step}:** {s.description}{deps}")

        lines.append("\nShall I execute this plan?")
        msg = "\n".join(lines)
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_schedule(self, user_input: str) -> str:
        """Suggest interview slots."""
        console.print("[cyan]📅 Suggesting interview slots...[/cyan]")

        role = self.current_jd.title if self.current_jd else "the role"
        data = scheduling.suggest_slots(
            self.config, candidate_name="candidate", role=role, preferences=user_input,
        )

        slots = data.get("suggested_slots", [])
        lines = ["📅 **Suggested interview slots:**\n"]
        for s in slots:
            lines.append(f"  - {s.get('date', '?')} at {s.get('time', '?')} ({s.get('duration_minutes', 60)} min)")

        if data.get("notes"):
            lines.append(f"\n💡 {data['notes']}")

        msg = "\n".join(lines)
        self.conversation.append({"role": "assistant", "content": msg})
        return msg

    def _handle_general(self, user_input: str) -> str:
        """Fallback: use the orchestrator LLM for general conversation."""
        context = ""
        if self.current_jd:
            context += f"\nActive JD: {self.current_jd.title} ({self.current_jd.company})"
        context += f"\nCandidates loaded: {len(self.candidates)}"
        context += f"\nDraft emails pending: {len(self.draft_emails)}"

        system = ORCHESTRATOR + f"\n\nCurrent state:{context}"

        response = chat(
            self.config,
            system=system,
            messages=self.conversation[-10:],  # keep context manageable
        )
        self.conversation.append({"role": "assistant", "content": response})
        return response

    def close(self) -> None:
        self.db.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_jd_with_llm(config: Config, text: str) -> dict:
    """Use LLM to extract structured data from a JD."""
    from open_recruiter.llm import chat_json

    system = (
        "Extract structured information from this job description.\n"
        "Return a JSON object with:\n"
        '- "title": job title\n'
        '- "company": company name\n'
        '- "requirements": list of must-have requirements\n'
        '- "nice_to_have": list of nice-to-have skills\n'
        '- "summary": 2-3 sentence summary of the role\n'
        "Only output valid JSON."
    )
    return chat_json(config, system=system, messages=[{"role": "user", "content": text}])


def _extract_number(text: str, default: int = 3) -> int:
    """Extract the first number from text, or return default."""
    import re
    match = re.search(r"\d+", text)
    return int(match.group()) if match else default


def _extract_indices(text: str, total: int) -> list[int]:
    """Extract which items to send from user input. Returns 0-based indices."""
    import re
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if numbers:
        return [n - 1 for n in numbers if 1 <= n <= total]
    # Default: send all
    return list(range(total))
