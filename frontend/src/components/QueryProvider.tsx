"use client";

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import axios from 'axios';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  }));

  // Globally apply the configured UI Cache TTL
  useEffect(() => {
    const fetchTtlAndApply = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/settings');
        if (res.data?.cache_ttl) {
          const ttlMs = parseInt(res.data.cache_ttl, 10) * 1000;
          queryClient.setDefaultOptions({
            queries: {
              staleTime: ttlMs,
              refetchOnWindowFocus: false,
            }
          });
        }
      } catch (err) {
        // ignore errors on startup
      }
    };
    fetchTtlAndApply();
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
