'use client';

import React from 'react';
import { LoginForm } from '@/modules/auth/components/LoginForm';

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-[#FAF7F2] flex items-center justify-center p-4">
      <LoginForm />
    </main>
  );
}
