'use client';

import { Suspense } from 'react';
import { useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { verifyMagicLink } from '@/lib/api/auth';
import { useAuth } from '@/providers/AuthProvider';

function VerifyContent() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const verifyAttempted = useRef(false);

  useEffect(() => {
    // Prevent double execution in React Strict Mode
    if (verifyAttempted.current) return;
    verifyAttempted.current = true;

    const token = searchParams.get('token');

    if (!token) {
      setStatus('error');
      setErrorMessage('No se encontró el token de verificación.');
      return;
    }

    const verify = async () => {
      try {
        const response = await verifyMagicLink(token);
        login(response.access_token, response.organization);
        setStatus('success');

        // Redirect to dashboard after a short delay
        setTimeout(() => {
          router.push('/schedule');
        }, 1500);
      } catch (err) {
        setStatus('error');
        setErrorMessage('El link es inválido o ha expirado. Por favor, solicita uno nuevo.');
        console.error(err);
      }
    };

    verify();
  }, [searchParams, login, router]);

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <h1 className="text-xl font-semibold text-gray-900">
            Verificando...
          </h1>
          <p className="text-gray-600 mt-2">
            Un momento, estamos validando tu acceso.
          </p>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              ¡Bienvenido!
            </h1>
            <p className="text-gray-600">
              Redirigiendo a tu panel de control...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Error de verificación
          </h1>
          <p className="text-gray-600 mb-6">
            {errorMessage}
          </p>
          <button
            onClick={() => router.push('/login')}
            className="bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 transition"
          >
            Volver a iniciar sesión
          </button>
        </div>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      }
    >
      <VerifyContent />
    </Suspense>
  );
}
