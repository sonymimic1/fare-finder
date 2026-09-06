import { createFileRoute, Link } from "@tanstack/react-router";
import { Radar, MailCheck, CalendarX, Plane } from "lucide-react";
import { FadeIn } from "@/components/fade-in";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Flight Price Notifier — 機票降價通知" },
      {
        name: "description",
        content:
          "設定航線與目標價，機票降價就通知你。Set a route and a target price — we email you when the fare drops.",
      },
      { property: "og:title", content: "Flight Price Notifier — 機票降價通知" },
      {
        property: "og:description",
        content:
          "Set a route and a target price — we email you when the fare drops.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LandingPage,
});

const features = [
  {
    icon: Radar,
    title: "盯緊熱門航線",
    subtitle: "Always-on route watching",
    body: "持續監控台北出發的熱門航線（東京、首爾），自動抓最低票價。",
  },
  {
    icon: MailCheck,
    title: "達標自動通知",
    subtitle: "Target-price email alerts",
    body: "低於你設定的目標價，就寄 email 提醒你，附上立即訂購連結。",
  },
  {
    icon: CalendarX,
    title: "隨時取消",
    subtitle: "Cancel anytime",
    body: "月訂閱制，不想用隨時停，沒有綁約。",
  },
];

function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Plane className="h-4 w-4" aria-hidden />
            </span>
            Flight Price Notifier
          </div>
          <Link
            to="/sign-in"
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/85"
          >
            Sign in / 登入
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(60rem 30rem at 50% -10%, oklch(0.62 0.22 290 / 18%), transparent 60%)",
            }}
          />
          <div className="relative mx-auto max-w-3xl px-4 py-24 text-center sm:px-6 sm:py-32">
            <FadeIn>
              <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
                Flight Price Notifier
              </h1>
            </FadeIn>
            <FadeIn delay={120}>
              <p className="mt-6 text-lg text-foreground sm:text-xl">
                設定航線與目標價，機票降價就通知你
              </p>
              <p className="mt-3 text-base text-muted-foreground sm:text-lg">
                Set a route and a target price — we email you when the fare
                drops.
              </p>
            </FadeIn>
            <FadeIn delay={240}>
              <div className="mt-10">
                <Link
                  to="/sign-up"
                  className="inline-flex items-center justify-center rounded-lg bg-primary px-6 py-3 text-base font-medium text-primary-foreground transition-colors hover:bg-primary/85"
                >
                  開始追蹤票價
                </Link>
              </div>
            </FadeIn>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <FadeIn key={f.title} delay={i * 120}>
                <article className="h-full rounded-2xl border border-border bg-card p-6 transition-colors hover:border-primary/40">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/15 text-primary">
                    <f.icon className="h-5 w-5" aria-hidden />
                  </div>
                  <h2 className="mt-5 text-lg font-semibold text-card-foreground">
                    {f.title}
                  </h2>
                  <p className="mt-1 text-sm font-medium text-primary">
                    {f.subtitle}
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {f.body}
                  </p>
                </article>
              </FadeIn>
            ))}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-8 text-center text-sm text-muted-foreground sm:px-6">
          © 2026 Flight Price Notifier
        </div>
      </footer>
    </div>
  );
}
