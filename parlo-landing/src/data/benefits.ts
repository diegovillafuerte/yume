export interface Benefit {
  icon: string;
  stat?: string;
  title: string;
  text: string;
}

export const benefits: Benefit[] = [
  {
    icon: '⏰',
    stat: '2 horas',
    title: 'Tiempo ahorrado al día',
    text: 'Usuarios reportan ahorrar 2 horas diarias. Tiempo que ahora usan para atender más clientes o tener más tiempo personal con sus familias.',
  },
  {
    icon: '📈',
    title: 'Incrementa tu negocio',
    text: 'Consigue nuevos clientes agendándolos de forma rápida y sin esfuerzo. Tu asistente nunca duerme, nunca pierde una oportunidad.',
  },
  {
    icon: '💳',
    title: 'Recibe menos efectivo',
    text: 'Que te paguen por WhatsApp por adelantado. Menos efectivo que contar, más seguridad para tu negocio.',
  },
  {
    icon: '🔔',
    title: 'Menos citas perdidas',
    text: 'Recordatorios automáticos para tus clientes. Reduce las citas perdidas y llena todos tus espacios disponibles.',
  },
];
