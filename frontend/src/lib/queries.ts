import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "./api";
import type { Application, Meta, User } from "./types";

export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: () => api.get<Meta>("/meta"), staleTime: Infinity });

export function useUsers() {
  const query = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/users") });
  const users = query.data ?? [];
  const name = useCallback(
    (id: number | null | undefined) => (id == null ? "-" : (users.find((u) => u.id === id)?.full_name ?? `User ${id}`)),
    [users],
  );
  return { users, name, isLoading: query.isLoading };
}

export function useApplications() {
  const query = useQuery({ queryKey: ["applications"], queryFn: () => api.get<Application[]>("/applications") });
  const applications = query.data ?? [];
  const name = useCallback(
    (id: number | null | undefined) => applications.find((a) => a.id === id)?.name ?? "-",
    [applications],
  );
  return { applications, name, isLoading: query.isLoading };
}
