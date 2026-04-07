import type { RepoDeepDiveRecord } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface RepoDeepDiveProps {
  deepDive: RepoDeepDiveRecord;
}

export function RepoDeepDive({ deepDive }: RepoDeepDiveProps) {
  return (
    <Card className="border border-border/70 bg-background/90">
      <CardHeader>
        <CardTitle>Repo Deep Dive</CardTitle>
        <CardDescription>Graph-backed opportunity and risk framing</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Startup Territories</div>
            <ul className="space-y-1 text-sm">
              {deepDive.startup_territories.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Why Now</div>
            <ul className="space-y-1 text-sm">
              {deepDive.why_now.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Architectural Focus</div>
            <ul className="space-y-1 text-sm">
              {deepDive.architectural_focus.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Risk Hotspots</div>
            <ul className="space-y-1 text-sm">
              {deepDive.risk_hotspots.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Evidence Trails</div>
          <div className="space-y-3">
            {deepDive.evidence_trails.map((trail) => (
              <div key={trail.trail_id} className="rounded-lg border border-border/70 p-3">
                <div className="font-medium">{trail.thesis}</div>
                <p className="mt-2 text-sm text-muted-foreground">{trail.explanation}</p>
                <div className="mt-2 text-xs text-muted-foreground">
                  {trail.supporting_node_ids.length} nodes · {trail.supporting_edge_ids.length} edges
                </div>
              </div>
            ))}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}
