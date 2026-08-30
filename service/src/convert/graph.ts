/**
 * Native High-Fidelity Office 365 Document Conversion via Microsoft Graph API.
 * Converts .docx, .doc, .pptx, .ppt, .xlsx files directly into native PDF via Microsoft's cloud rendering engine.
 */

export interface GraphConvertConfig {
  tenantId: string;
  clientId: string;
  clientSecret: string;
  driveId: string;
}

export const SUPPORTED_OFFICE_FORMATS = new Set(['docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls']);

/**
 * Acquire Microsoft Graph application-only OAuth2 Bearer token
 */
async function getGraphToken(config: GraphConvertConfig): Promise<string | null> {
  try {
    const params = new URLSearchParams({
      client_id: config.clientId,
      client_secret: config.clientSecret,
      scope: 'https://graph.microsoft.com/.default',
      grant_type: 'client_credentials',
    });

    const res = await fetch(`https://login.microsoftonline.com/${config.tenantId}/oauth2/v2.0/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    });

    if (!res.ok) return null;
    const json: any = await res.json();
    return json.access_token || null;
  } catch {
    return null;
  }
}

/**
 * Convert Office document bytes to native PDF using Microsoft 365 Cloud Engine.
 */
export async function convertOfficeToPdfViaGraph(
  fileBytes: Uint8Array,
  ext: string,
  config: GraphConvertConfig
): Promise<Uint8Array | null> {
  const normalizedExt = ext.replace(/^\./, '').toLowerCase();
  if (!SUPPORTED_OFFICE_FORMATS.has(normalizedExt)) {
    return null;
  }

  const token = await getGraphToken(config);
  if (!token) return null;

  const tempFilename = `_convert_tmp/${crypto.randomUUID()}.${normalizedExt}`;
  const graphRoot = 'https://graph.microsoft.com/v1.0';
  const itemUrl = `${graphRoot}/drives/${config.driveId}/root:/${tempFilename}`;

  try {
    // 1. Upload file buffer to temporary drive location
    const uploadRes = await fetch(`${itemUrl}:/content`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/octet-stream',
      },
      body: fileBytes.buffer as BodyInit,
    });

    if (!uploadRes.ok) return null;

    // 2. Request native PDF rendition (?format=pdf automatically 302 redirects to pre-signed stream)
    const convertRes = await fetch(`${itemUrl}:/content?format=pdf`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
      redirect: 'follow',
    });

    if (!convertRes.ok) return null;
    const pdfBuffer = await convertRes.arrayBuffer();
    const pdfBytes = new Uint8Array(pdfBuffer);

    // Verify PDF header %PDF
    if (pdfBytes.length < 4 || pdfBytes[0] !== 0x25 || pdfBytes[1] !== 0x50 || pdfBytes[2] !== 0x44 || pdfBytes[3] !== 0x46) {
      return null;
    }

    return pdfBytes;
  } catch {
    return null;
  } finally {
    // 3. Best-effort cleanup of temporary file
    try {
      await fetch(itemUrl, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
    } catch {
      // Ignore cleanup error
    }
  }
}
