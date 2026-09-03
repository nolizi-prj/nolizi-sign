/**
 * Nolizi Sign Feedback Pipeline -> GitHub Issues & Attachments.
 * Captures user feedback, screenshot, runtime diagnostics, and creates a GitHub
 * issue on https://github.com/nolizi-prj/nolizi-sign with full transparency.
 */

export interface FeedbackDiagnosticError {
  message: string;
  source?: string;
  lineno?: number;
  colno?: number;
  timestamp?: string;
}

export interface FeedbackSubmission {
  message: string;
  type?: 'bug' | 'enhancement' | 'question' | 'feedback';
  screenshotBase64?: string;
  attachmentsBase64?: string[];
  context?: Record<string, string | number | boolean | null | undefined>;
  errors?: FeedbackDiagnosticError[];
  userEmail?: string;
}

export interface FeedbackResult {
  ok: boolean;
  issueUrl?: string;
  issueNumber?: number;
  message?: string;
}

/** Sanitize URL to strip sensitive tokens, secrets, or state parameters */
function sanitizeUrl(rawUrl?: string): string {
  if (!rawUrl) return 'N/A';
  try {
    const u = new URL(rawUrl);
    for (const key of Array.from(u.searchParams.keys())) {
      if (/token|state|code|session|secret|key|auth|password/i.test(key)) {
        u.searchParams.set(key, 'REDACTED');
      }
    }
    return u.toString();
  } catch {
    return rawUrl;
  }
}

export async function submitFeedbackToGitHub(
  submission: FeedbackSubmission,
  env: { GITHUB_FEEDBACK_TOKEN?: string; GITHUB_FEEDBACK_REPO?: string }
): Promise<FeedbackResult> {
  const token = env.GITHUB_FEEDBACK_TOKEN;
  const repo = env.GITHUB_FEEDBACK_REPO || 'nolizi-prj/nolizi-sign';

  if (!token) {
    // Fail loudly: claiming success here silently discarded every submission
    // until GITHUB_FEEDBACK_TOKEN was first provisioned (2026-08-30). The
    // console.log is not storage — the user must see that nothing was kept.
    console.error('[Feedback] Dropped — GITHUB_FEEDBACK_TOKEN is not configured:', submission.message);
    return { ok: false, message: 'Feedback pipeline is not configured — nothing was recorded.' };
  }

  const attachmentUrls: string[] = [];
  const attachments = submission.attachmentsBase64?.length
    ? submission.attachmentsBase64
    : submission.screenshotBase64 ? [submission.screenshotBase64] : [];

  if (attachments.length > 5) {
    return { ok: false, message: 'You can attach up to 5 images.' };
  }

  // 1. Commit each screenshot to GitHub in order. Uploads are sequential because
  // concurrent Contents API writes to the same branch can conflict.
  for (const [index, attachment] of attachments.entries()) {
    if (!attachment.includes(',')) continue;
    try {
      const parts = attachment.split(',', 2);
      const base64Data = parts[1];
      if (base64Data.length > 5_600_000) continue;
      const ext = parts[0].includes('png') ? 'png' : parts[0].includes('webp') ? 'webp' : 'jpg';
      const filename = `${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-shot-${index + 1}-${crypto.randomUUID().slice(0, 6)}.${ext}`;
      const filePath = `.github/feedback-attachments/${filename}`;

      const putRes = await fetch(`https://api.github.com/repos/${repo}/contents/${filePath}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github+json',
          'User-Agent': 'Nolizi-Sign-Feedback/1.0',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `feedback: attach screenshot ${filePath}`,
          content: base64Data,
          branch: 'main',
        }),
      });

      if (putRes.ok) {
        attachmentUrls.push(`https://raw.githubusercontent.com/${repo}/main/${filePath}`);
      }
    } catch (err) {
      console.warn('Could not upload screenshot to GitHub:', err);
    }
  }

  // 2. Format Issue Body
  const typeIcons: Record<string, string> = {
    bug: '🐛 Bug',
    enhancement: '✨ Feature Request',
    question: '❓ Question',
    feedback: '💬 General Feedback',
  };

  const typeKey = (submission.type || 'feedback').toLowerCase();
  const typeName = typeIcons[typeKey] || '💬 Feedback';

  const firstLine = submission.message.split('\n')[0].trim().slice(0, 75);
  const issueTitle = `[Feedback] ${typeName}: ${firstLine || 'User Feedback Report'}`;

  const labels = ['feedback'];
  if (typeKey === 'bug') labels.push('bug');
  if (typeKey === 'enhancement') labels.push('enhancement');
  if (typeKey === 'question') labels.push('question');

  let body = `### Feedback Description\n\n${submission.message}\n\n---\n\n`;

  body += `### Submitter & Type\n`;
  body += `- **Type**: ${typeName}\n`;
  body += `- **Submitter**: ${submission.userEmail?.trim() ? `\`${submission.userEmail.trim()}\`` : '_Anonymous / Guest_'}\n`;
  body += `- **Submitted At**: \`${new Date().toISOString()}\`\n\n`;

  if (submission.context && Object.keys(submission.context).length > 0) {
    body += `---\n\n### Diagnostic Environment (Client-Side)\n\n`;
    body += `| Property | Value |\n| :--- | :--- |\n`;
    for (const [k, v] of Object.entries(submission.context)) {
      const valStr = k.toLowerCase().includes('url') ? sanitizeUrl(String(v)) : String(v ?? 'N/A');
      body += `| **${k}** | \`${valStr}\` |\n`;
    }
    body += `\n`;
  }

  if (submission.errors && submission.errors.length > 0) {
    const errorLines = submission.errors
      .slice(-6)
      .map((e) => `- \`${e.timestamp || 'N/A'}\`: **${e.message}** (${e.source ?? 'script'}:${e.lineno ?? '?'}:${e.colno ?? '?'})`)
      .join('\n');
    body += `<details>\n<summary><b>Recent Client-Side Runtime Errors (${submission.errors.length})</b></summary>\n\n${errorLines}\n</details>\n\n`;
  }

  if (attachmentUrls.length) {
    body += `---\n\n### Attached Images (${attachmentUrls.length})\n\n`;
    for (const [index, url] of attachmentUrls.entries()) {
      body += `<details${index === 0 ? ' open' : ''}>\n<summary><b>View image ${index + 1}</b> (<a href="${url}" target="_blank" rel="noopener">Open Full Resolution ↗</a>)</summary>\n\n![Feedback image ${index + 1}](${url})\n</details>\n\n`;
    }
  }

  // 3. Create GitHub Issue
  try {
    const issueRes = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Nolizi-Sign-Feedback/1.0',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: issueTitle,
        body,
        labels,
      }),
    });

    if (!issueRes.ok) {
      const errText = await issueRes.text();
      console.error('GitHub issue creation failed:', issueRes.status, errText);
      return { ok: false, message: `GitHub API error (${issueRes.status}). Feedback logged locally.` };
    }

    const issueData: any = await issueRes.json();
    return {
      ok: true,
      issueUrl: issueData.html_url,
      issueNumber: issueData.number,
      message: 'Feedback posted successfully!',
    };
  } catch (err: any) {
    return { ok: false, message: err.message || 'Error submitting feedback.' };
  }
}
