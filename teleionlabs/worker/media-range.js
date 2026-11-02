// Streaming byte-range adapter for hosted /media/*.mp4 files.
// Workers Static Assets omits Content-Length inside the Worker and returns 200 on Range requests;
// slicing into FixedLengthStream enables native HTML5 <video> seeking (206 Partial Content / 416)
// without full-file buffering, storage, or remote fetches.
import { MEDIA_BYTES } from "./media.generated.js";

const MAX_BYTES = 32 * 1024 * 1024;
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
  return Boolean(tag && !tag.startsWith("W/") && value.trim() === tag);
}

function partialStream(asset, start, end, size, ctx) {
  const len = end - start + 1;
  const hasFixed = typeof globalThis.FixedLengthStream === "function";
  const stream = hasFixed ? new globalThis.FixedLengthStream(len) : new TransformStream();
  const reader = asset.body.getReader();
  const writer = stream.writable.getWriter();
  const transfer = (async () => {
    let position = 0;
    try {
      while (position <= end) {
        const { value, done } = await reader.read();
        if (done) throw new Error("Media asset ended before requested byte interval");
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
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(transfer);
  else transfer.catch(() => {});
  const headers = new Headers(asset.headers);
  for (const name of ["Content-Length", "Transfer-Encoding", "Content-Digest", "Content-MD5"]) {
    headers.delete(name);
  }
  headers.set("Accept-Ranges", "bytes");
  headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
  if (!hasFixed) headers.set("Content-Length", String(len));
  return new Response(stream.readable, { status: 206, headers, encodeBody: "manual" });
}

export async function maybeMediaRange(request, asset, ctx) {
  const pathname = new URL(request.url).pathname;
  const knownBytes = MEDIA_BYTES[pathname];
  if (!knownBytes || asset.status !== 200) return asset;
  const method = request.method.toUpperCase();
  if (method !== "GET" && method !== "HEAD") return asset;
  const encoding = asset.headers.get("Content-Encoding");
  const length = asset.headers.get("Content-Length");
  if ((encoding && encoding.toLowerCase() !== "identity") ||
      (length !== null && !/^\d+$/.test(length))) {
    return asset;
  }
  const size = length === null ? knownBytes : Number(length);
  if (!Number.isSafeInteger(size) || size !== knownBytes || size <= 0 || size > MAX_BYTES) return asset;

  if (method === "HEAD") {
    const headers = new Headers(asset.headers);
    headers.set("Accept-Ranges", "bytes");
    headers.set("Content-Length", String(size));
    const range = request.headers.get("Range");
    const selected = range && ifRangeMatches(request.headers.get("If-Range"), asset)
      ? singleRange(range, size) : null;
    if (selected && selected.unsatisfiable) {
      headers.delete("Content-Length");
      headers.set("Content-Range", `bytes */${size}`);
      return new Response(null, { status: 416, headers });
    }
    if (selected) {
      headers.set("Content-Length", String(selected.end - selected.start + 1));
      headers.set("Content-Range", `bytes ${selected.start}-${selected.end}/${size}`);
      return new Response(null, { status: 206, headers });
    }
    return new Response(null, { status: 200, headers });
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
