"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Users2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTeam, useTeamMembers, useRemoveTeamMember } from "@/hooks/use-teams";

export default function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const { data: team, isLoading: teamLoading } = useTeam(teamId);
  const { data: members = [], isLoading: membersLoading } = useTeamMembers(teamId);
  const removeMember = useRemoveTeamMember(teamId);

  if (teamLoading || !team) {
    return <div className="animate-pulse text-muted-foreground">Loading team...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
          <Users2 className="h-7 w-7 text-primary" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{team.name}</h1>
          {team.description && <p className="text-muted-foreground">{team.description}</p>}
          <div className="flex items-center gap-2 mt-1">
            {team.platform && <Badge variant="secondary" className="text-[10px]">{team.platform}</Badge>}
            <span className="text-xs text-muted-foreground">{team.member_count} member{team.member_count !== 1 ? "s" : ""}</span>
          </div>
        </div>
      </div>

      <Tabs defaultValue="members" className="w-full">
        <TabsList>
          <TabsTrigger value="members">Members</TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
        </TabsList>

        <TabsContent value="members" className="mt-4">
          {membersLoading && <p className="text-muted-foreground animate-pulse">Loading members...</p>}
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead className="w-16 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.contributor_id}>
                    <TableCell>
                      <Link href={`/contributors/${m.contributor_id}`} className="flex items-center gap-2 font-medium hover:underline">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                          {m.contributor_name.charAt(0).toUpperCase()}
                        </div>
                        {m.contributor_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{m.contributor_email}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px]">{m.role}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => removeMember.mutate(m.contributor_id)}
                        disabled={removeMember.isPending}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {members.length === 0 && !membersLoading && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                      No members in this team yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="overview" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Team Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <span className="text-sm text-muted-foreground">Name</span>
                <p className="font-medium">{team.name}</p>
              </div>
              {team.description && (
                <div>
                  <span className="text-sm text-muted-foreground">Description</span>
                  <p>{team.description}</p>
                </div>
              )}
              <div>
                <span className="text-sm text-muted-foreground">Source</span>
                <p className="font-medium">{team.platform || "Manual"}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">Members</span>
                <p className="font-medium">{team.member_count}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">Created</span>
                <p className="text-sm">{team.created_at ? new Date(team.created_at).toLocaleString() : "—"}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
