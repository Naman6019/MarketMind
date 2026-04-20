export async function GET() {
  try {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`)
    return Response.json({ ok: true })
  } catch (error) {
    return Response.json({ ok: false, error: String(error) }, { status: 500 })
  }
}
