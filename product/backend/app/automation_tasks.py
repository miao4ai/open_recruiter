"""Built-in automation task implementations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import database as db

log = logging.getLogger(__name__)


def run_auto_match(conditions: dict, actions: dict) -> dict:
    """Match unmatched candidates against open jobs.

    Conditions:
        job_id: specific job to match against (empty = all jobs)
        min_score_threshold: minimum score to save (default 0.3)
    Actions:
        update_status: auto-move to screening if score >= 0.7
    """
    from app.agents.matching import match_candidate_to_job
    from app.routes.settings import get_config

    cfg = get_config()
    job_id = conditions.get("job_id", "")
    threshold = float(conditions.get("min_score_threshold", 0.3))
    update_status = actions.get("update_status", False)

    # Find candidates with status=new and no match score
    candidates = db.list_candidates(status="new")
    unmatched = [c for c in candidates if (c.get("match_score") or 0) == 0]

    if not unmatched:
        return {
            "summary": "No unmatched candidates found.",
            "details": {},
            "items_processed": 0,
            "items_affected": 0,
        }

    # Get target jobs
    if job_id:
        jobs = [db.get_job(job_id)]
        jobs = [j for j in jobs if j]
    else:
        jobs = db.list_jobs()

    if not jobs:
        return {
            "summary": "No open jobs to match against.",
            "details": {},
            "items_processed": 0,
            "items_affected": 0,
        }

    affected = 0
    match_details = []

    for candidate in unmatched:
        best_score = 0.0
        best_job = None
        best_result = None

        for job in jobs:
            try:
                result = match_candidate_to_job(cfg, job["id"], candidate["id"])
                score = result.get("score", 0.0)
                if score > best_score:
                    best_score = score
                    best_job = job
                    best_result = result
            except Exception as e:
                log.warning(
                    "Match failed for candidate %s / job %s: %s",
                    candidate["id"],
                    job["id"],
                    e,
                )

        if best_result and best_score >= threshold and best_job:
            updates: dict = {
                "match_score": best_score,
                "match_reasoning": best_result.get("reasoning", ""),
                "strengths": best_result.get("strengths", []),
                "gaps": best_result.get("gaps", []),
                "job_id": best_job["id"],
                "updated_at": datetime.now().isoformat(),
            }
            if update_status and best_score >= 0.7:
                updates["status"] = "screening"

            db.update_candidate(candidate["id"], updates)
            affected += 1
            match_details.append({
                "candidate": candidate["name"],
                "job": best_job["title"],
                "score": best_score,
            })

    return {
        "summary": f"Matched {affected}/{len(unmatched)} candidates.",
        "details": {"matches": match_details},
        "items_processed": len(unmatched),
        "items_affected": affected,
    }


def run_inbox_scan(conditions: dict, actions: dict) -> dict:
    """Check IMAP inbox for replies to sent emails.

    Actions:
        update_candidate_status: move candidate to 'replied' (default True)
    """
    from app.routes.settings import get_config
    from app.tools.imap_checker import check_replies

    cfg = get_config()

    if not cfg.imap_host or not cfg.imap_password:
        return {
            "summary": "IMAP not configured. Skipped.",
            "details": {},
            "items_processed": 0,
            "items_affected": 0,
        }

    try:
        matches = check_replies(cfg)
    except Exception as e:
        raise RuntimeError(f"IMAP check failed: {e}") from e

    update_status = actions.get("update_candidate_status", True)
    now = datetime.now().isoformat()
    updated = 0
    classification_results = []

    for m in matches:
        eid = m["email_id"]
        db.update_email(eid, {
            "reply_received": True,
            "reply_body": m.get("reply_body", ""),
            "replied_at": m.get("replied_at", now),
        })

        email_record = db.get_email(eid)
        if not email_record or not email_record.get("candidate_id"):
            updated += 1
            continue

        candidate_id = email_record["candidate_id"]

        # For recommendation emails, classify the employer's reply intent
        if email_record.get("email_type") == "recommendation" and m.get("reply_body"):
            try:
                from app.agents.employer import classify_employer_reply

                candidate = db.get_candidate(candidate_id)
                candidate_name = candidate["name"] if candidate else ""
                job_title = ""
                if candidate and candidate.get("job_id"):
                    job = db.get_job(candidate["job_id"])
                    job_title = job["title"] if job else ""

                classification = classify_employer_reply(
                    cfg, m["reply_body"], email_record.get("subject", ""),
                    candidate_name, job_title,
                )
                classification_results.append({
                    "email_id": eid,
                    "candidate": candidate_name,
                    "classification": classification,
                })

                # Auto-update candidate status based on classification
                new_status = classification.get("new_status")
                if new_status and candidate:
                    db.update_candidate(candidate_id, {
                        "status": new_status,
                        "updated_at": now,
                    })
                    log.info(
                        "Auto-updated %s to '%s' based on employer reply (intent: %s)",
                        candidate_name, new_status, classification.get("intent"),
                    )
                elif update_status:
                    db.update_candidate(candidate_id, {
                        "status": "replied",
                        "updated_at": now,
                    })
            except Exception as e:
                log.warning("Employer reply classification failed for email %s: %s", eid, e)
                if update_status:
                    db.update_candidate(candidate_id, {
                        "status": "replied",
                        "updated_at": now,
                    })
        elif update_status:
            db.update_candidate(candidate_id, {
                "status": "replied",
                "updated_at": now,
            })

        updated += 1

    summary = f"Found {updated} replies." if updated else "No new replies."
    if classification_results:
        summary += f" Classified {len(classification_results)} employer responses."

    return {
        "summary": summary,
        "details": {
            "replies_found": updated,
            "employer_classifications": classification_results,
        },
        "items_processed": len(matches),
        "items_affected": updated,
    }


def run_auto_followup(conditions: dict, actions: dict) -> dict:
    """Draft or send follow-up emails for candidates who haven't replied.

    Conditions:
        days_since_contact: days since last email with no reply (default 3)
        max_followups: max follow-up emails per candidate (default 2)
    Actions:
        auto_send: True = send immediately, False = draft only (default False)
        job_id: filter to specific job's candidates
    """
    from app.agents.communication import draft_email
    from app.models import Email
    from app.routes.settings import get_config

    cfg = get_config()
    days_threshold = int(conditions.get("days_since_contact", 3))
    max_followups = int(conditions.get("max_followups", 2))
    auto_send = actions.get("auto_send", False)
    filter_job_id = actions.get("job_id", "")

    cutoff = (datetime.now() - timedelta(days=days_threshold)).isoformat()

    # Find contacted candidates with no reply
    candidates = db.list_candidates(status="contacted")
    if filter_job_id:
        candidates = [c for c in candidates if c.get("job_id") == filter_job_id]

    drafted = 0
    sent = 0
    followup_details = []

    for candidate in candidates:
        emails = db.list_emails(candidate_id=candidate["id"])
        sent_emails = [e for e in emails if e["sent"] and not e["reply_received"]]
        followup_emails = [e for e in emails if e.get("email_type") == "followup"]

        if not sent_emails:
            continue
        if len(followup_emails) >= max_followups:
            continue

        # Check if the most recent sent email is older than threshold
        last_sent = sent_emails[0]  # list is DESC by created_at
        last_sent_at = last_sent.get("sent_at", "")
        if not last_sent_at or last_sent_at > cutoff:
            continue

        # Draft follow-up
        try:
            draft = draft_email(
                cfg,
                candidate["id"],
                candidate.get("job_id", ""),
                "followup",
                f"This is follow-up #{len(followup_emails) + 1}. "
                f"Previous email subject: {last_sent.get('subject', '')}",
            )
        except Exception as e:
            log.warning("Failed to draft followup for %s: %s", candidate["name"], e)
            continue

        new_email = Email(
            candidate_id=candidate["id"],
            candidate_name=candidate["name"],
            to_email=candidate.get("email", ""),
            subject=draft.get("subject", f"Following up — {last_sent.get('subject', '')}"),
            body=draft.get("body", ""),
            email_type="followup",
        )
        db.insert_email(new_email.model_dump())
        drafted += 1

        if auto_send and candidate.get("email"):
            from app.tools.email_sender import send_email as do_send

            result = do_send(
                backend=cfg.email_backend,
                from_email=cfg.email_from,
                to_email=candidate["email"],
                subject=new_email.subject,
                body=new_email.body,
                smtp_host=cfg.smtp_host,
                smtp_port=cfg.smtp_port,
                smtp_username=cfg.smtp_username,
                smtp_password=cfg.smtp_password,
            )
            if result.get("status") == "ok":
                db.update_email(new_email.id, {
                    "sent": True,
                    "sent_at": datetime.now().isoformat(),
                    "message_id": result.get("message_id", ""),
                })
                sent += 1

        followup_details.append({
            "candidate": candidate["name"],
            "email_id": new_email.id,
            "sent": auto_send and result.get("status") == "ok" if auto_send else False,
        })

    action_word = "Sent" if auto_send else "Drafted"
    count = sent if auto_send else drafted
    return {
        "summary": f"{action_word} {count} follow-up emails." if count else "No follow-ups needed.",
        "details": {"followups": followup_details},
        "items_processed": len(candidates),
        "items_affected": count,
    }


def run_pipeline_cleanup(conditions: dict, actions: dict) -> dict:
    """Find stale candidates and take cleanup actions.

    Conditions:
        days_stale: days without activity (default 7)
        target_statuses: statuses to check (default ["contacted"])
    Actions:
        reject_after_days: auto-reject after N days (default 14)
        archive_after_days: auto-archive (withdraw) after N days (default 21)
        dry_run: if True, only report, don't change status (default True)
    """
    days_stale = int(conditions.get("days_stale", 7))
    target_statuses = conditions.get("target_statuses", ["contacted"])
    reject_after = int(actions.get("reject_after_days", 14))
    archive_after = int(actions.get("archive_after_days", 21))
    dry_run = actions.get("dry_run", True)

    cutoff = (datetime.now() - timedelta(days=days_stale)).isoformat()
    now = datetime.now().isoformat()

    stale = []
    all_candidates = db.list_candidates()
    for c in all_candidates:
        if c.get("status") not in target_statuses:
            continue
        updated = c.get("updated_at") or c.get("created_at", "")
        if updated and updated < cutoff:
            days = (datetime.now() - datetime.fromisoformat(updated)).days
            stale.append({"candidate": c, "days": days})

    if not stale:
        return {
            "summary": f"No stale candidates found (>{days_stale} days).",
            "details": {},
            "items_processed": 0,
            "items_affected": 0,
        }

    cleanup_actions = []
    affected = 0

    for item in stale:
        c = item["candidate"]
        days = item["days"]

        if days >= archive_after:
            action = "withdrawn"
        elif days >= reject_after:
            action = "rejected"
        else:
            action = "flagged"

        if not dry_run and action in ("rejected", "withdrawn"):
            db.update_candidate(c["id"], {"status": action, "updated_at": now})
            affected += 1

        cleanup_actions.append({
            "candidate": c["name"],
            "days_stale": days,
            "action": action,
            "applied": not dry_run and action in ("rejected", "withdrawn"),
        })

    mode = "Dry run" if dry_run else "Executed"
    return {
        "summary": f"{mode}: {len(stale)} stale candidates, {affected} updated.",
        "details": {"cleanup_actions": cleanup_actions},
        "items_processed": len(stale),
        "items_affected": affected,
    }
