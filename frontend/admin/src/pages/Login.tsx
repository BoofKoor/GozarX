import { AxiosError } from "axios";
import { Eye, EyeOff, Lock, User } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { BrandMark } from "@/components/layout/Brand";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { useLogin } from "@/hooks/useAuth";

export function Login() {
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
          toast.error(
            status === 503 ? "پنل هنوز پیکربندی نشده است." : "نام کاربری یا رمز عبور نادرست است.",
          );
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
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BrandMark className="h-14 w-14" />
          <div>
            <h1 className="text-xl font-bold text-content">GozarX</h1>
            <p className="mt-1 text-sm text-content-muted">ورود به پنل مدیریت</p>
          </div>
        </div>

        <Card>
          <form onSubmit={submit} className="space-y-4">
            <Field label="نام کاربری">
              <Input
                icon={<User className="h-4 w-4" />}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </Field>
            <Field label="رمز عبور">
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
                    aria-label={reveal ? "پنهان‌کردن رمز" : "نمایش رمز"}
                    className="pointer-events-auto rounded p-1 text-content-subtle transition hover:text-content"
                  >
                    {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
              />
            </Field>
            <Button type="submit" size="lg" loading={login.isPending} className="w-full">
              ورود
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
