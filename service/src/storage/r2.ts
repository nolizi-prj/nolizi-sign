/**
 * Cloudflare R2 Storage Wrapper for Pumasi Sign documents, templates, and signed PDFs.
 */

export interface SignStorage {
  putDocument(key: string, data: Uint8Array, contentType: string): Promise<void>;
  getDocument(key: string): Promise<{ data: Uint8Array; contentType: string } | null>;
  deleteDocument(key: string): Promise<void>;
}

export class R2SignStorage implements SignStorage {
  constructor(private bucket: any) {}

  async putDocument(key: string, data: Uint8Array, contentType: string): Promise<void> {
    if (!this.bucket) {
      throw new Error('R2 bucket binding is not configured.');
    }
    await this.bucket.put(key, data, {
      httpMetadata: { contentType },
    });
  }

  async getDocument(key: string): Promise<{ data: Uint8Array; contentType: string } | null> {
    if (!this.bucket) return null;
    const obj = await this.bucket.get(key);
    if (!obj) return null;
    const arrayBuffer = await obj.arrayBuffer();
    const contentType = obj.httpMetadata?.contentType || 'application/pdf';
    return {
      data: new Uint8Array(arrayBuffer),
      contentType,
    };
  }

  async deleteDocument(key: string): Promise<void> {
    if (!this.bucket) return;
    await this.bucket.delete(key);
  }
}
