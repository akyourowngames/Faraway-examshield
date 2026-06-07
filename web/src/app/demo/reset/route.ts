import { resetDemoEnvironment } from "@/lib/evidence-store";

export const runtime = "nodejs";

export async function POST() {
  try {
    const payload = await resetDemoEnvironment();
    return Response.json(payload);
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Demo reset failed." },
      { status: 500 },
    );
  }
}
