import { QueryClient } from "@tanstack/react-query";

import { ApiError, SessionExpiredError } from "@/lib/api";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          if (error instanceof SessionExpiredError) return false;
          if (error instanceof ApiError) {
            // Only network failures and 5xx are retried once; 4xx never is.
            return (error.status === 0 || error.status >= 500) && failureCount < 1;
          }
          return failureCount < 1;
        },
      },
      mutations: { retry: false },
    },
  });
}
