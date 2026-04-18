"use client";

import { use, useState, useCallback, useDeferredValue } from "react";
import {
  Package, ShieldAlert, AlertTriangle, AlertCircle, ArrowUpCircle,
  CheckCircle2, Play, Loader2, ChevronDown, ChevronRight, Info,
  Download, ExternalLink, EyeOff, Search, ChevronLeft,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";

import {
  useProjectDepFindings,
  useProjectDepSummary,
  useProjectDepRuns,
  useTriggerProjectDepScan,
  useDismissProjectDepFinding,
} from "@/hooks/use-dependencies";
import { useProjectRepos } from "@/hooks/use-repos";
import { useActiveRunTracking } from "@/hooks/use-active-run-tracking";
import { api } from "@/lib/api-client";
import { SyncLogViewer } from "@/components/sync-log-viewer";
import type { DepFinding, DepSummary, DepScanRun, Repository } from "@/lib/types";
import { useRegisterUIContext } from "@/hooks/use-register-ui-context";

const ANIM_CARD = "animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both";
function stagger(i: number) { return { animationDelay: `${i * 60}ms` }; }

const SEVERITY_CONFIG: Record<string, { icon: typeof ShieldAlert; color: string; bg: string }> = {
  critical: { icon: ShieldAlert, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950/30" },
  high: { icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50 dark:bg-orange-950/30" },
  medium: { icon: AlertCircle, color: "text-amber-500", bg: "bg-amber-50 dark:bg-amber-950/30" },
  low: { icon: Info, color: "text-blue-500", bg: "bg-blue-50 dark:bg-blue-950/30" },
  none: { icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950/30" },
};

const ECOSYSTEM_COLORS: Record<string, string> = {
  PyPI: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  npm: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  Go: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300",
  "crates.io": "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  Docker: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  Maven: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  NuGet: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
  RubyGems: "bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300",
};

function formatRelativeTime(dateStr: string | null) {
  if (!dateStr) return "N/A";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Health Banner
// ---------------------------------------------------------------------------

function DepHealthBanner({
  summary,
  isLoading,
  lastRun,
  repos,
  reposLoading,
  onScanRepo,
  scanningRepoId,
  projectId,
}: {
  summary: DepSummary | undefined;
  isLoading: boolean;
  lastRun: DepScanRun | undefined;
  repos: Repository[];
  reposLoading: boolean;
  onScanRepo: (repoId: string) => void;
  scanningRepoId: string | null;
  projectId: string;
}) {
  const score = summary && summary.total_packages > 0
    ? Math.round(((summary.up_to_date) / summary.total_packages) * 100)
    : null;

  const scoreColor = score === null
    ? "bg-muted"
    : score >= 80
      ? "bg-emerald-500"
      : score >= 50
        ? "bg-amber-500"
        : "bg-red-500";

  const lastRunLabel = lastRun
    ? `Last scan: ${formatRelativeTime(lastRun.created_at)}`
    : "No scans yet";

  function handleReportDownload(format: string) {
    const token = api.getAuthToken();
    const baseUrl = api.getProjectDepReportUrl(projectId, format);
    const url = token ? `${baseUrl}&token=${encodeURIComponent(token)}` : baseUrl;
    window.open(url, "_blank");
  }

  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4 px-6 gap-4">
        <div className="flex items-center gap-4">
          {isLoading && !summary ? (
            <>
              <Skeleton className="h-12 w-12 rounded-full" />
              <div className="space-y-1.5">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-24" />
              </div>
            </>
          ) : (
            <>
              <div className={`h-12 w-12 rounded-full ${scoreColor} flex items-center justify-center`}>
                <span className="text-white font-bold text-lg">{score ?? "?"}</span>
              </div>
              <div>
                <p className="font-semibold text-lg">Dependency Health</p>
                <p className="text-sm text-muted-foreground">{lastRunLabel}</p>
              </div>
              {score !== null && (
                <div className="hidden sm:flex items-center gap-1 ml-4">
                  <div className="h-2 w-48 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${scoreColor}`}
                      style={{ width: `${score}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground ml-1">{score}% healthy</span>
                </div>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {repos.length > 1 && (
            <Button
              onClick={() => repos.forEach((r) => onScanRepo(r.id))}
              disabled={!!scanningRepoId}
              size="sm"
            >
              {scanningRepoId ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Scan All</>
              )}
            </Button>
          )}
          {repos.length === 1 && (
            <Button
              onClick={() => onScanRepo(repos[0].id)}
              disabled={scanningRepoId === repos[0].id}
              size="sm"
            >
              {scanningRepoId === repos[0].id ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-1" />Scanning...</>
              ) : (
                <><Play className="h-4 w-4 mr-1" />Run Scan</>
              )}
            </Button>
          )}
          {repos.length === 0 && reposLoading && (
            <Skeleton className="h-9 w-24 rounded-md" />
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-1" /> Report
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleReportDownload("json")}>
                Download JSON
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleReportDownload("csv")}>
                Download CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Finding Card
// ---------------------------------------------------------------------------

function FindingCard({
  finding,
  onDismiss,
}: {
  finding: DepFinding;
  onDismiss: () => void;
}) {
  const [open, setOpen] = useState(false);
  const sevConfig = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.none;
  const SevIcon = sevConfig.icon;
  const ecoClass = ECOSYSTEM_COLORS[finding.ecosystem] || "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className={`rounded-lg border ${finding.is_vulnerable ? sevConfig.bg : ""}`}>
        <CollapsibleTrigger className="flex items-center justify-between w-full p-4 text-left hover:bg-muted/50 transition-colors rounded-lg">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {finding.is_vulnerable ? (
              <SevIcon className={`h-5 w-5 shrink-0 ${sevConfig.color}`} />
            ) : finding.is_outdated ? (
              <ArrowUpCircle className="h-5 w-5 shrink-0 text-amber-500" />
            ) : (
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium truncate">{finding.package_name}</span>
                <Badge variant="outline" className={`text-xs ${ecoClass}`}>
                  {finding.ecosystem}
                </Badge>
                {finding.is_direct && (
                  <Badge variant="outline" className="text-xs">direct</Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {finding.current_version || "unknown"} {finding.latest_version && finding.is_outdated ? `→ ${finding.latest_version}` : ""}
                <span className="mx-1.5">·</span>
                {finding.file_path}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-2">
            {finding.is_vulnerable && (
              <Badge variant="destructive" className="text-xs">
                {(finding.vulnerabilities?.length || 0)} vuln{(finding.vulnerabilities?.length || 0) !== 1 ? "s" : ""}
              </Badge>
            )}
            {finding.is_outdated && !finding.is_vulnerable && (
              <Badge variant="secondary" className="text-xs">outdated</Badge>
            )}
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </div>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-4 space-y-3 border-t pt-3">
            {finding.vulnerabilities && finding.vulnerabilities.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Known Vulnerabilities</p>
                {finding.vulnerabilities.map((v, i) => {
                  const vSev = SEVERITY_CONFIG[(v.severity || "medium").toLowerCase()] || SEVERITY_CONFIG.medium;
                  return (
                    <div key={i} className="flex items-start gap-3 p-2 rounded-md bg-muted/50">
                      <vSev.icon className={`h-4 w-4 mt-0.5 shrink-0 ${vSev.color}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <a
                            href={v.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-primary hover:underline flex items-center gap-1"
                          >
                            {v.id} <ExternalLink className="h-3 w-3" />
                          </a>
                          <Badge variant="outline" className="text-xs capitalize">{v.severity}</Badge>
                          {v.fixed_version && (
                            <span className="text-xs text-muted-foreground">Fixed in {v.fixed_version}</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{v.summary}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground text-xs">Current</span>
                <p className="font-mono text-sm">{finding.current_version || "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">Latest</span>
                <p className="font-mono text-sm">{finding.latest_version || "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">File</span>
                <p className="text-sm truncate">{finding.file_path}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">Detected</span>
                <p className="text-sm">{formatRelativeTime(finding.first_detected_at)}</p>
              </div>
            </div>
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                <EyeOff className="h-4 w-4 mr-1" /> Dismiss
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ProjectDependenciesPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const [severityFilter, setSeverityFilter] = useState("");
  const [ecosystemFilter, setEcosystemFilter] = useState("");
  const [viewFilter, setViewFilter] = useState<"all" | "vulnerable" | "outdated">("all");
  const [scanningRepoId, setScanningRepoId] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const deferredSearch = useDeferredValue(searchInput);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const { data: repos = [], isLoading: reposLoading } = useProjectRepos(projectId);
  const { data: summary, isLoading: summaryLoading } = useProjectDepSummary(projectId);
  const { data: runs = [] } = useProjectDepRuns(projectId);

  const { data: findingsPage, isLoading: findingsLoading, isPlaceholderData } = useProjectDepFindings(projectId, {
    severity: severityFilter || undefined,
    ecosystem: ecosystemFilter || undefined,
    vulnerable: viewFilter === "vulnerable" ? true : undefined,
    outdated: viewFilter === "outdated" ? true : undefined,
    search: deferredSearch || undefined,
    page,
    page_size: PAGE_SIZE,
  });
  const findings = findingsPage?.items ?? [];
  const totalFindings = findingsPage?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalFindings / PAGE_SIZE));

  const triggerScan = useTriggerProjectDepScan(projectId);
  const dismissFinding = useDismissProjectDepFinding(projectId);

  const handleScanRepo = useCallback((repoId: string) => {
    setScanningRepoId(repoId);
    triggerScan.mutate(repoId, {
      onSettled: () => setScanningRepoId(null),
    });
  }, [triggerScan]);

  const lastRun = runs[0];
  useActiveRunTracking(lastRun);
  const activeRun = runs.find((r) => r.status === "queued" || r.status === "running") ?? null;
  const ecosystems = summary ? Object.keys(summary.by_ecosystem) : [];

  useRegisterUIContext("dependencies", {
    summary,
    totalFindings,
    ecosystems,
    filters: { severity: severityFilter, ecosystem: ecosystemFilter, view: viewFilter, search: deferredSearch },
  });

  const SEVERITIES = [
    { value: "", label: "All Severity" },
    { value: "critical", label: "Critical" },
    { value: "high", label: "High" },
    { value: "medium", label: "Medium" },
    { value: "low", label: "Low" },
  ];

  const VIEWS = [
    { value: "all" as const, label: "All" },
    { value: "vulnerable" as const, label: "Vulnerable" },
    { value: "outdated" as const, label: "Outdated" },
  ];

  return (
    <div className="space-y-6">
      {/* Health Banner */}
      <div className={ANIM_CARD} style={stagger(0)}>
        <DepHealthBanner
          summary={summary}
          isLoading={summaryLoading}
          lastRun={lastRun}
          repos={repos}
          reposLoading={reposLoading}
          onScanRepo={handleScanRepo}
          scanningRepoId={scanningRepoId}
          projectId={projectId}
        />
      </div>

      {/* Summary Cards */}
      <div className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 ${ANIM_CARD}`} style={stagger(1)}>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Total Packages</span>
            </div>
            <div className="text-2xl font-bold mt-1">
              {summaryLoading ? <Skeleton className="h-8 w-16" /> : summary?.total_packages ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-red-500" />
              <span className="text-sm text-muted-foreground">Vulnerable</span>
            </div>
            <div className="text-2xl font-bold mt-1 text-red-600">
              {summaryLoading ? <Skeleton className="h-8 w-16" /> : summary?.vulnerable ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <ArrowUpCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-muted-foreground">Outdated</span>
            </div>
            <div className="text-2xl font-bold mt-1 text-amber-600">
              {summaryLoading ? <Skeleton className="h-8 w-16" /> : summary?.outdated ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <span className="text-sm text-muted-foreground">Up to Date</span>
            </div>
            <div className="text-2xl font-bold mt-1 text-emerald-600">
              {summaryLoading ? <Skeleton className="h-8 w-16" /> : summary?.up_to_date ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Ecosystems</span>
            </div>
            <div className="text-2xl font-bold mt-1">
              {summaryLoading ? <Skeleton className="h-8 w-16" /> : ecosystems.length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Ecosystem Breakdown */}
      {ecosystems.length > 0 && (
        <div className={`flex flex-wrap gap-2 ${ANIM_CARD}`} style={stagger(2)}>
          {ecosystems.map((eco) => (
            <Badge
              key={eco}
              variant="outline"
              className={`text-sm cursor-pointer ${ECOSYSTEM_COLORS[eco] || ""} ${ecosystemFilter === eco ? "ring-2 ring-primary" : ""}`}
              onClick={() => { setEcosystemFilter(ecosystemFilter === eco ? "" : eco); setPage(1); }}
            >
              {eco}: {summary!.by_ecosystem[eco]}
            </Badge>
          ))}
        </div>
      )}

      {/* Search + Filter Bar */}
      <div className={`flex flex-wrap items-center gap-2 ${ANIM_CARD}`} style={stagger(3)}>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search packages…"
            value={searchInput}
            onChange={(e) => { setSearchInput(e.target.value); setPage(1); }}
            className="h-8 w-56 pl-8 text-sm"
          />
        </div>
        <div className="inline-flex h-8 items-center rounded-md bg-muted p-0.5 text-muted-foreground">
          {VIEWS.map((v) => (
            <button
              key={v.value}
              onClick={() => { setViewFilter(v.value); setPage(1); }}
              className={`inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-medium transition-all ${
                viewFilter === v.value
                  ? "bg-background text-foreground shadow-sm"
                  : "hover:text-foreground"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="inline-flex h-8 items-center rounded-md bg-muted p-0.5 text-muted-foreground">
          {SEVERITIES.map((s) => (
            <button
              key={s.value}
              onClick={() => { setSeverityFilter(s.value); setPage(1); }}
              className={`inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-medium transition-all ${
                severityFilter === s.value
                  ? "bg-background text-foreground shadow-sm"
                  : "hover:text-foreground"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
        {ecosystemFilter && (
          <Button variant="ghost" size="sm" onClick={() => { setEcosystemFilter(""); setPage(1); }}>
            Clear {ecosystemFilter} filter
          </Button>
        )}
      </div>

      {/* Findings List */}
      <div className={`space-y-2 ${ANIM_CARD}`} style={stagger(4)}>
        {!findingsLoading && totalFindings > 0 && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, totalFindings)} of {totalFindings.toLocaleString()} packages
            </span>
            {totalPages > 1 && (
              <span>Page {page} of {totalPages}</span>
            )}
          </div>
        )}
        {findingsLoading && !isPlaceholderData ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))
        ) : findings.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              <Package className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-lg font-medium">No dependency findings</p>
              <p className="text-sm">
                {deferredSearch ? "No packages match your search." : "Run a scan to analyze your project\u2019s dependencies."}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className={isPlaceholderData ? "opacity-60 transition-opacity" : ""}>
            {findings.map((f) => (
              <FindingCard
                key={f.id}
                finding={f}
                onDismiss={() =>
                  dismissFinding.mutate({ repoId: f.repository_id, findingId: f.id })
                }
              />
            ))}
          </div>
        )}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-1 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 7) {
                pageNum = i + 1;
              } else if (page <= 4) {
                pageNum = i + 1;
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 6 + i;
              } else {
                pageNum = page - 3 + i;
              }
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === page ? "default" : "outline"}
                  size="sm"
                  className="w-8 px-0"
                  onClick={() => setPage(pageNum)}
                >
                  {pageNum}
                </Button>
              );
            })}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* By-Repo Breakdown */}
      {repos.length > 1 && (
        <Card className={ANIM_CARD} style={stagger(5)}>
          <CardHeader>
            <CardTitle className="text-base">Repositories</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Repository</TableHead>
                  <TableHead className="text-right">Packages</TableHead>
                  <TableHead className="text-right">Vulnerable</TableHead>
                  <TableHead className="text-right">Outdated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {repos.map((repo) => {
                  const latestRun = runs.find((r) => r.repository_id === repo.id && r.status === "completed");
                  const pkgCount = latestRun?.findings_count ?? 0;
                  const vulnCount = latestRun?.vulnerable_count ?? 0;
                  const outdatedCount = latestRun?.outdated_count ?? 0;
                  return (
                    <TableRow key={repo.id}>
                      <TableCell className="font-medium">{repo.name}</TableCell>
                      <TableCell className="text-right">{pkgCount}</TableCell>
                      <TableCell className="text-right">
                        {vulnCount > 0 ? (
                          <span className="text-red-600 font-medium">{vulnCount}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {outdatedCount > 0 ? (
                          <span className="text-amber-600 font-medium">{outdatedCount}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleScanRepo(repo.id)}
                          disabled={scanningRepoId === repo.id}
                        >
                          {scanningRepoId === repo.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Scan History */}
      {runs.length > 0 && (
        <Card className={ANIM_CARD} style={stagger(6)}>
          <CardHeader>
            <CardTitle className="text-base">Scan History</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Finished</TableHead>
                  <TableHead className="text-right">Packages</TableHead>
                  <TableHead className="text-right">Vulnerable</TableHead>
                  <TableHead className="text-right">Outdated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.slice(0, 10).map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>
                      <Badge
                        variant={
                          run.status === "completed" ? "default" :
                          run.status === "running" ? "secondary" :
                          run.status === "failed" ? "destructive" : "outline"
                        }
                        className="text-xs"
                      >
                        {run.status === "running" && <Loader2 className="h-3 w-3 animate-spin mr-1" />}
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{formatRelativeTime(run.started_at)}</TableCell>
                    <TableCell className="text-sm">{formatRelativeTime(run.finished_at)}</TableCell>
                    <TableCell className="text-right">{run.findings_count}</TableCell>
                    <TableCell className="text-right">{run.vulnerable_count}</TableCell>
                    <TableCell className="text-right">{run.outdated_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Active Scan Log */}
      {activeRun && (
        <Card className={ANIM_CARD} style={stagger(7)}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Scan in Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SyncLogViewer
              logUrl={`${api.getApiBase()}/repositories/${activeRun.repository_id}/dependencies/runs/${activeRun.id}/logs`}
              compact
              title="Dependency Scan"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
