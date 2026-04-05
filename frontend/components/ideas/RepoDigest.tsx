import type { RepoDigestSummary } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface RepoDigestProps {
  digest: RepoDigestSummary;
}

export function RepoDigest({ digest }: RepoDigestProps) {
  return (
    <Card className="border border-border/70 bg-background/90">
      <CardHeader>
        <CardTitle>{digest.repo_name}</CardTitle>
        <CardDescription>
          {digest.source_type} · {digest.file_count} files
          {digest.branch ? ` · ${digest.branch}` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Tech Stack</div>
          <div className="flex flex-wrap gap-2">
            {digest.tech_stack.map((item) => (
              <Badge key={item} variant="outline">
                {item}
              </Badge>
            ))}
          </div>
        </section>

        <section className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Domains</div>
          <div className="flex flex-wrap gap-2">
            {digest.dominant_domains.map((item) => (
              <Badge key={item} variant="secondary">
                {item}
              </Badge>
            ))}
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">README Claims</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {digest.readme_claims.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Issue Themes</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {digest.issue_themes.map((item) => (
                <li key={item.label}>
                  {item.label} · {item.frequency}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Hot Files</div>
            <ul className="space-y-1 text-sm text-foreground/90">
              {digest.hot_files.map((file) => (
                <li key={file.path}>
                  {file.path} · {file.line_count} lines
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Tree Preview</div>
            <pre className="overflow-x-auto rounded-lg bg-muted/70 p-3 text-xs leading-5 text-muted-foreground">
              {digest.tree_preview.join("\n")}
            </pre>
          </div>
        </section>
      </CardContent>
    </Card>
  );
}
