import { AxiosError } from "axios";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useLogin } from "@/hooks/useAuth";

export function Login() {
  const navigate = useNavigate();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

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
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-xl font-bold text-brand">GozarX</h1>
        <p className="mb-6 text-center text-sm text-slate-500 dark:text-slate-400">
          ورود به پنل مدیریت
        </p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm" htmlFor="username">
              نام کاربری
            </label>
            <Input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm" htmlFor="password">
              رمز عبور
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <Button type="submit" loading={login.isPending} className="w-full">
            ورود
          </Button>
        </form>
      </Card>
    </div>
  );
}
