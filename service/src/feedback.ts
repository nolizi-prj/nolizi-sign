/**
 * Pumasi Sign Feedback Pipeline -> GitHub Issues & Attachments.
 */

export interface FeedbackSubmission {
  message: string;
  type?: 'bug' | 'enhancement' | 'question' | 'feedback';
  screenshotBase64?: string;
  context?: Record<string, string>;
  userEmail?: string;
}

export interface FeedbackResult {
  ok: boolean;
  issueUrl?: string;
  issueNumber?: number;
  message?: string;
}

export async function submitFeedbackToGitHub(
  submission: FeedbackSubmission,
  env: { GITHUB_FEEDBACK_TOKEN?: string; GITHUB_FEEDBACK_REPO?: string }
): Promise<FeedbackResult> {
  const token = env.GITHUB_FEEDBACK_TOKEN;
  const repo = env.GITHUB_FEEDBACK_REPO || 'pumasi-ai/pumasi-sign';

  if (!token) {
    // Fail loudly: claiming success here silently discarded every submission
    // until GITHUB_FEEDBACK_TOKEN was first provisioned (2026-08-30). The
    // console.log is not storage — the user must see that nothing was kept.
    console.error('[Feedback] Dropped — GITHUB_FEEDBACK_TOKEN is not configured:', submission.message);
    return { ok: false, message: 'Feedback pipeline is not configured — nothing was recorded.' };
  }

  let screenshotUrl: string | null = null;

  // 1. If screenshot provided, commit attachment to GitHub repository
  if (submission.screenshotBase64 && submission.screenshotBase64.includes(',')) {
    try {
      const parts = submission.screenshotBase64.split(',');
      const base64Data = parts[1];
      const isPng = parts[0].includes('png');
      const ext = isPng ? 'png' : 'jpg';
      const filename = `${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-shot-${crypto.randomUUID().slice(0, 6)}.${ext}`;
      const filePath = `.github/feedback-attachments/${filename}`;

      const putRes = await fetch(`https://api.github.com/repos/${repo}/contents/${filePath}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github+json',
          'User-Agent': 'Pumasi-Sign-Feedback/1.0',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `feedback: attach screenshot ${filePath}`,
          content: base64Data,
          branch: 'main',
        }),
      });

      if (putRes.ok) {
        screenshotUrl = `https://raw.githubusercontent.com/${repo}/main/${filePath}`;
      }
    } catch (err) {
      console.warn('Could not upload screenshot to GitHub:', err);
    }
  }

  // 2. Format Issue Body
  const titlePrefix = submission.type === 'bug' ? '🐛 Bug: ' : submission.type === 'enhancement' ? '✨ Feature Request: ' : '';
  const firstLine = submission.message.split('\n')[0].trim().slice(0, 80);
  const issueTitle = `[Feedback] ${titlePrefix}${firstLine || 'User Feedback Report'}`;

  const labels = ['feedback'];
  if (submission.type === 'bug') labels.push('bug');
  if (submission.type === 'enhancement') labels.push('enhancement');

  let body = `### Feedback Description\n\n${submission.message}\n\n`;

  if (screenshotUrl) {
    body += `### Screenshot\n\n![Screenshot](${screenshotUrl})\n\n`;
  }

  if (submission.context && Object.keys(submission.context).length > 0) {
    body += `<details>\n<summary><strong>Client & System Diagnostics</strong></summary>\n\n| Property | Value |\n| :--- | :--- |\n`;
    for (const [k, v] of Object.entries(submission.context)) {
      body += `| **${k}** | \`${v}\` |\n`;
    }
    if (submission.userEmail) {
      body += `| **Submitter Email** | \`${submission.userEmail}\` |\n`;
    }
    body += `\n</details>\n`;
  }

  // 3. Create GitHub Issue
  try {
    const issueRes = await fetch(`https://api.github.com/repos/${repo}/issues`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Pumasi-Sign-Feedback/1.0',
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
      return { ok: false, message: 'Could not create GitHub issue.' };
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
