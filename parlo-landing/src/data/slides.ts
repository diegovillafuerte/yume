/**
 * Carousel slide data — growth team: edit messages here!
 *
 * Each slide has:
 *   - tabLabel: text shown in the tab button
 *   - stepNumber: number badge on the slide
 *   - slideTitle: heading above the phone mockup
 *   - chatHeader: { name, subtitle, avatarEmoji, avatarStyle }
 *   - messages: array of { role, text, time? }
 *       role: 'bot' | 'client' | 'owner'
 *       text: supports HTML (<br>, <strong>, <em>)
 *       time: optional timestamp string (e.g. "9:41")
 *       voiceNote: optional { duration, transcript } for voice messages
 *       paymentLink: optional { label, amount } for payment buttons
 */

export interface VoiceNote {
  duration: string;
  transcript: string;
}

export interface PaymentLink {
  label: string;
  amount: string;
}

export interface ChatMessage {
  role: 'bot' | 'client' | 'owner';
  text: string;
  time?: string;
  voiceNote?: VoiceNote;
  paymentLink?: PaymentLink;
}

export interface SlideData {
  tabLabel: string;
  stepNumber: number;
  slideTitle: string;
  chatHeader: {
    name: string;
    subtitle: string;
    avatarEmoji: string;
    avatarStyle: 'parlo' | 'business';
  };
  messages: ChatMessage[];
}

export const slides: SlideData[] = [
  // ── Slide 1: Onboarding ──
  {
    tabLabel: 'Configuración',
    stepNumber: 1,
    slideTitle: 'Configuración inicial (5 min)',
    chatHeader: {
      name: 'Parlo',
      subtitle: 'tu asistente',
      avatarEmoji: '💜',
      avatarStyle: 'parlo',
    },
    messages: [
      {
        role: 'bot',
        text: '¡Hola! 👋 Soy Parlo, tu nuevo asistente.<br><br>Voy a ayudarte a gestionar todo. Primero cuéntame sobre tu negocio.',
        time: '9:41',
      },
      { role: 'bot', text: '¿Cómo se llama tu estética o barbería?', time: '9:41' },
      { role: 'owner', text: 'Barbería El Clásico', time: '9:42' },
      {
        role: 'bot',
        text: 'Perfecto, Barbería El Clásico ✂️<br><br>¿Dónde está ubicada?',
        time: '9:42',
      },
      { role: 'owner', text: 'Av. Chapultepec 123, Col. Americana', time: '9:43' },
      { role: 'bot', text: 'Excelente. Ahora cuéntame: ¿Qué servicios ofreces?', time: '9:43' },
      {
        role: 'owner',
        text: '- Corte caballero $150<br>- Barba $100<br>- Corte + barba $220',
        time: '9:44',
      },
      {
        role: 'bot',
        text: '¡Listo! 🎉<br><br>Ya estoy configurado. Tus clientes ya pueden agendar citas conmigo.',
        time: '9:45',
      },
    ],
  },

  // ── Slide 2: Client Booking ──
  {
    tabLabel: 'Agendar',
    stepNumber: 2,
    slideTitle: 'Tus clientes agendan solos',
    chatHeader: {
      name: 'Barbería El Clásico',
      subtitle: 'en línea',
      avatarEmoji: '✂️',
      avatarStyle: 'business',
    },
    messages: [
      { role: 'client', text: 'Hola, quiero sacar cita para mañana', time: '10:23' },
      {
        role: 'bot',
        text: '¡Hola Carlos! 👋<br><br>Perfecto. ¿Qué servicio te interesa?<br><br>• Corte caballero - $150<br>• Barba - $100<br>• Corte + barba - $220',
        time: '10:23',
      },
      { role: 'client', text: 'Corte + barba', time: '10:24' },
      {
        role: 'bot',
        text: 'Excelente elección. Estos son los horarios disponibles para mañana:<br><br>• 11:00 AM<br>• 3:00 PM ⭐<br>• 5:00 PM',
        time: '10:24',
      },
      { role: 'client', text: 'A las 3 está bien', time: '10:25' },
      {
        role: 'bot',
        text: '✅ ¡Confirmado!<br><br><strong>Mañana sábado</strong><br>🕒 3:00 PM<br>✂️ Corte + barba<br>💰 $220<br><br>Te enviaré un recordatorio 2 horas antes 😊',
        time: '10:25',
      },
    ],
  },

  // ── Slide 3: Owner Management ──
  {
    tabLabel: 'Gestionar',
    stepNumber: 3,
    slideTitle: 'Gestiona todo desde WhatsApp',
    chatHeader: {
      name: 'Parlo',
      subtitle: 'tu asistente',
      avatarEmoji: '💜',
      avatarStyle: 'parlo',
    },
    messages: [
      {
        role: 'owner',
        text: '',
        time: '15:42',
        voiceNote: { duration: '0:03', transcript: '"Parlo, cuál es mi agenda de mañana?"' },
      },
      {
        role: 'bot',
        text: 'Agenda del sábado 8 feb:<br><br><strong>11:00 AM</strong> - Juan Pérez<br>Corte caballero ($150)<br><br><strong>3:00 PM</strong> - Carlos Méndez<br>Corte + barba ($220)<br><br><strong>5:00 PM</strong> - Roberto Silva<br>Barba ($100)<br><br>💰 Total: $470',
        time: '15:42',
      },
      { role: 'owner', text: 'Cambia la cita de Carlos de las 3 a las 5', time: '15:43' },
      {
        role: 'bot',
        text: 'Perfecto, hago el cambio:<br><br>Carlos Méndez: 3:00 PM → 5:00 PM<br><br>¿Le aviso del cambio?',
        time: '15:43',
      },
      { role: 'owner', text: 'Sí por favor', time: '15:44' },
      {
        role: 'bot',
        text: '✅ Listo. Le avisé por WhatsApp del cambio de horario.<br><br>Carlos confirmó que sí puede a las 5 PM 👍',
        time: '15:45',
      },
    ],
  },

  // ── Slide 4: Reminders ──
  {
    tabLabel: 'Recordatorios',
    stepNumber: 4,
    slideTitle: 'Recordatorios automáticos',
    chatHeader: {
      name: 'Barbería El Clásico',
      subtitle: 'en línea',
      avatarEmoji: '✂️',
      avatarStyle: 'business',
    },
    messages: [
      {
        role: 'bot',
        text: 'Hola Roberto! 👋<br><br>Te recuerdo que hoy tienes tu cita a las 2:00 PM para barba.<br><br>¿Nos vemos en unas horas?',
        time: '11:30',
      },
      { role: 'client', text: 'Uy se me complicó hoy, puedo mañana?', time: '11:35' },
      {
        role: 'bot',
        text: 'Sin problema! Horarios disponibles para mañana:<br><br>• 10:00 AM<br>• 2:00 PM<br>• 4:00 PM',
        time: '11:35',
      },
      { role: 'client', text: 'A las 4 está perfecto', time: '11:36' },
      {
        role: 'bot',
        text: '✅ ¡Listo! Reagendé tu cita:<br><br><strong>Mañana domingo</strong><br>🕒 4:00 PM<br>💈 Barba<br><br>Nos vemos mañana! 😊',
        time: '11:36',
      },
    ],
  },

  // ── Slide 5: Payments ──
  {
    tabLabel: 'Pagos',
    stepNumber: 5,
    slideTitle: 'Cobra por adelantado',
    chatHeader: {
      name: 'Estética Lourdes',
      subtitle: 'en línea',
      avatarEmoji: '💅',
      avatarStyle: 'business',
    },
    messages: [
      { role: 'client', text: 'Hola! Me gustaría agendar para el viernes', time: '16:45' },
      {
        role: 'bot',
        text: '¡Hola Ana! 💅<br><br>Claro que sí. Tengo estos horarios:<br><br>• 11:00 AM<br>• 2:00 PM<br>• 4:00 PM',
        time: '16:45',
      },
      { role: 'client', text: 'A las 2 por favor', time: '16:46' },
      {
        role: 'bot',
        text: 'Perfecto! ✨<br><br>Para confirmar tu cita, realiza el pago por WhatsApp:<br><br><strong>Viernes 2:00 PM</strong><br>💅 Manicure + Pedicure<br>💰 $350 MXN<br><br><em>*Reembolso completo si cancelas con 2+ horas de anticipación</em>',
        time: '16:46',
      },
      {
        role: 'bot',
        text: '',
        time: '16:47',
        paymentLink: { label: '💳 Pagar $350 MXN', amount: '$350' },
      },
      {
        role: 'bot',
        text: '✅ ¡Pago detectado!<br><br>Tu cita está confirmada Ana 🎉<br><br><strong>Viernes 2:00 PM</strong><br>💅 Manicure + Pedicure<br>💰 Pagado: $350<br><br>Te veo el viernes! 😊',
        time: '16:47',
      },
    ],
  },

  // ── Slide 6: Promotions ──
  {
    tabLabel: 'Promociones',
    stepNumber: 6,
    slideTitle: 'Promociones personalizadas',
    chatHeader: {
      name: 'Estética Lourdes',
      subtitle: 'en línea',
      avatarEmoji: '💅',
      avatarStyle: 'parlo',
    },
    messages: [
      {
        role: 'bot',
        text: 'Hola Laura! 💅<br><br>Tu último corte fue hace un mes, ¡te extrañamos en la Estética Lourdes!<br><br>¿Quieres que te agende para esta semana?',
      },
      { role: 'client', text: 'Sí me urge! Qué días tienes?' },
      {
        role: 'bot',
        text: 'Tengo estos horarios disponibles:<br><br><strong>Miércoles</strong><br>• 3:00 PM<br>• 5:30 PM<br><br><strong>Jueves</strong><br>• 11:00 AM<br>• 4:00 PM<br><br><strong>Viernes</strong><br>• 2:00 PM',
      },
      { role: 'client', text: 'El miércoles a las 5:30' },
      {
        role: 'bot',
        text: '¡Perfecto! Y tengo una sorpresa... 🎉<br><br>Como es tu 7ma visita con nosotros, tienes <strong>50% de descuento</strong> en tu próximo servicio!<br><br>✅ Cita confirmada:<br>Miércoles 5:30 PM<br>Corte con descuento especial 💜',
      },
      { role: 'client', text: 'Wow que padre! Gracias! 😍' },
    ],
  },
];
