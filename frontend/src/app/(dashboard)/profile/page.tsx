"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api-client";
import {
  User as UserIcon, Mail, Shield, ShieldCheck, Smartphone, KeyRound,
  Loader2, Check, AlertCircle, Lock, Eye, EyeOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { MfaSetupDialog } from "@/components/mfa-setup-dialog";

export default function ProfilePage() {
  const { user, refresh } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [profileError, setProfileError] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState("");

  const [mfaSetupOpen, setMfaSetupOpen] = useState(false);

  async function handleProfileSave() {
    setProfileError("");
    setProfileSuccess(false);
    setProfileSaving(true);
    try {
      await api.updateProfile({ full_name: fullName, email });
      await refresh();
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordChange() {
    setPwError("");
    setPwSuccess(false);
    if (newPassword !== confirmPassword) {
      setPwError("Passwords do not match");
      return;
    }
    if (newPassword.length < 8) {
      setPwError("Password must be at least 8 characters");
      return;
    }
    setPwSaving(true);
    try {
      await api.changeOwnPassword({ current_password: currentPassword, new_password: newPassword });
      setPwSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setPwSuccess(false), 3000);
    } catch (err: unknown) {
      setPwError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setPwSaving(false);
    }
  }

  const methods = user?.mfa_methods ?? [];
  const isLocal = user?.auth_provider === "local";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground">Manage your account settings and security.</p>
      </div>

      {/* Avatar + Identity */}
      <Card>
        <CardContent className="flex items-center gap-5 pt-6">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-primary/15 text-2xl font-bold text-primary">
            {user?.username?.charAt(0).toUpperCase() ?? "U"}
          </div>
          <div className="min-w-0">
            <p className="text-lg font-semibold truncate">{user?.full_name || user?.username}</p>
            <p className="text-sm text-muted-foreground truncate">@{user?.username}</p>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="text-xs">
                {user?.auth_provider === "local" ? "Local account" : `SSO (${user?.auth_provider})`}
              </Badge>
              {user?.is_admin && (
                <Badge variant="secondary" className="text-xs">Admin</Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserIcon className="h-4 w-4" /> Personal Information
          </CardTitle>
          <CardDescription>Update your display name and email address.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {profileError && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" /> {profileError}
            </div>
          )}
          {profileSuccess && (
            <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
              <Check className="h-4 w-4 shrink-0" /> Profile updated successfully.
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input id="username" value={user?.username ?? ""} disabled className="bg-muted" />
            <p className="text-xs text-muted-foreground">Usernames cannot be changed. Contact an administrator if needed.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="fullName">Full name</Label>
            <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your display name" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <Button
            onClick={handleProfileSave}
            disabled={profileSaving || (fullName === (user?.full_name ?? "") && email === (user?.email ?? ""))}
          >
            {profileSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</> : "Save changes"}
          </Button>
        </CardContent>
      </Card>

      {/* Password */}
      {isLocal && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-4 w-4" /> Password
            </CardTitle>
            <CardDescription>Change the password you use to sign in.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {pwError && (
              <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" /> {pwError}
              </div>
            )}
            {pwSuccess && (
              <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
                <Check className="h-4 w-4 shrink-0" /> Password changed successfully.
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current password</Label>
              <div className="relative">
                <Input
                  id="currentPassword"
                  type={showCurrentPw ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                  onClick={() => setShowCurrentPw(!showCurrentPw)}
                >
                  {showCurrentPw ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-muted-foreground" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">New password</Label>
              <div className="relative">
                <Input
                  id="newPassword"
                  type={showNewPw ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                  onClick={() => setShowNewPw(!showNewPw)}
                >
                  {showNewPw ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-muted-foreground" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm new password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat new password"
                onKeyDown={(e) => { if (e.key === "Enter" && currentPassword && newPassword && confirmPassword) handlePasswordChange(); }}
              />
            </div>
            <Button onClick={handlePasswordChange} disabled={pwSaving || !currentPassword || !newPassword || !confirmPassword}>
              {pwSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Changing...</> : "Change password"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Security / MFA */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" /> Security
          </CardTitle>
          <CardDescription>Two-factor authentication methods enrolled on your account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-3">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full ${methods.includes("totp") ? "bg-green-100 dark:bg-green-900/30" : "bg-muted"}`}>
                <Smartphone className={`h-4 w-4 ${methods.includes("totp") ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`} />
              </div>
              <div>
                <p className="text-sm font-medium">Authenticator App</p>
                <p className="text-xs text-muted-foreground">TOTP via Google Authenticator, Authy, etc.</p>
              </div>
            </div>
            {methods.includes("totp") ? (
              <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Enrolled</Badge>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setMfaSetupOpen(true)}>Enroll</Button>
            )}
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-3">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full ${methods.includes("email") ? "bg-green-100 dark:bg-green-900/30" : "bg-muted"}`}>
                <Mail className={`h-4 w-4 ${methods.includes("email") ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`} />
              </div>
              <div>
                <p className="text-sm font-medium">Email OTP</p>
                <p className="text-xs text-muted-foreground">One-time code sent to your email address.</p>
              </div>
            </div>
            {methods.includes("email") ? (
              <Badge variant="secondary" className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Enrolled</Badge>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setMfaSetupOpen(true)}>Enroll</Button>
            )}
          </div>
          {methods.length > 0 && (
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                  <KeyRound className="h-4 w-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">Recovery Codes</p>
                  <p className="text-xs text-muted-foreground">Backup codes for account recovery.</p>
                </div>
              </div>
              <Badge variant="secondary">Available</Badge>
            </div>
          )}
          {!user?.mfa_enabled && (
            <>
              <Separator />
              <div className="flex items-center gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                <Shield className="h-4 w-4 shrink-0" />
                MFA is not enabled. We recommend enrolling at least one method.
              </div>
              <Button onClick={() => setMfaSetupOpen(true)}>Set up MFA</Button>
            </>
          )}
        </CardContent>
      </Card>

      <MfaSetupDialog
        open={mfaSetupOpen}
        onOpenChange={setMfaSetupOpen}
        dismissible
        onComplete={async (at, rt) => {
          if (at && rt) {
            localStorage.setItem("access_token", at);
            localStorage.setItem("refresh_token", rt);
          }
          await refresh();
          setMfaSetupOpen(false);
        }}
      />
    </div>
  );
}
