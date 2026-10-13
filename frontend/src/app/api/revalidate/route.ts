import { createHash, timingSafeEqual } from "node:crypto";
import { revalidateTag } from "next/cache";
import { FEC_DATA_TAG } from "@/api/cacheTags";

// Called by the ingestion workflows once new FEC data is in the database.
export async function POST(request: Request) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return Response.json(
      { error: "REVALIDATE_SECRET is not configured" },
      { status: 500 },
    );
  }
  const authorization = request.headers.get("authorization") ?? "";
  if (!sameSecret(authorization, `Bearer ${secret}`)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  revalidateTag(FEC_DATA_TAG, "max");
  return Response.json({ revalidated: true });
}

// Hash first so timingSafeEqual gets equal-length inputs and leaks no length.
function sameSecret(a: string, b: string) {
  const digest = (s: string) => createHash("sha256").update(s).digest();
  return timingSafeEqual(digest(a), digest(b));
}
