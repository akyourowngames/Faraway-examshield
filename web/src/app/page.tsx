import { Suspense } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Hero } from "@/components/sections/Hero";
import { AuthRedirectHandler } from "@/components/AuthRedirectHandler";

export default function Home() {
  return (
    <main className="min-h-screen">
      <Suspense>
        <AuthRedirectHandler />
      </Suspense>
      <Navbar />
      <Hero />
    </main>
  );
}
