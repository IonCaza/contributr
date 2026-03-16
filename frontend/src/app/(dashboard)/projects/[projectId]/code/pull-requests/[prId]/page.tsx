"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  GitPullRequest, MessageSquare, Clock, FileCode, Users,
  ArrowLeft, CheckCircle2, XCircle, AlertCircle,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import type { PRDetail, PRCommentItem, PRReview } from "@/lib/types";

function stateColor(state: string) {
  switch (state) {
    case "open": return "bg-green-500/15 text-green-700 dark:text-green-400";
    case "merged": return "bg-purple-500/15 text-purple-700 dark:text-purple-400";
    case "closed": return "bg-red-500/15 text-red-700 dark:text-red-400";
    default: return "bg-muted text-muted-foreground";
  }
}

function reviewIcon(state: string) {
  switch (state) {
    case "approved": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "changes_requested": return <AlertCircle className="h-4 w-4 text-amber-500" />;
    default: return <MessageSquare className="h-4 w-4 text-blue-500" />;
  }
}

function formatCycleTime(hours: number | null) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export default function PRDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; prId: string }>;
}) {
  const { projectId, prId } = use(params);

  const { data: pr, isLoading } = useQuery({
    queryKey: queryKeys.pullRequests.detail(projectId, prId),
    queryFn: () => api.getPullRequest(projectId, prId),
    enabled: !!projectId && !!prId,
  });

  const groupedComments = useMemo(() => {
    if (!pr?.comments) return { general: [], byFile: new Map<string, PRCommentItem[]>() };
    const general: PRCommentItem[] = [];
    const byFile = new Map<string, PRCommentItem[]>();
    for (const c of pr.comments) {
      if (c.file_path) {
        const arr = byFile.get(c.file_path) || [];
        arr.push(c);
        byFile.set(c.file_path, arr);
      } else {
        general.push(c);
      }
    }
    return { general, byFile };
  }, [pr?.comments]);

  if (isLoading || !pr) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-4 w-64" />
        <div className="grid grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href={`/projects/${projectId}/code/pull-requests`}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Pull Requests
      </Link>

      {/* Header */}
      <div>
        <div className="flex items-start gap-3">
          <GitPullRequest className="h-6 w-6 mt-1 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-muted-foreground mr-2">#{pr.platform_pr_id}</span>
              {pr.title || "(no title)"}
            </h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
              <Badge variant="secondary" className={cn("text-xs", stateColor(pr.state))}>
                {pr.state}
              </Badge>
              {pr.author_name && (
                <span>by {pr.contributor_id ? (
                  <Link href={`/contributors/${pr.contributor_id}`} className="font-medium text-foreground hover:underline">{pr.author_name}</Link>
                ) : (
                  <span className="font-medium text-foreground">{pr.author_name}</span>
                )}</span>
              )}
              <span>in <span className="font-medium text-foreground">{pr.repository_name}</span></span>
              <span>opened {new Date(pr.created_at).toLocaleDateString()}</span>
              {pr.merged_at && <span>merged {new Date(pr.merged_at).toLocaleDateString()}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        <Card className="p-3 text-center">
          <div className="text-lg font-bold">{formatCycleTime(pr.cycle_time_hours)}</div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-1"><Clock className="h-3 w-3" /> Cycle Time</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-lg font-bold">{formatCycleTime(pr.review_turnaround_hours)}</div>
          <div className="text-[10px] text-muted-foreground">Review Turnaround</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-lg font-bold">{pr.iteration_count}</div>
          <div className="text-[10px] text-muted-foreground">Iterations</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-lg font-bold">{pr.comment_count}</div>
          <div className="text-[10px] text-muted-foreground flex items-center justify-center gap-1"><MessageSquare className="h-3 w-3" /> Comments</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-lg font-bold whitespace-nowrap">
            <span className="text-emerald-500">+{pr.lines_added.toLocaleString()}</span>
            {" / "}
            <span className="text-red-500">-{pr.lines_deleted.toLocaleString()}</span>
          </div>
          <div className="text-[10px] text-muted-foreground">Lines Changed</div>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="reviews" className="gap-1.5">
            <Users className="h-3.5 w-3.5" /> Reviews ({pr.reviews.length})
          </TabsTrigger>
          <TabsTrigger value="comments" className="gap-1.5">
            <MessageSquare className="h-3.5 w-3.5" /> Comments ({pr.comments.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 mt-4">
          {/* Timeline */}
          <Card>
            <CardHeader><CardTitle className="text-sm">Timeline</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                <TimelineEvent
                  icon={<GitPullRequest className="h-4 w-4 text-green-500" />}
                  label={`${pr.author_name || "Someone"} opened this PR`}
                  date={pr.created_at}
                />
                {pr.first_review_at && (
                  <TimelineEvent
                    icon={<MessageSquare className="h-4 w-4 text-blue-500" />}
                    label="First review submitted"
                    date={pr.first_review_at}
                  />
                )}
                {pr.reviews.map((r) => (
                  <TimelineEvent
                    key={r.id}
                    icon={reviewIcon(r.state)}
                    label={`${r.reviewer_name || "Reviewer"} ${r.state.replace("_", " ")}`}
                    date={r.submitted_at}
                  />
                ))}
                {pr.merged_at && (
                  <TimelineEvent
                    icon={<CheckCircle2 className="h-4 w-4 text-purple-500" />}
                    label="PR merged"
                    date={pr.merged_at}
                  />
                )}
                {pr.closed_at && pr.state === "closed" && (
                  <TimelineEvent
                    icon={<XCircle className="h-4 w-4 text-red-500" />}
                    label="PR closed"
                    date={pr.closed_at}
                  />
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reviews" className="space-y-3 mt-4">
          {pr.reviews.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">No reviews yet.</p>
          ) : (
            pr.reviews.map((r: PRReview) => (
              <Card key={r.id} className="p-4">
                <div className="flex items-center gap-3">
                  {reviewIcon(r.state)}
                  <div className="flex-1">
                    <div className="font-medium">
                      {r.reviewer_id ? (
                        <Link href={`/contributors/${r.reviewer_id}`} className="hover:underline">{r.reviewer_name || "Unknown Reviewer"}</Link>
                      ) : (
                        r.reviewer_name || "Unknown Reviewer"
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {r.state.replace("_", " ")} · {r.comment_count} comment{r.comment_count !== 1 ? "s" : ""}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(r.submitted_at).toLocaleDateString()}
                  </div>
                </div>
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="comments" className="space-y-6 mt-4">
          {pr.comments.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">No comments.</p>
          ) : (
            <>
              {/* General comments */}
              {groupedComments.general.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-3">General Discussion</h3>
                  <div className="space-y-2">
                    {groupedComments.general.map((c) => (
                      <CommentCard key={c.id} comment={c} />
                    ))}
                  </div>
                </div>
              )}

              {/* File-level comments */}
              {Array.from(groupedComments.byFile.entries()).map(([filePath, comments]) => (
                <div key={filePath}>
                  <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
                    <FileCode className="h-3.5 w-3.5" />
                    {filePath}
                  </h3>
                  <div className="space-y-2 ml-5">
                    {comments.map((c) => (
                      <CommentCard key={c.id} comment={c} showLine />
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TimelineEvent({ icon, label, date }: { icon: React.ReactNode; label: string; date: string }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      {icon}
      <span className="flex-1">{label}</span>
      <span className="text-xs text-muted-foreground tabular-nums">
        {new Date(date).toLocaleString()}
      </span>
    </div>
  );
}

function CommentCard({ comment, showLine }: { comment: PRCommentItem; showLine?: boolean }) {
  return (
    <Card className="p-3">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
          {comment.author_name.charAt(0).toUpperCase()}
        </div>
        {comment.author_id ? (
          <Link href={`/contributors/${comment.author_id}`} className="text-sm font-medium hover:underline">{comment.author_name}</Link>
        ) : (
          <span className="text-sm font-medium">{comment.author_name}</span>
        )}
        {showLine && comment.line_number && (
          <Badge variant="outline" className="text-[9px]">line {comment.line_number}</Badge>
        )}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {new Date(comment.created_at).toLocaleString()}
        </span>
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {comment.body}
        </ReactMarkdown>
      </div>
    </Card>
  );
}
