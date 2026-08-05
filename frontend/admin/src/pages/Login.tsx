import { AxiosError } from "axios";
import { Eye, EyeOff, Lock, User } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { BrandTile } from "@/components/layout/Brand";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { LanguagePill } from "@/components/layout/LanguagePill";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useLogin } from "@/hooks/useAuth";
import { useI18n } from "@/i18n";

export function Login() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);

  function submit(e: FormEvent) {
    e.preventDefault();
    login.mutate(
      { username, password },
      {
        onSuccess: () => navigate("/", { replace: true }),
        onError: (err) => {
          const status = (err as AxiosError).response?.status;
          toast.error(status === 503 ? t("login.notConfigured") : t("login.failed"));
        },
      },
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      {/* Brand wash behind the card — the same blue→cyan pairing the public site's hero uses. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_40rem_at_50%_-10%,rgb(var(--brand-500)/0.14),transparent_70%)]"
      />
      <div className="relative w-full max-w-sm">
        {/* The language and theme controls live in the top bar, which this screen has no room for —
            but an admin who reads English, or who works in the light theme, meets THIS page first,
            so both have to be switchable here too. */}
        <div className="mb-4 flex items-center justify-center gap-1">
          <LanguagePill />
          <ThemeToggle />
        </div>
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BrandTile className="h-14 w-14" />
          <div>
            <h1 className="text-xl font-bold text-content">GozarX</h1>
            <p className="mt-1 text-sm text-content-muted">{t("login.title")}</p>
          </div>
        </div>

        <Card>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("login.username")}>
              <Input
                icon={<User className="h-4 w-4" />}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </Field>
            <Field label={t("login.password")}>
              <Input
                icon={<Lock className="h-4 w-4" />}
                type={reveal ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                suffix={
                  <button
                    type="button"
                    onClick={() => setReveal((v) => !v)}
                    aria-label={reveal ? t("login.hide") : t("login.reveal")}
                    className="pointer-events-auto rounded p-1 text-content-subtle transition hover:text-content"
                  >
                    {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
              />
            </Field>
            <Button type="submit" size="lg" loading={login.isPending} className="w-full">
              {t("login.submit")}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
