import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route, Routes } from "react-router";

import { ErrorBoundary } from "@/components/error-boundary";
import { RequireAuth } from "@/components/require-auth";
import { AppShellPage } from "@/pages/app";
import { LandingPage } from "@/pages/landing";
import { NotFoundPage } from "@/pages/not-found";
import { SignInPage } from "@/pages/sign-in";
import { SignUpPage } from "@/pages/sign-up";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/sign-in" element={<SignInPage />} />
          <Route path="/sign-up" element={<SignUpPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/app" element={<AppShellPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
