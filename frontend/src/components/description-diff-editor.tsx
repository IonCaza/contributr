"use client";

import { Check, X, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RichTextEditor } from "@/components/rich-text-editor";
import { useMemo } from "react";

interface DescriptionDiffEditorProps {
  originalHtml: string;
  proposedHtml: string;
  onProposedChange: (html: string) => void;
  onAccept: (html: string) => void;
  onKeepOriginal: () => void;
  onDiscard: () => void;
  isLoading?: boolean;
}

function cleanAdoHtml(raw: string): string {
  return raw
    .replace(/\s*style="[^"]*"/gi, "")
    .replace(/<font[^>]*>/gi, "")
    .replace(/<\/font>/gi, "")
    .replace(/<span[^>]*>\s*<\/span>/gi, "")
    .replace(/(<div><br\s*\/?><\/div>\s*){2,}/gi, "<div><br/></div>");
}

export function DescriptionDiffEditor({
  originalHtml,
  proposedHtml,
  onProposedChange,
  onAccept,
  onKeepOriginal,
  onDiscard,
  isLoading,
}: DescriptionDiffEditorProps) {
  const cleanOriginal = useMemo(() => cleanAdoHtml(originalHtml), [originalHtml]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Left: original (read-only) */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Original
            </CardTitle>
          </CardHeader>
          <CardContent>
            {cleanOriginal ? (
              <div
                className="prose prose-sm dark:prose-invert max-w-none ado-description prose-headings:text-foreground prose-a:text-primary prose-code:rounded prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:text-sm prose-code:before:content-none prose-code:after:content-none prose-img:rounded-md min-h-48"
                dangerouslySetInnerHTML={{ __html: cleanOriginal }}
              />
            ) : (
              <p className="text-sm text-muted-foreground italic min-h-48">
                No description.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Right: proposed (editable) */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              AI Proposal
              {isLoading && (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground ml-1" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {proposedHtml ? (
              <RichTextEditor
                content={proposedHtml}
                onChange={onProposedChange}
              />
            ) : (
              <div className="flex flex-col items-center justify-center min-h-48 text-center rounded-md border border-dashed border-border p-6">
                <Sparkles className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm text-muted-foreground">
                  {isLoading
                    ? "Agent is generating a proposal..."
                    : "Use the AI Assistant to generate a proposal. The agent will populate this panel."}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-end gap-2 pt-1">
        <Button variant="ghost" size="sm" onClick={onDiscard}>
          <X className="mr-1.5 h-3.5 w-3.5" />
          Close
        </Button>
        <Button variant="outline" size="sm" onClick={onKeepOriginal}>
          Keep Original
        </Button>
        {proposedHtml && (
          <Button size="sm" onClick={() => onAccept(proposedHtml)}>
            <Check className="mr-1.5 h-3.5 w-3.5" />
            Accept Proposal
          </Button>
        )}
      </div>
    </div>
  );
}
