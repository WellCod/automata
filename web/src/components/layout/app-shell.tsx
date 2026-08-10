"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const withSidebar = pathname !== "/login";

  return (
    <>
      {withSidebar && <Sidebar />}
      <div className={withSidebar ? "min-h-full flex-1 pl-[200px]" : "min-h-full flex-1"}>
        {children}
      </div>
    </>
  );
}
