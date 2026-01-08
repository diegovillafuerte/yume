'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api/client';

// Meta Embedded Signup Config ID
const META_CONFIG_ID = '1407542027823054';

// Yume WhatsApp number for deep linking back
const YUME_WHATSAPP_NUMBER = '17759674528';

interface SessionInfo {
  session_id: string;
  business_name: string;
  owner_name: string | null;
  services: Array<{ name: string; price: number; duration_minutes: number }>;
  state: string;
}

interface ConnectResult {
  success: boolean;
  organization_id: string;
  business_name: string;
  dashboard_url: string;
  message: string;
}

type PageState = 'loading' | 'ready' | 'connecting' | 'success' | 'error';

function ConnectPageContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [pageState, setPageState] = useState<PageState>('loading');
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [connectResult, setConnectResult] = useState<ConnectResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load session info on mount
  useEffect(() => {
    async function loadSession() {
      if (!token) {
        setError('Token no proporcionado. Por favor usa el link que recibiste por WhatsApp.');
        setPageState('error');
        return;
      }

      try {
        const response = await api.get<SessionInfo>(`/connect/session?token=${token}`);
        setSessionInfo(response.data);
        setPageState('ready');
      } catch (err: unknown) {
        console.error('Error loading session:', err);
        const axiosError = err as { response?: { data?: { detail?: string } } };
        setError(axiosError.response?.data?.detail || 'Error al cargar la sesion. El link puede haber expirado.');
        setPageState('error');
      }
    }

    loadSession();
  }, [token]);

  // Initialize Facebook SDK
  useEffect(() => {
    // Load Facebook SDK
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const win = window as any;
    if (typeof window !== 'undefined' && !win.FB) {
      const script = document.createElement('script');
      script.src = 'https://connect.facebook.net/en_US/sdk.js';
      script.async = true;
      script.defer = true;
      script.crossOrigin = 'anonymous';
      document.body.appendChild(script);

      script.onload = () => {
        win.fbAsyncInit = () => {
          win.FB.init({
            appId: META_CONFIG_ID,
            cookie: true,
            xfbml: true,
            version: 'v18.0',
          });
        };
      };
    }
  }, []);

  const handleConnect = useCallback(async () => {
    setPageState('connecting');
    setError(null);

    try {
      // Launch Meta Embedded Signup
      const FB = (window as { FB?: {
        login: (
          callback: (response: {
            authResponse?: {
              code?: string;
              accessToken?: string;
            };
            status?: string;
          }) => void,
          options: object
        ) => void
      } }).FB;

      if (!FB) {
        throw new Error('Facebook SDK no cargado. Recarga la pagina.');
      }

      FB.login(
        async (response) => {
          if (response.authResponse?.code) {
            // For now, we'll use the code directly
            // In production, exchange this for a long-lived token
            try {
              const completeResponse = await api.post<ConnectResult>('/connect/complete', {
                token: token,
                phone_number_id: 'pending_' + Date.now(), // Placeholder - Meta will provide this
                waba_id: 'pending_' + Date.now(), // Placeholder - Meta will provide this
                access_token: response.authResponse.code,
              });

              setConnectResult(completeResponse.data);
              setPageState('success');
            } catch (err: unknown) {
              console.error('Error completing connection:', err);
              const axiosError = err as { response?: { data?: { detail?: string } } };
              setError(axiosError.response?.data?.detail || 'Error al completar la conexion.');
              setPageState('error');
            }
          } else {
            setError('Conexion cancelada o fallida. Por favor intenta de nuevo.');
            setPageState('ready');
          }
        },
        {
          config_id: META_CONFIG_ID,
          response_type: 'code',
          override_default_response_type: true,
          extras: {
            setup: {},
            featureType: '',
            sessionInfoVersion: '2',
          },
        }
      );
    } catch (err: unknown) {
      console.error('Error launching Meta signup:', err);
      setError(err instanceof Error ? err.message : 'Error al iniciar conexion');
      setPageState('ready');
    }
  }, [token]);

  const handleBackToWhatsApp = () => {
    window.location.href = `https://wa.me/${YUME_WHATSAPP_NUMBER}`;
  };

  // Loading state
  if (pageState === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (pageState === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-900 mb-2">Error</h1>
            <p className="text-gray-600 mb-6">{error}</p>
            <button
              onClick={handleBackToWhatsApp}
              className="w-full bg-green-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-green-700 transition"
            >
              Volver a WhatsApp
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Success state
  if (pageState === 'success' && connectResult) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
        <div className="max-w-md w-full">
          <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {connectResult.message}
            </h1>
            <p className="text-gray-600 mb-2">
              <span className="font-semibold">{connectResult.business_name}</span> esta listo para recibir citas.
            </p>
            <p className="text-sm text-gray-500 mb-6">
              Tus clientes ya pueden agendar por WhatsApp.
            </p>

            <div className="space-y-3">
              <button
                onClick={handleBackToWhatsApp}
                className="w-full bg-green-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-green-700 transition flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                Volver a WhatsApp
              </button>

              <a
                href={connectResult.dashboard_url}
                className="block w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition text-center"
              >
                Ir al Dashboard
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Ready state - show connect button
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
      <div className="max-w-md w-full">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Yume</h1>
          <p className="text-gray-600">Conecta tu WhatsApp Business</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-8">
          {sessionInfo && (
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                {sessionInfo.business_name}
              </h2>

              {sessionInfo.services.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-4 mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Tus servicios:
                  </p>
                  <ul className="space-y-1">
                    {sessionInfo.services.map((service, index) => (
                      <li key={index} className="text-sm text-gray-600 flex justify-between">
                        <span>{service.name}</span>
                        <span className="text-gray-500">
                          ${service.price} ({service.duration_minutes} min)
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="space-y-4">
            <p className="text-sm text-gray-600 text-center">
              Conecta tu cuenta de WhatsApp Business para que tus clientes puedan agendar citas automaticamente.
            </p>

            <button
              onClick={handleConnect}
              disabled={pageState === 'connecting'}
              className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
            >
              {pageState === 'connecting' ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Conectando...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                  </svg>
                  Conectar con Facebook
                </>
              )}
            </button>

            {error && (
              <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg text-sm text-center">
                {error}
              </div>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-gray-500">
          Al conectar, autorizas a Yume a gestionar tus citas por WhatsApp.
        </p>
      </div>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-gray-50">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-gray-600">Cargando...</p>
      </div>
    </div>
  );
}

export default function ConnectPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ConnectPageContent />
    </Suspense>
  );
}
