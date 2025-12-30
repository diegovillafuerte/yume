'use client';

import { AdminAuthProvider } from '@/providers/AdminAuthProvider';
import { QueryProvider } from '@/providers/QueryProvider';

export default function AdminRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <QueryProvider>
      <AdminAuthProvider>
        {children}
      </AdminAuthProvider>
    </QueryProvider>
  );
}
