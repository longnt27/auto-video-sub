export function GET() {
  return Response.json({
    status: "alive",
    service: "auto-video-sub-web",
    version: "0.1.0",
  });
}
