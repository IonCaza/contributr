"use client";

import { type ReactNode, useState, useEffect } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive" | "warning";
  onConfirm: () => void;
  /** When set, user must type this exact name to enable the confirm button. */
  expectedName?: string;
  /** Placeholder for the name confirmation input. */
  expectedNameLabel?: string;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  variant = "destructive",
  onConfirm,
  expectedName,
  expectedNameLabel = "Type the name to confirm",
}: ConfirmDialogProps) {
  const [typedName, setTypedName] = useState("");
  useEffect(() => {
    if (!open) setTypedName("");
  }, [open]);
  const nameMatches = expectedName ? typedName.trim() === expectedName.trim() : true;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              {description}
              {expectedName != null && expectedName !== "" && (
                <div className="space-y-2 pt-2">
                  <Label htmlFor="confirm-name">{expectedNameLabel}</Label>
                  <Input
                    id="confirm-name"
                    value={typedName}
                    onChange={(e) => setTypedName(e.target.value)}
                    placeholder={expectedName}
                    className="font-mono"
                    autoComplete="off"
                  />
                </div>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={!nameMatches}
            className={
              variant === "destructive"
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
                : variant === "warning"
                  ? "bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
                  : undefined
            }
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
