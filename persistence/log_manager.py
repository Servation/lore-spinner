import os
import datetime

def write_dm_log(campaign_slug: str, entry: str, llm_client = None) -> str:
    """Writes an entry to the DM's log file for the specified campaign.
    
    Handles automatic compaction when the active log reaches 30 entries.
    Archived entries are stored in dm_log_archive.md.
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        campaign_dir = os.path.join("saves", campaign_slug)
        os.makedirs(campaign_dir, exist_ok=True)
        
        active_file = os.path.join(campaign_dir, "dm_log.md")
        archive_file = os.path.join(campaign_dir, "dm_log_archive.md")
        
        # Format the entry with a clean markdown bullet point
        clean_entry = entry.strip().replace("\n", " ")
        log_line = f"- [{timestamp}] {clean_entry}\n"
        
        # Write to active log
        with open(active_file, "a", encoding="utf-8") as f:
            f.write(log_line)
            
        # Check active log line count
        with open(active_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Compaction threshold
        COMPACTION_THRESHOLD = 30
        compacted_msg = ""
        
        if len(lines) >= COMPACTION_THRESHOLD and llm_client is not None:
            full_content = "".join(lines)
            
            # Append to raw archive log
            with open(archive_file, "a", encoding="utf-8") as f_arch:
                archive_header = f"\n### ARCHIVE SESSION COMPACTION: {timestamp}\n"
                f_arch.write(archive_header + full_content)
                
            # Call LLM client to summarize the log entries into exactly 5 bullet points
            prompt = f"""You are the chronicler summarizing the campaign log history.
Summarize the following raw chronological log entries into a concise summary of EXACTLY 5 bullet points.
Retain key locations, characters, faction changes, major level ups, and plot milestones.
Start each bullet with '-'. Do NOT include date timestamps in the summary.

Raw Campaign Log Entries:
{full_content}

Summarized Campaign Log (exactly 5 bullet points, starting with '-'):"""
            
            try:
                summary = llm_client.generate(prompt)
                
                # Overwrite active log with summary
                with open(active_file, "w", encoding="utf-8") as f_active:
                    f_active.write(summary.strip() + "\n")
                compacted_msg = " (Notice: DM log compacted and archived to manage memory)"
            except Exception as summary_err:
                compacted_msg = f" (Warning: Compaction failed during LLM summary: {summary_err})"
                
        return f"Successfully recorded campaign log entry.{compacted_msg}"
        
    except Exception as e:
        return f"Error writing to campaign log: {e}"


def read_dm_log(campaign_slug: str) -> str:
    """Reads the active narrative log of the campaign."""
    active_file = os.path.join("saves", campaign_slug, "dm_log.md")
    try:
        if not os.path.exists(active_file):
            return "No campaign log entries have been recorded yet."
        with open(active_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content if content else "The campaign log is empty."
    except Exception as e:
        return f"Error reading campaign log: {e}"
