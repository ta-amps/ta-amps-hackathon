// Compatibility fallback for build-allowlisted media. Native partial/conditional
// responses pass through. No full-file buffering, new storage or remote fetches.
import { MEDIA_BYTES } from "./media.generated.js";
// ASSETS may omit Content-Length inside the Worker and add it only at the HTTP
// boundary. This exact asset's size is checked against the file by the tests.
export const VIDEO_BYTES = MEDIA_BYTES["/media/main-film-20261103.mp4"];
const MAX_BYTES = 25 * 1024 * 1024;
const WRITE_CHUNK = 64 * 1024;

function singleRange(value, size) {
  const match = /^bytes=(\d*)-(\d*)$/i.exec(value.trim());
  if (!match || (!match[1] && !match[2])) return null;
  const first = match[1] ? Number(match[1]) : null;
  const last = match[2] ? Number(match[2]) : null;
  if ((first !== null && !Number.isSafeInteger(first)) ||
      (last !== null && !Number.isSafeInteger(last))) return null;
  if (first === null) {
    return last === 0 ? { unsatisfiable: true } : {
      start: Math.max(0, size - last), end: size - 1,
    };
  }
  if (first >= size || (last !== null && last < first)) return { unsatisfiable: true };
  return { start: first, end: last === null ? size - 1 : Math.min(last, size - 1) };
}

function ifRangeMatches(value, asset) {
  if (!value) return true;
  const tag = asset.headers.get("ETag");
  // An unverifiable date, weak validator or mismatch takes the full-response path.
  return Boolean(tag && !tag.startsWith("W/") && value.trim() === tag);
}

function partialStream(asset, start, end, size, ctx) {
  const reader = asset.body.getReader();
  const hasFixed = typeof globalThis.FixedLengthStream === "function";
  const fixed = hasFixed ? new globalThis.FixedLengthStream(end - start + 1) : new TransformStream();
  const writer = fixed.writable.getWriter();
  const transfer = (async () => {
    let position = 0;
    try {
      while (position <= end) {
        const { value, done } = await reader.read();
        if (done) throw new Error("Preview ended before the requested byte interval");
        const lower = Math.max(0, start - position);
        const upper = Math.min(value.byteLength, end + 1 - position);
        for (let offset = lower; offset < upper; offset += WRITE_CHUNK) {
          await writer.write(value.subarray(offset, Math.min(offset + WRITE_CHUNK, upper)));
        }
        position += value.byteLength;
      }
      await writer.close();
    } catch (error) {
      await writer.abort(error).catch(() => {});
      throw error;
    } finally {
      await reader.cancel().catch(() => {});
    }
  })();
  ctx.waitUntil(transfer);
  const headers = new Headers(asset.headers);
  for (const name of ["Content-Length", "Transfer-Encoding", "Content-Digest", "Content-MD5"]) {
    headers.delete(name);
  }
  headers.set("Accept-Ranges", "bytes");
  headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
  // workerd uses FixedLengthStream; Node-only fixtures need an explicit header.
  if (!hasFixed) headers.set("Content-Length", String(end - start + 1));
  return new Response(fixed.readable, { status: 206, headers, encodeBody: "manual" });
}

export async function maybeMediaRange(request, asset, ctx) {
  const knownBytes = MEDIA_BYTES[new URL(request.url).pathname];
  const encoding = asset.headers.get("Content-Encoding");
  const length = asset.headers.get("Content-Length");
  const contentType = asset.headers.get("Content-Type")?.split(";", 1)[0].trim().toLowerCase();
  if (!["GET", "HEAD"].includes(request.method) || !knownBytes ||
      asset.status !== 200 || !["video/mp4", "audio/mpeg"].includes(contentType) ||
      (encoding && encoding.toLowerCase() !== "identity") ||
      (length !== null && !/^\d+$/.test(length))) {
    return asset;
  }
  const size = length === null ? knownBytes : Number(length);
  if (!Number.isSafeInteger(size) || size !== knownBytes || size <= 0 || size > MAX_BYTES) return asset;
  if (request.method === "HEAD") {
    const headers = new Headers(asset.headers);
    headers.set("Accept-Ranges", "bytes");
    headers.set("Content-Length", String(size));
    return new Response(null, {status: 200, headers});
  }
  if (!asset.body) return asset;
  const range = request.headers.get("Range");
  const selected = range && ifRangeMatches(request.headers.get("If-Range"), asset)
    ? singleRange(range, size) : null;
  if (!selected) {
    const full = new Response(asset.body, asset);
    full.headers.set("Accept-Ranges", "bytes");
    return full;
  }
  if (selected.unsatisfiable) {
    await asset.body.cancel();
    const headers = new Headers(asset.headers);
    for (const name of ["Content-Length", "Transfer-Encoding", "Content-Digest", "Content-MD5"]) {
      headers.delete(name);
    }
    headers.set("Accept-Ranges", "bytes");
    headers.set("Content-Range", `bytes */${size}`);
    return new Response(null, { status: 416, headers });
  }
  return partialStream(asset, selected.start, selected.end, size, ctx);
}
