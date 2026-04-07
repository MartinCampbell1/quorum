import type { RepoGraphResult } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface RepoGraphProps {
  result: RepoGraphResult;
}

export function RepoGraph({ result }: RepoGraphProps) {
  const topNodes = result.nodes.slice(0, 12);

  return (
    <Card className="border border-border/70 bg-background/90">
      <CardHeader>
        <CardTitle>{result.repo_name} Graph</CardTitle>
        <CardDescription>
          {result.stats.node_count} nodes · {result.stats.edge_count} edges · {result.stats.community_count} communities
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg bg-muted/60 p-3 text-sm">
            <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">APIs</div>
            <div className="mt-2 text-2xl font-semibold">{result.stats.api_count}</div>
          </div>
          <div className="rounded-lg bg-muted/60 p-3 text-sm">
            <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Packages</div>
            <div className="mt-2 text-2xl font-semibold">{result.stats.package_count}</div>
          </div>
          <div className="rounded-lg bg-muted/60 p-3 text-sm">
            <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Problems</div>
            <div className="mt-2 text-2xl font-semibold">{result.stats.problem_count}</div>
          </div>
        </section>

        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Communities</div>
          <div className="grid gap-3 md:grid-cols-2">
            {result.communities.map((community) => (
              <div key={community.community_id} className="rounded-lg border border-border/70 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{community.title}</div>
                  <Badge variant="secondary">{community.rank_score.toFixed(2)}</Badge>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{community.summary}</p>
                <ul className="mt-3 space-y-1 text-sm">
                  {community.finding_points.map((point) => (
                    <li key={point}>• {point}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Top Nodes</div>
          <div className="flex flex-wrap gap-2">
            {topNodes.map((node) => (
              <Badge key={node.node_id} variant="outline">
                {node.kind}: {node.label}
              </Badge>
            ))}
          </div>
        </section>
      </CardContent>
    </Card>
  );
}
