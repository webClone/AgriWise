import { ObjectId } from "bson";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";

export type DevelopmentSeedAuthorization =
  | { userId: string; status: 200; error: null }
  | { userId: null; status: 401 | 403 | 404; error: string };

/** Authorize the explicit farm-page demo seeder on loopback development only. */
export async function authorizeDevelopmentSeed(
  request: NextRequest,
): Promise<DevelopmentSeedAuthorization> {
  if (process.env.NODE_ENV !== "development") {
    return { userId: null, status: 404, error: "Not found" };
  }
  if (
    !["localhost", "127.0.0.1", "::1"].includes(request.nextUrl.hostname)
    || request.headers.get("origin") !== request.nextUrl.origin
    || request.headers.get("x-agriwise-dev-seed") !== "farm-page"
  ) {
    return { userId: null, status: 403, error: "Development seed request rejected" };
  }

  const session = await getSession();
  if (!session?.userId || !ObjectId.isValid(session.userId)) {
    return { userId: null, status: 401, error: "Authentication required" };
  }
  const user = await prisma.user.findUnique({
    where: { id: session.userId },
    select: { id: true },
  });
  return user
    ? { userId: user.id, status: 200, error: null }
    : { userId: null, status: 401, error: "Session owner no longer exists" };
}
