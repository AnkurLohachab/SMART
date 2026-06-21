'use client';

import { Toaster } from 'sonner';
import { useTheme } from 'next-themes';

export function ToastProvider() {
  const { resolvedTheme } = useTheme();

  return (
    <Toaster
      position="top-right"
      expand={false}
      richColors
      closeButton
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      toastOptions={{
        style: {
          background: resolvedTheme === 'dark' ? '#1e293b' : '#ffffff',
          border: '1px solid',
          borderColor: resolvedTheme === 'dark' ? '#334155' : '#e2e8f0',
        },
      }}
    />
  );
}
