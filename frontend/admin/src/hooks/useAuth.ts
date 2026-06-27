import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { clearAuth, setTokens, setUsername } from "@/lib/auth";
import type { TokenPair } from "@/types/api";

export function useLogin() {
  return useMutation({
    mutationFn: async (creds: { username: string; password: string }) => {
      const { data } = await api.post<TokenPair>("/admin/auth/login", creds);
      return data;
    },
    onSuccess: (data, vars) => {
      setTokens(data.access_token, data.refresh_token);
      setUsername(vars.username);
    },
  });
}

export function logout(): void {
  clearAuth();
  window.location.replace("/login");
}
