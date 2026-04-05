import type { RepoDNAProfile } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface RepoProfileProps {
  profile: RepoDNAProfile;
}

export function RepoProfile({ profile }: RepoProfileProps) {
  return (
    <Card className="border border-border/70 bg-background/90">
      <CardHeader>
        <CardTitle>{profile.repo_name} RepoDNA</CardTitle>
        <CardDescription>{profile.preferred_complexity} complexity bias</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Clusters</div>
          <div className="flex flex-wrap gap-2">
            {profile.domain_clusters.map((item) => (
              <Badge key={item} variant="secondary">
                {item}
              </Badge>
            ))}
            {profile.languages.map((item) => (
              <Badge key={item} variant="outline">
                {item}
              </Badge>
            ))}
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Repeated Builds</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {profile.repeated_builds.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Recurring Pain</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {profile.recurring_pain_areas.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Opportunities</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {profile.adjacent_product_opportunities.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Swipe Explanations</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {profile.swipe_explanation_points.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Idea Generation Context</div>
          <pre className="overflow-x-auto rounded-lg bg-muted/70 p-3 text-xs leading-5 text-muted-foreground">
            {profile.idea_generation_context}
          </pre>
        </section>
      </CardContent>
    </Card>
  );
}
