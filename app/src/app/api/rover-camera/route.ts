import { createHash, timingSafeEqual } from "node:crypto";

const MAX_BYTES = 256 * 1024;
const MAX_AGE_MS = 6_000;
const noCache = { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" };

let frame: { bytes: Uint8Array<ArrayBuffer>; timestamp: number } | undefined;
let expiry: ReturnType<typeof setTimeout> | undefined;

function clearFrame() {
  clearTimeout(expiry);
  frame = undefined;
}

function authorize(request: Request, digest: string | undefined) {
  const token = request.headers.get("authorization")?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
  if (!digest || !/^[a-f0-9]{64}$/.test(digest)) {
    return new Response(null, { status: 503, headers: noCache });
  }
  if (!token || !timingSafeEqual(createHash("sha256").update(token).digest(), Buffer.from(digest, "hex"))) {
    return new Response(null, { status: 401, headers: noCache });
  }
}

export async function GET(request: Request) {
  const denied = authorize(request, process.env.NEXA_CAMERA_VIEW_SHA256);
  if (denied) return denied;
  if (!frame || Date.now() - frame.timestamp >= MAX_AGE_MS) {
    clearFrame();
    return new Response(null, { status: 204, headers: noCache });
  }
  return new Response(frame.bytes, {
    headers: { ...noCache, "Content-Type": "image/jpeg" },
  });
}

export async function POST(request: Request) {
  const denied = authorize(request, process.env.NEXA_CAMERA_PUBLISH_SHA256);
  if (denied) return denied;
  if (request.headers.get("content-type") !== "image/jpeg") {
    return new Response(null, { status: 415, headers: noCache });
  }
  const length = Number(request.headers.get("content-length"));
  if (!Number.isInteger(length) || length < 4 || length > MAX_BYTES || !request.body) {
    return new Response(null, { status: 413, headers: noCache });
  }
  const reader = request.body.getReader();
  const bytes = new Uint8Array(length);
  let offset = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (offset + value.byteLength > length) {
        await reader.cancel();
        return new Response(null, { status: 413, headers: noCache });
      }
      bytes.set(value, offset);
      offset += value.byteLength;
    }
  } finally {
    reader.releaseLock();
  }
  if (offset !== length || bytes[0] !== 0xff || bytes[1] !== 0xd8 ||
      bytes[length - 2] !== 0xff || bytes[length - 1] !== 0xd9) {
    return new Response(null, { status: 400, headers: noCache });
  }
  clearFrame();
  frame = { bytes, timestamp: Date.now() };
  expiry = setTimeout(clearFrame, MAX_AGE_MS);
  expiry.unref();
  return new Response(null, { status: 204, headers: noCache });
}

export async function DELETE(request: Request) {
  const denied = authorize(request, process.env.NEXA_CAMERA_PUBLISH_SHA256);
  if (denied) return denied;
  clearFrame();
  return new Response(null, { status: 204, headers: noCache });
}
