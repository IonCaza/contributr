"use client";

import { useState } from "react";
import { MessageSquarePlus, Send, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useCreateFeedback } from "@/hooks/use-feedback";

const CATEGORIES = [
  { value: "bug", label: "Bug Report" },
  { value: "suggestion", label: "Suggestion" },
  { value: "missing_data", label: "Missing Data" },
  { value: "capability_gap", label: "Missing Feature" },
  { value: "other", label: "Other" },
] as const;

export function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("");
  const [content, setContent] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const createFeedback = useCreateFeedback();

  function reset() {
    setCategory("");
    setContent("");
    setSubmitted(false);
  }

  function handleSubmit() {
    if (!content.trim()) return;
    createFeedback.mutate(
      {
        source: "human",
        category: category || undefined,
        content: content.trim(),
      },
      {
        onSuccess: () => {
          setSubmitted(true);
          setTimeout(() => {
            setOpen(false);
            reset();
          }, 1500);
        },
      },
    );
  }

  return (
    <Popover
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) setTimeout(reset, 200);
      }}
    >
      <PopoverTrigger asChild>
        <Button
          size="icon"
          className="fixed top-4 right-4 z-50 h-10 w-10 rounded-full shadow-lg"
        >
          <MessageSquarePlus className="h-5 w-5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={8}
        className="w-80"
      >
        {submitted ? (
          <div className="flex flex-col items-center gap-2 py-6">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <p className="text-sm font-medium">Thanks for your feedback!</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <h4 className="text-sm font-semibold">Send Feedback</h4>
              <p className="text-xs text-muted-foreground">
                Help us improve Contributr.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="fb-category" className="text-xs">
                Category
              </Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="fb-category" className="h-8 text-xs">
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="fb-content" className="text-xs">
                What&apos;s on your mind?
              </Label>
              <Textarea
                id="fb-content"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Describe your issue or idea..."
                className="min-h-24 resize-none text-sm"
              />
            </div>

            <Button
              size="sm"
              className="w-full"
              disabled={!content.trim() || createFeedback.isPending}
              onClick={handleSubmit}
            >
              {createFeedback.isPending ? (
                "Sending..."
              ) : (
                <>
                  <Send className="mr-1.5 h-3.5 w-3.5" />
                  Submit Feedback
                </>
              )}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
